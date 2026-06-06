import asyncio
import logging
import sys
from datetime import datetime
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.agent import router as agent_router
from api.news import router as news_router
from api.ranking import router as ranking_router
from api.stock import router as stock_router
from api.strategy import router as strategy_router
from core.config import settings
from core.kis_auth import auth, get_kis_env
from core.kis_fetch import start_kis_worker
from core.logging import setup_logging
from tasks.auth_scheduler import AuthScheduler
from tasks.cache_scheduler import CacheScheduler

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    애플리케이션 생명주기 관리 (Startup & Shutdown)
    """
    # 1. KIS 인증 초기화 (최우선)
    try:
        logger.info("Initializing KIS Authentication...")
        await asyncio.to_thread(auth)

        # 인증 실패 시 서버 기동 중단
        if get_kis_env() is None:
            logger.critical("KIS Authentication failed: Environment configuration is missing.")
            sys.exit(1)
        
        logger.info("KIS Authentication initialized successfully.")
    except Exception as e:
        logger.critical(f"Critical error during KIS Authentication: {e}")
        sys.exit(1)

    # 2. KIS API 워커 및 스케줄러 초기화
    await start_kis_worker()
    
    cache_scheduler = CacheScheduler()
    cache_scheduler.start()

    # 3. 초기 데이터 적재
    logger.info("Populating initial cache (Force)...")
    try:
        await cache_scheduler.update_rankings(force=True)
        await cache_scheduler.update_minute_bars(force=True)
        logger.info("Initial cache population completed successfully.")
    except Exception as e:
        logger.error(f"Initial cache population failed: {e}")

    # 4. 토큰 갱신용 인증 스케줄러
    scheduler = None
    if settings.ENABLE_SCHEDULER:
        scheduler = AuthScheduler()
        scheduler.start()
        logger.info("Auth scheduler started.")

    yield

    # Shutdown: 자원 해제
    if cache_scheduler:
        cache_scheduler.stop()
    if scheduler:
        scheduler.stop()
        logger.info("All schedulers stopped.")


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


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "app": "Trading Server"
    }


@app.get("/")
def read_root():
    return {"Hello": "World"}
