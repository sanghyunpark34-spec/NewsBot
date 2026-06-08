import requests
import os
from datetime import datetime, timedelta
import pytz

# [설정 및 초기화 생략]
# ... (앞부분은 동일) ...

# 1차 검색 실행 시 로그 출력 추가
print(f"검색 시작: {keywords}")

for keyword in keywords:
    url = f"https://openapi.naver.com/v1/search/news.json?query={keyword}&display=100&sort=date"
    response = requests.get(url, headers=naver_headers)
    items = response.json().get('items', [])
    
    print(f"키워드 '{keyword}'에서 {len(items)}개의 기사 발견")
    
    for item in items:
        # 필터링 로직에 도달했는지 확인
        original_link = item.get('originallink', item['link'])
        if is_valid_article(item['title'], original_link, item['pubDate']):
            # [생략]
            unique_articles.append({"title": item['title'], "link": original_link, "keyword": keyword})
        else:
            # 필터링에 걸린 기사의 제목을 찍어봅니다.
            pass 

print(f"필터 통과 최종 기사 수: {len(unique_articles)}")

# 메시지 발송 직전에 로그 출력
if len(unique_articles) > 0:
    print("텔레그램 메시지 발송 시도...")
    # ... (전송 로직) ...
else:
    print("수집된 기사가 없어 발송을 건너뜁니다.")
