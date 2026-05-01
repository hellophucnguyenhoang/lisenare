import time

from app.services import push_token_service

token1 = "ExponentPushToken[7FvPnAPY3Oc2qg0FfEFVIO]"
token2 = "ExponentPushToken[lSR-eoBE1DXUxnm4zY7cGg]"

try:
    usernames = ["Sam", "Phúc"]
    titles, bodies = push_token_service.build_notifications(
        receiver_names=usernames
    )
    ticket_map = push_token_service.send_push_notification(
        tokens=[token1, token2],
        titles=titles,
        bodies=bodies,
    )
    time.sleep(3)
    invalid_ticket_ids = push_token_service.check_push_receipts(
        [t["ticket_id"] for t in ticket_map]
    )
    invalid_tokens = [
        t["token"] for t in ticket_map if t["ticket_id"] in invalid_ticket_ids
    ]
    print(invalid_tokens)

except Exception as e:
    print(e)
