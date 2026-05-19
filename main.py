import os
import csv
import tempfile

from dotenv import load_dotenv

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    HTTPException
)

import os
import ssl

# -----------------------------------
# SSL FIX
# -----------------------------------

ssl._create_default_https_context = (
    ssl._create_unverified_context
)

# -----------------------------------
# LOCAL TIKTOKEN CACHE
# -----------------------------------
TIKTOKEN_CACHE_DIR = os.path.abspath(
    "tiktoken_cache"
)
os.environ["TIKTOKEN_CACHE_DIR"] = (
    TIKTOKEN_CACHE_DIR
)
assert os.path.exists(
    os.path.join(
        TIKTOKEN_CACHE_DIR,
        "9b5ad71b2ce5302211f9c61530b329a4922fc6a4"
    )
), "tiktoken cache not found!"

from fastapi.middleware.cors import CORSMiddleware
import httpx
from pydantic import BaseModel
from langchain_openai import (
    OpenAIEmbeddings,
    ChatOpenAI
)
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter
)
from langchain_community.document_loaders import (
    PyPDFLoader
)
# -----------------------------------
# ENV
# -----------------------------------
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = "https://genailab.tcs.in"
EMBEDDING_MODEL = (
    "azure/genailab-maas-text-embedding-3-large"
)
LLM_MODEL = (
    "azure_ai/genailab-maas-DeepSeek-V3-0324"
)
CHROMA_DIR = "./chroma_db"

# -----------------------------------
# FASTAPI
# -----------------------------------

app = FastAPI(
    title="Minimal Complete RAG Backend"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------
# HTTP CLIENT
# IMPORTANT FOR TCS LAB
# -----------------------------------

ssl_client = httpx.Client(
    verify=False
)

# -----------------------------------
# EMBEDDINGS
# -----------------------------------

embeddings = OpenAIEmbeddings(
    base_url=BASE_URL,
    model=EMBEDDING_MODEL,
    api_key=API_KEY,
    http_client=ssl_client
)

# -----------------------------------
# LLM
# -----------------------------------

llm = ChatOpenAI(
    base_url=BASE_URL,
    model=LLM_MODEL,
    api_key=API_KEY,
    http_client=ssl_client
)

# -----------------------------------
# HELPERS
# -----------------------------------

def get_db(session_id: str):

    return Chroma(
        collection_name=f"session_{session_id}",
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR
    )

# -----------------------------------
# SCHEMAS
# -----------------------------------

class TextRequest(BaseModel):
    text: str
    session_id: str


class QueryRequest(BaseModel):
    question: str
    session_id: str

# -----------------------------------
# HEALTH
# -----------------------------------

@app.get("/health")
async def health():

    return {
        "status": "ok"
    }

# -----------------------------------
# PDF INGEST
# -----------------------------------

@app.post("/api/ingest/pdf")
async def ingest_pdf(
    file: UploadFile = File(...),
    session_id: str = Form(...)
):

    if not file.filename.endswith(".pdf"):

        raise HTTPException(
            status_code=400,
            detail="PDF required"
        )

    try:

        # save temp pdf
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".pdf"
        ) as tmp:

            content = await file.read()

            tmp.write(content)

            tmp_path = tmp.name

        # load pdf
        loader = PyPDFLoader(tmp_path)

        documents = loader.load()

        # split
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )

        split_docs = splitter.split_documents(
            documents
        )

        # metadata
        for doc in split_docs:

            doc.metadata.update({
                "source": file.filename,
                "session_id": session_id,
                "type": "pdf"
            })

        # vector db
        db = get_db(session_id)

        db.add_documents(split_docs)

        # cleanup
        os.remove(tmp_path)

        return {
            "status": "success",
            "chunks": len(split_docs)
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }

# -----------------------------------
# CSV INGEST
# -----------------------------------

@app.post("/api/ingest/csv")
async def ingest_csv(
    file: UploadFile = File(...),
    session_id: str = Form(...)
):

    if not file.filename.endswith(".csv"):

        raise HTTPException(
            status_code=400,
            detail="CSV required"
        )

    try:

        content = await file.read()

        decoded = content.decode("utf-8").splitlines()

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
                "session_id": session_id,
                "source": file.filename,
                "type": "csv"
            })

        db = get_db(session_id)

        db.add_texts(
            texts=texts,
            metadatas=metadatas
        )

        return {
            "status": "success",
            "rows": len(texts)
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }

# -----------------------------------
# TEXT INGEST
# -----------------------------------

@app.post("/api/ingest/text")
async def ingest_text(
    payload: TextRequest
):

    try:

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50
        )

        chunks = splitter.split_text(
            payload.text
        )

        metadatas = [{
            "session_id": payload.session_id,
            "type": "text"
        } for _ in chunks]

        db = get_db(payload.session_id)

        db.add_texts(
            texts=chunks,
            metadatas=metadatas
        )

        return {
            "status": "success",
            "chunks": len(chunks)
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }

# -----------------------------------
# CHAT QUERY
# -----------------------------------

@app.post("/api/chat/query")
async def query_rag(
    payload: QueryRequest
):

    try:

        # load vector db
        db = get_db(payload.session_id)

        # similarity search
        docs = db.similarity_search(
            payload.question,
            k=4
        )

        if not docs:

            return {
                "answer": "No relevant information found."
            }

        # combine retrieved chunks
        context = "\n\n".join([
            doc.page_content
            for doc in docs
        ])

        # prompt
        prompt = f"""
You are a helpful AI assistant.

Answer ONLY from the given context.

If the answer is not available in the context,
say:
"I could not find this in the uploaded documents."

Context:
{context}

Question:
{payload.question}
"""

        # llm response
        response = llm.invoke(prompt)

        return {
            "answer": response.content,
            "sources": [
                doc.metadata
                for doc in docs
            ]
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }

# -----------------------------------
# RUN
# -----------------------------------

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )