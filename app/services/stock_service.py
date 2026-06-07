import logging
from datetime import datetime

from services.scanner import fetch_ohlcv_df

logger = logging.getLogger(__name__)


async def get_stock_chart(iscd: str, market_div: str = "J", count: int = 120):
    """
    주식 분봉 데이터를 가져와 차트 형식(Lightweight Charts 등)으로 변환하여 반환합니다.
    이미 최적화된 fetch_ohlcv_df를 사용하여 캐시 혜택을 자동으로 받습니다.
    """
    try:
        # fetch_ohlcv_df는 캐시가 있으면 240분, 없으면 실시간으로 데이터를 가져옴
        df = await fetch_ohlcv_df(iscd, market_div=market_div)

        if df.empty:
            return []

        formatted_data = []
        # DataFrame 레코드를 차트 형식으로 변환
        for dt, row in df.iterrows():
            timestamp = int(dt.timestamp())

            formatted_data.append(
                {
                    "time": timestamp,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                }
            )

        # 최신 count개만 반환 (이미 시간 정순으로 정렬되어 있음)
        return formatted_data[-count:]

    except Exception as e:
        logger.error(f"Failed to get stock chart for {iscd}: {e}")
        return []
