from fastapi import APIRouter, Query
from services.stock_service import get_stock_chart

router = APIRouter(prefix="/stock", tags=["stock"])


@router.get("/chart/{iscd}")
async def read_stock_chart(
    iscd: str, count: int = Query(120, description="조회할 데이터 개수 (최대 120)")
):
    """
    주식일별분봉조회 API를 사용하여 120건의 데이터를 한 번에 가져옵니다.
    """
    data = await get_stock_chart(iscd, count=count)
    return {"iscd": iscd, "count": len(data), "data": data}
