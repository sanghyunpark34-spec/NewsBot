import requests
import os
from datetime import datetime, timedelta
import pytz

# 설정 부분 생략 (기존과 동일)
telegram_token = os.environ.get("TELEGRAM_TOKEN")
telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
naver_client_id = os.environ.get("NAVER_CLIENT_ID")
naver_client_secret = os.environ.get("NAVER_CLIENT_SECRET")

kst = pytz.timezone('Asia/Seoul')
now_kst = datetime.now(kst)
days_to_subtract = 3 if now_kst.weekday() == 0 else 1
cutoff_time = (now_kst.replace(hour=16, minute=0, second=0, microsecond=0) - timedelta(days=days_to_subtract))

keywords = ["금융권 M&A", "보험사 자본확충", "대체투자 사모펀드", "시장 금리 거시경제", "금융당국 정책 규제", "한화생명 전략", "증권사 IB"]
premium_media_domains = ["einfomax.co.kr", "dealsite.co.kr", "investchosun.com", "insjournal.co.kr", "hankyung.com", "thebell.co.kr", "sedaily.com", "mt.co.kr", "kfenews.co.kr"]
negative_keywords = ["내정", "취임", "부임", "영입", "선임", "인사", "동정", "포토", "이벤트", "봉사활동", "공모전", "캠페인", "기부", "한줄뉴스"]

unique_articles = []
seen_links = set()
naver_headers = {"X-Naver-Client-Id": naver_client_id, "X-Naver-Client-Secret": naver_client_secret}

print(f"DEBUG: 시작 시간 기준 {cutoff_time}")

for keyword in keywords:
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=100&sort=date"
    response = requests.get(url, headers=naver_headers)
    items = response.json().get('items', [])
    print(f"키워드 '{keyword}'에서 {len(items)}개 검색됨")
    
    for item in items:
        original_link = item.get('originallink', item['link'])
        pub_date = datetime.strptime(item['pubDate'], '%a, %d %b %Y %H:%M:%S %z').astimezone(kst).replace(tzinfo=None)
        
        # 필터링 로직 진단용 출력
        if any(neg in item['title'] for neg in negative_keywords): continue
        if not any(domain in original_link for domain in premium_media_domains): continue
        if pub_date < cutoff_time: 
            print(f"DEBUG: 너무 오래된 기사 제외: {item['title']} ({pub_date})")
            continue
            
        if original_link not in seen_links:
            seen_links.add(original_link)
            unique_articles.append({"title": item['title'], "link": original_link, "keyword": keyword})
            print(f"DEBUG: 통과! {item['title']}")

print(f"필터 최종 통과: {len(unique_articles)}개")
if unique_articles:
    # 전송 로직 (생략)
    # ... (기존과 동일)
