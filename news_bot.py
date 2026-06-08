import requests
import os

telegram_token = os.environ.get("TELEGRAM_TOKEN")
telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
naver_client_id = os.environ.get("NAVER_CLIENT_ID")
naver_client_secret = os.environ.get("NAVER_CLIENT_SECRET")

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
                    unique_articles.append({"title": clean_title, "link": original_link, "keyword": keyword})
                    keyword_count += 1
            
            if keyword_count >= 4:
                break
    except Exception as e:
        print(f"검색 오류 발생: {e}")
        continue

final_articles = unique_articles[:25]

message_text = f"[오늘의 금융 및 전략 핵심 뉴스 브리핑]\n\n"
if len(final_articles) < 10:
    message_text += f"※ 오늘은 핵심 기사가 {len(final_articles)}개 수집되었습니다.\n\n"

for i, article in enumerate(final_articles, 1):
    message_text += f"{i}. [{article['keyword']}] {article['title']}\n{article['link']}\n\n"

telegram_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
telegram_payload = {
    "chat_id": telegram_chat_id,
    "text": message_text,
    "disable_web_page_preview": True
}

if final_articles:
    requests.post(telegram_url, data=telegram_payload)
    print(f"총 {len(final_articles)}개의 뉴스를 성공적으로 발송했습니다.")
else:
    print("전송할 기사가 없습니다.")
