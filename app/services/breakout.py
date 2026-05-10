from io import BytesIO
from typing import Any, List, Dict
import pandas as pd


def prepare_ohlcv_df(ohlcv_list: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    외부에서 전달받은 OHLCV 데이터 리스트를 분석에 적합한 pandas DataFrame으로 변환합니다.
    예상 입력 포맷:
    [
        {"date": "20231024", "open": 50000, "high": 51000, "low": 49000, "close": 50500, "volume": 100000},
        ...
    ]
    """
    if not ohlcv_list:
        return pd.DataFrame()

    df = pd.DataFrame(ohlcv_list)
    
    # 컬럼명 표준화 (소문자로 변환 후 매핑)
    df.columns = [str(col).lower() for col in df.columns]
    col_map = {
        "date": "trade_date",
        "trade_date": "trade_date",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume"
    }
    df.rename(columns=col_map, inplace=True)

    # 필수 컬럼 존재 여부 확인
    required_cols = ["trade_date", "Open", "High", "Low", "Close", "Volume"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # 데이터 타입 변환
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 인덱스 설정 및 정렬 (과거 -> 최신)
    df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
    df.dropna(subset=["trade_date"], inplace=True)
    df.set_index("trade_date", inplace=True)
    df.sort_index(ascending=True, inplace=True)

    return df


def calculate_breakout(df: pd.DataFrame, request) -> dict[str, Any]:
    """
    OHLCV 데이터프레임을 기반으로 돌파 시그널을 계산하고 카테고리를 분류합니다.
    """
    if df.empty or len(df) < max({request.anchor_ma, *request.target_mas, request.trend_ma or 0}):
        return {
            "breakout_category": "NONE",
            "signal_date": str(df.index[-1]) if not df.empty else "-",
            "close": 0.0,
            "volume": 0,
            "convergence_score": None
        }

    # DataFrame 복사본 사용 (원본 훼손 방지)
    df = df.copy()

    required_mas = {request.anchor_ma, *request.target_mas}
    if request.breakout_ma > 1:
        required_mas.add(request.breakout_ma)
    if request.trend_ma:
        required_mas.add(request.trend_ma)

    for ma in sorted(required_mas):
        df[f"MA{ma}"] = df["Close"].rolling(window=ma).mean()

    # 1. 수렴 여부 확인
    gap_columns: list[str] = []
    for target_ma in request.target_mas:
        col = f"gap{target_ma}"
        gap_columns.append(col)
        df[col] = (abs(df[f"MA{target_ma}"] - df[f"MA{request.anchor_ma}"]) / df[f"MA{request.anchor_ma}"]) * 100

    df["convergence_score"] = df[gap_columns].sum(axis=1)
    is_recently_converged = (
        df["convergence_score"].rolling(window=request.convergence_window).min() < request.convergence_threshold
    )

    # 2. 돌파 여부 확인
    if request.breakout_ma == 1:
        is_breaking_out = (df["Close"] > df[f"MA{request.anchor_ma}"]) & (df["Open"] < df["Close"])
    else:
        is_breaking_out = (df[f"MA{request.breakout_ma}"] > df[f"MA{request.anchor_ma}"]) & (df["Open"] < df["Close"])

    # 3. 거래량 폭발 확인
    df["Vol_MA"] = df["Volume"].rolling(window=request.volume_ma_window).mean().shift(1)
    is_volume_spiked = df["Volume"] > (df["Vol_MA"] * request.volume_multiplier)
    is_volume_strong = df["Volume"] > (df["Vol_MA"] * request.strong_volume_multiplier)

    # 4. 추세 필터
    trend_filter = True
    if request.trend_ma:
        trend_filter = (df["Close"] >= df[f"MA{request.trend_ma}"])

    # 카테고리 결정 (최신 index 기준, base_index 오프셋 적용)
    target_idx = -(1 + request.base_index)
    latest = df.iloc[target_idx]
    
    converged = bool(is_recently_converged.iloc[target_idx]) if pd.notna(is_recently_converged.iloc[target_idx]) else False
    broken_out = bool(is_breaking_out.iloc[target_idx]) if pd.notna(is_breaking_out.iloc[target_idx]) else False
    vol_spiked = bool(is_volume_spiked.iloc[target_idx]) if pd.notna(is_volume_spiked.iloc[target_idx]) else False
    vol_strong = bool(is_volume_strong.iloc[target_idx]) if pd.notna(is_volume_strong.iloc[target_idx]) else False
    trend_ok = bool(trend_filter.iloc[target_idx]) if not isinstance(trend_filter, bool) else trend_filter

    category = "NONE"
    if converged:
        if broken_out and vol_spiked and trend_ok:
            if vol_strong:
                category = "BREAKOUT_STRONG"
            else:
                category = "BREAKOUT_NORMAL"
        else:
            category = "READY"

    # 날짜 포맷팅 안전 처리
    signal_date = df.index[target_idx]
    formatted_date = signal_date.strftime("%Y-%m-%d %H:%M:%S") if isinstance(signal_date, pd.Timestamp) else str(signal_date)

    return {
        "breakout_category": category,
        "signal_date": formatted_date,
        "close": float(latest["Close"]),
        "volume": int(latest["Volume"]),
        "convergence_score": round(float(latest["convergence_score"]), 4) if pd.notna(latest["convergence_score"]) else None,
    }
