from pydantic import BaseModel

class BreakoutRequest(BaseModel):
    """돌파 전략 분석 요청 파라미터"""

    anchor_ma: int = 20
    target_mas: list[int] = [5, 10, 60]
    breakout_ma: int = 1
    convergence_window: int = 20
    convergence_threshold: float = 1.5
    volume_ma_window: int = 20
    volume_multiplier: float = 2.0
    strong_volume_multiplier: float = 3.0
    trend_ma: int | None = 0
    base_index: int = 0
