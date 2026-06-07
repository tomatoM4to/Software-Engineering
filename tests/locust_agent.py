import random

from locust import HttpUser, between, task


class AnalyzeUser(HttpUser):
    """
    AI 분석 API 부하 테스트 (비용 고려하여 최대 동시 5건 제한 권장)
    """

    host = "https://168.107.30.239.nip.io"

    # LLM 호출이 포함되어 있어 응답 시간이 길 수 있으므로 대기 시간을 넉넉히 둠
    wait_time = between(10, 20)

    # 테스트용 주요 종목 코드
    stock_codes = [
        ("005930", "J"),  # 삼성전자
        ("000660", "J"),  # SK하이닉스
        ("035420", "J"),  # NAVER
        ("035720", "J"),  # 카카오
        ("005380", "J"),  # 현대차
        ("068270", "J"),  # 셀트리온
        ("000270", "J"),  # 기아
        ("005490", "J"),  # POSCO홀딩스
    ]

    @task
    def test_analyze_auto(self):
        stock_code, market = random.choice(self.stock_codes)
        payload = {
            "stock_code": stock_code,
            "market": market,
            "ai_persona": "swing_short",
        }
        self.client.post(
            "/api/agent/analyze/auto", json=payload, name="/api/agent/analyze/auto"
        )
