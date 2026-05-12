from datetime import datetime

from pydantic import BaseModel


class NewsItem(BaseModel):
    title: str
    originallink: str | None = None
    link: str
    description: str
    pub_date: datetime | None = None
    query: str


class NewsSearchResponse(BaseModel):
    query: str
    count: int
    items: list[NewsItem]
