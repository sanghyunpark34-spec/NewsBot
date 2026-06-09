import requests
import os
from datetime import datetime, timedelta
import pytz

# 초기 설정
telegram_token = os.environ.get("TELEGRAM_TOKEN")
telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
naver_client_id = os.environ.get("NAVER_CLIENT_ID")
naver_client_secret = os.environ.get("NAVER_CLIENT_SECRET")

kst = pytz.timezone('Asia/Seoul')
now_kst = datetime.now(kst)
# 지난 영업일 16시 기준 설정
days_to_subtract = 3 if now_kst.weekday() == 0 else 1
cutoff_time = (now_kst.replace(hour=16, minute=0, second=0, microsecond=0) - timedelta(days=days_to_subtract))

# [수정] 검색 키워드 대폭 확장
keywords = [
    "금융권 M&A", "보험사 자본확충", "대체투자 사모펀드", "시장 금리 거시경제", 
    "금융당국 정책 규제", "한화생명 전략", "보험업 주요 이슈", 
    "기업 지배구조", "금융 자산관리", "글로벌 금융 시장",
    "투자은행 IB", "주주환원 정책", "금융권 자본건전성"
]

premium_media_domains = ["einfomax.co.kr", "dealsite.co.kr", "investchosun.com", "insjournal.co.kr", "hankyung.com", "sisajournal-e.com", "mtn.co.kr", "kfenews.co.kr"]
negative_keywords = ["MOU", "봉사활동", "공모전", "캠페인", "기부", "동정", "포토", "이벤트", "내정", "취임", "부임", "영입", "선임"]

unique_articles = []
seen_links = set()
naver_headers = {"X-Naver-Client-Id": naver_client_id, "X-Naver-Client-Secret": naver_client_secret}

def is_valid_article(title, original_link, pub_date_str):
    if any(neg_word in title for neg_word in negative_keywords): return False
    if not any(domain in original_link for domain in premium_media_domains): return False
    pub_date = datetime.strptime(pub_date_str, '%a, %d %b %Y %H:%M:%S %z').astimezone(kst)
    return pub_date.replace(tzinfo=None) >= cutoff_time.replace(tzinfo=None)

# 검색 및 수집 로직
for keyword in keywords:
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=100&sort=date"
    response = requests.get(url, headers=naver_headers)
    items = response.json().get('items', [])
    for item in items:
        original_link = item.get('originallink', item['link'])
        if original_link not in seen_links:
            if is_valid_article(item['title'], original_link, item['pubDate']):
                clean_title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", "")
                seen_links.add(original_link)
                unique_articles.append({"title": clean_title, "link": original_link, "keyword": keyword})

# [수정] 수집된 기사 전송 최대 40개까지 상향
final_articles = unique_articles[:40]
if final_articles:
    message_text = f"[금융/전략 핵심 브리핑 - 총 {len(final_articles)}건]\n\n"
    for i, article in enumerate(final_articles, 1):
        message_text += f"{i}. [{article['keyword']}] {article['title']}\n{article['link']}\n\n"
    telegram_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    requests.post(telegram_url, data={"chat_id": telegram_chat_id, "text": message_text, "disable_web_page_preview": True})
