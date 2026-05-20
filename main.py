#main.py
from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form
)

from fastapi.middleware.cors import (
    CORSMiddleware
)

from schemas import (
    TextRequest,
    QueryRequest
)

from services import (
    process_pdf,
    process_csv,
    process_text,
    ask_question,
    process_voice_query
)

app = FastAPI(
    title="Minimal Banking RAG"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------
# HEALTH
# -------------------------

@app.get("/health")
async def health():

    return {
        "status": "ok"
    }

# -------------------------
# PDF INGEST
# -------------------------

@app.post("/api/ingest/pdf")
async def ingest_pdf(
    file: UploadFile = File(...),
    session_id: str = Form(...)
):

    chunks = await process_pdf(
        file,
        session_id
    )

    return {
        "status": "success",
        "chunks": chunks
    }

# -------------------------
# CSV INGEST
# -------------------------

@app.post("/api/ingest/csv")
async def ingest_csv(
    file: UploadFile = File(...),
    session_id: str = Form(...)
):

    rows = await process_csv(
        file,
        session_id
    )

    return {
        "status": "success",
        "rows": rows
    }

# -------------------------
# TEXT INGEST
# -------------------------

@app.post("/api/ingest/text")
async def ingest_text(
    payload: TextRequest
):

    chunks = await process_text(
        payload.text,
        payload.session_id
    )

    return {
        "status": "success",
        "chunks": chunks
    }

# -------------------------
# CHAT
# -------------------------

@app.post("/api/chat/query")
async def chat(
    payload: QueryRequest
):

    return await ask_question(
        payload.question,
        payload.session_id
    )

