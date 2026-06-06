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


async def fetch_ohlcv_df(
    iscd: str, market_div: str = "J", bypass_cache: bool = False, priority: int = 5
):
    """
    1분봉 데이터(약 240분)를 가져와 OHLCV DataFrame으로 반환.
    캐시 적중 시 1회, 미적중 시 2회 페칭합니다.
    """
    # 1회차 페칭 (최신 데이터)
    batch1 = await fetch_chart_data(
        iscd, market_div=market_div, bypass_cache=bypass_cache, priority=priority
    )
    if not batch1:
        return prepare_ohlcv_df([])

    # 캐시에서 가져온 경우 이미 240분 분량이 합쳐져 있음 (len > 120)
    if len(batch1) > 120:
        combined = batch1[::-1]  # 전체 데이터를 시간 정순(과거->현재)으로 뒤집음
    else:
        # 실시간 데이터인 경우(120개) 1회 더 페칭하여 연속성 확보
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
        # 과거(batch2) + 최신(batch1) 순으로 합친 후 뒤집음
        combined = batch2[::-1] + batch1[::-1]

    ohlcv = [
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
    return prepare_ohlcv_df(ohlcv)


async def fetch_and_analyze_stock(
    iscd: str, name: str, market_div: str, request_params
):
    """
    종목별 1분봉 데이터를 2회 페칭(240분)하여 breakout 분석을 수행합니다.
    """
    try:
        df = await fetch_ohlcv_df(iscd, market_div)
        if df.empty:
            return None
        result = calculate_breakout(df, request_params)
        result.update({"code": iscd, "name": name})
        return result
    except Exception as e:
        logger.error(f"Error analyzing {iscd} ({name}): {e}")
        return None


async def get_breakout_rankings(market: str, breakout_request):
    """
    거래량 상위 30개 종목에 대해 돌파 전략 스캔을 수행합니다.
    """
    # 1. 거래량 순위 가져오기 (마스크 적용됨)
    rank_res = await get_volume_rank(market_div=market)
    if not rank_res.is_ok():
        logger.error(f"Failed to fetch volume rank: {rank_res.get_error_message()}")
        return []

    stocks = rank_res.get_body().output[:30]

    # 2. 병렬 분석 태스크 생성
    # inquire-time-itemchartprice의 FID_COND_MRKT_DIV_CODE는 상장시장 구분과 다를 수 있으나
    # 국내주식의 경우 보통 'J'를 사용합니다.
    tasks = [
        fetch_and_analyze_stock(
            s["mksc_shrn_iscd"], s["hts_kor_isnm"], "J", breakout_request
        )
        for s in stocks
    ]

    # 3. 병렬 실행 및 결과 취합
    results = await asyncio.gather(*tasks)

    # 4. 결과 필터링 및 정렬
    valid_results = [r for r in results if r is not None]

    # 정렬 우선순위: BREAKOUT_STRONG > BREAKOUT_NORMAL > READY > NONE
    category_order = {"BREAKOUT_STRONG": 0, "BREAKOUT_NORMAL": 1, "READY": 2, "NONE": 3}

    valid_results.sort(key=lambda x: category_order.get(x["breakout_category"], 4))

    return valid_results
