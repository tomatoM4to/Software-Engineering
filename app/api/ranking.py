# app/api/ranking.py

from fastapi import APIRouter, HTTPException
from services.ranking_list import get_volume_rank

router = APIRouter(prefix="/ranking", tags=["ranking"])


@router.get("/volume")
async def read_volume_rank(market: str = "kospi"):
    market_div = "J" if market.lower() == "kospi" else "Q"
    res = await get_volume_rank(market_div=market_div)
    if not res.is_ok():
        raise HTTPException(status_code=400, detail=res.get_error_message())

    return res.get_body().output
