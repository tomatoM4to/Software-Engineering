from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from schemas.breakout import BreakoutRequest
from services.ranking_list import get_volume_rank
from services.scanner import get_breakout_rankings

router = APIRouter(prefix="/strategy", tags=["strategy"])

@router.get("/breakout")
async def read_breakout_rank(
    market: str = Query("Q", description="시장 구분 (J: 코스피, Q: 코스닥)"),
    anchor_ma: int = 20,
    convergence_threshold: float = 1.5,
):
    """
    거래량 상위 30개 종목에 대해 1분봉 돌파 전략 스캔을 수행합니다.
    """
    # 기본 분석 파라미터 생성
    request_params = BreakoutRequest(
        anchor_ma=anchor_ma, convergence_threshold=convergence_threshold
    )

    results = await get_breakout_rankings(market, request_params)

    return {
        "timestamp": datetime.now().isoformat(),
        "market": market,
        "summary": {
            "total_scanned": len(results),
            "breakout_strong": len(
                [r for r in results if r["breakout_category"] == "BREAKOUT_STRONG"]
            ),
            "breakout_normal": len(
                [r for r in results if r["breakout_category"] == "BREAKOUT_NORMAL"]
            ),
            "ready": len([r for r in results if r["breakout_category"] == "READY"]),
            "none": len([r for r in results if r["breakout_category"] == "NONE"]),
        },
        "results": results,
    }
