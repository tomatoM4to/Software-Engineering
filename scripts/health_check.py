import argparse
import sys
import time

import requests

# ANSI Color Codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def check_endpoint(name, url, expected_status=200, timeout=60, retries=5, delay=5):
    print(f"{BLUE}🔍 Checking {name}...{RESET}")
    print(f"   URL: {url}")

    for i in range(retries):
        try:
            start_time = time.time()
            response = requests.get(url, timeout=timeout)
            duration = time.time() - start_time

            if response.status_code == expected_status:
                print(
                    f"   {GREEN}✅ {name} is UP ({response.status_code}) - {duration:.2f}s{RESET}"
                )
                return True
            else:
                print(
                    f"   {YELLOW}⚠️ Attempt {i + 1}/{retries}: Status {response.status_code}{RESET}"
                )
        except Exception as e:
            print(f"   {YELLOW}⚠️ Attempt {i + 1}/{retries}: Error {str(e)}{RESET}")

        if i < retries - 1:
            time.sleep(delay)

    print(f"   {RED}❌ {name} failed after {retries} attempts!{RESET}")
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", required=True)
    args = parser.parse_args()

    domain = args.domain.rstrip("/")
    if not domain.startswith("http"):
        domain = f"https://{domain}"

    print(f"\n{BOLD}{BLUE}🚀 Starting System Health Check for {domain}{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")

    # 헬스체크 목록 정의
    # 주식 분석 API는 좀 오래 걸릴 수 있으므로 timeout을 충분히 줌
    checks = [
        ("1. 기본 서버 접속", f"{domain}/", 200, 10),
        ("2. AI 에이전트 시스템", f"{domain}/api/agent/health", 200, 10),
        (
            "3. 주식 분석 (실시간 시세/차트)",
            f"{domain}/api/stock/chart/005930",
            200,
            60,
        ),
        ("4. 네이버 뉴스 검색 API", f"{domain}/news/search?query=삼성전자", 200, 15),
    ]

    results = []
    for name, url, status, t_out in checks:
        success = check_endpoint(name, url, expected_status=status, timeout=t_out)
        results.append((name, success))
        print("-" * 40)

    print(f"\n{BOLD}📊 최종 점검 결과{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")

    all_passed = True
    for name, success in results:
        status_str = f"{GREEN}PASS{RESET}" if success else f"{RED}FAIL{RESET}"
        print(f"{name.ljust(40)}: {status_str}")
        if not success:
            all_passed = False

    print(f"{BOLD}{'=' * 60}{RESET}")
    if all_passed:
        print(f"{GREEN}{BOLD}🎉 모든 시스템이 정상적으로 배포되었습니다!{RESET}\n")
        sys.exit(0)
    else:
        print(
            f"{RED}{BOLD}⚠️ 일부 시스템에 문제가 발견되었습니다. 로그를 확인하세요.{RESET}\n"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
