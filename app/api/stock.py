from fastapi import APIRouter, Query
from services.stock_service import get_stock_chart

router = APIRouter(prefix="/stock", tags=["stock"])


@router.get("/chart/{iscd}")
async def read_stock_chart(
    iscd: str,
    market: str = Query("J", description="시장 구분 (J: 주식, Q: 코스닥 등)"),
    count: int = Query(120, description="조회할 데이터 개수 (최대 120)"),
):
    """
    주식일별분봉조회 API를 사용하여 120건의 데이터를 한 번에 가져옵니다.
    """
    data = await get_stock_chart(iscd, market_div=market, count=count)
    return {"iscd": iscd, "count": len(data), "data": data}
