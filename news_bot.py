import requests
import os
from datetime import datetime, timedelta
import pytz

# [설정 부분 생략 - 기존과 동일]
# ...

# [수정] 노이즈 기사를 원천 차단하는 필터 키워드 강화
negative_keywords = [
    "MOU", "봉사활동", "공모전", "캠페인", "기부", "동정", "포토", "이벤트", 
    "내정", "취임", "부임", "영입", "선임", "인사", "한줄뉴스", 
    "회사채", "수요예측", "언더금리", "주식 전망", "성장주", "테크", 
    "양자컴퓨터", "우주", "콘텐츠", "상장 첫날", "주가" 
]

def is_valid_article(title, original_link, pub_date_str):
    # 1. 인사/홍보/기술테크/단순회사채 키워드 필터
    if any(neg_word in title for neg_word in negative_keywords): return False
    
    # 2. 비금융/테크 중심 매체 및 섹션 필터 (필요시 추가 강화)
    # 3. 화이트리스트 검증
    if not any(domain in original_link for domain in premium_media_domains): return False
    
    # 4. 시간 필터
    pub_date = datetime.strptime(pub_date_str, '%a, %d %b %Y %H:%M:%S %z').astimezone(kst)
    return pub_date.replace(tzinfo=None) >= cutoff_time.replace(tzinfo=None)

# [검색 키워드 수정]
# 단순 기술주나 테크 기사를 배제하고 금융/지배구조/딜 중심 키워드로 집중
keywords = [
    "금융권 M&A", "보험사 자본확충", "대체투자 사모펀드", 
    "금융 지배구조 개편", "한화생명 전략", "저축은행 M&A", 
    "금융권 지분투자", "금융 건전성"
]

# ... 나머지 검색 및 전송 로직 동일 ...
