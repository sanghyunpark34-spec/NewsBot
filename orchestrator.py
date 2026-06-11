import subprocess
import time
from datetime import datetime
import pytz

KST = pytz.timezone('Asia/Seoul')

def is_korean_workday():
    now = datetime.now(KST)
    
    # 1. 주말 체크 (5: 토요일, 6: 일요일)
    if now.weekday() >= 5:
        print(f"[{now.strftime('%Y-%m-%d')}] 주말이므로 자동화를 진행하지 않습니다.")
        return False
        
    # 2. 한국 법정 공휴일 체크 (holidays 라이브러리 활용)
    try:
        import holidays
        kr_holidays = holidays.KR(years=now.year)
        today_str = now.strftime('%Y-%m-%d')
        
        if today_str in kr_holidays:
            print(f"[{today_str}] 오늘은 한국 공휴일({kr_holidays.get(today_str)})이므로 자동화를 진행하지 않습니다.")
            return False
    except Exception as e:
        print(f"공휴일 검증 중 일시적 오류 발생, 영업일로 가정하고 계속 진행합니다: {e}")
        
    return True

def run_script(script_name):
    """각 파이썬 파일을 독립적으로 실행하고 결과를 확인하는 함수"""
    print(f"[{datetime.now(KST).strftime('%H:%M:%S')}] {script_name} 가동 시작...")
    result = subprocess.run(['python', script_name], capture_output=True, text=True)
    
    if result.returncode == 0:
        print(result.stdout)
        return True
    else:
        print(f"❌ {script_name} 실행 중 에러 발생!")
        print(f"에러 내용: {result.stderr}")
        return False

def main():
    # 영업일 검증 단계
    if not is_korean_workday():
        return

    print("💼 한국 영업일 확인 완료. 뉴스 자동화 파이프라인 제어를 시작합니다.")

    while True:
        now = datetime.now(KST)
        
        # 데드라인 검증 (오후 4시 정각 혹은 그 이후이면 종료)
        if now.hour >= 16:
            print("⏰ 오후 4시까지 작업이 완료되지 못해 금일 파이프라인을 최종 실패 처리하고 종료합니다.")
            break

        print(f"\n==================================================")
        print(f"🔄 파이프라인 실행 시도 (시작 시간: {now.strftime('%Y-%m-%d %H:%M:%S')})")
        print(f"==================================================")

        # 4단계 파이프라인 순차 가동
        success = True
        
        if not run_script('news_collector.py'): 
            success = False
            
        if success and not run_script('analyzer_base.py'): 
            success = False
            
        if success and not run_script('analyzer_ai.py'): 
            success = False
            
        if success and not run_script('telegram_reporter.py'): 
            success = False

        # 전체 성공 시 당일 작업 조기 종료
        if success:
            print("\n🎉 모든 파이프라인이 오차 없이 성공적으로 완료되었습니다. 금일 작업을 종료합니다.")
            break
            
        # 일부 단계 실패 시 재시도 스케줄링
        now_after = datetime.now(KST)
        if now_after.hour >= 16:
            print("⏰ 오류 발생 후 재시도하려 했으나 오후 4시가 지나 더 이상 가동하지 않습니다.")
            break
            
        print("⚠ 일부 구간에 장애가 발견되었습니다. 7분 후 처음부터 다시 안전하게 재시도합니다...")
        time.sleep(7 * 60) # 정확히 7분(420초) 대기

if __name__ == "__main__":
    main()
