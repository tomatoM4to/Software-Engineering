"""
[Issue #4] AI 에이전트 의사결정 모듈 — Pydantic 스키마

사용 지표 (단순):
  MA5, MA20, MA60 / 거래량 비율 / 20일 고점 돌파 / 전일 대비 등락률
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

# Enums


class AgentPosition(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class AgentPersona(StrEnum):
    CONSERVATIVE = "CONSERVATIVE"  # 리스크 회피 중심
    AGGRESSIVE = "AGGRESSIVE"  # 타점 돌파 중심


class AgentConflictFlag(StrEnum):
    AGREEMENT = "AGREEMENT"  # 만장일치 (BUY·SELL)
    CONFLICT = "CONFLICT"  # 의견 상충 → HOLD 처리
    HOLD_CONSENSUS = "HOLD_CONSENSUS"  # 둘 다 HOLD


# 일봉 지표


class DailyIndicators(BaseModel):
    """
    ohlcv 테이블 OHLCV + Pandas rolling 으로 계산.
    """

    stock_code: str = Field(..., description="종목 코드 (short_code)")
    stock_name: str | None = Field(None, description="종목명 (stock_name_kr)")
    market: str | None = Field(None, description="KOSPI / KOSDAQ")
    trade_date: str = Field(..., description="기준 거래일 (YYYYMMDD)")

    # OHLCV
    open_price: int = Field(..., gt=0)
    high_price: int = Field(..., gt=0)
    low_price: int = Field(..., gt=0)
    close_price: int = Field(..., gt=0, description="종가 / 현재가")
    volume: int = Field(..., ge=0)
    turnover: int | None = Field(None, ge=0, description="거래대금 (원)")

    # 전일 비교
    prev_close: int | None = Field(None, description="전일 종가")
    change_rate: float | None = Field(None, description="전일 대비 등락률 (%)")

    # 이동평균 (Pandas rolling)
    ma5: float | None = Field(None)
    ma20: float | None = Field(None)
    ma60: float | None = Field(None)

    # 거래량 분석
    volume_ma20: float | None = Field(None, description="20일 평균 거래량")
    volume_ratio: float | None = Field(None, description="거래량 비율 (현재/20일 평균)")

    # 박스권 돌파
    high_20d: float | None = Field(None, description="직전 20일 최고가")
    is_breakout: bool | None = Field(None, description="직전 20일 고점 돌파 여부")

    # 추세 (MA 배열 기반)
    trend_direction: str | None = Field(None, description="UP | DOWN | SIDEWAYS")

    @field_validator("trend_direction")
    @classmethod
    def _check_trend(cls, v: str | None) -> str | None:
        if v is not None and v not in ("UP", "DOWN", "SIDEWAYS"):
            raise ValueError("trend_direction must be UP, DOWN, or SIDEWAYS")
        return v


# 분봉 지표


class MinuteIndicators(BaseModel):
    """
    분봉 기술 지표.
    """

    timeframe: str = Field(default="1m")
    data_source: str = Field(
        default="daily_proxy",
        description="realtime | daily_proxy",
    )

    latest_price: int = Field(..., gt=0)
    latest_volume: int = Field(..., ge=0)

    ma15: float | None = Field(None)
    ma30: float | None = Field(None)

    is_minute_breakout: bool | None = Field(None)
    minute_breakout_level: float | None = Field(None)
    volume_spike: bool | None = Field(
        None, description="거래량 급등 (20봉 평균 대비 1.5배 이상)"
    )

    @field_validator("timeframe")
    @classmethod
    def _check_tf(cls, v: str) -> str:
        allowed = ("1m", "3m", "5m", "15m", "30m", "daily_proxy")
        if v not in allowed:
            raise ValueError(f"timeframe must be one of {allowed}")
        return v


# 뉴스 스키마 (News None)


class AgentNewsItem(BaseModel):
    """Issue #5 schemas/news.py 의 NewsItem 과 별개로 관리하는 에이전트용 뉴스 아이템."""

    title: str = Field(..., max_length=300)
    summary: str | None = Field(None, max_length=500)
    published_at: datetime | None = Field(None)
    sentiment_score: float | None = Field(None, ge=-1.0, le=1.0)


class AgentNewsContext(BaseModel):
    """
    에이전트용 뉴스 컨텍스트.
    NewsDataAdapter 가 schemas/news.py → AgentNewsItem 으로 변환해 주입.
    현재는 항상 None (차트 단독 분석 폴백).
    """

    stock_code: str
    news_items: list[AgentNewsItem] = Field(default_factory=list, max_length=10)
    overall_sentiment: float | None = Field(None, ge=-1.0, le=1.0)


# 통합 컨텍스트 Request (LLM 프롬프트 주입용)


class AgentAnalysisRequest(BaseModel):
    """
    AI 에이전트 분석 요청.
    일봉 + 분봉 + 뉴스(Optional)를 하나의 컨텍스트로 묶어 LLM 프롬프트에 주입.
    """

    stock_code: str
    stock_name: str | None = None
    market: str | None = None

    daily_indicators: DailyIndicators
    minute_indicators: MinuteIndicators
    news_context: AgentNewsContext | None = Field(
        None,
        description="뉴스 컨텍스트 (Issue #5 구현 전: None → 차트 단독 분석)",
    )

    analysis_mode: str = Field(default="swing_short")
    requested_at: datetime = Field(default_factory=datetime.now)

    @field_validator("analysis_mode")
    @classmethod
    def _validate_mode(cls, v: str) -> str:
        if v not in ("swing_short", "day_trade"):
            raise ValueError("analysis_mode must be swing_short or day_trade")
        return v


# 자동 수집 Request (/api/agent/analyze/auto 전용)


class AgentAutoRequest(BaseModel):
    """
    stock_code 하나만 보내면 DB + KIS API 로 자동 조립.
    """

    stock_code: str = Field(..., description="종목 코드 (예: '005930')")
    stock_name: str | None = Field(None)
    analysis_mode: str = Field(default="swing_short")

    # 분봉 파라미터
    minute_timeframe: str = Field(
        default="1m",
        description="분봉 단위: 1m | 3m | 5m | 15m | 30m",
    )
    minute_limit: int = Field(
        default=60,
        ge=30,
        le=200,
        description="수집할 분봉 개수 (KIS 1회 30건 반환 → 자동 연속 호출)",
    )

    @field_validator("analysis_mode")
    @classmethod
    def _check_mode(cls, v: str) -> str:
        if v not in ("swing_short", "day_trade"):
            raise ValueError("analysis_mode must be swing_short or day_trade")
        return v

    @field_validator("minute_timeframe")
    @classmethod
    def _check_tf(cls, v: str) -> str:
        if v not in ("1m", "3m", "5m", "15m", "30m"):
            raise ValueError("minute_timeframe must be one of 1m, 3m, 5m, 15m, 30m")
        return v


# 에이전트 응답


class AgentReasoning(BaseModel):
    chart_basis: str = Field(..., description="차트 근거 (수치 직접 인용 필수)")
    news_basis: str | None = Field(None, description="뉴스 근거 (없으면 null)")
    key_signals: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)


class AgentResponse(BaseModel):
    """단일 AI 에이전트(보수적 or 공격적) 결정 결과."""

    persona: AgentPersona
    position: AgentPosition
    confidence: int = Field(..., ge=1, le=10, description="확신도 1~10")
    reasoning: AgentReasoning
    target_price: int | None = Field(None, gt=0, description="목표가 (원)")
    stop_loss: int | None = Field(None, gt=0, description="손절가 (원)")
    raw_llm_response: str | None = Field(None, description="LLM 원본 응답 (디버그용)")


# 최종 투자 시그널 Response


class AgentSignalResponse(BaseModel):
    """
    두 에이전트 결과를 취합한 최종 투자 시그널.
    클라이언트에 응답하는 JSON.
    """

    stock_code: str
    stock_name: str | None = None
    market: str | None = None

    analysis_mode: str
    trade_date: str = Field(..., description="분석 기준 거래일 (YYYYMMDD)")

    conservative_agent: AgentResponse
    aggressive_agent: AgentResponse

    final_position: AgentPosition
    final_confidence: float = Field(..., ge=1.0, le=10.0)
    conflict_flag: AgentConflictFlag

    warning_message: str | None = None
    aggregated_signals: list[str] = Field(default_factory=list)
    aggregated_risks: list[str] = Field(default_factory=list)

    # 데이터 출처 메타
    news_available: bool = Field(default=False)
    minute_data_source: str = Field(default="daily_proxy")

    analyzed_at: datetime = Field(default_factory=datetime.now)
    latency_ms: float | None = Field(None, ge=0)
