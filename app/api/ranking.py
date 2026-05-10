# app/api/ranking.py
from fastapi import APIRouter, HTTPException
from services.ranking_list import get_volume_rank

router = APIRouter(prefix="/ranking", tags=["ranking"])

@router.get("/volume")
async def read_volume_rank():
    res = await get_volume_rank()
    if not res.is_ok():
        raise HTTPException(status_code=400, detail=res.get_error_message())
    
    return res.get_body().output
