import os, json, gspread
from datetime import datetime, timedelta
import pytz
from oauth2client.service_account import ServiceAccountCredentials

KST = pytz.timezone('Asia/Seoul')

def clean_databases():
    print("🧹 [DB 대청소] 영구 보존소 이관 및 운영 시트 정리를 시작합니다.")
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(os.environ["GOOGLE_SHEETS_CREDENTIALS"]),
        ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    )
    spreadsheet = gspread.authorize(creds).open("News_Management_DB")
    
    # 3일(72시간) 커트라인 설정
    cutoff_time = datetime.now(KST) - timedelta(days=3)
    
    # 정리할 시트와 짝지어질 영구 보존소(Vault) 이름
    targets = {
        "DB_Archive": "DB_Vault_Archive",
        "DB_AI_Report": "DB_Vault_Report"
    }
    
    for hot_sheet_name, vault_sheet_name in targets.items():
        try:
            hot_sheet = spreadsheet.worksheet(hot_sheet_name)
        except Exception as e:
            print(f"⚠️ {hot_sheet_name} 시트를 찾을 수 없어 건너뜁니다.")
            continue
            
        # Vault 시트가 없으면 생성
        try:
            vault_sheet = spreadsheet.worksheet(vault_sheet_name)
        except:
            vault_sheet = spreadsheet.add_worksheet(title=vault_sheet_name, rows="1000", cols="20")
            print(f"📁 영구 보존소 '{vault_sheet_name}'를 새로 생성했습니다.")

        rows = hot_sheet.get_all_values()
        if len(rows) <= 1:
            continue
            
        headers = rows[0]
        # 시간 기준점이 될 열 찾기 (Date 또는 Execution_Time)
        if "Execution_Time" in headers:
            time_idx = headers.index("Execution_Time")
        elif "Date" in headers:
            time_idx = headers.index("Date")
        else:
            time_idx = 0

        keep_rows = [headers]
        move_to_vault_rows = []
        
        for row in rows[1:]:
            try:
                row_time = datetime.strptime(row[time_idx], "%Y-%m-%d %H:%M:%S")
                row_time = KST.localize(row_time)
                
                # 3일이 지난 과거 데이터는 Vault로 이동, 최신 데이터는 유지
                if row_time < cutoff_time:
                    move_to_vault_rows.append(row)
                else:
                    keep_rows.append(row)
            except:
                # 시간 파싱 에러 시 안전하게 유지
                keep_rows.append(row)

        # 1. Vault에 과거 데이터 백업 (원자성 보장)
        if move_to_vault_rows:
            # Vault가 완전히 비어있다면 헤더 먼저 추가
            if len(vault_sheet.get_all_values()) == 0:
                vault_sheet.append_row(headers)
            vault_sheet.append_rows(move_to_vault_rows)
            print(f"📦 {hot_sheet_name} -> {len(move_to_vault_rows)}개의 과거 데이터를 {vault_sheet_name}로 안전하게 백업했습니다.")
            
            # 2. 백업 성공 후 운영 시트 덮어쓰기 (기존 데이터 지우고 최신 데이터만 삽입)
            hot_sheet.clear()
            hot_sheet.update(range_name='A1', values=keep_rows)
            print(f"✨ {hot_sheet_name} 시트 정리가 완료되었습니다. (최신 데이터 {len(keep_rows)-1}개 유지)")
        else:
            print(f"🟢 {hot_sheet_name}에는 3일이 지난 과거 데이터가 없습니다.")

if __name__ == "__main__":
    clean_databases()
