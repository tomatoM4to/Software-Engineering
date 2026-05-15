"""
AI 에이전트 의사결정 라우터

엔드포인트:
  POST /api/agent/analyze/auto — stock_code를 통해 자동 수집 + AI 분석
  POST /api/agent/analyze      — 데이터 직접 주입 + AI 분석 (테스트용)
  GET  /api/agent/health       — 서비스 상태 확인
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from schemas.agent import (
    AgentAnalysisRequest,
    AgentAutoRequest,
    AgentSignalResponse,
)
from services.agent_data import agent_data_orchestrator
from services.agent_service import AgentService, get_agent_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["AI Agent"])


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
        "stock_code 하나만 입력하면 KIS API로 분봉 데이터를 수집하고 "
        "보수적 AI + 공격적 AI를 비동기 병렬 호출하여 최종 투자 시그널을 반환합니다.\n\n"
        "**파이프라인**\n"
        "1. KIS 1분봉 2회 조회 (약 240분)\n"
        "2. breakout.py 로 돌파/수렴 지표 계산\n"
        "3. 네이버 뉴스 수집\n"
        "4. 보수적 + 공격적 AI 병렬 호출 → 의견 취합 → 시그널 반환"
    ),
    responses={
        200: {"description": "분석 성공"},
        400: {"description": "데이터 수집 실패"},
        503: {"description": "ANTHROPIC_API_KEY 미설정"},
    },
)
async def analyze_auto(
    request: AgentAutoRequest,
    service: AgentService = Depends(_get_service),
) -> AgentSignalResponse:
    logger.info("[/agent/analyze/auto] 요청 — 종목:%s", request.stock_code)

    try:
        agent_request = await agent_data_orchestrator.build_request(
            stock_code=request.stock_code,
            stock_name=request.stock_name,
            market_div=request.market,
            ai_persona=request.ai_persona,
            minute_limit=request.minute_limit,
            anchor_ma=request.anchor_ma,
            target_mas=request.target_mas,
            convergence_threshold=request.convergence_threshold,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "데이터 수집 실패",
                "message": str(exc),
                "hint": "stock_code 가 올바른지, KIS 인증이 정상인지 확인하세요.",
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
async def agent_health() -> JSONResponse:
    api_key_set = bool(os.environ.get("ANTHROPIC_API_KEY", ""))

    return JSONResponse(
        content={
            "status": "ok" if api_key_set else "degraded",
            "service": "AI Agent Decision Module",
            "api_key_configured": api_key_set,
            "personas": ["CONSERVATIVE (리스크 회피)", "AGGRESSIVE (타점 돌파)"],
            "data_pipeline": {
                "minute_engine": "KIS 1분봉 직접 수집 (scanner 패턴)",
                "news": "네이버 뉴스 API",
            },
            "endpoints": {
                "auto": "POST /api/agent/analyze/auto",
                "manual": "POST /api/agent/analyze",
                "health": "GET  /api/agent/health",
            },
            "timestamp": datetime.now().isoformat(),
        }
    )
