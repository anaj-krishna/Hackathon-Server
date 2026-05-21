import os
import ssl
import httpx
import sqlite3

from dotenv import load_dotenv

from langchain_openai import (
    OpenAIEmbeddings,
    ChatOpenAI
)
from langchain_community.vectorstores import (
    Chroma
)
from openai import OpenAI

from langchain_ollama import ChatOllama
local_llm = ChatOllama(model="deepseek-r1")
# -------------------------
# ENV
# -------------------------

load_dotenv()

ssl._create_default_https_context = (
    ssl._create_unverified_context
)

API_KEY = os.getenv("OPENAI_API_KEY")

# MONGO_URL not needed anymore
JWT_SECRET = os.getenv("JWT_SECRET", "mysecretkey")

BASE_URL = "https://genailab.tcs.in"

EMBEDDING_MODEL = "azure/genailab-maas-text-embedding-3-large"
LLM_MODEL = "azure_ai/genailab-maas-DeepSeek-V3-0324"

CHROMA_DIR = "./chroma_db"

# -------------------------
# SQLITE DB SETUP
# -------------------------

SQLITE_DB_PATH = "users.db"

def init_db():
    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Create table
init_db()

def get_db_connection():
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# -------------------------
# HTTP CLIENT
# -------------------------

ssl_client = httpx.Client(
    verify=False
)

ssl_async_client = httpx.AsyncClient(
    verify=False
)

# -------------------------
# EMBEDDINGS
# -------------------------

embeddings = OpenAIEmbeddings(
    base_url=BASE_URL,
    model=EMBEDDING_MODEL,
    api_key=API_KEY,
    http_client=ssl_client,
    http_async_client=ssl_async_client
)

# -------------------------
# LLM
# -------------------------

llm = ChatOpenAI(
    base_url=BASE_URL,
    model=LLM_MODEL,
    api_key=API_KEY,
    http_client=ssl_client,
    http_async_client=ssl_async_client
)

# -------------------------
# VECTOR DB
# -------------------------

def get_db():

    return Chroma(
        collection_name="documents",
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR
    )

#For voice
client=OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
    http_client=ssl_client
)