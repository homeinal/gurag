"""
Semantic Caching for RAG

임베딩 기반 유사도 검색으로 의미적으로 유사한 쿼리에 대해 캐시 히트를 제공합니다.
예: "Transformer란?", "트랜스포머가 뭐야?" → 동일한 캐시 히트

임베딩 생성 실패 시 exact_match로 폴백합니다.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models.db_models import QueryCache
from app.config import get_settings
from app.services.llm.openai_client import get_embedding
from app.services.cache import exact_match  # Fallback용

settings = get_settings()


def generate_query_hash(query: str) -> str:
    """쿼리 문자열의 해시 생성 (정규화 후)"""
    normalized = " ".join(query.lower().strip().split())
    return hashlib.sha256(normalized.encode()).hexdigest()[:32]


async def _get_query_embedding(query: str) -> Optional[List[float]]:
    """
    쿼리의 임베딩 벡터 생성

    실패 시 None 반환 (exact_match로 폴백)
    """
    try:
        embedding = await get_embedding(query)
        return embedding
    except Exception as e:
        print(f"[SemanticCache] Embedding generation failed: {e}")
        return None


async def get_cached_response(
    db: AsyncSession,
    query: str,
) -> Optional[Tuple[str, list]]:
    """
    캐시된 응답 조회 (Semantic Search)

    1. 쿼리 임베딩 생성
    2. 코사인 유사도로 가장 유사한 캐시 검색
    3. 유사도가 threshold 이상이면 캐시 히트
    4. 임베딩 실패 시 exact_match로 폴백

    Returns:
        (response, sources) 튜플 또는 None
    """
    # Semantic cache 비활성화 시 exact_match 사용
    if not settings.semantic_cache_enabled:
        return await exact_match.get_cached_response(db, query)

    # 쿼리 임베딩 생성
    query_embedding = await _get_query_embedding(query)

    # 임베딩 생성 실패 시 exact_match로 폴백
    if query_embedding is None:
        print("[SemanticCache] Falling back to exact_match")
        return await exact_match.get_cached_response(db, query)

    now = datetime.now(timezone.utc)
    threshold = settings.semantic_cache_threshold

    # pgvector 코사인 유사도 검색
    # 1 - cosine_distance = cosine_similarity
    # <=> 연산자는 cosine distance를 계산
    sql = text("""
        SELECT
            id, query_text, response, sources, hit_count,
            1 - (query_embedding <=> :embedding) as similarity
        FROM query_cache
        WHERE
            query_embedding IS NOT NULL
            AND expires_at > :now
        ORDER BY query_embedding <=> :embedding
        LIMIT 1
    """)

    result = await db.execute(
        sql,
        {
            "embedding": str(query_embedding),
            "now": now,
        }
    )
    row = result.fetchone()

    if row and row.similarity >= threshold:
        # 캐시 히트! 히트 카운트 증가
        cache_id = row.id
        await db.execute(
            text("UPDATE query_cache SET hit_count = hit_count + 1 WHERE id = :id"),
            {"id": cache_id}
        )
        await db.flush()

        sources = json.loads(row.sources) if row.sources else []
        print(f"[SemanticCache] HIT (similarity: {row.similarity:.4f}) for: {query[:50]}...")
        return row.response, sources

    # 유사한 캐시가 없으면 exact_match도 시도
    exact_result = await exact_match.get_cached_response(db, query)
    if exact_result:
        print(f"[SemanticCache] Exact match fallback HIT for: {query[:50]}...")
        return exact_result

    print(f"[SemanticCache] MISS for: {query[:50]}...")
    return None


async def save_to_cache(
    db: AsyncSession,
    query: str,
    response: str,
    sources: list = None,
) -> None:
    """
    응답을 캐시에 저장 (임베딩 포함)

    임베딩 생성 실패 시에도 exact_match용으로 저장
    """
    query_hash = generate_query_hash(query)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=settings.cache_ttl_hours)

    # 쿼리 임베딩 생성 (실패해도 계속 진행)
    query_embedding = await _get_query_embedding(query)

    # 기존 캐시 확인 (해시 기반)
    result = await db.execute(
        select(QueryCache).where(QueryCache.query_hash == query_hash)
    )
    existing = result.scalar_one_or_none()

    if existing:
        # 기존 캐시 업데이트
        existing.response = response
        existing.sources = json.dumps(sources) if sources else None
        existing.expires_at = expires_at
        existing.hit_count = 0
        if query_embedding:
            existing.query_embedding = query_embedding
    else:
        # 새 캐시 생성
        cache_entry = QueryCache(
            query_hash=query_hash,
            query_text=query,
            query_embedding=query_embedding,
            response=response,
            sources=json.dumps(sources) if sources else None,
            expires_at=expires_at,
        )
        db.add(cache_entry)

    await db.flush()
    print(f"[SemanticCache] Saved cache for: {query[:50]}...")


async def invalidate_cache(db: AsyncSession, query: str) -> bool:
    """특정 쿼리 캐시 무효화"""
    query_hash = generate_query_hash(query)

    result = await db.execute(
        select(QueryCache).where(QueryCache.query_hash == query_hash)
    )
    cache_entry = result.scalar_one_or_none()

    if cache_entry:
        await db.delete(cache_entry)
        await db.flush()
        print(f"[SemanticCache] Invalidated cache for: {query[:50]}...")
        return True

    return False


async def find_similar_queries(
    db: AsyncSession,
    query: str,
    limit: int = 5,
    min_similarity: float = 0.8,
) -> List[dict]:
    """
    유사한 쿼리 목록 조회 (디버깅/분석용)

    Returns:
        [{"query": str, "similarity": float, "hit_count": int}, ...]
    """
    query_embedding = await _get_query_embedding(query)
    if query_embedding is None:
        return []

    now = datetime.now(timezone.utc)

    sql = text("""
        SELECT
            query_text,
            1 - (query_embedding <=> :embedding) as similarity,
            hit_count
        FROM query_cache
        WHERE
            query_embedding IS NOT NULL
            AND expires_at > :now
            AND 1 - (query_embedding <=> :embedding) >= :min_similarity
        ORDER BY query_embedding <=> :embedding
        LIMIT :limit
    """)

    result = await db.execute(
        sql,
        {
            "embedding": str(query_embedding),
            "now": now,
            "min_similarity": min_similarity,
            "limit": limit,
        }
    )

    return [
        {
            "query": row.query_text,
            "similarity": row.similarity,
            "hit_count": row.hit_count,
        }
        for row in result.fetchall()
    ]
