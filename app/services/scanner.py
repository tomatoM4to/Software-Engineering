import asyncio
import logging
from datetime import datetime, timedelta

from core.kis_fetch import async_cache_fetch, async_url_fetch
from services.breakout import calculate_breakout, prepare_ohlcv_df
from services.ranking_list import get_volume_rank

logger = logging.getLogger(__name__)


def get_prev_minute(date_str: str, time_str: str) -> tuple[str, str]:
    """
    KIS API 1분봉 조회를 위한 오프셋 시간 계산.
    09:00분인 경우 이전 영업일 15:30분으로 점프합니다.
    """
    dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
    prev_dt = dt - timedelta(minutes=1)

    # 09:00 이전 또는 09:00 정각에서 1분 뺀 경우 (08:59)
    if prev_dt.hour < 9 or (prev_dt.hour == 8 and prev_dt.minute == 59):
        weekday = prev_dt.weekday()
        if weekday == 0:  # 월요일 -> 금요일 (-3일)
            days_back = 3
        elif weekday == 6:  # 일요일 -> 금요일 (-2일)
            days_back = 2
        else:  # 평일 -> 전일 (-1일)
            days_back = 1

        prev_dt = prev_dt - timedelta(days=days_back)
        prev_dt = prev_dt.replace(hour=15, minute=30, second=0)

    return prev_dt.strftime("%Y%m%d"), prev_dt.strftime("%H%M%S")


async def fetch_chart_data(
    iscd: str,
    end_time: str = "",
    market_div: str = "J",
    bypass_cache: bool = False,
    priority: int = 5,
):
    """
    특정 종목의 1분봉 데이터를 가져옵니다 (최대 120건, 캐시 시 240건).
    """
    api_url = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
    params = {
        "FID_COND_MRKT_DIV_CODE": market_div,
        "FID_INPUT_ISCD": iscd,
        "FID_INPUT_HOUR_1": end_time,
        "FID_PW_DATA_INCU_YN": "Y",
        "FID_ETC_CLS_CODE": "",
    }

    if not bypass_cache:
        res = await async_cache_fetch(ptr_id="FHKST03010200", params=params)
        if res.is_ok():
            return res.get_body().output2
        return []

    res = await async_url_fetch(
        api_url,
        "FHKST03010200",
        "",
        params,
        bypass_cache=bypass_cache,
        priority=priority,
    )

    if res.is_ok():
        return res.get_body().output2
    return []


async def fetch_ohlcv_raw_list(
    iscd: str, market_div: str = "J", bypass_cache: bool = False, priority: int = 5
):
    """
    1분봉 데이터를 가져와 정제되지 않은 리스트 형태로 반환합니다. (Pandas 연산 제외)
    """
    batch1 = await fetch_chart_data(
        iscd, market_div=market_div, bypass_cache=bypass_cache, priority=priority
    )
    if not batch1:
        return []

    if len(batch1) > 120:
        combined = batch1[::-1]
    else:
        oldest = batch1[-1]
        _, prev_time = get_prev_minute(
            str(oldest["stck_bsop_date"]),
            str(oldest["stck_cntg_hour"]).zfill(6),
        )
        batch2 = await fetch_chart_data(
            iscd,
            end_time=prev_time,
            market_div=market_div,
            bypass_cache=bypass_cache,
            priority=priority,
        )
        combined = batch2[::-1] + batch1[::-1]

    return [
        {
            "date": f"{c['stck_bsop_date']}{str(c['stck_cntg_hour']).zfill(6)}",
            "open": c["stck_oprc"],
            "high": c["stck_hgpr"],
            "low": c["stck_lwpr"],
            "close": c["stck_prpr"],
            "volume": c["cntg_vol"],
        }
        for c in combined
    ]


def sync_bulk_analyze(stocks_raw_data: list[dict], request_params):
    """
    [동기 함수] 여러 종목의 Pandas 연산을 하나의 쓰레드에서 순차적으로 처리합니다.
    """
    final_results = []
    for item in stocks_raw_data:
        iscd = item["code"]
        name = item["name"]
        raw_list = item["raw_list"]

        try:
            if not raw_list:
                final_results.append({
                    "code": iscd, "name": name, "breakout_category": "NONE",
                    "signal_date": "-", "close": 0.0, "volume": 0, "convergence_score": None
                })
                continue

            # Pandas 연산 수행
            df = prepare_ohlcv_df(raw_list)
            result = calculate_breakout(df, request_params)
            result.update({"code": iscd, "name": name})
            final_results.append(result)
        except Exception as e:
            logger.error(f"Error analyzing {iscd}: {e}")
            final_results.append({
                "code": iscd, "name": name, "breakout_category": "NONE",
                "signal_date": "Error", "close": 0.0, "volume": 0, "convergence_score": None
            })
    return final_results


async def get_breakout_rankings(market: str, breakout_request):
    """
    거래량 상위 30개 종목에 대해 돌파 전략 스캔을 수행합니다.
    최적화: 데이터 수집은 비동기 병렬, 연산은 단일 쓰레드 벌크 처리.
    """
    rank_res = await get_volume_rank(market_div=market)
    if not rank_res.is_ok():
        return []

    stocks = rank_res.get_body().output[:30]

    # 1. 30개 종목 데이터 비동기 병렬 수집 (I/O 병목 제거)
    tasks = [
        fetch_ohlcv_raw_list(s["mksc_shrn_iscd"], "J")
        for s in stocks
    ]
    raw_data_lists = await asyncio.gather(*tasks)

    # 2. 연산용 데이터 구조화
    bulk_input = [
        {"code": s["mksc_shrn_iscd"], "name": s["hts_kor_isnm"], "raw_list": raw_data_lists[i]}
        for i, s in enumerate(stocks)
    ]

    # 3. 단 한 번의 to_thread 호출로 30개 종목의 Pandas 연산 처리 (CPU 병목 제거)
    results = await asyncio.to_thread(sync_bulk_analyze, bulk_input, breakout_request)

    # 4. 결과 정렬
    category_order = {"BREAKOUT_STRONG": 0, "BREAKOUT_NORMAL": 1, "READY": 2, "NONE": 3}
    results.sort(key=lambda x: category_order.get(x["breakout_category"], 4))

    return results


# 하위 호환성을 위해 유지 (fetch_ohlcv_df를 사용하는 다른 모듈이 있을 수 있음)
async def fetch_ohlcv_df(iscd: str, market_div: str = "J", bypass_cache: bool = False, priority: int = 5):
    raw_list = await fetch_ohlcv_raw_list(iscd, market_div, bypass_cache, priority)
    return prepare_ohlcv_df(raw_list)
