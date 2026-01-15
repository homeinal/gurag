"""
Analytics API Router

분석 통계, 피드백 기록, 대시보드 데이터 제공
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.db.neon import get_db
from app.services.analytics.logger import (
    record_feedback,
    get_analytics_summary,
    get_popular_queries,
    get_recent_queries,
    get_negative_feedback_queries,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# Request/Response Models
class FeedbackRequest(BaseModel):
    analytics_id: str
    feedback: int  # 1: positive (👍), -1: negative (👎)


class FeedbackResponse(BaseModel):
    success: bool
    message: str


class AnalyticsSummary(BaseModel):
    period_days: int
    total_queries: int
    source_distribution: Dict[str, int]
    feedback: Dict[str, int]
    avg_latency_ms: Optional[int]


class PopularQuery(BaseModel):
    query: str
    count: int
    positive_feedback: int
    negative_feedback: int


class RecentQuery(BaseModel):
    id: str
    query: str
    source_type: str
    feedback: Optional[int]
    latency_ms: Optional[int]
    created_at: str


class NegativeFeedbackQuery(BaseModel):
    query: str
    total_count: int
    negative_count: int


class DashboardData(BaseModel):
    summary: AnalyticsSummary
    popular_queries: List[PopularQuery]
    recent_queries: List[RecentQuery]
    negative_feedback_queries: List[NegativeFeedbackQuery]


# API Endpoints
@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    사용자 피드백 제출

    - analytics_id: 채팅 응답에서 받은 ID
    - feedback: 1 (좋아요) 또는 -1 (싫어요)
    """
    if request.feedback not in (1, -1):
        raise HTTPException(
            status_code=400,
            detail="feedback must be 1 (positive) or -1 (negative)"
        )

    success = await record_feedback(db, request.analytics_id, request.feedback)

    if success:
        await db.commit()
        return FeedbackResponse(
            success=True,
            message="피드백이 기록되었습니다."
        )
    else:
        raise HTTPException(
            status_code=404,
            detail="해당 analytics_id를 찾을 수 없습니다."
        )


@router.get("/summary", response_model=AnalyticsSummary)
async def get_summary(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    """분석 요약 통계 조회"""
    if days < 1 or days > 365:
        raise HTTPException(
            status_code=400,
            detail="days must be between 1 and 365"
        )

    summary = await get_analytics_summary(db, days)
    return AnalyticsSummary(**summary)


@router.get("/popular", response_model=List[PopularQuery])
async def get_popular(
    days: int = 7,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """인기 쿼리 목록 조회"""
    queries = await get_popular_queries(db, days, limit)
    return [PopularQuery(**q) for q in queries]


@router.get("/recent", response_model=List[RecentQuery])
async def get_recent(
    limit: int = 20,
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """최근 쿼리 목록 조회"""
    queries = await get_recent_queries(db, limit, user_id)
    return [RecentQuery(**q) for q in queries]


@router.get("/negative-feedback", response_model=List[NegativeFeedbackQuery])
async def get_negative_feedback(
    days: int = 7,
    min_negative: int = 2,
    db: AsyncSession = Depends(get_db),
):
    """부정 피드백이 많은 쿼리 목록 (Phase 4 개선용)"""
    queries = await get_negative_feedback_queries(db, days, min_negative)
    return [NegativeFeedbackQuery(**q) for q in queries]


@router.get("/dashboard", response_model=DashboardData)
async def get_dashboard(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
):
    """대시보드용 통합 데이터"""
    summary = await get_analytics_summary(db, days)
    popular = await get_popular_queries(db, days, 10)
    recent = await get_recent_queries(db, 20)
    negative = await get_negative_feedback_queries(db, days)

    return DashboardData(
        summary=AnalyticsSummary(**summary),
        popular_queries=[PopularQuery(**q) for q in popular],
        recent_queries=[RecentQuery(**q) for q in recent],
        negative_feedback_queries=[NegativeFeedbackQuery(**q) for q in negative],
    )
