import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class KISCache:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(KISCache, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        # 데이터 저장소
        # rankings: { "J": [stock_list], "Q": [stock_list] }
        self._rankings: dict[str, list[dict]] = {"J": [], "Q": []}
        
        # minute_bars: { "005930": { "output2": [...], "timestamp": datetime } }
        self._minute_bars: dict[str, dict[str, Any]] = {}

        # 레지스트리: TR_ID별 캐시 핸들러 매핑
        self._registry = {
            "FHPST01710000": self._handle_volume_rank,
            "FHKST03010200": self._handle_minute_bars,
        }
        
        self._initialized = True
        logger.info("[KISCache] Initialized Singleton Instance.")

    async def get_from_cache(self, tr_id: str, params: dict) -> dict | None:
        """
        TR_ID와 파라미터를 기반으로 레지스트리에서 핸들러를 찾아 캐시 데이터를 반환합니다.
        """
        handler = self._registry.get(tr_id)
        if not handler:
            return None

        async with self._lock:
            result = await handler(params)
            if result:
                # API 응답 표준 포맷 구성
                response_data = {
                    "rt_cd": "0", 
                    "msg_cd": "CACHE", 
                    "msg1": "Success"
                }
                response_data.update(result)
                return response_data
        
        return None

    async def _handle_volume_rank(self, params: dict) -> dict | None:
        """거래량 순위 캐시 핸들러"""
        input_iscd = params.get("FID_INPUT_ISCD", "")
        market = "J" if input_iscd == "0001" else "Q"
        data = self._rankings.get(market, [])
        if data:
            return {"output": data}
        return None

    async def _handle_minute_bars(self, params: dict) -> dict | None:
        """분봉 데이터 캐시 핸들러"""
        stock_code = params.get("FID_INPUT_ISCD", "")
        end_time = params.get("FID_INPUT_HOUR_1", "")
        # 스케줄러는 end_time이 비어있는(최신) 데이터만 캐싱함
        if not end_time:
            data = self._minute_bars.get(stock_code, [])
            if data:
                return {"output2": data}
        return None

    async def update_ranking(self, market: str, data: list[dict]):
        async with self._lock:
            self._rankings[market] = data
            logger.debug(f"[KISCache] Updated ranking for {market} (count: {len(data)})")

    async def get_ranking(self, market: str) -> list[dict]:
        async with self._lock:
            return self._rankings.get(market, [])

    async def update_minute_bars(self, stock_code: str, data: list[dict]):
        async with self._lock:
            # KIS API의 응답 구조(output2)를 그대로 유지하여 호환성 확보
            self._minute_bars[stock_code] = data
            logger.debug(f"[KISCache] Updated minute bars for {stock_code}")

    async def get_minute_bars(self, stock_code: str) -> list[dict]:
        async with self._lock:
            return self._minute_bars.get(stock_code, [])

    def clear(self):
        self._rankings = {"J": [], "Q": []}
        self._minute_bars = {}
        logger.info("[KISCache] Cache cleared.")

# 전역 인스턴스
kis_cache = KISCache()
