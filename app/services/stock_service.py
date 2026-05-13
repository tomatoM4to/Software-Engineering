import logging
from datetime import datetime, timedelta
from core.kis_fetch import async_url_fetch

logger = logging.getLogger(__name__)

def get_prev_minute(date_str: str, time_str: str) -> tuple[str, str]:
    """
    KIS API 1분봉 조회를 위한 오프셋 시간 계산.
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

async def fetch_chart_data_batch(iscd: str, end_time: str = "", market_div: str = "J"):
    """
    특정 종목의 1분봉 데이터를 가져옵니다 (최대 120건).
    """
    api_url = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
    params = {
        "FID_COND_MRKT_DIV_CODE": market_div,
        "FID_INPUT_ISCD": iscd,
        "FID_INPUT_HOUR_1": end_time,
        "FID_PW_DATA_INCU_YN": "Y",
        "FID_ETC_CLS_CODE": "",
    }
    res = await async_url_fetch(api_url, "FHKST03010200", "", params)
    if res.is_ok():
        return res.get_body().output2
    return []

async def get_stock_chart(iscd: str, market_div: str = "J", count: int = 120):
    """
    특정 종목의 1분봉 데이터를 가져와 lightweight-charts 형식으로 반환합니다.
    """
    all_data = []
    current_end_time = ""
    
    # 120개씩 가져옴 (KIS API 제한)
    batches_needed = (count + 119) // 120
    
    for _ in range(batches_needed):
        batch = await fetch_chart_data_batch(iscd, end_time=current_end_time, market_div=market_div)
        if not batch:
            break
        
        all_data.extend(batch)
        
        # 다음 배치를 위한 시간 계산
        oldest = batch[-1]
        _, current_end_time = get_prev_minute(
            str(oldest["stck_bsop_date"]),
            str(oldest["stck_cntg_hour"]).zfill(6),
        )
        
        if len(all_data) >= count:
            break

    # 최신 데이터가 뒤로 오도록 정렬하고 필요한 개수만큼 자름
    all_data = all_data[:count]
    all_data.reverse()

    formatted_data = []
    for c in all_data:
        # KIS date: YYYYMMDD, time: HHMMSS
        date_str = str(c["stck_bsop_date"])
        time_str = str(c["stck_cntg_hour"]).zfill(6)
        
        dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
        timestamp = int(dt.timestamp())
        
        formatted_data.append({
            "time": timestamp,
            "open": float(c["stck_oprc"]),
            "high": float(c["stck_hgpr"]),
            "low": float(c["stck_lwpr"]),
            "close": float(c["stck_prpr"]),
            "volume": float(c["cntg_vol"]),
        })

    return formatted_data
