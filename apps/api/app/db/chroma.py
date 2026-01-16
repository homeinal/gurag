import chromadb
from chromadb.config import Settings
from app.config import get_settings

settings = get_settings()

# ChromaDB 클라이언트 설정
# Render free tier는 in-memory 모드 사용 (ephemeral filesystem)
if settings.chroma_in_memory or settings.environment == "production":
    chroma_client = chromadb.Client(
        settings=Settings(
            anonymized_telemetry=False,
            allow_reset=True,
        ),
    )
else:
    # 로컬 개발 환경은 영구 저장소 사용
    chroma_client = chromadb.PersistentClient(
        path=settings.chroma_persist_directory,
        settings=Settings(
            anonymized_telemetry=False,
            allow_reset=True,
        ),
    )


def get_collection():
    """RAG용 컬렉션 가져오기 또는 생성"""
    return chroma_client.get_or_create_collection(
        name=settings.chroma_collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def reset_collection():
    """컬렉션 초기화 (테스트용)"""
    try:
        chroma_client.delete_collection(settings.chroma_collection_name)
    except ValueError:
        pass
    return get_collection()
