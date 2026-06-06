import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from core.kis_cache import kis_cache
from services.ranking_list import get_volume_rank
from services.scanner import fetch_chart_data, get_prev_minute

logger = logging.getLogger(__name__)


class CacheScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._is_updating = False  # 중복 실행 방지 플래그

    def _is_market_open(self) -> bool:
        """현재 시간이 한국 시장 운영 시간(평일 08:30~16:00)인지 확인"""
        now = datetime.now()
        # 0:월, 1:화, ..., 4:금, 5:토, 6:일
        if now.weekday() >= 5:
            return False

        current_time = now.hour * 100 + now.minute
        # 08:30 ~ 16:00
        return 830 <= current_time <= 1600

    def start(self):
        # 1. 랭킹 갱신: 5분마다 실행
        self.scheduler.add_job(
            self.update_rankings,
            CronTrigger(minute="*/5"),
            id="update_rankings",
            name="Update Volume Rankings (J/Q)",
            replace_existing=True,
        )

        # 2. 분봉 데이터 갱신: 1분마다 실행
        self.scheduler.add_job(
            self.update_minute_bars,
            CronTrigger(minute="*"),
            id="update_minute_bars",
            name="Update Minute Bars for Top Stocks",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("[CacheScheduler] Started successfully.")

    def stop(self):
        self.scheduler.shutdown()
        logger.info("[CacheScheduler] Stopped.")

    async def update_rankings(self, force: bool = False):
        """KOSPI, KOSDAQ 상위 30개 종목 리스트 갱신"""
        if not force and not self._is_market_open():
            logger.debug("[CacheScheduler] Market is closed. Skipping rankings update.")
            return

        logger.info("[CacheScheduler] Updating rankings...")
        for market in ["J", "Q"]:
            try:
                # 스케줄러 요청은 낮은 우선순위(10) 부여
                res = await get_volume_rank(
                    market_div=market, bypass_cache=True, priority=10
                )
                if res.is_ok():
                    stocks = res.get_body().output[:30]
                    await kis_cache.update_ranking(market, stocks)
                else:
                    logger.warning(
                        f"[CacheScheduler] Failed to update {market} ranking: {res.get_error_message()}"
                    )
            except Exception as e:
                logger.error(f"[CacheScheduler] Error updating {market} ranking: {e}")

    async def update_minute_bars(self, force: bool = False):
        """캐시된 상위 종목들의 1분봉 데이터(2회 fetch) 갱신"""
        if not force and not self._is_market_open():
            logger.debug(
                "[CacheScheduler] Market is closed. Skipping minute bars update."
            )
            return

        if self._is_updating:
            logger.warning(
                "[CacheScheduler] Previous update still in progress. Skipping..."
            )
            return

        self._is_updating = True
        try:
            logger.info("[CacheScheduler] Updating minute bars...")

            # J, Q 통합 상위 종목 추출
            stocks_j = await kis_cache.get_ranking("J")
            stocks_q = await kis_cache.get_ranking("Q")

            all_stocks = []
            for s in stocks_j:
                all_stocks.append((s["mksc_shrn_iscd"], "J"))
            for s in stocks_q:
                all_stocks.append((s["mksc_shrn_iscd"], "Q"))

            if not all_stocks:
                logger.info(
                    "[CacheScheduler] No stocks in ranking yet. Skipping minute bars update."
                )
                return

            # 병렬로 데이터 수집하되, API 큐에 과부하를 주지 않기 위해 10개씩 배치 처리
            batch_size = 10
            for i in range(0, len(all_stocks), batch_size):
                batch = all_stocks[i : i + batch_size]
                tasks = [
                    self._fetch_and_cache_minute_bars(code, market)
                    for code, market in batch
                ]
                await asyncio.gather(*tasks)
                # 배치 사이 약간의 휴식 (선택 사항, 큐 워커가 초당 20건 처리하므로 10개씩은 안전함)

            logger.info(
                f"[CacheScheduler] Completed minute bars update for {len(all_stocks)} stocks."
            )
        finally:
            self._is_updating = False

    async def _fetch_and_cache_minute_bars(self, stock_code: str, market: str):
        """개별 종목 분봉 수집 및 캐시 저장"""
        try:
            # 1회차: 현재 시점 기준 (priority=10)
            batch1 = await fetch_chart_data(
                stock_code, market_div="J", bypass_cache=True, priority=10
            )
            if not batch1:
                return

            # 2회차: 이전 시점 기준 (연속성 확보)
            oldest = batch1[-1]
            _, prev_time = get_prev_minute(
                str(oldest["stck_bsop_date"]),
                str(oldest["stck_cntg_hour"]).zfill(6),
            )
            batch2 = await fetch_chart_data(
                stock_code,
                end_time=prev_time,
                market_div="J",
                bypass_cache=True,
                priority=10,
            )

            # 데이터 순서 교정: batch1(최신 120개) + batch2(과거 120개) = 총 240개 (최신순)
            combined = batch1 + batch2
            await kis_cache.update_minute_bars(stock_code, combined)

        except Exception as e:
            logger.error(f"[CacheScheduler] Error fetching bars for {stock_code}: {e}")
