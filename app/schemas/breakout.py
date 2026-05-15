from pydantic import BaseModel


class BreakoutRequest(BaseModel):
    """돌파 전략 분석 요청 파라미터 (1분봉 단타 최적화)"""

    # --- 프론트엔드에서 주로 제어하는 영역 (유지) ---
    anchor_ma: int = 30
    target_mas: list[int] = [5, 15]
    convergence_threshold: float = 3.0  # (프론트에서 0.1~0.3 수준으로 덮어씌워질 값)

    # --- 백엔드 기본값 튜닝 영역 ---
    breakout_ma: int = 1
    convergence_window: int = 20

    # 거래량 조건 완화 & 민감도 향상
    volume_ma_window: int = 5          # 변경: 20 -> 5
    volume_multiplier: float = 1.5      # 변경: 2.0 -> 1.5
    strong_volume_multiplier: float = 2.0 # 변경: 3.0 -> 2.0

    # 추세 필터 도입 (가짜 반등 방지)
    trend_ma: int | None = 60           # 변경: 0 -> 60

    base_index: int = 0
