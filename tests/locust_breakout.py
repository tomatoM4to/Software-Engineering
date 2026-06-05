import random
from locust import HttpUser, task, between

class BreakoutUser(HttpUser):
    """
    돌파 전략 스캐너 부하 테스트
    동시 10건 정도 호출 시의 성능 확인
    """
    host = "https://168.107.30.239.nip.io"
    
    wait_time = between(1, 5)

    @task
    def test_breakout(self):
        # 코스닥(Q), 코스피(J) 랜덤 선택
        market = random.choice(["Q", "J"])
        params = {
            "market": market,
            "anchor_ma": 20,
            "target_mas": [5, 10],
            "convergence_threshold": 1.5
        }
        # name 파라미터를 사용하여 통계에서 쿼리 스트링 제외하고 그룹화
        self.client.get("/api/strategy/breakout", params=params, name="/api/strategy/breakout")
