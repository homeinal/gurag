"""
Self-Learning API Router (Phase 4)

셀프러닝 시스템 관리 및 실행 API
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from app.db.neon import get_db
from app.services.learning.self_learner import SelfLearner, run_self_learning

router = APIRouter(prefix="/api/learning", tags=["learning"])


# Request/Response Models
class LearningTaskResponse(BaseModel):
    task_id: str
    status: str
    message: str


class LearningResultResponse(BaseModel):
    started_at: Optional[str]
    completed_at: Optional[str]
    pre_warming: Optional[Dict[str, Any]]
    response_improvement: Optional[Dict[str, Any]]
    cache_cleanup: Optional[Dict[str, Any]]


class PreWarmRequest(BaseModel):
    days: int = 7
    min_count: int = 3
    limit: int = 20


class CleanupRequest(BaseModel):
    max_age_days: int = 30
    min_hit_count: int = 0


# 상태 저장 (실제 서비스에서는 Redis 등 사용)
_learning_status: Dict[str, Any] = {
    "is_running": False,
    "last_run": None,
    "last_result": None,
}


@router.post("/run", response_model=LearningTaskResponse)
async def trigger_learning_cycle(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    셀프러닝 사이클 실행 (백그라운드)

    전체 학습 사이클:
    1. 인기 쿼리 Pre-warming
    2. 부정 피드백 응답 개선
    3. 오래된 캐시 정리
    """
    if _learning_status["is_running"]:
        raise HTTPException(
            status_code=409,
            detail="Learning cycle is already running"
        )

    task_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    async def run_learning_task():
        global _learning_status
        _learning_status["is_running"] = True
        try:
            result = await run_self_learning(db)
            _learning_status["last_result"] = result
            _learning_status["last_run"] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            _learning_status["last_result"] = {"error": str(e)}
        finally:
            _learning_status["is_running"] = False

    background_tasks.add_task(run_learning_task)

    return LearningTaskResponse(
        task_id=task_id,
        status="started",
        message="Learning cycle started in background",
    )


@router.get("/status")
async def get_learning_status():
    """셀프러닝 상태 조회"""
    return {
        "is_running": _learning_status["is_running"],
        "last_run": _learning_status["last_run"],
        "last_result": _learning_status["last_result"],
    }


@router.post("/pre-warm")
async def pre_warm_cache(
    request: PreWarmRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    인기 쿼리 Pre-warming 실행

    - 자주 묻는 질문을 미리 캐싱
    - 사용자 응답 속도 향상
    """
    learner = SelfLearner(db)
    result = await learner.pre_warm_popular_queries(
        days=request.days,
        min_count=request.min_count,
        limit=request.limit,
    )
    return result


@router.post("/improve-responses")
async def improve_negative_responses(
    days: int = 7,
    min_negative: int = 2,
    db: AsyncSession = Depends(get_db),
):
    """
    부정 피드백 응답 개선

    - 부정 피드백이 많은 쿼리를 재처리
    - 개선된 응답으로 캐시 업데이트
    """
    learner = SelfLearner(db)
    result = await learner.improve_negative_responses(
        days=days,
        min_negative=min_negative,
    )
    return result


@router.post("/cleanup")
async def cleanup_cache(
    request: CleanupRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    오래된 캐시 정리

    - 지정된 기간 이상 된 캐시 삭제
    - 조회수가 낮은 캐시 정리
    """
    learner = SelfLearner(db)
    result = await learner.cleanup_stale_cache(
        max_age_days=request.max_age_days,
        min_hit_count=request.min_hit_count,
    )
    return result


@router.post("/extend-ttl")
async def extend_high_quality_cache(
    positive_threshold: int = 3,
    extension_days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    """
    좋은 응답의 캐시 TTL 연장

    - 긍정 피드백이 많은 캐시는 더 오래 유지
    """
    learner = SelfLearner(db)
    result = await learner.extend_high_quality_cache(
        positive_threshold=positive_threshold,
        extension_days=extension_days,
    )
    return result


@router.get("/stats")
async def get_learning_stats(
    db: AsyncSession = Depends(get_db),
):
    """
    셀프러닝 통계

    - 캐시 상태
    - 피드백 통계
    - 개선 가능한 쿼리 수
    """
    from sqlalchemy import select, func, and_
    from datetime import timedelta
    from app.models.db_models import QueryCache, QueryAnalytics

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    # 캐시 통계
    cache_result = await db.execute(
        select(
            func.count(QueryCache.id).label("total"),
            func.sum(QueryCache.hit_count).label("total_hits"),
        )
    )
    cache_stats = cache_result.first()

    # 만료된 캐시 수
    expired_result = await db.execute(
        select(func.count(QueryCache.id)).where(QueryCache.expires_at < now)
    )
    expired_count = expired_result.scalar() or 0

    # 개선 가능한 쿼리 수 (부정 피드백 2개 이상)
    from app.services.analytics.logger import get_negative_feedback_queries
    negative_queries = await get_negative_feedback_queries(db, days=7, min_negative=2)

    return {
        "cache": {
            "total_entries": cache_stats[0] or 0,
            "total_hits": cache_stats[1] or 0,
            "expired_entries": expired_count,
        },
        "improvement_candidates": len(negative_queries),
        "last_learning_run": _learning_status["last_run"],
        "is_running": _learning_status["is_running"],
    }
