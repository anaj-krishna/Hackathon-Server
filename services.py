#Services.py
import os
import csv
import tempfile

from langchain_community.document_loaders import (
    PyPDFLoader
)

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter
)

from langchain_community.retrievers import (
    BM25Retriever
)

from langchain_core.documents import (
    Document
)

from config import (
    get_db,
    llm
)
from config import client
import uuid
from config import local_llm
# -----------------------------------
# SPLITTER
# -----------------------------------

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)

MAX_CONTEXT_CHARS = 12000

# -----------------------------------
# PDF INGEST
# -----------------------------------

async def process_pdf(
    file,
    user_id
):

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".pdf"
    ) as tmp:

        content = await file.read()

        tmp.write(content)

        path = tmp.name

    loader = PyPDFLoader(path)

    documents = loader.load()

    split_docs = splitter.split_documents(
        documents
    )

    for doc in split_docs:

        doc.metadata.update({
            "source": file.filename,
            "user_id": user_id,
            "type": "pdf"
        })

    db = get_db()

    db.add_documents(split_docs)

    os.remove(path)

    return len(split_docs)

# -----------------------------------
# CSV INGEST
# -----------------------------------

async def process_csv(
    file,
    user_id
):

    content = await file.read()

    decoded = content.decode(
        "utf-8"
    ).splitlines()

    reader = csv.DictReader(decoded)

    texts = []

    metadatas = []

    for index, row in enumerate(reader):

        text = "\n".join([
            f"{k}: {v}"
            for k, v in row.items()
        ])

        texts.append(text)

        metadatas.append({
            "row": index,
            "user_id": user_id,
            "source": file.filename,
            "type": "csv"
        })

    db = get_db()

    db.add_texts(
        texts=texts,
        metadatas=metadatas
    )

    return len(texts)

# -----------------------------------
# TEXT INGEST
# -----------------------------------

async def process_text(
    text,
    user_id
):

    chunks = splitter.split_text(text)

    metadatas = [{
        "user_id": user_id,
        "type": "text"
    } for _ in chunks]

    db = get_db()

    db.add_texts(
        texts=chunks,
        metadatas=metadatas
    )

    return len(chunks)

# -----------------------------------
# HYBRID SEARCH
# -----------------------------------

def hybrid_search(
    question,
    db,
    user_id
):

    # -----------------------------------
    # VECTOR SEARCH
    # -----------------------------------

    vector_results = db.similarity_search_with_score(
        question,
        k=4,
        filter={
            "user_id": user_id
        }
    )

    vector_docs = []

    for doc, score in vector_results:

        vector_docs.append({
            "doc": doc,
            "score": score
        })

    # -----------------------------------
    # LOAD SESSION DOCS
    # -----------------------------------

    all_docs = db.get(
        where={
            "user_id": user_id
        }
    )

    raw_docs = all_docs.get(
        "documents",
        []
    )

    raw_metadatas = all_docs.get(
        "metadatas",
        []
    )

    documents = []

    for text, metadata in zip(
        raw_docs,
        raw_metadatas
    ):

        documents.append(
            Document(
                page_content=text,
                metadata=metadata
            )
        )

    # -----------------------------------
    # BM25
    # -----------------------------------

    keyword_docs = []

    if documents:

        bm25 = BM25Retriever.from_documents(
            documents
        )

        bm25.k = 4

        keyword_docs = bm25.invoke(
            question
        )

    # -----------------------------------
    # RRF FUSION
    # -----------------------------------

    rrf_scores = {}

    K = 60

    vector_weight = 0.6

    keyword_weight = 0.4

    # VECTOR RANKING

    for rank, item in enumerate(vector_docs):

        doc = item["doc"]

        similarity_score = item["score"]

        content = doc.page_content

        if content not in rrf_scores:

            rrf_scores[content] = {
                "doc": doc,
                "score": 0.0
            }

        adjusted_weight = vector_weight

        # weaker semantic match fallback
        if similarity_score > 1.2:

            adjusted_weight = 0.15

        rrf_scores[content]["score"] += (
            adjusted_weight / (K + (rank + 1))
        )

    # KEYWORD RANKING

    for rank, doc in enumerate(keyword_docs):

        content = doc.page_content

        if content not in rrf_scores:

            rrf_scores[content] = {
                "doc": doc,
                "score": 0.0
            }

        rrf_scores[content]["score"] += (
            keyword_weight / (K + (rank + 1))
        )

    # -----------------------------------
    # SORT
    # -----------------------------------

    sorted_results = sorted(
        rrf_scores.values(),
        key=lambda x: x["score"],
        reverse=True
    )

    final_docs = [
        item["doc"]
        for item in sorted_results
    ]

    return final_docs[:6]


# -----------------------------------
# CHAT
# -----------------------------------

async def ask_question(
    question,
    user_id,
    privacy_mode=False
):

    print("\n================ FUNCTION STARTED ================", flush=True)
    print(f"QUESTION      : {question}", flush=True)
    print(f"USER ID       : {user_id}", flush=True)
    print(f"PRIVACY MODE  : {privacy_mode}", flush=True)
    print("==================================================", flush=True)

    db = get_db()

    # -----------------------------------
    # HYBRID SEARCH
    # -----------------------------------

    docs = hybrid_search(
        question,
        db,
        user_id
    )

    # -----------------------------------
    # NO RESULTS
    # -----------------------------------

    if not docs:

        print("\n[RAG] NO DOCUMENTS FOUND", flush=True)

        return {
            "answer": "I could not find this in the uploaded documents.",
            "sources": []
        }

    # -----------------------------------
    # CONTEXT BUILDING
    # -----------------------------------

    context = ""
    valid_docs = []

    for doc in docs:

        if (
            len(context) + len(doc.page_content)
            > MAX_CONTEXT_CHARS
        ):
            break

        context += doc.page_content + "\n\n"

        valid_docs.append(doc)

    # -----------------------------------
    # PROMPT
    # -----------------------------------

    prompt = f"""
You are a secure banking AI assistant.

Answer ONLY from context.

Context:
{context}

Question:
{question}
"""

    try:

        # -----------------------------------
        # LOCAL LLM
        # -----------------------------------

        if privacy_mode:

            print("\n===================================", flush=True)
            print("USING LOCAL OLLAMA MODEL", flush=True)
            print(f"MODEL : {local_llm.model}", flush=True)
            print("===================================\n", flush=True)

            response = local_llm.invoke(prompt)

        # -----------------------------------
        # CLOUD LLM
        # -----------------------------------

        else:

            print("\n===================================", flush=True)
            print("USING CLOUD MODEL", flush=True)
            print(f"MODEL : {llm.model_name}", flush=True)
            print("===================================\n", flush=True)

            response = llm.invoke(prompt)

        # -----------------------------------
        # RESPONSE PRINT
        # -----------------------------------

        print("\n=============== LLM RESPONSE ===============", flush=True)
        print(f"ANSWERED BY   : {'Local Ollama (' + local_llm.model + ')' if privacy_mode else 'Cloud Model (' + llm.model_name + ')'}", flush=True)

        if hasattr(response, "content"):

            print(response.content, flush=True)

            final_answer = response.content

        else:

            print(response, flush=True)

            final_answer = str(response)

        print("============================================\n", flush=True)

        return {
            "answer": final_answer,
            "sources": [
                doc.metadata
                for doc in valid_docs
            ]
        }

    except Exception as e:

        print("\n=============== ERROR ===============", flush=True)
        print(str(e), flush=True)
        print("=====================================\n", flush=True)

        raise e