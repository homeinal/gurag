"""
Self-Learning Service (Phase 4)

1. 인기 쿼리 자동 캐싱 (Pre-warming)
2. 부정 피드백 기반 응답 개선
3. 스마트 캐시 관리
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, update

from app.models.db_models import QueryAnalytics, QueryCache
from app.services.analytics.logger import get_popular_queries, get_negative_feedback_queries
from app.services.cache.semantic_cache import save_to_cache, get_cached_response, invalidate_cache, generate_query_hash
from app.services.rag.retriever import retrieve_documents, format_context
from app.services.llm.openai_client import generate_response
from app.services.router.llm_router import classify_query, QueryType
from app.services.mcp.arxiv_client import get_arxiv_client
from app.services.mcp.huggingface_client import get_huggingface_client


class SelfLearner:
    """셀프러닝 엔진"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def run_learning_cycle(self) -> Dict[str, Any]:
        """
        전체 학습 사이클 실행

        Returns:
            학습 결과 요약
        """
        results = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "pre_warming": None,
            "response_improvement": None,
            "cache_cleanup": None,
        }

        # 1. 인기 쿼리 Pre-warming
        results["pre_warming"] = await self.pre_warm_popular_queries()

        # 2. 부정 피드백 응답 개선
        results["response_improvement"] = await self.improve_negative_responses()

        # 3. 캐시 정리 및 최적화
        results["cache_cleanup"] = await self.cleanup_stale_cache()

        results["completed_at"] = datetime.now(timezone.utc).isoformat()
        return results

    async def pre_warm_popular_queries(
        self,
        days: int = 7,
        min_count: int = 3,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        인기 쿼리를 미리 캐싱 (Pre-warming)

        - 자주 묻는 질문을 미리 처리해서 캐시에 저장
        - 사용자 응답 속도 향상
        """
        popular = await get_popular_queries(self.db, days, limit)

        warmed = 0
        skipped = 0
        errors = []

        for item in popular:
            query = item["query"]
            count = item["count"]

            # 최소 조회수 미만이면 스킵
            if count < min_count:
                continue

            # 이미 캐시에 있으면 스킵
            cached = await get_cached_response(self.db, query)
            if cached:
                skipped += 1
                continue

            try:
                # 새로 응답 생성
                await self._generate_and_cache_response(query)
                warmed += 1
                print(f"[PreWarm] Cached: {query[:50]}...")
            except Exception as e:
                errors.append({"query": query[:50], "error": str(e)})
                print(f"[PreWarm] Error: {query[:50]}... - {e}")

        return {
            "total_popular": len(popular),
            "warmed": warmed,
            "skipped": skipped,
            "errors": len(errors),
        }

    async def improve_negative_responses(
        self,
        days: int = 7,
        min_negative: int = 2,
    ) -> Dict[str, Any]:
        """
        부정 피드백이 많은 응답 개선

        - 부정 피드백이 많은 쿼리를 재처리
        - 개선된 응답으로 캐시 업데이트
        """
        negative_queries = await get_negative_feedback_queries(
            self.db, days, min_negative
        )

        improved = 0
        errors = []

        for item in negative_queries:
            query = item["query"]
            negative_count = item["negative_count"]

            try:
                # 기존 캐시 삭제
                await self._invalidate_cache(query)

                # 개선된 프롬프트로 재생성
                await self._generate_improved_response(query, negative_count)
                improved += 1
                print(f"[Improve] Regenerated: {query[:50]}...")
            except Exception as e:
                errors.append({"query": query[:50], "error": str(e)})
                print(f"[Improve] Error: {query[:50]}... - {e}")

        return {
            "total_negative": len(negative_queries),
            "improved": improved,
            "errors": len(errors),
        }

    async def cleanup_stale_cache(
        self,
        max_age_days: int = 30,
        min_hit_count: int = 0,
    ) -> Dict[str, Any]:
        """
        오래된 캐시 정리

        - 지정된 기간 이상 된 캐시 삭제
        - 조회수가 낮은 캐시 정리
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

        # 오래된 캐시 조회
        result = await self.db.execute(
            select(QueryCache).where(
                and_(
                    QueryCache.created_at < cutoff,
                    QueryCache.hit_count <= min_hit_count,
                )
            )
        )
        stale_caches = result.scalars().all()

        deleted = 0
        for cache in stale_caches:
            await self.db.delete(cache)
            deleted += 1

        if deleted > 0:
            await self.db.commit()
            print(f"[Cleanup] Deleted {deleted} stale cache entries")

        return {
            "deleted": deleted,
            "cutoff_date": cutoff.isoformat(),
        }

    async def extend_high_quality_cache(
        self,
        positive_threshold: int = 3,
        extension_days: int = 7,
    ) -> Dict[str, Any]:
        """
        긍정 피드백이 많은 캐시의 TTL 연장

        - 좋은 응답은 더 오래 캐시
        """
        # 긍정 피드백이 많은 쿼리 조회
        since = datetime.now(timezone.utc) - timedelta(days=30)

        result = await self.db.execute(
            select(
                QueryAnalytics.query_text,
                func.count(QueryAnalytics.id).label("positive_count"),
            )
            .where(
                and_(
                    QueryAnalytics.created_at >= since,
                    QueryAnalytics.feedback == 1,
                )
            )
            .group_by(QueryAnalytics.query_text)
            .having(func.count(QueryAnalytics.id) >= positive_threshold)
        )

        extended = 0
        for row in result:
            query_text = row[0]
            query_hash = generate_query_hash(query_text)

            # 해당 캐시의 expires_at 연장
            cache_result = await self.db.execute(
                select(QueryCache).where(QueryCache.query_hash == query_hash)
            )
            cache = cache_result.scalar_one_or_none()

            if cache:
                cache.expires_at = datetime.now(timezone.utc) + timedelta(days=extension_days)
                extended += 1

        if extended > 0:
            await self.db.commit()
            print(f"[Extend] Extended TTL for {extended} high-quality caches")

        return {
            "extended": extended,
            "extension_days": extension_days,
        }

    async def _generate_and_cache_response(self, query: str) -> None:
        """쿼리에 대한 응답을 생성하고 캐시에 저장"""
        # 쿼리 분류
        router_result = await classify_query(query)

        # 컨텍스트 수집
        contexts = []
        sources = []

        if router_result.query_type in (QueryType.RAG, QueryType.HYBRID):
            documents = await retrieve_documents(query, top_k=5)
            if documents:
                contexts.append(format_context(documents))
                for doc in documents:
                    metadata = doc.get("metadata", {})
                    sources.append({
                        "title": metadata.get("title", "Unknown"),
                        "url": metadata.get("url"),
                        "type": metadata.get("type", "rag"),
                        "relevance_score": doc.get("score"),
                    })

        if router_result.query_type in (QueryType.MCP, QueryType.HYBRID):
            if "arxiv" in router_result.mcp_targets:
                arxiv_client = get_arxiv_client()
                papers = await arxiv_client.search_papers(query, max_results=3)
                if papers:
                    contexts.append(arxiv_client.format_papers_as_context(papers))
                    for paper in papers:
                        sources.append({
                            "title": paper.title,
                            "url": paper.arxiv_url,
                            "type": "arxiv",
                            "relevance_score": 0.9,
                        })

        # 응답 생성
        combined_context = "\n\n---\n\n".join(contexts) if contexts else ""
        if combined_context:
            response_text = await generate_response(query, combined_context)
        else:
            response_text = "관련 정보를 찾을 수 없습니다."

        # 캐시 저장
        await save_to_cache(self.db, query, response_text, sources)
        await self.db.commit()

    async def _generate_improved_response(self, query: str, negative_count: int) -> None:
        """개선된 응답 생성 (더 상세하고 정확한 답변)"""
        # 쿼리 분류
        router_result = await classify_query(query)

        # 컨텍스트 수집 (더 많이)
        contexts = []
        sources = []

        # RAG에서 더 많은 문서 검색
        documents = await retrieve_documents(query, top_k=8, min_score=0.2)
        if documents:
            contexts.append(format_context(documents))
            for doc in documents:
                metadata = doc.get("metadata", {})
                sources.append({
                    "title": metadata.get("title", "Unknown"),
                    "url": metadata.get("url"),
                    "type": metadata.get("type", "rag"),
                    "relevance_score": doc.get("score"),
                })

        # MCP에서도 더 많은 결과
        arxiv_client = get_arxiv_client()
        papers = await arxiv_client.search_papers(query, max_results=5)
        if papers:
            contexts.append(arxiv_client.format_papers_as_context(papers))
            for paper in papers:
                sources.append({
                    "title": paper.title,
                    "url": paper.arxiv_url,
                    "type": "arxiv",
                    "relevance_score": 0.9,
                })

        # 개선된 프롬프트로 응답 생성
        combined_context = "\n\n---\n\n".join(contexts) if contexts else ""

        improved_system_prompt = f"""당신은 AI 분야 전문가입니다. 이 질문에 대해 이전에 {negative_count}개의 부정적인 피드백이 있었습니다.

다음 사항에 특히 주의하여 더 나은 답변을 제공해주세요:
1. 정확하고 구체적인 정보를 제공하세요.
2. 전문 용어는 쉽게 설명해주세요.
3. 예시나 비유를 사용하여 이해를 도우세요.
4. 참고 자료의 출처를 명확히 인용하세요.
5. 답변은 한국어로 작성하세요."""

        if combined_context:
            response_text = await generate_response(query, combined_context, improved_system_prompt)
        else:
            response_text = "죄송합니다. 더 나은 답변을 위해 관련 정보를 수집 중입니다."

        # 개선된 응답 캐시
        await save_to_cache(self.db, query, response_text, sources)
        await self.db.commit()

    async def _invalidate_cache(self, query: str) -> bool:
        """특정 쿼리의 캐시 무효화"""
        return await invalidate_cache(self.db, query)


async def run_self_learning(db: AsyncSession) -> Dict[str, Any]:
    """셀프러닝 실행 헬퍼 함수"""
    learner = SelfLearner(db)
    return await learner.run_learning_cycle()
