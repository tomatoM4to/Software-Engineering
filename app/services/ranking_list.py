# app/services/ranking_list.py
from core.kis_fetch import async_url_fetch
from schemas.core import KisTrId


async def get_volume_rank(
    market_div: str = "J", target_div: str = "0", exclude_div: str = "1111111111"
):
    """거래량 순위 조회 서비스"""
    api_url = "/uapi/domestic-stock/v1/quotations/volume-rank"

    # 시장 구분 매핑 (J: 코스피, Q: 코스닥)
    # KIS 거래량순위 API는 FID_COND_MRKT_DIV_CODE에 'J'를 쓰고
    # FID_INPUT_ISCD에 업종코드(0001:코스피, 1001:코스닥)를 넣어 구분함
    real_mrkt_div = "J"
    if market_div == "W":  # ELW인 경우만 W 사용
        real_mrkt_div = "W"

    input_iscd = "0000"  # 전체
    if market_div == "J":
        input_iscd = "0001"  # 코스피
    elif market_div == "Q":
        input_iscd = "1001"  # 코스닥

    params = {
        "FID_COND_MRKT_DIV_CODE": real_mrkt_div,
        "FID_COND_SCR_DIV_CODE": "20171",
        "FID_INPUT_ISCD": input_iscd,
        "FID_DIV_CLS_CODE": "0",
        "FID_BLNG_CLS_CODE": "0",
        "FID_TRGT_CLS_CODE": target_div,
        "FID_TRGT_EXLS_CLS_CODE": exclude_div,
        "FID_INPUT_PRICE_1": "",
        "FID_INPUT_PRICE_2": "",
        "FID_VOL_CNT": "",
        "FID_INPUT_DATE_1": "",
    }

    return await async_url_fetch(
        api_url=api_url, ptr_id=KisTrId.VOLUME_RANK, tr_cont="", params=params
    )
