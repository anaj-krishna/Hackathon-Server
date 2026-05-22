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

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
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
# REQUIREMENT JSON INGEST
# -----------------------------------

async def process_requirement_json(
    data,
    user_id
):
    if isinstance(data, dict):
        records = [data]
    elif isinstance(data, list):
        records = data
    else:
        raise ValueError("Invalid data format for requirement json")

    docs = []
    for record in records:
        req_id = record.get("id") or record.get("requirement_id")
        domain = record.get("domain", "")
        subdomain = record.get("subdomain", "")
        raw_requirement = record.get("raw_requirement", "")
        ambiguities = record.get("ambiguities", [])
        clarification_questions = record.get("clarification_questions", [])
        user_clarifications = record.get("user_clarifications", [])
        refined_summary = record.get("refined_summary", "")

        content_parts = [
            f"Requirement ID: {req_id}",
            f"Domain: {domain}",
            f"Subdomain: {subdomain}",
            f"Raw Requirement: {raw_requirement}"
        ]
        if ambiguities:
            content_parts.append("Ambiguities:\n" + "\n".join(f"- {a}" for a in ambiguities))
        if clarification_questions:
            content_parts.append("Clarification Questions:\n" + "\n".join(f"- {q}" for q in clarification_questions))
        if user_clarifications:
            content_parts.append("User Clarifications:\n" + "\n".join(f"- {c}" for c in user_clarifications))
        if refined_summary:
            content_parts.append(f"Refined Summary: {refined_summary}")

        page_content = "\n\n".join(content_parts)

        doc = Document(
            page_content=page_content,
            metadata={
                "domain": domain,
                "subdomain": subdomain,
                "requirement_id": str(req_id),
                "user_id": user_id,
                "type": "requirement"
            }
        )
        docs.append(doc)

    db = get_db()
    db.add_documents(docs)

    return len(docs)

# -----------------------------------
# HYBRID SEARCH
# -----------------------------------

def hybrid_search(
    question,
    db,
    user_id,
    domain=None
):

    # -----------------------------------
    # VECTOR SEARCH
    # -----------------------------------

    if domain:
        filter_dict = {
            "$and": [
                {"user_id": user_id},
                {"domain": domain}
            ]
        }
    else:
        filter_dict = {"user_id": user_id}

    vector_results = db.similarity_search_with_score(
        question,
        k=4,
        filter=filter_dict
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

    where_dict = {"user_id": user_id}
    if domain:
        where_dict = {
            "$and": [
                {"user_id": user_id},
                {"domain": domain}
            ]
        }

    all_docs = db.get(
        where=where_dict
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

# -----------------------------------
# LANGGRAPH STATE & WORKFLOW
# -----------------------------------

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    question: str
    privacy_mode: bool
    user_id: str
    context: str
    documents: list
    answer: str
    domain: str
    ambiguities: list
    clarification_questions: list
    refined_requirement: str

def format_messages(messages):
    formatted = []
    for msg in messages:
        role = "User" if isinstance(msg, HumanMessage) else "Assistant"
        formatted.append(f"{role}: {msg.content}")
    return "\n".join(formatted)

async def condense_query_node(state: AgentState):
    messages = state["messages"]
    # If it is the first user query (only 1 human message in the thread), don't condense
    if len(messages) <= 1:
        return {
            "question": state["question"],
            "answer": "",
            "context": "",
            "documents": [],
            "ambiguities": [],
            "clarification_questions": [],
            "refined_requirement": ""
        }
        
    active_llm = local_llm if state["privacy_mode"] else llm
    
    condense_prompt = f"""Given the following conversation history and a follow-up question, rewrite the follow-up question to be a standalone question. Keep it concise.

History:
{format_messages(messages[:-1])}

Follow-up: {state["question"]}
Standalone question:"""
    
    try:
        response = await active_llm.ainvoke(condense_prompt)
        standalone_query = response.content.strip() if hasattr(response, "content") else str(response).strip()
        return {
            "question": standalone_query,
            "answer": "",
            "context": "",
            "documents": [],
            "ambiguities": [],
            "clarification_questions": [],
            "refined_requirement": ""
        }
    except Exception as e:
        print(f"[LangGraph] Query condensation failed: {e}", flush=True)
        return {
            "question": state["question"],
            "answer": "",
            "context": "",
            "documents": [],
            "ambiguities": [],
            "clarification_questions": [],
            "refined_requirement": ""
        }

async def retrieve_docs_node(state: AgentState):
    db = get_db()
    docs = hybrid_search(state["question"], db, state["user_id"], state.get("domain"))
    
    context = ""
    valid_docs = []
    if docs:
        for doc in docs:
            if len(context) + len(doc.page_content) > MAX_CONTEXT_CHARS:
                break
            context += doc.page_content + "\n\n"
            valid_docs.append(doc)
            print("\n=============== RETRIEVED CHUNKS ===============", flush=True)
            print(f"Total chunks retrieved: {len(valid_docs)}", flush=True)
            for i, doc in enumerate(valid_docs):
                print(f"\n--- Chunk {i + 1} ---", flush=True)
                print(f"Metadata : {doc.metadata}", flush=True)
                safe_content = doc.page_content.encode('ascii', errors='backslashreplace').decode('ascii')
                print(f"Content  :\n{safe_content}", flush=True)
            print("================================================\n", flush=True)
        
    return {"context": context, "documents": valid_docs}

async def ambiguity_detection_node(state: AgentState):
    privacy_mode = state["privacy_mode"]
    active_llm = local_llm if privacy_mode else llm
    
    history = format_messages(state["messages"])
    domain = state.get("domain", "")
    
    prompt = f"""You are a professional Business Analyst. Analyze the following requirement and conversation history to identify ambiguities, gaps, missing details, or unclear business rules.

Domain: {domain}
Requirement/Conversation:
{history}

Identify all ambiguities. List them clearly.
Format your output as a JSON list of strings. Do not include markdown code block formatting or any explanation outside the JSON list.
Example output format:
[
  "The payment methods are not specified.",
  "The response time SLA is undefined."
]
"""
    try:
        response = await active_llm.ainvoke(prompt)
        content = response.content.strip() if hasattr(response, "content") else str(response).strip()
        
        # strip codeblocks if present
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines).strip()
            
        import json
        ambiguities = json.loads(content)
        if not isinstance(ambiguities, list):
            ambiguities = [content]
    except Exception as e:
        print(f"[LangGraph] Ambiguity detection failed: {e}", flush=True)
        ambiguities = ["Requirement detail is ambiguous or needs clarification."]
        
    return {"ambiguities": ambiguities}

async def clarification_generation_node(state: AgentState):
    privacy_mode = state["privacy_mode"]
    active_llm = local_llm if privacy_mode else llm
    
    ambiguities = state.get("ambiguities", [])
    context = state.get("context", "")
    domain = state.get("domain", "")
    
    if not ambiguities:
        return {"clarification_questions": []}
        
    prompt = f"""You are a professional Business Analyst. Generate clear, actionable clarification questions to resolve the identified ambiguities.
Use the retrieved reference context (which contains templates or similar requirements) to align the questions with best practices in this domain.

Domain: {domain}
Identified Ambiguities:
{chr(10).join(f"- {a}" for a in ambiguities)}

Retrieved Reference Context:
{context}

Format your output as a JSON list of strings (questions). Do not include markdown code block formatting or any explanation outside the JSON list.
Example output format:
[
  "Which payment methods should be supported?",
  "What is the expected response time?"
]
"""
    try:
        response = await active_llm.ainvoke(prompt)
        content = response.content.strip() if hasattr(response, "content") else str(response).strip()
        
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines).strip()
            
        import json
        questions = json.loads(content)
        if not isinstance(questions, list):
            questions = [content]
    except Exception as e:
        print(f"[LangGraph] Clarification question generation failed: {e}", flush=True)
        questions = ["Can you please clarify the specific requirements for this module?"]
        
    return {"clarification_questions": questions}

async def refinement_node(state: AgentState):
    privacy_mode = state["privacy_mode"]
    active_llm = local_llm if privacy_mode else llm
    
    history = format_messages(state["messages"])
    context = state.get("context", "")
    domain = state.get("domain", "")
    
    prompt = f"""You are a professional Business Analyst. Combine the original requirements, user's clarifications from the conversation, and retrieved reference examples to compile a refined, professional business requirement summary.

Domain: {domain}
Conversation History (containing requirements and clarifications):
{history}

Retrieved Reference Context:
{context}

Generate a clear, structured, and professional business requirement summary. Outline the refined scope and details.
"""
    try:
        response = await active_llm.ainvoke(prompt)
        refined_requirement = response.content.strip() if hasattr(response, "content") else str(response).strip()
    except Exception as e:
        print(f"[LangGraph] Refinement failed: {e}", flush=True)
        refined_requirement = "Incomplete requirement; awaiting user clarification."
        
    return {"refined_requirement": refined_requirement}

async def generate_answer_node(state: AgentState):
    context = state.get("context", "")
    privacy_mode = state["privacy_mode"]
    active_llm = local_llm if privacy_mode else llm
    
    ambiguities = state.get("ambiguities", [])
    questions = state.get("clarification_questions", [])
    refined_req = state.get("refined_requirement", "")
    domain = state.get("domain", "")
    
    system_instruction = f"""You are an AI business analyst assistant.

Your responsibilities:
- detect ambiguities
- ask clarification questions
- refine incomplete business requirements
- generate professional summaries

Use retrieved context when available.

Domain: {domain}
Retrieved Reference Context:
{context}

Current state of analysis:
- Detected Ambiguities: {ambiguities}
- Clarification Questions: {questions}
- Refined Requirement Summary: {refined_req}

Formulate a professional and structured response. 
1. Present the detected ambiguities clearly.
2. Ask the generated clarification questions to the user.
3. Show the current refined requirement summary.
Maintain a helpful and structured business analyst tone.
"""
    llm_messages = [SystemMessage(content=system_instruction)] + list(state["messages"])
    
    try:
        try:
            if privacy_mode:
                print("\n===================================", flush=True)
                print("USING LOCAL OLLAMA MODEL VIA LANGGRAPH", flush=True)
                print(f"MODEL : {local_llm.model}", flush=True)
                print("===================================\n", flush=True)
            else:
                print("\n===================================", flush=True)
                print("USING CLOUD MODEL VIA LANGGRAPH", flush=True)
                print(f"MODEL : {llm.model_name}", flush=True)
                print("===================================\n", flush=True)
        except Exception:
            pass
            
        response = await active_llm.ainvoke(llm_messages)
        final_answer = response.content if hasattr(response, "content") else str(response)
        
        try:
            print("\n=============== LLM RESPONSE ===============", flush=True)
            print(f"ANSWERED BY   : {'Local Ollama (' + local_llm.model + ')' if privacy_mode else 'Cloud Model (' + llm.model_name + ')'}", flush=True)
            # Encode and decode using backslashreplace or ignore to avoid terminal output crash
            safe_ans = final_answer.encode('ascii', errors='backslashreplace').decode('ascii')
            print(safe_ans, flush=True)
            print("============================================\n", flush=True)
        except Exception:
            pass
        
        return {
            "answer": final_answer,
            "messages": [AIMessage(content=final_answer)]
        }
    except Exception as e:
        print("\n=============== ERROR ===============", flush=True)
        print(str(e), flush=True)
        print("=====================================\n", flush=True)
        raise e

# Build and Compile LangGraph Workflow
workflow = StateGraph(AgentState)

workflow.add_node("condense", condense_query_node)
workflow.add_node("retrieve", retrieve_docs_node)
workflow.add_node("ambiguity_detection", ambiguity_detection_node)
workflow.add_node("clarification_generation", clarification_generation_node)
workflow.add_node("refinement", refinement_node)
workflow.add_node("generate", generate_answer_node)

workflow.add_edge(START, "condense")
workflow.add_edge("condense", "retrieve")
workflow.add_edge("retrieve", "ambiguity_detection")
workflow.add_edge("ambiguity_detection", "clarification_generation")
workflow.add_edge("clarification_generation", "refinement")
workflow.add_edge("refinement", "generate")
workflow.add_edge("generate", END)

memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)


async def ask_question(
    question,
    user_id,
    privacy_mode=False,
    session_id="default",
    domain=""
):

    try:
        print("\n================ FUNCTION STARTED ================", flush=True)
        safe_q = question.encode('ascii', errors='backslashreplace').decode('ascii')
        print(f"QUESTION      : {safe_q}", flush=True)
        print(f"USER ID       : {user_id}", flush=True)
        print(f"PRIVACY MODE  : {privacy_mode}", flush=True)
        print(f"SESSION ID    : {session_id}", flush=True)
        print(f"DOMAIN        : {domain}", flush=True)
        print("==================================================", flush=True)
    except Exception:
        pass

    config = {"configurable": {"thread_id": f"{user_id}:{session_id}"}}

    try:
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content=question)],
                "question": question,
                "privacy_mode": privacy_mode,
                "user_id": user_id,
                "domain": domain,
                "ambiguities": [],
                "clarification_questions": [],
                "refined_requirement": ""
            },
            config=config
        )
        
        valid_docs = result.get("documents", [])
        final_answer = result.get("answer", "Failed to refine business requirements.")
        
        return {
            "answer": final_answer,
            "sources": [
                doc.metadata
                for doc in valid_docs
            ],
            "ambiguities": result.get("ambiguities", []),
            "clarification_questions": result.get("clarification_questions", []),
            "refined_requirement": result.get("refined_requirement", "")
        }

    except Exception as e:

        print("\n=============== ERROR ===============", flush=True)
        print(str(e), flush=True)
        print("=====================================\n", flush=True)

        raise e