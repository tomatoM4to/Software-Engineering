"""
AI 에이전트 데이터 오케스트레이터

scanner.py + breakout.py 패턴으로 분봉 수집 및 지표 계산.
"""

from __future__ import annotations

import asyncio
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
        ai_persona: str = "swing_short",
        minute_limit: int = 60,
        anchor_ma: int = 20,
        target_mas: list[int] | None = None,
        convergence_threshold: float = 1.5,
        override_news: AgentNewsContext | None = None,
    ) -> AgentAnalysisRequest:
        """
        Raises:
            ValueError: 분봉 데이터를 가져올 수 없을 때
        """
        if target_mas is None:
            target_mas = [5, 10]

        # 1. 분봉 fetch (scanner.fetch_ohlcv_df 재사용)
        df = await fetch_ohlcv_df(stock_code, market_div=market_div)
        if df.empty:
            raise ValueError(
                f"종목 '{stock_code}' 의 분봉 데이터를 가져올 수 없습니다. "
                "stock_code 가 올바른지, KIS 인증이 정상인지 확인하세요."
            )

        # 2. 돌파 지표 및 기술적 지표 계산을 쓰레드로 오프로딩하여 이벤트 루프 차단 방지
        breakout_params = BreakoutRequest(
            anchor_ma=anchor_ma,
            target_mas=target_mas,
            convergence_threshold=convergence_threshold,
        )

        # 복잡한 Pandas 연산들을 하나의 동기 함수로 묶어 쓰레드에서 실행
        def _calculate_all_indicators(df_local: pd.DataFrame, br_params):
            br_result = calculate_breakout(df_local, br_params)

            latest = df_local.iloc[-1]
            latest_close = int(float(latest["Close"]))
            latest_volume = int(float(latest["Volume"]))

            def _flt_local(series: pd.Series, window: int) -> float:
                return round(
                    float(series.rolling(window, min_periods=1).mean().iloc[-1]), 2
                )

            ma5 = _flt_local(df_local["Close"], 5)
            ma20 = _flt_local(df_local["Close"], 20)
            ma60 = _flt_local(df_local["Close"], 60)
            vol_ma20 = _flt_local(df_local["Volume"], 20)
            volume_ratio = round(latest_volume / vol_ma20, 2) if vol_ma20 > 0 else None

            prev_close_val = df_local["Close"].shift(1).iloc[-1]
            prev_close = (
                int(float(prev_close_val))
                if len(df_local) > 1 and pd.notna(prev_close_val)
                else None
            )
            change_rate = (
                round((latest_close - prev_close) / prev_close * 100, 2)
                if prev_close
                else None
            )

            high_20d_val = (
                df_local["High"].shift(1).rolling(20, min_periods=5).max().iloc[-1]
            )
            high_20d = round(float(high_20d_val), 2) if pd.notna(high_20d_val) else None
            is_breakout_flag = (
                (latest_close > high_20d) if high_20d is not None else None
            )

            if ma5 > ma20 and ma20 > ma60:
                trend = "UP"
            elif ma5 < ma20 and ma20 < ma60:
                trend = "DOWN"
            else:
                trend = "SIDEWAYS"

            trade_date = df_local.index[-1].strftime("%Y%m%d")

            # 분봉 지표용 추가 계산
            ma_anchor_val = _flt_local(df_local["Close"], anchor_ma)
            ma_target_val = _flt_local(df_local["Close"], target_mas[0])
            volume_spike_flag = (
                bool(latest_volume > vol_ma20 * 1.5) if vol_ma20 > 0 else None
            )

            return {
                "breakout_result": br_result,
                "latest_close": latest_close,
                "latest_volume": latest_volume,
                "ma5": ma5,
                "ma20": ma20,
                "ma60": ma60,
                "vol_ma20": vol_ma20,
                "volume_ratio": volume_ratio,
                "prev_close": prev_close,
                "change_rate": change_rate,
                "high_20d": high_20d,
                "is_breakout": is_breakout_flag,
                "trend_direction": trend,
                "trade_date": trade_date,
                "ma_anchor_val": ma_anchor_val,
                "ma_target_val": ma_target_val,
                "volume_spike": volume_spike_flag,
                "latest_open": int(float(latest["Open"])),
                "latest_high": int(float(latest["High"])),
                "latest_low": int(float(latest["Low"])),
            }

        calc = await asyncio.to_thread(_calculate_all_indicators, df, breakout_params)

        daily = DailyIndicators(
            stock_code=stock_code,
            stock_name=stock_name,
            market=None,
            trade_date=calc["trade_date"],
            open_price=calc["latest_open"],
            high_price=calc["latest_high"],
            low_price=calc["latest_low"],
            close_price=calc["latest_close"],
            volume=calc["latest_volume"],
            prev_close=calc["prev_close"],
            change_rate=calc["change_rate"],
            ma5=calc["ma5"],
            ma20=calc["ma20"],
            ma60=calc["ma60"],
            volume_ma20=calc["vol_ma20"],
            volume_ratio=calc["volume_ratio"],
            high_20d=calc["high_20d"],
            is_breakout=calc["is_breakout"],
            trend_direction=calc["trend_direction"],
        )

        is_minute_breakout = calc["breakout_result"]["breakout_category"] in (
            "BREAKOUT_STRONG",
            "BREAKOUT_NORMAL",
        )

        minute = MinuteIndicators(
            timeframe="1m",
            data_source="realtime",
            latest_price=calc["latest_close"],
            latest_volume=calc["latest_volume"],
            ma15=calc["ma_target_val"],
            ma30=calc["ma_anchor_val"],
            is_minute_breakout=is_minute_breakout,
            minute_breakout_level=calc["high_20d"],
            volume_spike=calc["volume_spike"],
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
            "[Orchestrator] %s | 거래일:%s | 앵커:%d | 타겟:%s",
            stock_code,
            calc["trade_date"],
            anchor_ma,
            target_mas,
        )

        return AgentAnalysisRequest(
            stock_code=stock_code,
            stock_name=stock_name,
            market=None,
            daily_indicators=daily,
            minute_indicators=minute,
            news_context=news,
            anchor_ma=anchor_ma,
            target_mas=target_mas,
            ai_persona=ai_persona,
        )


agent_data_orchestrator = AgentDataOrchestrator()
