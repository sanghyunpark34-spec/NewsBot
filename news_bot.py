import requests
import os

# 깃허브 비밀 금고에서 네이버와 텔레그램 출입증을 가져옵니다.
telegram_token = os.environ.get("TELEGRAM_TOKEN")
telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
naver_client_id = os.environ.get("NAVER_CLIENT_ID")
naver_client_secret = os.environ.get("NAVER_CLIENT_SECRET")

# 1차로 검색할 핵심 주제 키워드들을 리스트로 선언합니다.
primary_keywords = ["금융 분야 인수 합병", "금융업 이슈", "경제 주요 현황", "인수 합병", "가산자산 등 디지털 금융"]

# 1차 기사가 부족할 때만 사용할 2차 보완 키워드들을 선언합니다.
secondary_keywords = ["보험업", "한화그룹"]

# 중복 기사를 걸러내고 최종 목록을 담을 바구니들을 준비합니다.
unique_articles = []
seen_links = set()

naver_headers = {
    "X-Naver-Client-Id": naver_client_id,
    "X-Naver-Client-Secret": naver_client_secret
}

# 1차 핵심 주제들에 대해 관련도 높은 순서로 검색을 수행합니다.
for keyword in primary_keywords:
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=5&sort=sim"
    try:
        response = requests.get(url, headers=naver_headers)
        items = response.json().get('items', [])
        for item in items:
            link = item['link']
            # 기존에 수집하지 않은 새로운 인터넷 주소인 경우에만 바구니에 담습니다.
            if link not in seen_links:
                seen_links.add(link)
                clean_title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", "")
                unique_articles.append({"title": clean_title, "link": link})
    except Exception as e:
        print(f"검색 진행 중 오류가 발생했습니다: {e}")

# 수집된 독창적인 기사가 15개 미만인 경우에만 2차 검색 알고리즘이 작동합니다.
if len(unique_articles) < 15:
    print(f"1차 검색 결과가 {len(unique_articles)}개로 부족하여 2차 재검색을 시작합니다.")
    for keyword in secondary_keywords:
        if len(unique_articles) >= 15:
            break
        url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=10&sort=sim"
        try:
            response = requests.get(url, headers=naver_headers)
            items = response.json().get('items', [])
            for item in items:
                link = item['link']
                if link not in seen_links:
                    seen_links.add(link)
                    clean_title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", "")
                    unique_articles.append({"title": clean_title, "link": link})
                if len(unique_articles) >= 15:
                    break
        except Exception as e:
            print(f"2차 검색 진행 중 오류가 발생했습니다: {e}")

# 최종 수집된 기사들 중에서 가장 관련도가 높은 정확히 15개만 칼같이 잘라냅니다.
final_articles = unique_articles[:15]

# 요약문 없이 제목과 주소만으로 구성된 깔끔한 메시지 텍스트를 작성합니다.
message_text = "[오늘의 금융 및 전략 핵심 뉴스 15선]\n\n"
for i, article in enumerate(final_articles, 1):
    message_text += f"{i}. {article['title']}\n{article['link']}\n\n"

# 최종 완성된 뉴스 리스트 15선을 텔레그램으로 전송합니다.
telegram_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
telegram_payload = {
    "chat_id": telegram_chat_id,
    "text": message_text,
    "disable_web_page_preview": True  # 링크가 많으므로 주소 미리보기 창은 작동하지 않도록 설정합니다.
}

requests.post(telegram_url, data=telegram_payload)
print(f"정확히 {len(final_articles)}개의 주소 포함 뉴스레터 발송을 완료했습니다.")
