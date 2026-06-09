# ... 앞부분 동일 ...
keywords = [
    "금융권 M&A 지분투자", "보험사 자본확충 건전성", "대체투자 사모펀드 운용", 
    "시장 금리 거시경제", "금융당국 정책 규제", "한화생명 전략 동향", 
    "증권사 IB 디지털자산"
]

premium_media_domains = [
    "einfomax.co.kr", "dealsite.co.kr", "investchosun.com", "insjournal.co.kr", 
    "hankyung.com", "thebell.co.kr", "sedaily.com", "mt.co.kr", "kfenews.co.kr"
]

# 인사 및 홍보성 기사를 철저히 배제
negative_keywords = [
    "내정", "취임", "부임", "영입", "선임", "인사", "동정", "포토", "이벤트", 
    "봉사활동", "공모전", "캠페인", "기부", "한줄뉴스", "오늘의 뉴스"
]

def is_valid_article(title, original_link, pub_date_str):
    # 제목 내 인사/홍보 키워드 필터링
    if any(neg_word in title for neg_word in negative_keywords): return False
    # 화이트리스트 매체 확인
    if not any(domain in original_link for domain in premium_media_domains): return False
    # 시간 필터링 (기존 로직 유지)
    pub_date = datetime.strptime(pub_date_str, '%a, %d %b %Y %H:%M:%S %z').astimezone(kst)
    return pub_date.replace(tzinfo=None) >= cutoff_time.replace(tzinfo=None)

# ... 나머지 검색 및 전송 로직 동일 ...
