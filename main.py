#main.py
from fastapi import (
    FastAPI,
    UploadFile,
    File,
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
    # process_voice_query
)
from fastapi import Depends

from auth.routes import (
    router as auth_router
)

from auth.dependencies import (
    get_current_user
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
app.include_router(auth_router)
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
    user_id: str = Depends(get_current_user)
):

    chunks = await process_pdf(
        file,
        user_id
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
    user_id: str = Depends(get_current_user)
):

    rows = await process_csv(
        file,
        user_id
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
    payload: TextRequest,
    user_id: str = Depends(get_current_user)
):

    chunks = await process_text(
        payload.text,
        user_id
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
    payload: QueryRequest,
    user_id: str = Depends(get_current_user)
):

    return await ask_question(
        payload.question,
        user_id,
        payload.privacy_mode,
        payload.session_id
    )

    