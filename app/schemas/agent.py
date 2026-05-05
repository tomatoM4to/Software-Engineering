"""
[Issue #4] AI 에이전트 의사결정 모듈 — Pydantic 스키마
 
실제 DB 구조 기반:
  - stock_list: id, market, short_code, standard_code, stock_name_kr, group_code
  - ohlcv: id, stock_id, trade_date(YYYYMMDD), open, high, low, close, volume, turnover
  - 기술지표 컬럼 없음 → 서비스 레이어에서 Pandas로 실시간 계산
  - News x → news_context Optional 처리
 
사용 지표 (단순):
  MA5, MA20, MA60 / 거래량 비율(현재/20일 평균) / 20일 고점 돌파 / 전일 대비 등락률
"""
 
from __future__ import annotations
 
from datetime import datetime
from enum import Enum
from typing import Optional
 
from pydantic import BaseModel, Field, field_validator
 
 
# ── Enums ─────────────────────────────────────────────────────────────────────
 
class AgentPosition(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
 
 
class AgentPersona(str, Enum):
    CONSERVATIVE = "CONSERVATIVE"   # 리스크 회피 중심
    AGGRESSIVE   = "AGGRESSIVE"     # 타점 돌파 중심
 
 
class AgentConflictFlag(str, Enum):
    AGREEMENT      = "AGREEMENT"       # 만장일치 (BUY·SELL)
    CONFLICT       = "CONFLICT"        # 의견 상충 → HOLD 처리
    HOLD_CONSENSUS = "HOLD_CONSENSUS"  # 둘 다 HOLD
 
 
# ── 일봉 지표 (DB ohlcv → Pandas 계산 결과) ───────────────────────────────────
 
class DailyIndicators(BaseModel):
    """
    실제 trading.db ohlcv 테이블에서 읽어온 OHLCV +
    Pandas rolling 으로 서비스 레이어에서 계산한 단순 기술 지표.
    """
    stock_code:  str            = Field(..., description="종목 코드 (short_code, 6자리)")
    stock_name:  Optional[str]  = Field(None, description="종목명 (stock_name_kr)")
    market:      Optional[str]  = Field(None, description="시장 구분 (KOSPI / KOSDAQ)")
    trade_date:  str            = Field(..., description="기준 거래일 (YYYYMMDD)")
 
    # OHLCV (ohlcv 테이블 직접)
    open_price:  int  = Field(..., gt=0)
    high_price:  int  = Field(..., gt=0)
    low_price:   int  = Field(..., gt=0)
    close_price: int  = Field(..., gt=0, description="종가 / 현재가")
    volume:      int  = Field(..., ge=0)
    turnover:    Optional[int] = Field(None, ge=0, description="거래대금 (원)")
 
    # 전일 데이터
    prev_close:  Optional[int]   = Field(None, description="전일 종가")
    change_rate: Optional[float] = Field(None, description="전일 대비 등락률 (%)")
 
    # 이동평균 (Pandas rolling)
    ma5:  Optional[float] = Field(None, description="5일 이동평균")
    ma20: Optional[float] = Field(None, description="20일 이동평균")
    ma60: Optional[float] = Field(None, description="60일 이동평균")
 
    # 거래량 분석
    volume_ma20:  Optional[float] = Field(None, description="20일 평균 거래량")
    volume_ratio: Optional[float] = Field(None, description="거래량 비율 (현재/20일 평균)")
 
    # 박스권 돌파
    high_20d:    Optional[float] = Field(None, description="직전 20일 최고가")
    is_breakout: Optional[bool]  = Field(None, description="직전 20일 고점 돌파 여부")
 
    # 추세 (MA 배열 기반)
    trend_direction: Optional[str] = Field(
        None, description="추세 방향: 'UP' | 'DOWN' | 'SIDEWAYS'"
    )
 
    @field_validator("trend_direction")
    @classmethod
    def _validate_trend(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("UP", "DOWN", "SIDEWAYS"):
            raise ValueError("trend_direction must be UP, DOWN, or SIDEWAYS")
        return v
 
 
# ── 분봉 지표 (Issue #3 미연동 → 일봉 daily_proxy) ────────────────────────────
 
class MinuteIndicators(BaseModel):
    """
    분봉 기술 지표.
    """
    timeframe:   str = Field(default="1m")
    data_source: str = Field(
        default="daily_proxy",
        description="realtime(Issue#3 연동) | daily_proxy(일봉 당일 근사)"
    )
 
    latest_price:  int = Field(..., gt=0)
    latest_volume: int = Field(..., ge=0)
 
    ma15: Optional[float] = Field(None)
    ma30: Optional[float] = Field(None)
 
    is_minute_breakout:    Optional[bool]  = Field(None)
    minute_breakout_level: Optional[float] = Field(None)
    volume_spike:          Optional[bool]  = Field(None, description="거래량 급등 (비율≥1.5)")
 
    @field_validator("timeframe")
    @classmethod
    def _validate_tf(cls, v: str) -> str:
        allowed = ("1m", "3m", "5m", "15m", "30m", "daily_proxy")
        if v not in allowed:
            raise ValueError(f"timeframe must be one of {allowed}")
        return v
 
 
# ── 뉴스 스키마 (Issue #5 미구현, Optional) ────────────────────────────────────
 
class NewsItem(BaseModel):
    title:           str            = Field(..., max_length=300)
    summary:         Optional[str]  = Field(None, max_length=500)
    source:          Optional[str]  = None
    published_at:    Optional[datetime] = None
    sentiment_score: Optional[float]   = Field(None, ge=-1.0, le=1.0)
    keywords:        Optional[list[str]] = Field(default_factory=list)
 
 
class NewsContext(BaseModel):
    """News 완료 후 실제 DB에서 주입. 현재는 항상 None."""
    stock_code:        str
    news_items:        list[NewsItem]    = Field(default_factory=list, max_length=10)
    overall_sentiment: Optional[float]  = Field(None, ge=-1.0, le=1.0)
    top_keywords:      Optional[list[str]] = Field(default_factory=list)
    crawled_at:        Optional[datetime] = None
 
 
# ── 통합 컨텍스트 Request (LLM 프롬프트 주입용) ────────────────────────────────
 
class AgentAnalysisRequest(BaseModel):
    """
    AI 에이전트 분석 요청 모델.
    일봉 지표 + 분봉 지표 + 뉴스(Optional)를 하나의 컨텍스트로 통합.
    /api/agent/analyze 에서 직접 주입 / /api/agent/analyze/auto 에서 자동 조립.
    """
    stock_code:  str           = Field(..., description="종목 코드 (short_code)")
    stock_name:  Optional[str] = None
    market:      Optional[str] = None
 
    daily_indicators:  DailyIndicators  = Field(..., description="일봉 기술 지표")
    minute_indicators: MinuteIndicators = Field(..., description="분봉 기술 지표")
    news_context:      Optional[NewsContext] = Field(
        None, description="뉴스 컨텍스트 (Issue #5 구현 전: None)"
    )
 
    analysis_mode: str = Field(
        default="swing_short",
        description="'swing_short' | 'day_trade'"
    )
    requested_at: datetime = Field(default_factory=datetime.now)
 
    @field_validator("analysis_mode")
    @classmethod
    def _validate_mode(cls, v: str) -> str:
        if v not in ("swing_short", "day_trade"):
            raise ValueError("analysis_mode must be swing_short or day_trade")
        return v
 
 
# ── 자동 수집 Request (/api/agent/analyze/auto 전용) ──────────────────────────
 
class AgentAutoRequest(BaseModel):
    """
    stock_code 하나만 보내면 DB + Pandas 로 자동 조립.
    Issue #1(KIS 인증) · #2(일봉 DB) · #3(분봉) · #5(뉴스)를 자동 연동.
    """
    stock_code:    str           = Field(..., description="종목 코드 (예: '005930')")
    stock_name:    Optional[str] = Field(None, description="종목명 (없으면 DB에서 자동 조회)")
    analysis_mode: str           = Field(default="swing_short")
    news_max_age_hours: int      = Field(default=24, ge=1, le=168)
 
    @field_validator("analysis_mode")
    @classmethod
    def _validate_mode(cls, v: str) -> str:
        if v not in ("swing_short", "day_trade"):
            raise ValueError("analysis_mode must be swing_short or day_trade")
        return v
 
 
# ── 에이전트 응답 모델 ─────────────────────────────────────────────────────────
 
class AgentReasoning(BaseModel):
    chart_basis:  str            = Field(..., description="차트 근거 (수치 직접 인용)")
    news_basis:   Optional[str]  = Field(None, description="뉴스 근거 (없으면 null)")
    key_signals:  list[str]      = Field(default_factory=list, description="핵심 시그널")
    risk_factors: list[str]      = Field(default_factory=list, description="리스크 요인")
 
 
class AgentResponse(BaseModel):
    """단일 AI 에이전트(보수적 or 공격적) 결정 결과."""
    persona:          AgentPersona
    position:         AgentPosition
    confidence:       int              = Field(..., ge=1, le=10, description="확신도 1~10")
    reasoning:        AgentReasoning
    target_price:     Optional[int]    = Field(None, gt=0, description="목표가 (원)")
    stop_loss:        Optional[int]    = Field(None, gt=0, description="손절가 (원)")
    raw_llm_response: Optional[str]   = Field(None, description="LLM 원본 응답 (디버그용)")
 
 
# ── 최종 투자 시그널 Response ─────────────────────────────────────────────────
 
class AgentSignalResponse(BaseModel):
    """
    두 에이전트 결과를 취합한 최종 투자 시그널.
    의견 일치(BUY/SELL) 또는 상충(HOLD + CONFLICT 플래그 + 경고)를 포함.
    """
    stock_code: str
    stock_name: Optional[str] = None
    market:     Optional[str] = None
 
    analysis_mode: str
    trade_date:    str = Field(..., description="분석 기준 거래일 (YYYYMMDD)")
 
    conservative_agent: AgentResponse
    aggressive_agent:   AgentResponse
 
    final_position:   AgentPosition
    final_confidence: float = Field(..., ge=1.0, le=10.0)
    conflict_flag:    AgentConflictFlag
 
    warning_message:    Optional[str]  = None
    aggregated_signals: list[str]      = Field(default_factory=list)
    aggregated_risks:   list[str]      = Field(default_factory=list)
 
    # 데이터 출처 메타
    news_available:     bool = Field(default=False, description="뉴스 사용 여부 (Issue #5 전: False)")
    minute_data_source: str  = Field(default="daily_proxy")
 
    analyzed_at: datetime = Field(default_factory=datetime.now)
    latency_ms:  Optional[float] = Field(None, ge=0, description="병렬 호출 소요 시간 (ms)")