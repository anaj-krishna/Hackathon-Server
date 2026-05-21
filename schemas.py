# schemas.py

from pydantic import BaseModel

class TextRequest(BaseModel):
    text: str

class QueryRequest(BaseModel):
    question: str
    session_id: str = "default"
    privacy_mode: bool = False