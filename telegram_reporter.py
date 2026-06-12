# telegram_reporter.py 수정
    # ... (생략)
    tg_author_send = config.get("TELEGRAM_AUTHOR_SEND", "OFF")
    extra_ids = config.get("EXTRA_TELEGRAM_IDS", "").split(',')

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    group_chat_id = os.environ.get("TELEGRAM_GROUP_CHAT_ID", "")
    my_chat_id = os.environ.get("MY_CHAT_ID", "") 

    # ... (데이터 취합 로직 동일)

    # 1. 단톡방 발송
    if tg_group_send == "ON": send_telegram_message(group_chat_id, bot_token, msg)

    # 2. 작성자 개인 발송 (MY_CHAT_ID)
    if tg_author_send == "ON" and my_chat_id: send_telegram_message(my_chat_id, bot_token, msg)

    # 3. 추가 수신자 발송
    for extra_id in extra_ids:
        clean_id = extra_id.strip()
        if clean_id:
            send_telegram_message(clean_id, bot_token, msg)
# ...
