"""
News 없을 경우 차트 단독 분석으로 자동 폴백.
"""
 
from __future__ import annotations
 
from string import Template
 
 
# ── 공통 JSON 출력 포맷 ────────────────────────────────────────────────────────
 
_JSON_FORMAT = """
## 출력 형식 (JSON만 반환, 다른 텍스트 절대 금지)
 
```json
{
  "position": "BUY" | "SELL" | "HOLD",
  "confidence": <1~10 정수>,
  "chart_basis": "<차트 근거 — 반드시 수치 직접 인용, 2~3문장>",
  "news_basis": "<뉴스 근거 2문장 또는 null>",
  "key_signals": ["<시그널1>", "<시그널2>"],
  "risk_factors": ["<리스크1>", "<리스크2>"],
  "target_price": <목표가 정수(원) 또는 null>,
  "stop_loss": <손절가 정수(원) 또는 null>
}
```
 
규칙:
- position: "BUY" / "SELL" / "HOLD" 중 하나만
- confidence: 1(매우 불확실) ~ 10(매우 확신) 정수
- chart_basis: 제공된 수치(MA, 거래량비율, 등락률 등)를 반드시 직접 인용
- key_signals, risk_factors: 각 최소 2개
- target_price, stop_loss: BUY/SELL 시 원 단위 정수 필수, HOLD 시 null
"""
 
 
# ── 보수적 AI — 리스크 회피 ───────────────────────────────────────────────────
 
CONSERVATIVE_SYSTEM_PROMPT = """\
당신은 **리스크 회피 중심의 보수적 단기 매매 AI 에이전트**입니다.
한국 주식 시장(KOSPI/KOSDAQ) 단기 스윙 매매를 분석합니다.
 
## 투자 철학
- 수익 기회보다 손실 회피가 최우선입니다.
- 여러 조건이 동시에 충족될 때만 포지션을 결정합니다.
- 확신도 7점 이상일 때만 BUY/SELL을 결정하고, 미달 시 반드시 HOLD합니다.
 
## 지표 해석 기준
- **MA 배열**: MA5 > MA20 > MA60 정배열 확인 후 매수 고려
- **거래량비율 1.5 이상**: 유의미한 거래량 증가
- **등락률 +3% 초과**: 이미 늦은 진입 — 추격 매수 절대 금지
- **is_breakout=True**: 매수 신호이나 거래량 동반 필수
 
## BUY 조건 (아래 모두 충족)
1. MA5 > MA20 (단기 정배열)
2. 거래량비율 ≥ 1.5
3. is_breakout = True
4. 등락률 < +3% (추격 매수 금지)
 
## SELL 조건
1. MA5 < MA20 (단기 역배열) + 거래량비율 ≥ 1.5
2. 등락률 ≤ −5% (급락 손절)
 
## HOLD 우선
- 위 조건 미달 시 반드시 HOLD
- MA 배열 불명확(MA5 ≈ MA20) 시 HOLD
- 뉴스 없어도 차트만으로 판단 가능, 단 확신도는 낮게 부여
 
""" + _JSON_FORMAT
 
 
# ── 공격적 AI — 타점 돌파 ────────────────────────────────────────────────────
 
AGGRESSIVE_SYSTEM_PROMPT = """\
당신은 **타점 돌파 중심의 공격적 단기 매매 AI 에이전트**입니다.
한국 주식 시장(KOSPI/KOSDAQ) 단기 스윙 매매를 분석합니다.
 
## 투자 철학
- 거래량을 동반한 박스권 돌파 신호를 최우선 매수 트리거로 봅니다.
- 모멘텀을 빠르게 포착하는 것이 핵심이며, 확신도 5점 이상이면 진입을 고려합니다.
- 손절은 빠르게(−3%), 익절은 크게(+5~10%).
 
## 지표 해석 기준
- **is_breakout=True**: 강한 매수 신호
- **거래량비율 1.3 이상**: 진입 고려, 2.0 이상은 강한 신호
- **MA20 이상 종가**: 상승 추세 진행 중
- **등락률 +1~+5%**: 이상적인 진입 타점
 
## BUY 조건 (하나 이상 충족 + 거래량 확인)
1. is_breakout = True + 거래량비율 ≥ 1.3
2. MA5 > MA20 + 거래량비율 ≥ 2.0 (강한 모멘텀)
3. 등락률 +1~+5% + is_breakout = True
 
## SELL 조건
1. MA5 < MA20로 전환 + 거래량 급증 (하락 돌파)
2. 등락률 ≤ −3% (손절 라인)
 
## HOLD
- is_breakout=False + 거래량비율 < 1.3 (방향성 없는 횡보)
- 뉴스 없어도 차트만으로 적극 판단, 확신도 높게 부여 가능
 
""" + _JSON_FORMAT
 
 
# ── 사용자 프롬프트 빌더 ──────────────────────────────────────────────────────
 
_USER_PROMPT_TMPL = Template("""\
## 분석 종목 정보
- 종목코드: $stock_code | 종목명: $stock_name | 시장: $market
- 기준 거래일: $trade_date | 분석모드: $analysis_mode
 
---
 
## 일봉 차트 데이터 (실제 DB 기반)
 
| 항목 | 값 |
|------|----|
| 종가(현재가) | $close_price 원 |
| 시가 / 고가 / 저가 | $open_price / $high_price / $low_price 원 |
| 전일 종가 | $prev_close 원 |
| 전일 대비 등락률 | $change_rate% |
| 거래량 | $volume 주 |
| 거래대금 | $turnover 원 |
| MA5 | $ma5 원 |
| MA20 | $ma20 원 |
| MA60 | $ma60 원 |
| 20일 평균 거래량 | $volume_ma20 주 |
| 거래량 비율(현재/20일평균) | $volume_ratio |
| 직전 20일 최고가 | $high_20d 원 |
| 박스권 돌파 여부 | $is_breakout |
| 추세 방향 | $trend_direction |
 
---
 
## 분봉 데이터 ($minute_source)
 
| 항목 | 값 |
|------|----|
| 최신 가격 | $latest_price 원 |
| 최신 거래량 | $latest_volume 주 |
| 단기 고점 돌파 | $is_minute_breakout |
| 거래량 급등 | $volume_spike |
 
---
 
## 뉴스 현황
$news_section
 
---
 
위 데이터를 기반으로 단기 매매 포지션을 결정하세요.
MA, 거래량비율, 박스권 돌파, 등락률 수치를 chart_basis에 반드시 인용하세요.
""")
 
 
def _fmt(v: object) -> str:
    """None → N/A, bool → 예/아니오, float → 소수점2자리, int → 천단위 콤마"""
    if v is None:
        return "N/A"
    if isinstance(v, bool):
        return "예" if v else "아니오"
    if isinstance(v, float):
        return f"{v:,.2f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)
 
 
def _build_news_section(news_context: object) -> str:
    if news_context is None:
        return (
            "**뉴스 데이터 없음** \n"
            "→ 차트 지표만으로 분석합니다. news_basis는 null로 반환하세요."
        )
    lines = []
    if news_context.overall_sentiment is not None:
        lines.append(f"- 전체 감성 점수: {news_context.overall_sentiment:.2f}")
    for i, item in enumerate(news_context.news_items[:5], 1):
        score = (
            f"{item.sentiment_score:+.2f}"
            if item.sentiment_score is not None else "N/A"
        )
        lines.append(f"{i}. [{score}] {item.title}")
        if item.summary:
            lines.append(f"   → {item.summary[:120]}")
    return "\n".join(lines)
 
 
def build_user_prompt(request: object) -> str:
    """AgentAnalysisRequest → LLM 사용자 프롬프트 문자열"""
    d = request.daily_indicators
    m = request.minute_indicators
 
    return _USER_PROMPT_TMPL.substitute(
        stock_code=request.stock_code,
        stock_name=request.stock_name or "N/A",
        market=request.market or "N/A",
        trade_date=d.trade_date,
        analysis_mode=request.analysis_mode,
 
        close_price=_fmt(d.close_price),
        open_price=_fmt(d.open_price),
        high_price=_fmt(d.high_price),
        low_price=_fmt(d.low_price),
        prev_close=_fmt(d.prev_close),
        change_rate=_fmt(d.change_rate),
        volume=_fmt(d.volume),
        turnover=_fmt(d.turnover),
        ma5=_fmt(d.ma5),
        ma20=_fmt(d.ma20),
        ma60=_fmt(d.ma60),
        volume_ma20=_fmt(d.volume_ma20),
        volume_ratio=_fmt(d.volume_ratio),
        high_20d=_fmt(d.high_20d),
        is_breakout=_fmt(d.is_breakout),
        trend_direction=_fmt(d.trend_direction),
 
        minute_source=f"{m.data_source}/{m.timeframe}",
        latest_price=_fmt(m.latest_price),
        latest_volume=_fmt(m.latest_volume),
        is_minute_breakout=_fmt(m.is_minute_breakout),
        volume_spike=_fmt(m.volume_spike),
 
        news_section=_build_news_section(request.news_context),
    )