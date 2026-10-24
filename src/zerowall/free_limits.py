MAX_ATTEMPTS = 12
CHAT_MAX_ATTEMPTS = 20
DAILY_ATTEMPTS = 50
RETRY_ALLOWANCE = 3
RETRIES_PER_TURN = 2


def attempt_limit(connection, mission_id):
    row = connection.execute(
        "SELECT json_extract(body,'$.surface'),json_extract(body,'$.direct_attempt_window.start_attempt'),json_extract(body,'$.direct_attempt_window.allowance') FROM records WHERE id=? AND kind='mission'",
        (mission_id,),
    ).fetchone()
    if row and row[1] is not None and row[2] is not None:
        return int(row[1]) + int(row[2])
    return CHAT_MAX_ATTEMPTS if row and row[0] == "chat" else MAX_ATTEMPTS
