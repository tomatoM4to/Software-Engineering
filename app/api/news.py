from typing import Literal

from core.naver_news import NaverNewsError, search_news
from fastapi import APIRouter, HTTPException, Query
from schemas.news import NewsSearchResponse

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/search", response_model=NewsSearchResponse)
def search_news_endpoint(
    query: str = Query(..., min_length=1),
    display: int = Query(10, ge=1, le=100),
    start: int = Query(1, ge=1, le=1000),
    sort: Literal["sim", "date"] = "date",
) -> NewsSearchResponse:
    try:
        return search_news(query=query, display=display, start=start, sort=sort)
    except NaverNewsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
