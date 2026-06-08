import requests
import os
from datetime import datetime, timedelta
import pytz

# 한국 시간대 설정
kst = pytz.timezone('Asia/Seoul')

telegram_token = os.environ.get("TELEGRAM_TOKEN")
telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
naver_client_id = os.environ.get("NAVER_CLIENT_ID")
naver_client_secret = os.environ.get("NAVER_CLIENT_SECRET")

# 한국 현재 시간 기준 커트라인 설정
now_kst = datetime.now(kst)
# 월요일(0)이면 지난주 금요일(3일 전), 그 외에는 전날(1일 전)을 기준으로 함
days_to_subtract = 3 if now_kst.weekday() == 0 else 1
cutoff_time = (now_kst.replace(hour=16, minute=0, second=0, microsecond=0) - timedelta(days=days_to_subtract))

keywords = [
    "금융권 M&A", "보험사 자본확충", "대체투자 사모펀드", 
    "시장 금리 거시경제", "금융당국 정책 규제", "한화생명 전략", "보험업 주요 이슈"
]

premium_media_domains = [
    "einfomax.co.kr", "dealsite.co.kr", "investchosun.com", "insjournal.co.kr", 
    "hankyung.com", "sisajournal-e.com", "metroseoul.co.kr", "mtn.co.kr", "kfenews.co.kr"
]

negative_keywords = ["MOU", "영입", "봉사활동", "공모전", "캠페인", "기부", "인사", "동정", "포토", "이벤트"]

unique_articles = []
seen_links = set()

naver_headers = {
    "X-Naver-Client-Id": naver_client_id,
    "X-Naver-Client-Secret": naver_client_secret
}

def is_valid_article(title, original_link, pub_date_str):
    if any(neg_word in title for neg_word in negative_keywords): return False
    if not any(domain in original_link for domain in premium_media_domains): return False
    
    # 네이버 발행 시간을 파싱하고 한국 시간대로 변환
    pub_date = datetime.strptime(pub_date_str, '%a, %d %b %Y %H:%M:%S %z').astimezone(kst)
    # tzinfo를 제거하여 비교 가능하게 함
    if pub_date.replace(tzinfo=None) < cutoff_time.replace(tzinfo=None): return False
    
    return True

for keyword in keywords:
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=100&sort=date" # 시간순으로 변경
    try:
        response = requests.get(url, headers=naver_headers)
        items = response.json().get('items', [])
        
        keyword_count = 0
        for item in items:
            original_link = item.get('originallink', item['link'])
            if original_link not in seen_links and is_valid_article(item['title'], original_link, item['pubDate']):
                clean_title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", "")
                seen_links.add(original_link)
                unique_articles.append({"title": clean_title, "link": original_link, "keyword": keyword})
                keyword_count += 1
            if keyword_count >= 4: break
    except Exception as e:
        print(f"검색 오류: {e}")

final_articles = unique_articles[:25]
# ... 이후 전송 코드는 동일 ...
