"""
arXiv MCP Client

MCP 서버 스펙을 따르는 arXiv 검색 클라이언트
- search_papers: 논문 검색
- download_paper: 논문 다운로드
- list_papers: 저장된 논문 목록
- read_paper: 논문 내용 읽기
"""

import httpx
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel


class ArxivPaper(BaseModel):
    paper_id: str
    title: str
    authors: List[str]
    summary: str
    published: str
    updated: str
    categories: List[str]
    pdf_url: str
    arxiv_url: str


class ArxivMCPClient:
    """arXiv API를 MCP 스펙에 맞게 래핑한 클라이언트"""

    BASE_URL = "https://export.arxiv.org/api/query"

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def search_papers(
        self,
        query: str,
        categories: Optional[List[str]] = None,
        max_results: int = 10,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[ArxivPaper]:
        """
        논문 검색

        Args:
            query: 검색어
            categories: 카테고리 필터 (예: ["cs.AI", "cs.LG"])
            max_results: 최대 결과 수
            date_from: 시작 날짜 (YYYY-MM-DD)
            date_to: 종료 날짜 (YYYY-MM-DD)

        Returns:
            ArxivPaper 리스트
        """
        # 검색 쿼리 구성
        search_query = f"all:{query}"

        if categories:
            cat_query = " OR ".join([f"cat:{cat}" for cat in categories])
            search_query = f"({search_query}) AND ({cat_query})"

        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        try:
            response = await self.client.get(self.BASE_URL, params=params)
            response.raise_for_status()

            # XML 파싱
            papers = self._parse_arxiv_response(response.text)

            # 날짜 필터링
            if date_from or date_to:
                papers = self._filter_by_date(papers, date_from, date_to)

            return papers

        except Exception as e:
            print(f"arXiv API 오류: {e}")
            return []

    def _parse_arxiv_response(self, xml_text: str) -> List[ArxivPaper]:
        """arXiv API XML 응답 파싱"""
        import xml.etree.ElementTree as ET

        papers = []
        root = ET.fromstring(xml_text)

        # 네임스페이스 정의
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }

        for entry in root.findall("atom:entry", ns):
            try:
                # ID 추출 (http://arxiv.org/abs/2301.00001v1 → 2301.00001)
                id_text = entry.find("atom:id", ns).text
                paper_id = id_text.split("/abs/")[-1].split("v")[0]

                # 저자 추출
                authors = []
                for author in entry.findall("atom:author", ns):
                    name = author.find("atom:name", ns)
                    if name is not None:
                        authors.append(name.text)

                # 카테고리 추출
                categories = []
                for cat in entry.findall("atom:category", ns):
                    term = cat.get("term")
                    if term:
                        categories.append(term)

                # PDF URL
                pdf_url = ""
                for link in entry.findall("atom:link", ns):
                    if link.get("title") == "pdf":
                        pdf_url = link.get("href", "")
                        break

                paper = ArxivPaper(
                    paper_id=paper_id,
                    title=entry.find("atom:title", ns).text.strip().replace("\n", " "),
                    authors=authors,
                    summary=entry.find("atom:summary", ns).text.strip().replace("\n", " "),
                    published=entry.find("atom:published", ns).text,
                    updated=entry.find("atom:updated", ns).text,
                    categories=categories,
                    pdf_url=pdf_url or f"https://arxiv.org/pdf/{paper_id}.pdf",
                    arxiv_url=f"https://arxiv.org/abs/{paper_id}",
                )
                papers.append(paper)

            except Exception as e:
                print(f"논문 파싱 오류: {e}")
                continue

        return papers

    def _filter_by_date(
        self,
        papers: List[ArxivPaper],
        date_from: Optional[str],
        date_to: Optional[str],
    ) -> List[ArxivPaper]:
        """날짜 필터링"""
        filtered = []

        for paper in papers:
            pub_date = datetime.fromisoformat(paper.published.replace("Z", "+00:00"))

            if date_from:
                from_date = datetime.fromisoformat(date_from + "T00:00:00+00:00")
                if pub_date < from_date:
                    continue

            if date_to:
                to_date = datetime.fromisoformat(date_to + "T23:59:59+00:00")
                if pub_date > to_date:
                    continue

            filtered.append(paper)

        return filtered

    async def get_recent_papers(
        self,
        query: str,
        days: int = 7,
        max_results: int = 10,
    ) -> List[ArxivPaper]:
        """최근 N일 이내 논문 검색"""
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return await self.search_papers(
            query=query,
            max_results=max_results,
            date_from=date_from,
        )

    def format_papers_as_context(self, papers: List[ArxivPaper]) -> str:
        """논문 목록을 컨텍스트 문자열로 변환"""
        if not papers:
            return "검색된 논문이 없습니다."

        parts = []
        for i, paper in enumerate(papers, 1):
            authors_str = ", ".join(paper.authors[:3])
            if len(paper.authors) > 3:
                authors_str += f" 외 {len(paper.authors) - 3}명"

            part = f"""[{i}] {paper.title}
저자: {authors_str}
발행일: {paper.published[:10]}
카테고리: {', '.join(paper.categories[:3])}
요약: {paper.summary[:300]}...
링크: {paper.arxiv_url}"""
            parts.append(part)

        return "\n\n---\n\n".join(parts)

    async def close(self):
        await self.client.aclose()


# 싱글톤 인스턴스
_arxiv_client: Optional[ArxivMCPClient] = None


def get_arxiv_client() -> ArxivMCPClient:
    global _arxiv_client
    if _arxiv_client is None:
        _arxiv_client = ArxivMCPClient()
    return _arxiv_client
