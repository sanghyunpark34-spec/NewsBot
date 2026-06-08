import requests
import os

# 깃허브 비밀 금고에서 네이버와 텔레그램 출입증을 안전하게 가져옵니다.
telegram_token = os.environ.get("TELEGRAM_TOKEN")
telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
naver_client_id = os.environ.get("NAVER_CLIENT_ID")
naver_client_secret = os.environ.get("NAVER_CLIENT_SECRET")

# 1차로 검색할 자본시장 및 금융 정책 핵심 주제들입니다.
primary_keywords = ["금융 분야 인수 합병", "보험사 전략", "금융업 이슈", "경제 주요 현황", "금융업 정책"]

# 1차 기사가 최소 기준인 10개에 미달할 때만 가동할 2차 보완용 광범위 키워드입니다.
secondary_keywords = ["보험업 전반", "한화그룹 전반"]

# 철저하게 검증된 전문 금융 및 투자 매체들의 도메인 화이트리스트입니다.
premium_media_domains = [
    "einfomax.co.kr", "dealsite.co.kr", "investchosun.com", "insjournal.co.kr", 
    "hankyung.com", "sisajournal-e.com", "metroseoul.co.kr", "mtn.co.kr", "kfenews.co.kr"
]

# 기사 제목에 포함되면 무조건 쓰레기통으로 버릴 홍보성 제외 키워드 목록입니다.
negative_keywords = ["MOU", "영입", "봉사활동", "공모전", "캠페인", "기부", "인사", "동정", "포토"]

unique_articles = []
seen_links = set()

naver_headers = {
    "X-Naver-Client-Id": naver_client_id,
    "X-Naver-Client-Secret": naver_client_secret
}

# 기사의 제목과 매체를 검사하여 유익한 기사인지 판별하는 필터링 함수를 정의합니다.
def is_premium_and_clean(title, link):
    # 제외 키워드가 제목에 하나라도 섞여 있다면 즉시 탈락시킵니다.
    if any(neg_word in title for neg_word in negative_keywords):
        return False
    # 기사 원문 주소에 우리가 지정한 전문 경제 매체의 도메인이 포함되어 있는지 검사합니다.
    if any(domain in link for domain in premium_media_domains):
        return True
    return False

# 1차 핵심 주제들에 대해 검색을 진행하며 고품질 기사를 수집합니다.
for keyword in primary_keywords:
    # 매체 필터링으로 탈락할 기사를 감안하여 네이버로부터 관련도순으로 15개씩 넉넉하게 요청합니다.
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=15&sort=sim"
    try:
        response = requests.get(url, headers=naver_headers)
        items = response.json().get('items', [])
        for item in items:
            link = item['link']
            if link not in seen_links:
                clean_title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", "")
                # 우리가 설계한 깐깐한 프리미엄 필터를 통과한 기사만 바구니에 담습니다.
                if is_premium_and_clean(clean_title, link):
                    seen_links.add(link)
                    unique_articles.append({"title": clean_title, "link": link})
    except Exception as e:
        print(f"1차 검색 도중 오류가 발생했습니다: {e}")

# 수집된 기사가 최소 하한선인 10개에 미치지 못하는 가뭄 상황인 경우 2차 백업 검색 알고리즘이 깨어납니다.
if len(unique_articles) < 10:
    print(f"현재 확보된 기사가 {len(unique_articles)}개로 최소 기준에 부족하여 2차 재검색을 시작합니다.")
    for keyword in secondary_keywords:
        if len(unique_articles) >= 10:
            break
        url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=20&sort=sim"
        try:
            response = requests.get(url, headers=naver_headers)
            items = response.json().get('items', [])
            for item in items:
                link = item['link']
                if link not in seen_links:
                    clean_title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", "")
                    # 2차 검색에서도 품질 검증 필터는 동일하게 적용하여 물관리를 유지합니다.
                    if is_premium_and_clean(clean_title, link):
                        seen_links.add(link)
                        unique_articles.append({"title": clean_title, "link": link})
                if len(unique_articles) >= 10:
                    break
        except Exception as e:
            print(f"2차 검색 도중 오류가 발생했습니다: {e}")

# 최종 전송할 기사의 개수를 동적으로 결정하는 슬라이싱 규칙을 실행합니다.
if len(unique_articles) > 25:
    # 기사가 너무 많아 범람할 때는 가장 관련도가 높은 최대 상한선인 25개까지만 잘라냅니다.
    final_articles = unique_articles[:25]
else:
    # 기사 수가 10개에서 25개 사이이거나 최소 하한선인 경우에는 수집된 개수 그대로 유연하게 전송합니다.
    final_articles = unique_articles

# 요약문을 과감히 생략하고 순수한 기사 제목과 주소 링크로만 채워진 리스트 전문을 만듭니다.
message_text = f"[오늘의 금융 및 전략 핵심 뉴스 브리핑]\n\n"
for i, article in enumerate(final_articles, 1):
    message_text += f"{i}. {article['title']}\n{article['link']}\n\n"

# 완성된 지면을 텔레그램으로 안전하게 쏘아 올립니다.
telegram_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
telegram_payload = {
    "chat_id": telegram_chat_id,
    "text": message_text,
    "disable_web_page_preview": True
}

requests.post(telegram_url, data=telegram_payload)
print(f"동적 수량 제어 알고리즘에 의해 총 {len(final_articles)}개의 엄선된 뉴스를 성공적으로 발송했습니다.")
