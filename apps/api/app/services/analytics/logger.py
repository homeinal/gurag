"""
Analytics Logger Service

쿼리/응답을 기록하고 통계를 제공합니다.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, case

from app.models.db_models import QueryAnalytics


async def log_query(
    db: AsyncSession,
    query_text: str,
    response_text: str,
    source_type: str,
    user_id: Optional[str] = None,
    latency_ms: Optional[int] = None,
) -> str:
    """
    쿼리/응답 로깅

    Returns:
        생성된 analytics 레코드 ID
    """
    analytics = QueryAnalytics(
        user_id=user_id,
        query_text=query_text,
        response_text=response_text,
        source_type=source_type,
        latency_ms=latency_ms,
    )
    db.add(analytics)
    await db.flush()
    await db.refresh(analytics)
    return analytics.id


async def record_feedback(
    db: AsyncSession,
    analytics_id: str,
    feedback: int,  # 1: positive, -1: negative
) -> bool:
    """사용자 피드백 기록"""
    result = await db.execute(
        select(QueryAnalytics).where(QueryAnalytics.id == analytics_id)
    )
    record = result.scalar_one_or_none()

    if record:
        record.feedback = feedback
        await db.flush()
        return True
    return False


async def get_analytics_summary(
    db: AsyncSession,
    days: int = 7,
) -> Dict[str, Any]:
    """분석 요약 통계"""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # 전체 쿼리 수
    total_result = await db.execute(
        select(func.count(QueryAnalytics.id)).where(
            QueryAnalytics.created_at >= since
        )
    )
    total_queries = total_result.scalar() or 0

    # 소스 타입별 분포
    source_result = await db.execute(
        select(
            QueryAnalytics.source_type,
            func.count(QueryAnalytics.id).label("count")
        )
        .where(QueryAnalytics.created_at >= since)
        .group_by(QueryAnalytics.source_type)
    )
    source_distribution = {row[0] or "unknown": row[1] for row in source_result}

    # 피드백 통계
    positive_result = await db.execute(
        select(func.count(QueryAnalytics.id)).where(
            and_(
                QueryAnalytics.created_at >= since,
                QueryAnalytics.feedback == 1
            )
        )
    )
    positive_count = positive_result.scalar() or 0

    negative_result = await db.execute(
        select(func.count(QueryAnalytics.id)).where(
            and_(
                QueryAnalytics.created_at >= since,
                QueryAnalytics.feedback == -1
            )
        )
    )
    negative_count = negative_result.scalar() or 0

    # 평균 응답 시간
    latency_result = await db.execute(
        select(func.avg(QueryAnalytics.latency_ms)).where(
            and_(
                QueryAnalytics.created_at >= since,
                QueryAnalytics.latency_ms.isnot(None)
            )
        )
    )
    avg_latency = latency_result.scalar()

    return {
        "period_days": days,
        "total_queries": total_queries,
        "source_distribution": source_distribution,
        "feedback": {
            "positive": positive_count,
            "negative": negative_count,
            "total": positive_count + negative_count,
        },
        "avg_latency_ms": round(avg_latency) if avg_latency else None,
    }


async def get_popular_queries(
    db: AsyncSession,
    days: int = 7,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """인기 쿼리 목록 (Phase 4 셀프러닝용)"""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            QueryAnalytics.query_text,
            func.count(QueryAnalytics.id).label("count"),
            func.sum(
                case(
                    (QueryAnalytics.feedback == 1, 1),
                    else_=0
                )
            ).label("positive"),
            func.sum(
                case(
                    (QueryAnalytics.feedback == -1, 1),
                    else_=0
                )
            ).label("negative"),
        )
        .where(QueryAnalytics.created_at >= since)
        .group_by(QueryAnalytics.query_text)
        .order_by(desc("count"))
        .limit(limit)
    )

    return [
        {
            "query": row[0],
            "count": row[1],
            "positive_feedback": row[2] or 0,
            "negative_feedback": row[3] or 0,
        }
        for row in result
    ]


async def get_recent_queries(
    db: AsyncSession,
    limit: int = 20,
    user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """최근 쿼리 목록"""
    query = select(QueryAnalytics).order_by(desc(QueryAnalytics.created_at)).limit(limit)

    if user_id:
        query = query.where(QueryAnalytics.user_id == user_id)

    result = await db.execute(query)
    records = result.scalars().all()

    return [
        {
            "id": r.id,
            "query": r.query_text[:100] + "..." if len(r.query_text) > 100 else r.query_text,
            "source_type": r.source_type,
            "feedback": r.feedback,
            "latency_ms": r.latency_ms,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]


async def get_negative_feedback_queries(
    db: AsyncSession,
    days: int = 7,
    min_negative: int = 2,
) -> List[Dict[str, Any]]:
    """부정 피드백이 많은 쿼리 (Phase 4 개선용)"""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            QueryAnalytics.query_text,
            func.count(QueryAnalytics.id).label("total"),
            func.sum(
                case(
                    (QueryAnalytics.feedback == -1, 1),
                    else_=0
                )
            ).label("negative"),
        )
        .where(QueryAnalytics.created_at >= since)
        .group_by(QueryAnalytics.query_text)
        .having(
            func.sum(
                case(
                    (QueryAnalytics.feedback == -1, 1),
                    else_=0
                )
            ) >= min_negative
        )
        .order_by(desc("negative"))
    )

    return [
        {
            "query": row[0],
            "total_count": row[1],
            "negative_count": row[2],
        }
        for row in result
    ]
