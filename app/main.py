import logging
import os
from contextlib import asynccontextmanager

from api.news import router as news_router
from core.logging import setup_logging
from fastapi import FastAPI

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    disable_scheduler = os.getenv("DISABLE_SCHEDULER", "false").lower() == "true"
    auth_scheduler = None

    if disable_scheduler:
        logger.info("auth scheduler disabled")
    else:
        from tasks.auth_scheduler import auth_scheduler

        auth_scheduler.start()

    try:
        yield
    finally:
        if auth_scheduler is not None:
            auth_scheduler.stop()


app = FastAPI(title="Trading Server", lifespan=lifespan)
app.include_router(news_router)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}
