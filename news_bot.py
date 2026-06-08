import requests
import os
from datetime import datetime, timedelta
import pytz

# [설정 부분 동일]
telegram_token = os.environ.get("TELEGRAM_TOKEN")
telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
naver_client_id = os.environ.get("NAVER_CLIENT_ID")
naver_client_secret = os.environ.get("NAVER_CLIENT_SECRET")

kst = pytz.timezone('Asia/Seoul')
now_kst = datetime.now(kst)
days_to_subtract = 3 if now_kst.weekday() == 0 else 1
cutoff_time = (now_kst.replace(hour=16, minute=0, second=0, microsecond=0) - timedelta(days=days_to_subtract))

keywords = ["금융권 M&A", "보험사 자본확충", "대체투자 사모펀드", "시장 금리 거시경제", "금융당국 정책 규제", "한화생명 전략", "보험업 주요 이슈"]
# 메트로서울 제거
premium_media_domains = ["einfomax.co.kr", "dealsite.co.kr", "investchosun.com", "insjournal.co.kr", "hankyung.com", "sisajournal-e.com", "mtn.co.kr", "kfenews.co.kr"]
# 인사 관련 키워드 추가
negative_keywords = ["MOU", "봉사활동", "공모전", "캠페인", "기부", "동정", "포토", "이벤트", "내정", "취임", "부임", "영입", "선임"]

unique_articles = []
seen_links = set()
naver_headers = {"X-Naver-Client-Id": naver_client_id, "X-Naver-Client-Secret": naver_client_secret}

def is_valid_article(title, original_link, pub_date_str):
    if any(neg_word in title for neg_word in negative_keywords): return False
    if not any(domain in original_link for domain in premium_media_domains): return False
    pub_date = datetime.strptime(pub_date_str, '%a, %d %b %Y %H:%M:%S %z').astimezone(kst)
    return pub_date.replace(tzinfo=None) >= cutoff_time.replace(tzinfo=None)

# [검색 및 전송 로직 동일]
for keyword in keywords:
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=100&sort=date"
    response = requests.get(url, headers=naver_headers)
    items = response.json().get('items', [])
    keyword_count = 0
    for item in items:
        original_link = item.get('originallink', item['link'])
        if original_link not in seen_links:
            if is_valid_article(item['title'], original_link, item['pubDate']):
                clean_title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", "")
                seen_links.add(original_link)
                unique_articles.append({"title": clean_title, "link": original_link, "keyword": keyword})
                keyword_count += 1
        if keyword_count >= 4: break

final_articles = unique_articles[:25]
if final_articles:
    message_text = "[오늘의 금융 및 전략 핵심 뉴스 브리핑]\n\n"
    for i, article in enumerate(final_articles, 1):
        message_text += f"{i}. [{article['keyword']}] {article['title']}\n{article['link']}\n\n"
    telegram_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    requests.post(telegram_url, data={"chat_id": telegram_chat_id, "text": message_text, "disable_web_page_preview": True})
