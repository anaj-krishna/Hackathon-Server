#schemas.py
from pydantic import BaseModel

class TextRequest(BaseModel):
    text: str
    session_id: str

class QueryRequest(BaseModel):
    question: str
    session_id: str