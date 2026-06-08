import requests
import os

# 첫 번째 단계로 깃허브의 비밀 금고(Secrets)에서 나의 암호들을 꺼내옵니다.
telegram_token = os.environ.get("TELEGRAM_TOKEN")
telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
naver_client_id = os.environ.get("NAVER_CLIENT_ID")
naver_client_secret = os.environ.get("NAVER_CLIENT_SECRET")
gemini_api_key = os.environ.get("GEMINI_API_KEY")

# 두 번째 단계로 기사 개수를 10개로 늘려서 최신 뉴스를 요청합니다.
naver_url = "https://openapi.naver.com/v1/search/news.json?query=테슬라 모델Y&display=10"
naver_headers = {
    "X-Naver-Client-Id": naver_client_id,
    "X-Naver-Client-Secret": naver_client_secret
}
naver_response = requests.get(naver_url, headers=naver_headers)
news_items = naver_response.json()['items']

# 세 번째 단계로 가져온 기사 제목과 원문 링크를 짝지어서 하나의 긴 글로 합칩니다.
news_data_for_ai = ""
for item in news_items:
    clean_title = item['title'].replace("<b>", "").replace("</b>", "").replace("&quot;", "")
    article_link = item['link']
    news_data_for_ai = news_data_for_ai + clean_title + " (" + article_link + ")\n"

# 네 번째 단계로 인공지능에게 링크를 포함하여 정리해 달라고 부탁합니다.
prompt = f"다음은 오늘 수집된 열 개의 뉴스 기사 제목과 링크입니다. 이 내용을 바탕으로 친절한 아나운서가 브리핑하듯 전체적인 핵심 동향을 두세 문장으로 먼저 요약해 주세요. 그 다음 줄부터는 수집된 열 개의 기사 제목과 원문 링크를 하나씩 보기 좋게 나열해 주세요. 내가 수집한 데이터는 다음과 같습니다. \n{news_data_for_ai}"

gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={gemini_api_key}"
gemini_payload = {
    "contents": [{
        "parts": [{"text": prompt}]
    }]
}
gemini_response = requests.post(gemini_url, json=gemini_payload)
gemini_data = gemini_response.json()
final_summary = gemini_data['candidates'][0]['content']['parts'][0]['text']

# 마지막 다섯 번째 단계로 한층 고도화된 뉴스를 내 텔레그램으로 전송합니다.
telegram_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
telegram_payload = {
    "chat_id": telegram_chat_id,
    "text": f"오늘의 업그레이드 AI 큐레이션 뉴스입니다.\n\n{final_summary}"
}
requests.post(telegram_url, data=telegram_payload)

print("원문 링크가 포함된 10개의 뉴스 큐레이션 전송을 완료했습니다.")
