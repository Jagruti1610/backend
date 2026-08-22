from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

class DocumentStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class OCRLanguage(str, Enum):
    ENGLISH = "eng"
    HINDI = "hin"
    BOTH = "eng+hin"

class DocumentResponse(BaseModel):
    id: int
    filename: str
    summary: Optional[str] = None
    status: DocumentStatus
    model_used: str
    ocr_lang: Optional[str] = "eng"
    created_at: datetime

    # ✅ naye optional fields — Gemini-based smart analysis
    risk_score: Optional[int] = None
    risk_level: Optional[str] = None
    important_clauses: Optional[list[str]] = None
    missing_clauses: Optional[list[str]] = None
    pii_findings: Optional[dict] = None
    pii_found_count: Optional[int] = 0
    recommendations: Optional[list[str]] = None
    suggested_questions: Optional[list[str]] = None

    class Config:
        from_attributes = True

class ChatRequest(BaseModel):
    question: str
    model_choice: Optional[str] = "flash"
    session_id: Optional[int] = None

class ChatResponse(BaseModel):
    question: str
    answer: str
    created_at: datetime
    session_id: int
    session_title: str

class ChatHistoryItem(BaseModel):
    id: int
    question: str
    answer: str
    created_at: datetime

    class Config:
        from_attributes = True

class ChatSessionResponse(BaseModel):
    id: int
    title: str
    created_at: datetime

    class Config:
        from_attributes = True

class ChatMessageItem(BaseModel):
    id: int
    question: str
    answer: str
    created_at: datetime

    class Config:
        from_attributes = True

class ChatSessionDetail(BaseModel):
    id: int
    title: str
    created_at: datetime
    messages: List[ChatMessageItem]        

class TranslateRequest(BaseModel):
    language: str

class TranslateResponse(BaseModel):
    summary: str
    language: str