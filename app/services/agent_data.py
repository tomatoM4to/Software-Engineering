"""
AI 에이전트 데이터 오케스트레이터

scanner.py + breakout.py 패턴으로 분봉 수집 및 지표 계산.
"""

from __future__ import annotations

import logging

import pandas as pd
from schemas.agent import (
    AgentAnalysisRequest,
    AgentNewsContext,
    AgentNewsItem,
    DailyIndicators,
    MinuteIndicators,
)
from schemas.breakout import BreakoutRequest
from services.breakout import calculate_breakout
from services.naver_news import NaverNewsError, search_news
from services.scanner import fetch_ohlcv_df

logger = logging.getLogger(__name__)


# 뉴스 수집


class NewsDataAdapter:
    @staticmethod
    def fetch_latest_news(
        stock_code: str,
        stock_name: str | None = None,
        display: int = 5,
    ) -> AgentNewsContext | None:
        query = stock_name or stock_code
        try:
            result = search_news(query=query, display=display, sort="date")
        except NaverNewsError as exc:
            logger.warning("[NewsDataAdapter] %s 뉴스 수집 실패: %s", stock_code, exc)
            return None

        items = [
            AgentNewsItem(
                title=item.title,
                summary=item.description or None,
                published_at=item.pub_date,
                sentiment_score=None,
            )
            for item in result.items
        ]

        logger.debug("[NewsDataAdapter] %s 뉴스 %d건 수집", stock_code, len(items))
        return AgentNewsContext(
            stock_code=stock_code, news_items=items, overall_sentiment=None
        )


# 통합 오케스트레이터


class AgentDataOrchestrator:
    def __init__(self) -> None:
        self._news = NewsDataAdapter()

    async def build_request(
        self,
        stock_code: str,
        stock_name: str | None = None,
        market_div: str = "J",
        analysis_mode: str = "swing_short",
        minute_limit: int = 60,
        override_news: AgentNewsContext | None = None,
    ) -> AgentAnalysisRequest:
        """
        Raises:
            ValueError: 분봉 데이터를 가져올 수 없을 때
        """
        # 1. 분봉 fetch (scanner.fetch_ohlcv_df 재사용)
        df = await fetch_ohlcv_df(stock_code, market_div=market_div)
        if df.empty:
            raise ValueError(
                f"종목 '{stock_code}' 의 분봉 데이터를 가져올 수 없습니다. "
                "stock_code 가 올바른지, KIS 인증이 정상인지 확인하세요."
            )

        # 2. 돌파 지표 계산 (breakout 패턴)
        breakout_result = calculate_breakout(df, BreakoutRequest())

        # 3. 지표 계산
        latest = df.iloc[-1]
        latest_close = int(float(latest["Close"]))
        latest_volume = int(float(latest["Volume"]))

        def _flt(series: pd.Series, window: int) -> float:
            return round(
                float(series.rolling(window, min_periods=1).mean().iloc[-1]), 2
            )

        ma5 = _flt(df["Close"], 5)
        ma20 = _flt(df["Close"], 20)
        ma60 = _flt(df["Close"], 60)
        vol_ma20 = _flt(df["Volume"], 20)
        volume_ratio = round(latest_volume / vol_ma20, 2) if vol_ma20 > 0 else None

        prev_close_val = df["Close"].shift(1).iloc[-1]
        prev_close = (
            int(float(prev_close_val))
            if len(df) > 1 and pd.notna(prev_close_val)
            else None
        )
        change_rate = (
            round((latest_close - prev_close) / prev_close * 100, 2)
            if prev_close
            else None
        )

        high_20d_val = df["High"].shift(1).rolling(20, min_periods=5).max().iloc[-1]
        high_20d = round(float(high_20d_val), 2) if pd.notna(high_20d_val) else None
        is_breakout = (latest_close > high_20d) if high_20d is not None else None

        if ma5 > ma20 and ma20 > ma60:
            trend = "UP"
        elif ma5 < ma20 and ma20 < ma60:
            trend = "DOWN"
        else:
            trend = "SIDEWAYS"

        trade_date = df.index[-1].strftime("%Y%m%d")

        daily = DailyIndicators(
            stock_code=stock_code,
            stock_name=stock_name,
            market=None,
            trade_date=trade_date,
            open_price=int(float(latest["Open"])),
            high_price=int(float(latest["High"])),
            low_price=int(float(latest["Low"])),
            close_price=latest_close,
            volume=latest_volume,
            prev_close=prev_close,
            change_rate=change_rate,
            ma5=ma5,
            ma20=ma20,
            ma60=ma60,
            volume_ma20=vol_ma20,
            volume_ratio=volume_ratio,
            high_20d=high_20d,
            is_breakout=is_breakout,
            trend_direction=trend,
        )

        ma15 = _flt(df["Close"], 15)
        ma30 = _flt(df["Close"], 30)
        volume_spike = bool(latest_volume > vol_ma20 * 1.5) if vol_ma20 > 0 else None
        is_minute_breakout = breakout_result["breakout_category"] in (
            "BREAKOUT_STRONG",
            "BREAKOUT_NORMAL",
        )

        minute = MinuteIndicators(
            timeframe="1m",
            data_source="realtime",
            latest_price=latest_close,
            latest_volume=latest_volume,
            ma15=ma15,
            ma30=ma30,
            is_minute_breakout=is_minute_breakout,
            minute_breakout_level=high_20d,
            volume_spike=volume_spike,
        )

        # 4. 뉴스 수집
        news = (
            override_news
            if override_news is not None
            else self._news.fetch_latest_news(
                stock_code=stock_code,
                stock_name=stock_name,
            )
        )

        logger.info(
            "[Orchestrator] %s | 거래일:%s | 분봉:%s | 뉴스:%s",
            stock_code,
            trade_date,
            minute.data_source,
            f"{len(news.news_items)}건" if news else "없음",
        )

        return AgentAnalysisRequest(
            stock_code=stock_code,
            stock_name=stock_name,
            market=None,
            daily_indicators=daily,
            minute_indicators=minute,
            news_context=news,
            analysis_mode=analysis_mode,
        )


agent_data_orchestrator = AgentDataOrchestrator()
