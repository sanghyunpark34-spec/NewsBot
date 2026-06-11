import subprocess
from datetime import datetime
import pytz

KST = pytz.timezone('Asia/Seoul')

def is_korean_workday():
    now = datetime.now(KST)
    if now.weekday() >= 5:
        print(f"[{now.strftime('%Y-%m-%d')}] 주말이므로 자동화를 진행하지 않습니다.", flush=True)
        return False
        
    try:
        import holidays
        kr_holidays = holidays.KR(years=now.year)
        today_str = now.strftime('%Y-%m-%d')
        if today_str in kr_holidays:
            print(f"[{today_str}] 오늘은 한국 공휴일({kr_holidays.get(today_str)})이므로 자동화를 진행하지 않습니다.", flush=True)
            return False
    except Exception as e:
        print(f"공휴일 검증 중 오류가 발생하여 영업일로 가정하고 진행합니다. 오류 내용 {e}", flush=True)
    return True

def run_script(script_name):
    print(f"\n[{datetime.now(KST).strftime('%H:%M:%S')}] {script_name} 가동을 시작합니다.", flush=True)
    result = subprocess.run(['python', script_name])
    
    if result.returncode != 0:
        print(f"⚠ {script_name} 실행 중 에러가 발생했지만, 다음 단계로 멈춤 없이 계속 진행합니다.", flush=True)

def main():
    if not is_korean_workday():
        return

    print("한국 영업일이 확인되어 뉴스 자동화 파이프라인 제어를 시작합니다.", flush=True)
    print(f"\n파이프라인 실행을 시작합니다. 현재 시간은 {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')} 입니다.", flush=True)

    # 에러 발생 여부와 상관없이 무조건 끝까지 순차적으로 직진합니다.
    run_script('news_collector.py')
    run_script('analyzer_base.py')
    run_script('analyzer_ai.py')
    run_script('telegram_reporter.py')

    print("\n🎉 금일 예정된 모든 파이프라인 가동 시도가 지체 없이 완료되었습니다.", flush=True)

if __name__ == "__main__":
    main()
