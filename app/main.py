import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from tasks.auth_scheduler import auth_scheduler
from core.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    disable_scheduler = os.getenv("DISABLE_SCHEDULER", "false").lower() == "true"

    if disable_scheduler:
        logger.info("auth 비활성화")
    else:
        auth_scheduler.start()

    yield


app = FastAPI(title="Trading Server", lifespan=lifespan)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}
