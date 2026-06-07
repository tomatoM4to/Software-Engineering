import pandas as pd
import os
import sys

def generate_summary():
    stats_history_path = "locust_report_stats_history.csv"
    
    if not os.path.exists(stats_history_path):
        print(f"Error: {stats_history_path} not found.")
        return

    # CSV 데이터 로드
    df = pd.read_csv(stats_history_path)
    
    # NaN 값을 0으로 채움 (Mermaid xychart-beta 파싱 에러 방지)
    df = df.fillna(0)
    
    # 시간축을 상대 시간(초)으로 변경
    start_time = df['Timestamp'].iloc[0]
    df['RelativeTime'] = df['Timestamp'] - start_time
    
    # 너무 데이터가 많으면 샘플링 (최대 60개 지점)
    if len(df) > 60:
        df = df.iloc[::len(df)//60]

    # 1. Mermaid 차트 생성 (RPS 및 Response Time)
    mermaid_line = "```mermaid\nxychart-beta\n    title \"Load Test: RPS (Line 1) & P95 Latency (Line 2)\"\n"
    
    # X축 설정 (시간)
    x_axis = "    x-axis [" + ", ".join([f"\"{int(t)}s\"" for t in df['RelativeTime']]) + "]\n"
    mermaid_line += x_axis
    
    # Y축 설정 (공통)
    mermaid_line += "    y-axis \"Value\"\n"

    # RPS 데이터
    rps_data = "    line [" + ", ".join([f"{r:.1f}" for r in df['Requests/s']]) + "]\n"
    mermaid_line += rps_data
    
    # 95% 응답시간 데이터 (ms)
    p95_data = "    line [" + ", ".join([f"{p:.0f}" for p in df['95%']]) + "]\n"
    mermaid_line += p95_data
    mermaid_line += "```\n"

    # 2. Markdown 요약 테이블 생성
    summary_stats = "### 📊 Load Test Summary\n\n"
    summary_stats += "| Metric | Value |\n"
    summary_stats += "| --- | --- |\n"
    summary_stats += f"| **Total Users** | {df['User Count'].max()} |\n"
    summary_stats += f"| **Max RPS** | {df['Requests/s'].max():.1f} |\n"
    summary_stats += f"| **Avg P95 Latency** | {df['95%'].mean():.1f} ms |\n"
    summary_stats += "\n"

    # GitHub Step Summary에 쓰기
    summary_file = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_file:
        with open(summary_file, 'a', encoding='utf-8') as f:
            f.write(summary_stats)
            f.write(mermaid_line)
            f.write("\n> Tip: 차트가 보이지 않으면 페이지를 새로고침하세요.\n")
    else:
        print(summary_stats)
        print(mermaid_line)

if __name__ == "__main__":
    generate_summary()
