import requests
import os
from datetime import datetime, timedelta
import pytz

# 설정 (생략 - 기존과 동일)
telegram_token = os.environ.get("TELEGRAM_TOKEN")
telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
naver_client_id = os.environ.get("NAVER_CLIENT_ID")
naver_client_secret = os.environ.get("NAVER_CLIENT_SECRET")
kst = pytz.timezone('Asia/Seoul')
now_kst = datetime.now(kst)
days_to_subtract = 3 if now_kst.weekday() == 0 else 1
cutoff_time = (now_kst.replace(hour=16, minute=0, second=0, microsecond=0) - timedelta(days=days_to_subtract))

keywords = [
    "금융권 M&A", "보험사 자본확충", "대체투자 사모펀드", 
    "금융 지배구조 개편", "한화생명 전략", "저축은행 M&A", 
    "금융권 지분투자", "금융 건전성"
]

premium_media_domains = ["einfomax.co.kr", "dealsite.co.kr", "investchosun.com", "insjournal.co.kr", "hankyung.com", "sisajournal-e.com", "mtn.co.kr", "kfenews.co.kr", "thebell.co.kr"]
negative_keywords = ["MOU", "봉사활동", "공모전", "캠페인", "기부", "동정", "포토", "이벤트", "내정", "취임", "부임", "영입", "선임", "인사", "한줄뉴스", "회사채", "수요예측", "언더금리", "주식 전망", "성장주", "테크", "양자컴퓨터", "우주", "콘텐츠", "상장 첫날", "주가"]

unique_articles = []
seen_links = set()
naver_headers = {"X-Naver-Client-Id": naver_client_id, "X-Naver-Client-Secret": naver_client_secret}

def is_valid_article(title, original_link, pub_date_str):
    # 필터 로직: 노이즈 키워드 2개 이상일 때만 제외
    match_count = sum(1 for neg in negative_keywords if neg in title)
    if match_count >= 2: return False
    
    if not any(domain in original_link for domain in premium_media_domains): return False
    
    pub_date = datetime.strptime(pub_date_str, '%a, %d %b %Y %H:%M:%S %z').astimezone(kst)
    return pub_date.replace(tzinfo=None) >= cutoff_time.replace(tzinfo=None)

# 검색 실행
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

# [수정] 수집량 50개까지 확대
final_articles = unique_articles[:50]
if final_articles:
    message_text = f"[금융/전략 핵심 브리핑 - 총 {len(final_articles)}건]\n\n"
    for i, article in enumerate(final_articles, 1):
        message_text += f"{i}. [{article['keyword']}] {article['title']}\n{article['link']}\n\n"
    telegram_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    requests.post(telegram_url, data={"chat_id": telegram_chat_id, "text": message_text, "disable_web_page_preview": True})
