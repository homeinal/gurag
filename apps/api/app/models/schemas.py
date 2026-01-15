from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# User Schemas
class UserCreate(BaseModel):
    google_id: str
    email: EmailStr
    name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str]
    avatar_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class UserGuruUpdate(BaseModel):
    guru_ids: List[str]


# Guru Schemas
class GuruCreate(BaseModel):
    name: str
    threads_handle: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None


class GuruResponse(BaseModel):
    id: str
    name: str
    threads_handle: str
    avatar_url: Optional[str]
    bio: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Post Schemas
class PostResponse(BaseModel):
    id: str
    guru_id: str
    content: str
    threads_url: Optional[str]
    posted_at: datetime
    created_at: datetime
    guru: Optional[GuruResponse] = None

    class Config:
        from_attributes = True


class FeedResponse(BaseModel):
    posts: List[PostResponse]
    total: int
    has_more: bool


# Chat Schemas
class ChatSource(BaseModel):
    title: str
    url: Optional[str] = None
    type: str  # 'arxiv', 'huggingface', 'cache'
    relevance_score: Optional[float] = None


class ChatRequest(BaseModel):
    query: str
    user_id: Optional[str] = None


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: List[ChatSource] = []
    created_at: datetime


class ChatResponse(BaseModel):
    message: ChatMessageResponse
    cached: bool
    analytics_id: Optional[str] = None  # Phase 3: 피드백용 ID


# Analytics Schemas (Phase 3)
class FeedbackRequest(BaseModel):
    message_id: str
    feedback: int  # 1 or -1
