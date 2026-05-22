# schemas.py

from pydantic import BaseModel

class TextRequest(BaseModel):
    text: str

class QueryRequest(BaseModel):
    question: str
    domain: str = ""
    session_id: str = "default"
    privacy_mode: bool = False