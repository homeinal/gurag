from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://user:pass@localhost/db"

    # OpenAI
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"

    # ChromaDB
    chroma_persist_directory: str = "./chroma_data"
    chroma_collection_name: str = "ai_documents"
    chroma_in_memory: bool = False  # Render free tier는 True로 설정

    # Cache
    cache_ttl_hours: int = 24
    semantic_cache_threshold: float = 0.92  # 코사인 유사도 임계값
    semantic_cache_enabled: bool = True  # Semantic cache 활성화 여부

    # CORS
    allowed_origins: str = "http://localhost:3000"

    # Environment
    environment: str = "development"  # production, development

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
