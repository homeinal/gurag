from typing import List, Dict, Any
from app.db.chroma import get_collection
from app.services.llm.openai_client import get_embedding


async def retrieve_documents(
    query: str,
    top_k: int = 5,
    min_score: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    쿼리와 유사한 문서 검색

    Returns:
        List of documents with:
        - id: 문서 ID
        - content: 문서 내용
        - metadata: 메타데이터 (title, url, type 등)
        - score: 유사도 점수 (0-1, 높을수록 유사)
    """
    # 쿼리 임베딩 생성
    query_embedding = await get_embedding(query)

    # ChromaDB에서 검색
    collection = get_collection()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    # 결과 포맷팅
    documents = []
    if results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            # ChromaDB distance를 유사도 점수로 변환 (cosine distance)
            # distance가 낮을수록 유사 → 1 - distance로 변환
            distance = results["distances"][0][i] if results["distances"] else 0
            score = 1 - distance

            if score >= min_score:
                documents.append({
                    "id": doc_id,
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": round(score, 4),
                })

    return documents


def format_context(documents: List[Dict[str, Any]]) -> str:
    """검색된 문서들을 컨텍스트 문자열로 포맷팅"""
    if not documents:
        return "관련 문서를 찾을 수 없습니다."

    context_parts = []
    for i, doc in enumerate(documents, 1):
        metadata = doc.get("metadata", {})
        title = metadata.get("title", f"문서 {i}")
        source_type = metadata.get("type", "unknown")
        url = metadata.get("url", "")

        part = f"[{i}] {title}"
        if source_type:
            part += f" ({source_type})"
        if url:
            part += f"\n출처: {url}"
        part += f"\n{doc['content']}"

        context_parts.append(part)

    return "\n\n---\n\n".join(context_parts)
