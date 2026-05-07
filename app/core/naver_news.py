import html
import os
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Literal

import requests
from schemas.news import NewsItem, NewsSearchResponse

NAVER_NEWS_SEARCH_URL = "https://openapi.naver.com/v1/search/news.json"
SortOption = Literal["sim", "date"]


class NaverNewsError(RuntimeError):
    pass


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", "", value)
    return html.unescape(text).strip()


def _parse_pub_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def _get_credentials() -> tuple[str, str]:
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise NaverNewsError(
            "NAVER_CLIENT_ID and NAVER_CLIENT_SECRET environment variables are required"
        )

    return client_id, client_secret


def _to_news_item(query: str, item: dict[str, Any]) -> NewsItem:
    return NewsItem(
        title=_clean_text(item.get("title")),
        originallink=item.get("originallink") or None,
        link=item.get("link") or "",
        description=_clean_text(item.get("description")),
        pub_date=_parse_pub_date(item.get("pubDate")),
        query=query,
    )


def search_news(
    query: str,
    display: int = 10,
    start: int = 1,
    sort: SortOption = "date",
) -> NewsSearchResponse:
    client_id, client_secret = _get_credentials()
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {
        "query": query,
        "display": display,
        "start": start,
        "sort": sort,
    }

    try:
        response = requests.get(
            NAVER_NEWS_SEARCH_URL,
            headers=headers,
            params=params,
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise NaverNewsError(f"Naver news request failed: {exc}") from exc

    data = response.json()
    items = [_to_news_item(query, item) for item in data.get("items", [])]

    return NewsSearchResponse(query=query, count=len(items), items=items)
