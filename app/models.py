from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, EmailStr, Field

## -----------------------Auth------------------------------------------------------

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    full_name: str = Field(..., min_length=1)

class SigninRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str

class UserProfile(BaseModel):
    user_id: str
    email: str
    full_name: str
    created_at: datetime

## --------------------------Document-----------------------------------------------

class DocumentRecord(BaseModel):
    id: str
    user_id: str
    filename: str
    storage_path: str
    file_size_bytes: int
    created_at: datetime
    analyzed_at: datetime | None = None
    overall_risk: str | None = None

## -----------------------Analysis--------------------------------------------------

class RiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"
    UNKNOWN = "Unknown"

class ChunkResult(BaseModel):
    chunk_index: int
    chunk_text: str
    risk: RiskLevel
    summary: str
    suggestions: str
    from_cache: bool = False

class AnalysisReport(BaseModel):
    document_id: str
    document_name: str
    overall_risk: RiskLevel
    chunk_count: int
    high_risk_count: int
    critical_risk_count: int
    executive_summary: str
    top_issues: list[str]
    recommendations: list[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)

## -----------------------Streaming SSE events---------------------------------------------

class SSEEventType(str, Enum):
    STARTED = "started"
    CHUNK_DONE = "chunk_done"
    SYNTHESIS_DONE = "synthesis_done"
    ERROR = "error"
    DONE = "done"

class SSEEvent(BaseModel):
    event: SSEEventType
    data: Any

## ----------------------Conversation History------------------------------------------------

class ConversationRecord(BaseModel):
    user_id: str
    document_id: str
    document_name: str
    chunks: list[ChunkResult]
    report: AnalysisReport | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)