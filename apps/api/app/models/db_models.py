from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Table, Integer, Float
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import uuid

Base = declarative_base()

# OpenAI text-embedding-3-small 차원
EMBEDDING_DIMENSION = 1536


def generate_uuid():
    return str(uuid.uuid4())


# 다대다 관계 테이블: 사용자 - Guru
user_gurus = Table(
    "user_gurus",
    Base.metadata,
    Column("user_id", String, ForeignKey("users.id"), primary_key=True),
    Column("guru_id", String, ForeignKey("gurus.id"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    google_id = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 관계
    followed_gurus = relationship("Guru", secondary=user_gurus, back_populates="followers")


class Guru(Base):
    __tablename__ = "gurus"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    threads_handle = Column(String, unique=True, nullable=False, index=True)
    avatar_url = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 관계
    posts = relationship("GuruPost", back_populates="guru", cascade="all, delete-orphan")
    followers = relationship("User", secondary=user_gurus, back_populates="followed_gurus")


class GuruPost(Base):
    __tablename__ = "guru_posts"

    id = Column(String, primary_key=True, default=generate_uuid)
    guru_id = Column(String, ForeignKey("gurus.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    threads_url = Column(String, nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 관계
    guru = relationship("Guru", back_populates="posts")


class QueryCache(Base):
    __tablename__ = "query_cache"

    id = Column(String, primary_key=True, default=generate_uuid)
    query_hash = Column(String, unique=True, nullable=False, index=True)
    query_text = Column(Text, nullable=False)
    query_embedding = Column(Vector(EMBEDDING_DIMENSION), nullable=True)  # Semantic cache용 임베딩
    response = Column(Text, nullable=False)
    sources = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    hit_count = Column(Integer, default=0)


class QueryAnalytics(Base):
    """Phase 3에서 사용할 분석 테이블"""
    __tablename__ = "query_analytics"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    query_text = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)
    source_type = Column(String, nullable=True)  # 'rag', 'mcp', 'cache'
    feedback = Column(Integer, nullable=True)  # 1: positive, -1: negative
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
