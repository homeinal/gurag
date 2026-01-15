"""
HuggingFace Spaces MCP Client

MCP 서버 스펙을 따르는 HuggingFace 검색 클라이언트
- search_spaces: Space 검색
- search_models: 모델 검색
"""

import httpx
from typing import List, Optional
from pydantic import BaseModel


class HFSpace(BaseModel):
    id: str
    author: str
    title: str
    description: Optional[str] = None
    likes: int = 0
    sdk: Optional[str] = None
    url: str


class HFModel(BaseModel):
    id: str
    author: str
    model_name: str
    description: Optional[str] = None
    downloads: int = 0
    likes: int = 0
    tags: List[str] = []
    url: str


class HuggingFaceMCPClient:
    """HuggingFace API를 MCP 스펙에 맞게 래핑한 클라이언트"""

    BASE_URL = "https://huggingface.co/api"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def search_spaces(
        self,
        query: str,
        limit: int = 10,
        sort: str = "likes",
    ) -> List[HFSpace]:
        """
        HuggingFace Spaces 검색

        Args:
            query: 검색어
            limit: 최대 결과 수
            sort: 정렬 기준 (likes, trending, created)

        Returns:
            HFSpace 리스트
        """
        params = {
            "search": query,
            "limit": limit,
            "sort": sort,
            "direction": -1,
        }

        try:
            response = await self.client.get(f"{self.BASE_URL}/spaces", params=params)
            response.raise_for_status()

            spaces = []
            for item in response.json():
                space = HFSpace(
                    id=item.get("id", ""),
                    author=item.get("author", ""),
                    title=item.get("id", "").split("/")[-1],
                    description=item.get("cardData", {}).get("short_description"),
                    likes=item.get("likes", 0),
                    sdk=item.get("sdk"),
                    url=f"https://huggingface.co/spaces/{item.get('id', '')}",
                )
                spaces.append(space)

            return spaces

        except Exception as e:
            print(f"HuggingFace Spaces API 오류: {e}")
            return []

    async def search_models(
        self,
        query: str,
        limit: int = 10,
        sort: str = "downloads",
        filter_tags: Optional[List[str]] = None,
    ) -> List[HFModel]:
        """
        HuggingFace 모델 검색

        Args:
            query: 검색어
            limit: 최대 결과 수
            sort: 정렬 기준 (downloads, likes, trending)
            filter_tags: 태그 필터

        Returns:
            HFModel 리스트
        """
        params = {
            "search": query,
            "limit": limit,
            "sort": sort,
            "direction": -1,
        }

        if filter_tags:
            params["filter"] = ",".join(filter_tags)

        try:
            response = await self.client.get(f"{self.BASE_URL}/models", params=params)
            response.raise_for_status()

            models = []
            for item in response.json():
                model = HFModel(
                    id=item.get("id", ""),
                    author=item.get("author", item.get("id", "").split("/")[0]),
                    model_name=item.get("id", "").split("/")[-1],
                    description=item.get("cardData", {}).get("description"),
                    downloads=item.get("downloads", 0),
                    likes=item.get("likes", 0),
                    tags=item.get("tags", []),
                    url=f"https://huggingface.co/{item.get('id', '')}",
                )
                models.append(model)

            return models

        except Exception as e:
            print(f"HuggingFace Models API 오류: {e}")
            return []

    def format_spaces_as_context(self, spaces: List[HFSpace]) -> str:
        """Space 목록을 컨텍스트 문자열로 변환"""
        if not spaces:
            return "검색된 Space가 없습니다."

        parts = []
        for i, space in enumerate(spaces, 1):
            part = f"""[{i}] {space.title}
제작자: {space.author}
좋아요: {space.likes}
SDK: {space.sdk or 'N/A'}
설명: {space.description or 'N/A'}
링크: {space.url}"""
            parts.append(part)

        return "\n\n---\n\n".join(parts)

    def format_models_as_context(self, models: List[HFModel]) -> str:
        """모델 목록을 컨텍스트 문자열로 변환"""
        if not models:
            return "검색된 모델이 없습니다."

        parts = []
        for i, model in enumerate(models, 1):
            tags_str = ", ".join(model.tags[:5]) if model.tags else "N/A"
            part = f"""[{i}] {model.id}
다운로드: {model.downloads:,}
좋아요: {model.likes}
태그: {tags_str}
링크: {model.url}"""
            parts.append(part)

        return "\n\n---\n\n".join(parts)

    async def close(self):
        await self.client.aclose()


# 싱글톤 인스턴스
_hf_client: Optional[HuggingFaceMCPClient] = None


def get_huggingface_client() -> HuggingFaceMCPClient:
    global _hf_client
    if _hf_client is None:
        _hf_client = HuggingFaceMCPClient()
    return _hf_client
