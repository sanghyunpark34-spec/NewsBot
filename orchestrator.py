import subprocess
import time
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
    
    if result.returncode == 0:
        return True
    else:
        print(f"엑스 {script_name} 실행 중 치명적인 에러가 발생했습니다.", flush=True)
        return False

def main():
    if not is_korean_workday():
        return

    print("한국 영업일이 확인되어 뉴스 자동화 파이프라인 제어를 시작합니다.", flush=True)

    while True:
        now = datetime.now(KST)
        
        # 테스트를 위해 최초 데드라인 검증 로직을 임시로 주석 처리했습니다.
        # if now.hour >= 16:
        #     print("오후 4시까지 작업이 완료되지 못해 금일 파이프라인을 최종 실패 처리하고 종료합니다.", flush=True)
        #     break

        print(f"\n파이프라인 실행 시도를 시작합니다. 현재 시간은 {now.strftime('%Y-%m-%d %H:%M:%S')} 입니다.", flush=True)

        success = True
        
        if not run_script('news_collector.py'): 
            success = False
            
        if success and not run_script('analyzer_base.py'): 
            success = False
            
        if success and not run_script('analyzer_ai.py'): 
            success = False
            
        if success and not run_script('telegram_reporter.py'): 
            success = False

        if success:
            print("\n모든 파이프라인이 오차 없이 성공적으로 완료되어 금일 작업을 조기 종료합니다.", flush=True)
            break
            
        now_after = datetime.now(KST)
        
        # 테스트를 위해 재시도 전 데드라인 검증 로직도 임시로 주석 처리했습니다.
        # if now_after.hour >= 16:
        #     print("오류 발생 후 재시도하려 했으나 오후 4시가 지나 더 이상 가동하지 않습니다.", flush=True)
        #     break
            
        print("일부 구간에 장애가 발견되어 7분 후 처음부터 다시 안전하게 재시도합니다.", flush=True)
        time.sleep(7 * 60) 

if __name__ == "__main__":
    main()
