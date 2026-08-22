from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..core.database import Base
import enum

class DocumentStatus(str, enum.Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=True)
    extracted_text = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    model_used = Column(String, default="flash")
    ocr_lang = Column(String, default="eng")  # <-- NEW: stores OCR language
    status = Column(Enum(DocumentStatus), default=DocumentStatus.PROCESSING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ✅ Analysis — computed once at upload, stored here so it never has to
    # be recomputed (saves Gemini calls, and list/detail views always match).
    risk_score = Column(Integer, nullable=True)
    risk_level = Column(String, nullable=True)
    important_clauses = Column(JSON, nullable=True)
    missing_clauses = Column(JSON, nullable=True)
    pii_findings = Column(JSON, nullable=True)
    pii_found_count = Column(Integer, nullable=True, default=0)
    recommendations = Column(JSON, nullable=True)
    suggested_questions = Column(JSON, nullable=True)

    owner = relationship("User", backref="documents")