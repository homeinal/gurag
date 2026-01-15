"""
LLM Router: 사용자 쿼리를 분석하여 적절한 데이터 소스로 라우팅

라우팅 규칙:
- 시간 표현 ("최신", "최근", "이번 주", "오늘") → MCP (실시간 데이터)
- 개념 질문 ("설명해줘", "뭐야", "원리", "차이") → RAG (벡터 검색)
- 복합 질문 → MCP + RAG 병합
"""

from enum import Enum
from typing import Tuple, List
from openai import AsyncOpenAI
from pydantic import BaseModel
from app.config import get_settings

settings = get_settings()
client = AsyncOpenAI(api_key=settings.openai_api_key)


class QueryType(str, Enum):
    RAG = "rag"           # 개념/설명 질문 → 벡터 DB 검색
    MCP = "mcp"           # 실시간/최신 정보 → MCP 서버 호출
    HYBRID = "hybrid"     # 복합 질문 → RAG + MCP 병합


class RouterResult(BaseModel):
    query_type: QueryType
    confidence: float
    reasoning: str
    mcp_targets: List[str] = []  # ['arxiv', 'huggingface']


ROUTER_SYSTEM_PROMPT = """당신은 AI 관련 질문을 분류하는 라우터입니다.
사용자 질문을 분석하여 적절한 데이터 소스를 결정합니다.

## 분류 기준

### RAG (벡터 DB 검색)
- 개념 설명 요청: "~가 뭐야?", "~를 설명해줘", "~의 원리"
- 비교 질문: "~와 ~의 차이", "~는 어떻게 다른가"
- 일반적인 AI/ML 지식 질문

### MCP (실시간 검색)
- 시간 표현 포함: "최신", "최근", "이번 주", "오늘", "2024년", "새로운"
- 특정 논문/모델 검색: "~논문 찾아줘", "~모델 있어?"
- 트렌드 질문: "요즘 뜨는", "인기있는"

### HYBRID (복합)
- RAG + MCP 둘 다 필요한 경우
- 예: "최신 Transformer 연구 동향을 설명해줘" (개념 + 최신)

## 응답 형식 (JSON)
{
  "query_type": "rag" | "mcp" | "hybrid",
  "confidence": 0.0-1.0,
  "reasoning": "분류 이유 (한 문장)",
  "mcp_targets": ["arxiv", "huggingface"]  // MCP 사용 시 타겟
}

mcp_targets 규칙:
- 논문 관련 → ["arxiv"]
- 모델/데모 관련 → ["huggingface"]
- 둘 다 해당 → ["arxiv", "huggingface"]
"""


async def classify_query(query: str) -> RouterResult:
    """
    쿼리를 분석하여 라우팅 결정

    빠른 규칙 기반 분류를 먼저 시도하고,
    애매한 경우에만 LLM을 호출합니다.
    """
    # 1. 빠른 규칙 기반 분류
    rule_result = _rule_based_classify(query)
    if rule_result and rule_result.confidence >= 0.8:
        return rule_result

    # 2. LLM 기반 분류 (애매한 경우)
    return await _llm_classify(query)


def _rule_based_classify(query: str) -> RouterResult | None:
    """규칙 기반 빠른 분류"""
    query_lower = query.lower()

    # 시간 표현 키워드
    time_keywords = [
        "최신", "최근", "새로운", "오늘", "이번", "요즘",
        "2024", "2025", "2026", "트렌드", "동향", "뜨는"
    ]

    # 개념 설명 키워드
    concept_keywords = [
        "뭐야", "뭔가요", "설명", "알려줘", "원리", "개념",
        "차이", "비교", "어떻게 작동", "무엇인가"
    ]

    # 논문/모델 검색 키워드
    search_keywords = [
        "찾아", "검색", "논문", "paper", "있어", "알아봐"
    ]

    has_time = any(kw in query_lower for kw in time_keywords)
    has_concept = any(kw in query_lower for kw in concept_keywords)
    has_search = any(kw in query_lower for kw in search_keywords)

    # 복합 질문
    if has_time and has_concept:
        return RouterResult(
            query_type=QueryType.HYBRID,
            confidence=0.85,
            reasoning="시간 표현과 개념 설명이 모두 포함된 복합 질문",
            mcp_targets=["arxiv"]
        )

    # 실시간 검색 필요
    if has_time or has_search:
        targets = []
        if "논문" in query_lower or "paper" in query_lower or "arxiv" in query_lower:
            targets.append("arxiv")
        if "모델" in query_lower or "huggingface" in query_lower or "space" in query_lower:
            targets.append("huggingface")
        if not targets:
            targets = ["arxiv"]  # 기본값

        return RouterResult(
            query_type=QueryType.MCP,
            confidence=0.85,
            reasoning="시간 표현 또는 검색 키워드 포함",
            mcp_targets=targets
        )

    # 개념 설명
    if has_concept:
        return RouterResult(
            query_type=QueryType.RAG,
            confidence=0.85,
            reasoning="개념 설명 요청",
            mcp_targets=[]
        )

    # 명확하지 않음 → LLM 호출 필요
    return None


async def _llm_classify(query: str) -> RouterResult:
    """LLM을 사용한 쿼리 분류"""
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": f"다음 질문을 분류해주세요: {query}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=200,
        )

        import json
        result = json.loads(response.choices[0].message.content)

        return RouterResult(
            query_type=QueryType(result.get("query_type", "rag")),
            confidence=result.get("confidence", 0.7),
            reasoning=result.get("reasoning", "LLM 분류"),
            mcp_targets=result.get("mcp_targets", [])
        )
    except Exception as e:
        # 오류 시 RAG로 폴백
        return RouterResult(
            query_type=QueryType.RAG,
            confidence=0.5,
            reasoning=f"분류 오류, RAG로 폴백: {str(e)}",
            mcp_targets=[]
        )
