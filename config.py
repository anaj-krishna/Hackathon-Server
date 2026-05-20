import os
import ssl
import httpx

from dotenv import load_dotenv

from langchain_openai import (
    OpenAIEmbeddings,
    ChatOpenAI
)
from langchain_community.vectorstores import (
    Chroma
)
from openai import OpenAI

# -------------------------
# ENV
# -------------------------

load_dotenv()

ssl._create_default_https_context = (
    ssl._create_unverified_context
)

API_KEY = os.getenv("OPENAI_API_KEY")

BASE_URL = "https://genailab.tcs.in"

EMBEDDING_MODEL = (
    "azure/genailab-maas-text-embedding-3-large"
)

LLM_MODEL = (
    "azure_ai/genailab-maas-DeepSeek-V3-0324"
)

CHROMA_DIR = "./chroma_db"

# -------------------------
# HTTP CLIENT
# -------------------------

ssl_client = httpx.Client(
    verify=False
)

# -------------------------
# EMBEDDINGS
# -------------------------

embeddings = OpenAIEmbeddings(
    base_url=BASE_URL,
    model=EMBEDDING_MODEL,
    api_key=API_KEY,
    http_client=ssl_client
)

# -------------------------
# LLM
# -------------------------

llm = ChatOpenAI(
    base_url=BASE_URL,
    model=LLM_MODEL,
    api_key=API_KEY,
    http_client=ssl_client
)

# -------------------------
# VECTOR DB
# -------------------------

def get_db(session_id: str):

    return Chroma(
        collection_name=f"session_{session_id}",
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR
    )

#For voice
client=OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
    http_client=ssl_client
)