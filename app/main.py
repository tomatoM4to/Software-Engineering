import logging
from contextlib import asynccontextmanager

from api.agent import router as agent_router
from api.news import router as news_router
from api.ranking import router as ranking_router
from api.stock import router as stock_router
from api.strategy import router as strategy_router
from core.config import settings
from core.kis_fetch import start_kis_worker
from core.logging import setup_logging
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # KIS API 초당 제한 방어 워커 시작
    await start_kis_worker()

    enable_scheduler = settings.ENABLE_SCHEDULER
    scheduler = None

    if not enable_scheduler:
        logger.info("auth scheduler disabled")
    else:
        from tasks.auth_scheduler import AuthScheduler

        scheduler = AuthScheduler()
        scheduler.start()

    yield

    if scheduler:
        scheduler.stop()
        logger.info("Auth scheduler stopped during shutdown")


app = FastAPI(title="Trading Server", lifespan=lifespan)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 테스트용으로 모든 도메인 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(news_router)

app.include_router(ranking_router, prefix="/api")
app.include_router(strategy_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(stock_router, prefix="/api")


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}
