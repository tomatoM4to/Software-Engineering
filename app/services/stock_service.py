import logging
from datetime import datetime
from core.kis_fetch import async_url_fetch

logger = logging.getLogger(__name__)

async def get_stock_chart(iscd: str, count: int = 120):
    """
    주식일별분봉조회 API(FHKST03010230)를 사용하여 1분봉 데이터 120개를 한 번에 가져옵니다.
    """
    api_url = "/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice"
    
    # 시장 구분 코드: 국내 주식(코스피/코스닥)은 'J'를 사용합니다.
    req_market_div = "J"

    # 오늘 날짜와 현재 시간 설정
    now = datetime.now()
    # 장 중이 아닐 때를 고려하여 15:30으로 넉넉하게 잡거나 현재 시간을 사용
    # KIS API는 미래 시간을 넣으면 현재 시점까지의 데이터를 줍니다.
    current_date = now.strftime("%Y%m%d")
    current_time = "153000" if now.hour >= 16 else now.strftime("%H%M%S")

    params = {
        "FID_COND_MRKT_DIV_CODE": req_market_div,
        "FID_INPUT_ISCD": iscd,
        "FID_INPUT_HOUR_1": current_time,
        "FID_INPUT_DATE_1": current_date,
        "FID_PW_DATA_INCU_YN": "Y", # 과거 데이터 포함
        "FID_FAKE_TICK_INCU_YN": "N",
    }
    
    # TR_ID: FHKST03010230 (주식일별분봉조회)
    res = await async_url_fetch(api_url, "FHKST03010230", "", params)
    
    if not res.is_ok():
        logger.error(f"Failed to fetch chart data: {res.get_error_message()}")
        return []

    # output2에 분봉 데이터가 배열로 들어있음 (최대 120건)
    all_data = res.get_body().output2
    
    # 최신 데이터가 앞에 있으므로 차트 표시를 위해 뒤집음
    all_data.reverse()

    formatted_data = []
    for c in all_data:
        # KIS date: YYYYMMDD, time: HHMMSS
        date_str = str(c["stck_bsop_date"])
        time_str = str(c["stck_cntg_hour"]).zfill(6)
        
        try:
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
        except Exception as e:
            logger.warning(f"Failed to parse bar data: {e}")
            continue

    return formatted_data
