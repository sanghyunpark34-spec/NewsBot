import requests
import os

telegram_token = os.environ.get("TELEGRAM_TOKEN")
telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
naver_client_id = os.environ.get("NAVER_CLIENT_ID")
naver_client_secret = os.environ.get("NAVER_CLIENT_SECRET")

# 통합되고 한층 정교해진 7개의 전략 키워드 목록입니다.
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

def is_premium_and_clean(title, original_link):
    if any(neg_word in title for neg_word in negative_keywords):
        return False
    if any(domain in original_link for domain in premium_media_domains):
        return True
    return False

# 1, 2차 구분 없이 모든 키워드를 한 번에 순회합니다.
for keyword in keywords:
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=100&sort=sim"
    try:
        response = requests.get(url, headers=naver_headers)
        items = response.json().get('items', [])
        
        keyword_count = 0
        for item in items:
            link = item['link']
            original_link = item.get('originallink', link)
            
            if original_link not in seen_links:
                clean_title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", "")
                if is_premium_and_clean(clean_title, original_link):
                    seen_links.add(original_link)
                    # 나
