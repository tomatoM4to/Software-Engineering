"""
[Issue #4] AI 에이전트 의사결정 라우터

기존 라우터(routes/breakout.py, routes/strategy.py) 패턴을 그대로 따름:
  - prefix="/api" 는 main.py 의 include_router 에서 붙임
  - sqlite3 직접 연결 (kis_auth.py 참고)

엔드포인트:
  POST /api/agent/analyze/auto — stock_code를 통해 자동 수집 + AI 분석
  POST /api/agent/analyze      — 데이터 직접 주입 + AI 분석 (테스트용)
  GET  /api/agent/health       — 서비스 상태 확인
"""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.schemas.agent import (
    AgentAnalysisRequest,
    AgentAutoRequest,
    AgentSignalResponse,
)
from app.services.agent_data import agent_data_orchestrator
from app.services.agent_service import AgentService, get_agent_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["AI Agent"])


# DB 연결


def _get_db_path() -> Path:
    configured = os.getenv("SQLITE_DB_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "trading.db"


def get_db():
    """FastAPI Depends 용 SQLite 연결 제너레이터."""
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
    finally:
        conn.close()


# 서비스 의존성


def _get_service() -> AgentService:
    try:
        return get_agent_service()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "AI 에이전트 서비스를 사용할 수 없습니다.",
                "message": str(exc),
                "hint": "docker-compose.yml 또는 .env 에 ANTHROPIC_API_KEY=sk-ant-... 를 추가하세요.",
            },
        ) from exc


# POST /api/agent/analyze/auto


@router.post(
    "/analyze/auto",
    response_model=AgentSignalResponse,
    summary="[통합] 종목 코드만으로 AI 에이전트 자동 분석",
    description=(
        "stock_code 하나만 입력하면 DB에서 일봉 데이터를 자동 조회·계산하고 "
        "보수적 AI + 공격적 AI를 비동기 병렬 호출하여 최종 투자 시그널을 반환합니다.\n\n"
        "**파이프라인**\n"
        "1. `stock_list` 에서 종목 메타 조회 (Issue #2)\n"
        "2. `ohlcv` 300일치 → Pandas MA/거래량비율/돌파 계산 (Issue #2)\n"
        "3. 분봉 실시간 수집 (Issue #3) 또는 daily_proxy 폴백\n"
        "4. 뉴스 없음 — 차트 단독 분석 (Issue #5 구현 후 자동 연동)\n"
        "5. 보수적 + 공격적 AI 병렬 호출 → 의견 취합 → 시그널 반환"
    ),
    responses={
        200: {"description": "분석 성공"},
        400: {"description": "종목 없음 또는 DB 데이터 없음"},
        503: {"description": "ANTHROPIC_API_KEY 미설정"},
    },
)
async def analyze_auto(
    request: AgentAutoRequest,
    conn: sqlite3.Connection = Depends(get_db),
    service: AgentService = Depends(_get_service),
) -> AgentSignalResponse:
    logger.info("[/agent/analyze/auto] 요청 — 종목:%s", request.stock_code)

    try:
        agent_request = await agent_data_orchestrator.build_request(
            conn=conn,
            stock_code=request.stock_code,
            stock_name=request.stock_name,
            analysis_mode=request.analysis_mode,
            minute_timeframe=request.minute_timeframe,
            minute_limit=request.minute_limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "데이터 수집 실패",
                "message": str(exc),
                "hint": (
                    "stock_code 가 올바른지, "
                    "trading.db 에 해당 종목의 ohlcv 데이터가 있는지 확인하세요."
                ),
            },
        ) from exc

    result = await service.safe_analyze(agent_request)

    logger.info(
        "[/agent/analyze/auto] 완료 — 종목:%s 포지션:%s 확신도:%.1f 플래그:%s",
        result.stock_code,
        result.final_position.value,
        result.final_confidence,
        result.conflict_flag.value,
    )
    return result


# POST /api/agent/analyze


@router.post(
    "/analyze",
    response_model=AgentSignalResponse,
    summary="AI 에이전트 분석 (데이터 직접 주입)",
    description=(
        "일봉 지표 + 분봉 지표 + 뉴스를 직접 전달하여 AI 분석을 수행합니다.\n"
        "테스트 또는 외부 파이프라인 연동 시 사용하세요.\n"
        "일반 사용은 `/api/agent/analyze/auto` 를 권장합니다."
    ),
)
async def analyze_direct(
    request: AgentAnalysisRequest,
    service: AgentService = Depends(_get_service),
) -> AgentSignalResponse:
    logger.info("[/agent/analyze] 직접 주입 — 종목:%s", request.stock_code)
    result = await service.safe_analyze(request)
    logger.info(
        "[/agent/analyze] 완료 — 종목:%s 포지션:%s",
        result.stock_code,
        result.final_position.value,
    )
    return result


# GET /api/agent/health


@router.get(
    "/health",
    summary="AI 에이전트 서비스 상태 확인",
)
async def agent_health(
    conn: sqlite3.Connection = Depends(get_db),
) -> JSONResponse:
    api_key_set = bool(os.environ.get("ANTHROPIC_API_KEY", ""))

    tables: list[str] = []
    ohlcv_count = 0
    stock_count = 0
    try:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        if "ohlcv" in tables:
            ohlcv_count = conn.execute("SELECT COUNT(*) FROM ohlcv").fetchone()[0]
        if "stock_list" in tables:
            stock_count = conn.execute("SELECT COUNT(*) FROM stock_list").fetchone()[0]
    except Exception:
        pass

    return JSONResponse(
        content={
            "status": "ok" if api_key_set else "degraded",
            "service": "AI Agent Decision Module (Issue #4)",
            "api_key_configured": api_key_set,
            "personas": ["CONSERVATIVE (리스크 회피)", "AGGRESSIVE (타점 돌파)"],
            "issue_integration": {
                "#2_daily_ohlcv_db": (
                    f"ok — stock:{stock_count}개 / ohlcv:{ohlcv_count}행"
                    if "ohlcv" in tables
                    else "db_missing"
                ),
                "#3_minute_engine": "KIS 1분봉 직접 수집 (실패 시 daily_proxy)",
                "#5_news": "pending (구현 후 자동 연동)",
            },
            "endpoints": {
                "auto": "POST /api/agent/analyze/auto",
                "manual": "POST /api/agent/analyze",
                "health": "GET  /api/agent/health",
                "docs": "/api/docs#/AI%20Agent",
            },
            "timestamp": datetime.now().isoformat(),
        }
    )
