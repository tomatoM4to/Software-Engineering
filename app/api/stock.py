from fastapi import APIRouter, Query
from services.stock_service import get_stock_chart

router = APIRouter(prefix="/stock", tags=["stock"])

@router.get("/chart/{iscd}")
async def read_stock_chart(
    iscd: str,
    market: str = Query("J", description="시장 구분 (J: 코스피, Q: 코스닥)"),
    count: int = Query(120, description="조회할 데이터 개수")
):
    """
    특정 종목의 1분봉 차트 데이터를 가져옵니다.
    """
    data = await get_stock_chart(iscd, market_div=market, count=count)
    return {
        "iscd": iscd,
        "market": market,
        "count": len(data),
        "data": data
    }
