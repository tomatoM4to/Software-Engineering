# app/services/ranking_list.py
from core.kis_fetch import async_url_fetch
from schemas.core import KisTrId

async def get_volume_rank(
    market_div: str = "J",
    target_div: str = "111111111",
    exclude_div: str = "0000000000"
):
    """거래량 순위 조회 서비스"""
    api_url = "/uapi/domestic-stock/v1/quotations/volume-rank"
    params = {
        "FID_COND_MRKT_DIV_CODE": market_div,
        "FID_COND_SCR_DIV_CODE": "20171",
        "FID_INPUT_ISCD": "0000",
        "FID_DIV_CLS_CODE": "0",
        "FID_BLNG_CLS_CODE": "0",
        "FID_TRGT_CLS_CODE": target_div,
        "FID_TRGT_EXLS_CLS_CODE": exclude_div,
        "FID_INPUT_PRICE_1": "",
        "FID_INPUT_PRICE_2": "",
        "FID_VOL_CNT": "",
        "FID_INPUT_DATE_1": ""
    }
    
    return await async_url_fetch(
        api_url=api_url,
        ptr_id=KisTrId.VOLUME_RANK,
        tr_cont="",
        params=params
    )
