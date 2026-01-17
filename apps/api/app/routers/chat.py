from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
import uuid
import time
from typing import List, Dict, Any

from app.db.neon import get_db
from app.models.schemas import ChatRequest, ChatResponse, ChatMessageResponse, ChatSource
from app.services.cache.semantic_cache import get_cached_response, save_to_cache
from app.services.rag.retriever import retrieve_documents, format_context
from app.services.llm.openai_client import generate_response
from app.services.rag.embedder import get_document_count
from app.services.router.llm_router import classify_query, QueryType
from app.services.mcp.arxiv_client import get_arxiv_client
from app.services.mcp.huggingface_client import get_huggingface_client
from app.services.analytics.logger import log_query

router = APIRouter()


async def _get_mcp_context(query: str, targets: List[str]) -> tuple[str, List[Dict[str, Any]]]:
    """MCP 서버에서 실시간 데이터 가져오기"""
    contexts = []
    sources = []

    if "arxiv" in targets:
        arxiv_client = get_arxiv_client()
        papers = await arxiv_client.search_papers(query, max_results=5)
        if papers:
            contexts.append("## arXiv 최신 논문\n" + arxiv_client.format_papers_as_context(papers))
            for paper in papers:
                sources.append({
                    "title": paper.title,
                    "url": paper.arxiv_url,
                    "type": "arxiv",
                    "relevance_score": 0.9,
                })

    if "huggingface" in targets:
        hf_client = get_huggingface_client()

        # Space 검색
        spaces = await hf_client.search_spaces(query, limit=3)
        if spaces:
            contexts.append("## HuggingFace Spaces\n" + hf_client.format_spaces_as_context(spaces))
            for space in spaces:
                sources.append({
                    "title": f"Space: {space.title}",
                    "url": space.url,
                    "type": "huggingface",
                    "relevance_score": 0.85,
                })

        # 모델 검색
        models = await hf_client.search_models(query, limit=3)
        if models:
            contexts.append("## HuggingFace Models\n" + hf_client.format_models_as_context(models))
            for model in models:
                sources.append({
                    "title": f"Model: {model.id}",
                    "url": model.url,
                    "type": "huggingface",
                    "relevance_score": 0.85,
                })

    return "\n\n".join(contexts), sources


async def _get_rag_context(query: str) -> tuple[str, List[Dict[str, Any]]]:
    """RAG 벡터 검색으로 컨텍스트 가져오기"""
    documents = await retrieve_documents(query, top_k=5)

    sources = []
    for doc in documents:
        metadata = doc.get("metadata", {})
        sources.append({
            "title": metadata.get("title", "Unknown"),
            "url": metadata.get("url"),
            "type": metadata.get("type", "rag"),
            "relevance_score": doc.get("score"),
        })

    context = format_context(documents) if documents else ""
    return context, sources


def _merge_and_rank_sources(
    rag_sources: List[Dict],
    mcp_sources: List[Dict],
    query_type: QueryType,
) -> List[Dict[str, Any]]:
    """소스를 병합하고 관련성 점수로 재정렬"""
    all_sources = []

    # MCP 소스에 가중치 부여 (실시간 데이터 우선)
    for src in mcp_sources:
        score = src.get("relevance_score", 0.8)
        if query_type == QueryType.MCP:
            score *= 1.1  # MCP 쿼리면 MCP 소스 우선
        src["relevance_score"] = min(score, 1.0)
        all_sources.append(src)

    # RAG 소스
    for src in rag_sources:
        score = src.get("relevance_score", 0.7)
        if query_type == QueryType.RAG:
            score *= 1.1  # RAG 쿼리면 RAG 소스 우선
        src["relevance_score"] = min(score, 1.0)
        all_sources.append(src)

    # 관련성 점수로 정렬
    all_sources.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    # 상위 10개만 반환
    return all_sources[:10]


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    스마트 챗봇 질의 처리 (Phase 2 + 3)

    1. Exact Match 캐시 확인
    2. LLM Router로 쿼리 분류
    3. 분류에 따라 RAG/MCP/Hybrid 처리
    4. 응답 생성 및 캐시 저장
    5. Analytics 로깅
    """
    start_time = time.time()
    query = request.query.strip()

    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # 1. 캐시 확인
    cached = await get_cached_response(db, query)

    if cached:
        response_text, sources = cached
        latency_ms = int((time.time() - start_time) * 1000)

        # 캐시 히트도 로깅
        analytics_id = await log_query(
            db=db,
            query_text=query,
            response_text=response_text,
            source_type="cache",
            user_id=request.user_id,
            latency_ms=latency_ms,
        )
        await db.commit()

        return ChatResponse(
            message=ChatMessageResponse(
                id=str(uuid.uuid4()),
                role="assistant",
                content=response_text,
                sources=[ChatSource(**s) for s in sources],
                created_at=datetime.now(timezone.utc),
            ),
            cached=True,
            analytics_id=analytics_id,
        )

    # 2. LLM Router로 쿼리 분류
    router_result = await classify_query(query)
    print(f"[Router] {query[:50]}... → {router_result.query_type} (confidence: {router_result.confidence})")

    # 3. 분류에 따른 처리
    rag_context = ""
    mcp_context = ""
    rag_sources: List[Dict] = []
    mcp_sources: List[Dict] = []

    if router_result.query_type == QueryType.RAG:
        # RAG만 사용
        rag_context, rag_sources = await _get_rag_context(query)

    elif router_result.query_type == QueryType.MCP:
        # MCP만 사용
        mcp_context, mcp_sources = await _get_mcp_context(query, router_result.mcp_targets)

    elif router_result.query_type == QueryType.HYBRID:
        # RAG + MCP 둘 다 사용
        rag_context, rag_sources = await _get_rag_context(query)
        mcp_context, mcp_sources = await _get_mcp_context(query, router_result.mcp_targets)

    # 컨텍스트 병합
    contexts = []
    if mcp_context:
        contexts.append(f"## 실시간 검색 결과\n{mcp_context}")
    if rag_context:
        contexts.append(f"## 지식 베이스\n{rag_context}")

    combined_context = "\n\n---\n\n".join(contexts) if contexts else ""

    # 소스 병합 및 정렬
    all_sources = _merge_and_rank_sources(rag_sources, mcp_sources, router_result.query_type)

    # 4. 응답 생성
    if combined_context:
        # 쿼리 타입에 따른 시스템 프롬프트 조정
        if router_result.query_type == QueryType.MCP:
            system_prompt = """당신은 AI 분야 전문가입니다. 제공된 실시간 검색 결과를 기반으로 답변하세요.

규칙:
1. 검색 결과에 있는 정보를 중심으로 답변하세요.
2. 논문이나 모델의 제목과 링크를 인용하세요.
3. 최신 정보임을 강조하세요.
4. 답변은 한국어로 작성하세요."""
        else:
            system_prompt = None  # 기본 프롬프트 사용

        response_text = await generate_response(query, combined_context, system_prompt)
    else:
        # 컨텍스트가 없는 경우
        response_text = (
            "죄송합니다. 질문과 관련된 정보를 찾을 수 없습니다. "
            "다른 방식으로 질문해 주시거나, 더 구체적인 키워드를 사용해 보세요."
        )

    # 5. 캐시 저장
    await save_to_cache(db, query, response_text, all_sources)

    # 6. Analytics 로깅
    latency_ms = int((time.time() - start_time) * 1000)
    analytics_id = await log_query(
        db=db,
        query_text=query,
        response_text=response_text,
        source_type=router_result.query_type.value,
        user_id=request.user_id,
        latency_ms=latency_ms,
    )
    await db.commit()

    return ChatResponse(
        message=ChatMessageResponse(
            id=str(uuid.uuid4()),
            role="assistant",
            content=response_text,
            sources=[ChatSource(**s) for s in all_sources],
            created_at=datetime.now(timezone.utc),
        ),
        cached=False,
        analytics_id=analytics_id,
    )


@router.get("/stats")
async def get_chat_stats(db: AsyncSession = Depends(get_db)):
    """챗봇 통계 조회"""
    doc_count = get_document_count()

    return {
        "document_count": doc_count,
        "status": "ready" if doc_count > 0 else "no_documents",
        "features": ["rag", "mcp_arxiv", "mcp_huggingface", "llm_router"],
    }


@router.post("/classify")
async def classify_query_endpoint(request: ChatRequest):
    """쿼리 분류 테스트 엔드포인트 (디버깅용)"""
    result = await classify_query(request.query)
    return {
        "query": request.query,
        "classification": result.dict(),
    }
