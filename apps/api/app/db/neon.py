from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import ssl
from app.config import get_settings
from app.models.db_models import Base

settings = get_settings()


def _prepare_database_url(url: str) -> tuple[str, dict]:
    """
    asyncpg용 DATABASE_URL 변환

    asyncpg는 sslmode 파라미터를 지원하지 않음.
    sslmode=require → ssl=True로 변환 필요.
    """
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)

    # sslmode 파라미터 확인 및 제거
    ssl_required = False
    if "sslmode" in query_params:
        sslmode = query_params.pop("sslmode")[0]
        ssl_required = sslmode in ("require", "verify-ca", "verify-full")

    # 쿼리 파라미터 재구성 (sslmode 제외)
    new_query = urlencode(query_params, doseq=True)
    new_parsed = parsed._replace(query=new_query)
    clean_url = urlunparse(new_parsed)

    # asyncpg용 connect_args 생성
    connect_args = {}
    if ssl_required:
        # SSL 컨텍스트 생성 (서버 인증서 검증 없이)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_context

    return clean_url, connect_args


# DATABASE_URL 변환
clean_database_url, connect_args = _prepare_database_url(settings.database_url)

# Neon은 서버리스이므로 connection pooling 비활성화
engine = create_async_engine(
    clean_database_url,
    echo=False,
    poolclass=NullPool,
    connect_args=connect_args,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """데이터베이스 테이블 생성 및 pgvector 익스텐션 활성화"""
    async with engine.begin() as conn:
        # pgvector 익스텐션 활성화 (Neon은 기본 지원)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """의존성 주입용 세션 생성"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
