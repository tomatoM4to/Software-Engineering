"""
[Issue #4] AgentService — 핵심 비즈니스 로직

두 AI 페르소나를 asyncio.gather 로 비동기 병렬 호출하여
Latency 를 최소화하고, 의견 일치/상충 로직으로 최종 시그널 반환.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from core.agent_prompts import (
    AGGRESSIVE_SYSTEM_PROMPT,
    CONSERVATIVE_SYSTEM_PROMPT,
    build_user_prompt,
)
from schemas.agent import (
    AgentAnalysisRequest,
    AgentConflictFlag,
    AgentPersona,
    AgentPosition,
    AgentReasoning,
    AgentResponse,
    AgentSignalResponse,
)
from services.agent_llm import call_llm_async

logger = logging.getLogger(__name__)


# LLM JSON → AgentResponse


def _build_agent_response(
    data: dict[str, Any],
    raw_text: str,
    persona: AgentPersona,
    include_raw: bool = False,
) -> AgentResponse:
    reasoning = AgentReasoning(
        chart_basis=data.get("chart_basis", "차트 근거 없음"),
        news_basis=data.get("news_basis"),
        key_signals=data.get("key_signals", []),
        risk_factors=data.get("risk_factors", []),
    )
    return AgentResponse(
        persona=persona,
        position=AgentPosition(data["position"]),
        confidence=data["confidence"],
        reasoning=reasoning,
        target_price=data.get("target_price"),
        stop_loss=data.get("stop_loss"),
        raw_llm_response=raw_text if include_raw else None,
    )


# 신호 취합 로직


def _aggregate_signals(
    conservative: AgentResponse,
    aggressive: AgentResponse,
) -> tuple[AgentPosition, float, AgentConflictFlag, str | None]:
    """
    두 에이전트 포지션 취합.

    BUY+BUY     → BUY  + AGREEMENT  + 평균 확신도
    SELL+SELL   → SELL + AGREEMENT  + 평균 확신도
    HOLD+HOLD   → HOLD + HOLD_CONSENSUS
    그 외        → HOLD + CONFLICT + 경고 + 확신도 -2 페널티
    """
    c_pos, c_conf = conservative.position, conservative.confidence
    a_pos, a_conf = aggressive.position, aggressive.confidence
    avg = (c_conf + a_conf) / 2.0

    if c_pos == AgentPosition.BUY and a_pos == AgentPosition.BUY:
        return AgentPosition.BUY, avg, AgentConflictFlag.AGREEMENT, None

    if c_pos == AgentPosition.SELL and a_pos == AgentPosition.SELL:
        return AgentPosition.SELL, avg, AgentConflictFlag.AGREEMENT, None

    if c_pos == AgentPosition.HOLD and a_pos == AgentPosition.HOLD:
        return AgentPosition.HOLD, avg, AgentConflictFlag.HOLD_CONSENSUS, None

    penalized = max(1.0, avg - 2.0)
    warning = (
        f"⚠️ 두 AI 에이전트의 의견이 상충합니다. "
        f"보수적 AI: {c_pos.value}(확신도 {c_conf}/10), "
        f"공격적 AI: {a_pos.value}(확신도 {a_conf}/10). "
        f"명확한 시그널이 형성될 때까지 관망을 권장합니다."
    )
    logger.warning(
        "[AgentService] 의견 상충 — Conservative:%s(%d) vs Aggressive:%s(%d)",
        c_pos.value,
        c_conf,
        a_pos.value,
        a_conf,
    )
    return AgentPosition.HOLD, penalized, AgentConflictFlag.CONFLICT, warning


# AgentService


class AgentService:
    """다중 페르소나 AI 에이전트 서비스. ANTHROPIC_API_KEY 환경변수 필요."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-5",
        max_tokens: int = 1024,
        include_raw: bool = False,
    ) -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._model = model
        self._max_tokens = max_tokens
        self._include_raw = include_raw

        if not self._api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다. "
                ".env 또는 docker-compose.yml 에 ANTHROPIC_API_KEY=sk-ant-... 를 추가하세요."
            )

    async def _call_conservative(self, prompt: str) -> tuple[AgentResponse, float]:
        data, raw, ms = await call_llm_async(
            system_prompt=CONSERVATIVE_SYSTEM_PROMPT,
            user_prompt=prompt,
            api_key=self._api_key,
            model=self._model,
            max_tokens=self._max_tokens,
            persona_label="conservative",
        )
        return _build_agent_response(
            data, raw, AgentPersona.CONSERVATIVE, self._include_raw
        ), ms

    async def _call_aggressive(self, prompt: str) -> tuple[AgentResponse, float]:
        data, raw, ms = await call_llm_async(
            system_prompt=AGGRESSIVE_SYSTEM_PROMPT,
            user_prompt=prompt,
            api_key=self._api_key,
            model=self._model,
            max_tokens=self._max_tokens,
            persona_label="aggressive",
        )
        return _build_agent_response(
            data, raw, AgentPersona.AGGRESSIVE, self._include_raw
        ), ms

    async def analyze(self, request: AgentAnalysisRequest) -> AgentSignalResponse:
        """asyncio.gather 로 두 에이전트 병렬 호출 → 신호 취합."""
        t0 = time.perf_counter()
        prompt = build_user_prompt(request)

        logger.info(
            "[AgentService] 분석 시작 — 종목:%s 모드:%s",
            request.stock_code,
            request.analysis_mode,
        )

        (con_resp, con_ms), (agg_resp, agg_ms) = await asyncio.gather(
            self._call_conservative(prompt),
            self._call_aggressive(prompt),
        )

        wall_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "[AgentService] 병렬 완료 — 보수:%.1fms / 공격:%.1fms / 총:%.1fms",
            con_ms,
            agg_ms,
            wall_ms,
        )

        final_pos, final_conf, flag, warning = _aggregate_signals(con_resp, agg_resp)

        all_signals = list(
            dict.fromkeys(
                con_resp.reasoning.key_signals + agg_resp.reasoning.key_signals
            )
        )
        all_risks = list(
            dict.fromkeys(
                con_resp.reasoning.risk_factors + agg_resp.reasoning.risk_factors
            )
        )

        return AgentSignalResponse(
            stock_code=request.stock_code,
            stock_name=request.stock_name,
            market=request.market,
            analysis_mode=request.analysis_mode,
            trade_date=request.daily_indicators.trade_date,
            conservative_agent=con_resp,
            aggressive_agent=agg_resp,
            final_position=final_pos,
            final_confidence=round(final_conf, 1),
            conflict_flag=flag,
            warning_message=warning,
            aggregated_signals=all_signals,
            aggregated_risks=all_risks,
            news_available=request.news_context is not None,
            minute_data_source=request.minute_indicators.data_source,
            latency_ms=round(wall_ms, 1),
        )

    async def safe_analyze(self, request: AgentAnalysisRequest) -> AgentSignalResponse:
        """오류 시 HOLD 폴백."""
        try:
            return await self.analyze(request)
        except Exception as exc:
            logger.exception("[AgentService] 분석 중 예외: %s", exc)
            return self._error_response(request, exc)

    @staticmethod
    def _error_response(
        request: AgentAnalysisRequest, error: Exception
    ) -> AgentSignalResponse:
        err_reasoning = AgentReasoning(
            chart_basis="LLM 호출 실패로 분석 불가",
            key_signals=["시스템 오류"],
            risk_factors=[f"에이전트 오류: {type(error).__name__}"],
        )
        err_agent = AgentResponse(
            persona=AgentPersona.CONSERVATIVE,
            position=AgentPosition.HOLD,
            confidence=1,
            reasoning=err_reasoning,
        )
        return AgentSignalResponse(
            stock_code=request.stock_code,
            stock_name=request.stock_name,
            market=request.market,
            analysis_mode=request.analysis_mode,
            trade_date=request.daily_indicators.trade_date,
            conservative_agent=err_agent,
            aggressive_agent=err_agent.model_copy(
                update={"persona": AgentPersona.AGGRESSIVE}
            ),
            final_position=AgentPosition.HOLD,
            final_confidence=1.0,
            conflict_flag=AgentConflictFlag.HOLD_CONSENSUS,
            warning_message=f"⚠️ AI 에이전트 오류: {error}",
            aggregated_signals=[],
            aggregated_risks=["에이전트 서비스 오류"],
            news_available=False,
            minute_data_source=request.minute_indicators.data_source,
        )


# 싱글톤

_agent_service_instance: AgentService | None = None


def get_agent_service() -> AgentService:
    global _agent_service_instance
    if _agent_service_instance is None:
        _agent_service_instance = AgentService(
            include_raw=os.environ.get("AGENT_INCLUDE_RAW", "false").lower() == "true",
        )
    return _agent_service_instance
