"""
[Issue #4] 데이터 오케스트레이터

- scanner.py 의 fetch_chart_data / get_prev_minute 패턴으로 분봉 수집
- services/breakout.py 의 prepare_ohlcv_df + calculate_breakout 으로 지표 계산
- schemas/core.py 의 BreakoutRequest 사용

"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
from schemas.agent import (
    AgentAnalysisRequest,
    AgentNewsContext,
    DailyIndicators,
    MinuteIndicators,
)

logger = logging.getLogger(__name__)


# 분봉 수집 헬퍼


def _get_prev_minute(date_str: str, time_str: str) -> tuple[str, str]:
    """
    KIS 1분봉 연속 조회를 위한 이전 시간 계산.
    """
    dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
    prev_dt = dt - timedelta(minutes=1)

    if prev_dt.hour < 9 or (prev_dt.hour == 8 and prev_dt.minute == 59):
        weekday = prev_dt.weekday()
        if weekday == 0:
            days_back = 3
        elif weekday == 6:
            days_back = 2
        else:
            days_back = 1
        prev_dt = prev_dt - timedelta(days=days_back)
        prev_dt = prev_dt.replace(hour=15, minute=30, second=0)

    return prev_dt.strftime("%Y%m%d"), prev_dt.strftime("%H%M%S")


async def _fetch_minute_batch(
    stock_code: str,
    end_time: str = "",
    market_div: str = "J",
) -> list[dict]:
    """
    KIS 1분봉 1회 조회 (최대 30건).
    """
    from core.kis_fetch import async_url_fetch

    api_url = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
    params = {
        "FID_COND_MRKT_DIV_CODE": market_div,
        "FID_INPUT_ISCD": stock_code,
        "FID_INPUT_HOUR_1": end_time,
        "FID_PW_DATA_INCU_YN": "Y",
        "FID_ETC_CLS_CODE": "",
    }
    res = await async_url_fetch(api_url, "FHKST03010200", "", params)
    if res.is_ok():
        return res.get_body().output2 or []
    return []


async def _fetch_kis_ohlcv_df(
    stock_code: str,
    limit: int = 60,
) -> pd.DataFrame:
    """
    KIS 1분봉을 연속 호출하여 limit 개 이상의 분봉 DataFrame 반환.
    """
    from services.breakout import prepare_ohlcv_df

    all_raw: list[dict] = []
    end_time = ""
    end_date = datetime.now().strftime("%Y%m%d")
    max_loops = max(1, (limit // 30) + 2)

    for _ in range(max_loops):
        if len(all_raw) >= limit:
            break

        batch = await _fetch_minute_batch(stock_code, end_time=end_time)
        if not batch:
            break

        all_raw.extend(batch)

        oldest = batch[-1]
        end_date, end_time = _get_prev_minute(
            str(oldest.get("stck_bsop_date", end_date)),
            str(oldest.get("stck_cntg_hour", "090000")).zfill(6),
        )

    if not all_raw:
        return pd.DataFrame()

    all_raw = all_raw[::-1]

    ohlcv = [
        {
            "date": f"{c['stck_bsop_date']}{str(c['stck_cntg_hour']).zfill(6)}",
            "open": c["stck_oprc"],
            "high": c["stck_hgpr"],
            "low": c["stck_lwpr"],
            "close": c["stck_prpr"],
            "volume": c["cntg_vol"],
        }
        for c in all_raw
    ]

    return prepare_ohlcv_df(ohlcv)


# 1일봉 어댑터


class DailyOhlcvAdapter:
    """DB ohlcv 테이블 → DailyIndicators 변환."""

    def get_stock_info(self, conn: sqlite3.Connection, stock_code: str) -> dict | None:
        row = conn.execute(
            "SELECT id, market, stock_name_kr FROM stock_list WHERE short_code = ?",
            (stock_code,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": int(row["id"]),
            "market": str(row["market"]),
            "stock_name_kr": str(row["stock_name_kr"]),
        }

    def load_ohlcv_df(
        self,
        conn: sqlite3.Connection,
        stock_id: int,
        limit: int = 300,
    ) -> pd.DataFrame | None:
        rows = conn.execute(
            """
            SELECT trade_date, open, high, low, close, volume, turnover
            FROM ohlcv
            WHERE stock_id = ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            (stock_id, limit),
        ).fetchall()

        if not rows:
            return None

        df = pd.DataFrame(
            [dict(r) for r in rows],
            columns=[
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "turnover",
            ],
        )
        return df.sort_values("trade_date").reset_index(drop=True)

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df["ma5"] = df["close"].rolling(5, min_periods=1).mean()
        df["ma20"] = df["close"].rolling(20, min_periods=1).mean()
        df["ma60"] = df["close"].rolling(60, min_periods=1).mean()

        df["volume_ma20"] = df["volume"].rolling(20, min_periods=1).mean()
        df["volume_ratio"] = df["volume"] / df["volume_ma20"].replace(0, float("nan"))

        df["prev_close"] = df["close"].shift(1)
        df["change_rate"] = (
            (df["close"] - df["prev_close"]) / df["prev_close"] * 100
        ).round(2)

        df["high_20d"] = df["high"].shift(1).rolling(20, min_periods=5).max()
        df["is_breakout"] = df["close"] > df["high_20d"]

        def _trend(row: pd.Series) -> str:
            try:
                if row["ma5"] > row["ma20"] and row["ma20"] > row["ma60"]:
                    return "UP"
                if row["ma5"] < row["ma20"] and row["ma20"] < row["ma60"]:
                    return "DOWN"
            except Exception:
                pass
            return "SIDEWAYS"

        df["trend_direction"] = df.apply(_trend, axis=1)
        return df

    def fetch_latest(
        self, conn: sqlite3.Connection, stock_code: str
    ) -> DailyIndicators | None:
        info = self.get_stock_info(conn, stock_code)
        if info is None:
            logger.warning("[DailyOhlcvAdapter] 종목 없음: %s", stock_code)
            return None

        df = self.load_ohlcv_df(conn, info["id"])
        if df is None or df.empty:
            logger.warning("[DailyOhlcvAdapter] OHLCV 없음: %s", stock_code)
            return None

        df = self.compute_indicators(df)
        r = df.iloc[-1]

        def _int(v: object) -> int | None:
            try:
                return int(v) if pd.notna(v) else None
            except Exception:
                return None

        def _flt(v: object) -> float | None:
            try:
                return round(float(v), 2) if pd.notna(v) else None
            except Exception:
                return None

        def _bool(v: object) -> bool | None:
            try:
                return bool(v) if pd.notna(v) else None
            except Exception:
                return None

        return DailyIndicators(
            stock_code=stock_code,
            stock_name=info["stock_name_kr"],
            market=info["market"],
            trade_date=str(r["trade_date"]),
            open_price=int(r["open"]),
            high_price=int(r["high"]),
            low_price=int(r["low"]),
            close_price=int(r["close"]),
            volume=int(r["volume"]),
            turnover=_int(r.get("turnover")),
            prev_close=_int(r["prev_close"]),
            change_rate=_flt(r["change_rate"]),
            ma5=_flt(r["ma5"]),
            ma20=_flt(r["ma20"]),
            ma60=_flt(r["ma60"]),
            volume_ma20=_flt(r["volume_ma20"]),
            volume_ratio=_flt(r["volume_ratio"]),
            high_20d=_flt(r["high_20d"]),
            is_breakout=_bool(r["is_breakout"]),
            trend_direction=str(r["trend_direction"]),
        )


# 분봉 어댑터


class MinuteDataAdapter:
    """
    KIS 1분봉 실시간 수집 → MinuteIndicators 변환.
    """

    @staticmethod
    async def fetch_realtime(
        stock_code: str,
        limit: int = 60,
    ) -> MinuteIndicators | None:
        try:
            df = await _fetch_kis_ohlcv_df(stock_code, limit=limit)

            if df.empty:
                logger.warning("[MinuteDataAdapter] %s 분봉 없음", stock_code)
                return None

            closes = df["Close"]
            ma15 = float(closes.rolling(15, min_periods=1).mean().iloc[-1])
            ma30 = float(closes.rolling(30, min_periods=1).mean().iloc[-1])

            latest_close = float(df["Close"].iloc[-1])
            latest_volume = int(df["Volume"].iloc[-1])

            high_20 = (
                float(df["High"].shift(1).rolling(20, min_periods=5).max().iloc[-1])
                if len(df) >= 5
                else None
            )
            is_breakout = (latest_close > high_20) if high_20 is not None else None

            vol_ma20 = float(df["Volume"].rolling(20, min_periods=1).mean().iloc[-1])
            volume_spike = (
                bool(latest_volume > vol_ma20 * 1.5) if vol_ma20 > 0 else None
            )

            logger.info(
                "[MinuteDataAdapter] %s 1m %d봉 | 돌파:%s | 급등:%s",
                stock_code,
                len(df),
                is_breakout,
                volume_spike,
            )

            return MinuteIndicators(
                timeframe="1m",
                data_source="realtime",
                latest_price=int(latest_close),
                latest_volume=latest_volume,
                ma15=round(ma15, 2),
                ma30=round(ma30, 2),
                is_minute_breakout=is_breakout,
                minute_breakout_level=round(high_20, 2)
                if high_20 is not None
                else None,
                volume_spike=volume_spike,
            )

        except Exception as exc:
            logger.warning("[MinuteDataAdapter] %s 실시간 실패: %s", stock_code, exc)
            return None

    @staticmethod
    def build_daily_proxy(daily: DailyIndicators) -> MinuteIndicators:
        return MinuteIndicators(
            timeframe="daily_proxy",
            data_source="daily_proxy",
            latest_price=daily.close_price,
            latest_volume=daily.volume,
            ma15=daily.ma20,
            ma30=daily.ma60,
            is_minute_breakout=daily.is_breakout,
            minute_breakout_level=daily.high_20d,
            volume_spike=(
                daily.volume_ratio >= 1.5 if daily.volume_ratio is not None else None
            ),
        )


# News Stub


class NewsDataAdapter:
    @staticmethod
    def fetch_latest_news(
        stock_code: str,
        stock_name: str | None = None,
    ) -> AgentNewsContext | None:
        logger.debug("[NewsDataAdapter] %s 뉴스 미구현 → 차트 단독 분석", stock_code)
        return None


# 통합 오케스트레이터


class AgentDataOrchestrator:
    def __init__(self) -> None:
        self._daily = DailyOhlcvAdapter()
        self._news = NewsDataAdapter()

    async def build_request(
        self,
        conn: sqlite3.Connection,
        stock_code: str,
        stock_name: str | None = None,
        analysis_mode: str = "swing_short",
        minute_limit: int = 60,
        override_daily: DailyIndicators | None = None,
        override_minute: MinuteIndicators | None = None,
        override_news: AgentNewsContext | None = None,
    ) -> AgentAnalysisRequest:
        """
        Raises:
            ValueError: 종목 없거나 OHLCV 없을 때
        """
        daily = override_daily or self._daily.fetch_latest(conn, stock_code)
        if daily is None:
            raise ValueError(
                f"종목 '{stock_code}' 의 일봉 데이터를 DB에서 찾을 수 없습니다. "
                "stock_code 가 올바른지, trading.db 에 해당 종목이 있는지 확인하세요."
            )

        resolved_name = stock_name or daily.stock_name

        if override_minute is not None:
            minute = override_minute
        else:
            minute = await MinuteDataAdapter.fetch_realtime(
                stock_code=stock_code,
                limit=minute_limit,
            )
            if minute is None:
                minute = MinuteDataAdapter.build_daily_proxy(daily)
                logger.info("[Orchestrator] %s 분봉 실패 → daily_proxy", stock_code)

        news = (
            override_news
            if override_news is not None
            else self._news.fetch_latest_news(
                stock_code=stock_code,
                stock_name=resolved_name,
            )
        )

        logger.info(
            "[Orchestrator] %s | 거래일:%s | 분봉:%s | 뉴스:%s",
            stock_code,
            daily.trade_date,
            minute.data_source,
            f"{len(news.news_items)}건" if news else "없음",
        )

        return AgentAnalysisRequest(
            stock_code=stock_code,
            stock_name=resolved_name,
            market=daily.market,
            daily_indicators=daily,
            minute_indicators=minute,
            news_context=news,
            analysis_mode=analysis_mode,
        )


agent_data_orchestrator = AgentDataOrchestrator()
