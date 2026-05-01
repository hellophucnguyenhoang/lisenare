from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy.orm import selectinload
from sqlmodel import Session, or_, select

from app.database import Learner, PushToken
from app.schemas import PushTokenRegister

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
EXPO_RECEIPT_URL = "https://exp.host/--/api/v2/push/getReceipts"
PUSH_NOTI_SEND_BATCH_SIZE = 90  # safe limit


def register_push_token(
    session: Session, data: PushTokenRegister, learner_id: int
) -> PushToken:
    # Check if this token is already registered in the system
    statement = select(PushToken).where(PushToken.token == data.token)
    db_token = session.exec(statement).first()

    if db_token:
        # If it exists, ensure it's linked to the correct user and update info
        db_token.learner_id = learner_id
        db_token.device_name = data.device_name
        # Note: We don't update last_sent_at here, only when a notification is sent
    else:
        # If it's a new device/token, create a new record
        db_token = PushToken(
            token=data.token,
            device_name=data.device_name,
            learner_id=learner_id,
        )
        session.add(db_token)

    session.commit()
    session.refresh(db_token)
    return db_token


def send_push_notification(
    tokens, titles, bodies, data_objs=None
) -> list[str] | None:
    if len(tokens) > 90:
        print()
        return None

    headers = {
        "Accept": "application/json",
        "Accept-encoding": "gzip, deflate",
        "Content-Type": "application/json",
    }

    messages = []
    for i, (token, title, body) in enumerate(zip(tokens, titles, bodies)):
        message = {
            "to": token,
            "sound": "default",
            "title": title,
            "body": body,
            "data": data_objs[i] if data_objs else {},
        }
        messages.append(message)

    response = requests.post(EXPO_PUSH_URL, headers=headers, json=messages)
    response.raise_for_status()

    results = response.json()
    tickets = results.get("data", [])

    ticket_map = []
    for i, ticket in enumerate(tickets):
        if ticket["status"] == "ok":
            ticket_map.append(
                {
                    "ticket_id": ticket["id"],
                    "token": tokens[i],
                }
            )
        else:
            print("Push ticket error:", ticket)
    return ticket_map


def check_push_receipts(ticket_ids) -> list[str]:
    """
    Return a list of invalid ticket ids, not delivered messages.
    """

    response = requests.post(
        EXPO_RECEIPT_URL,
        headers={"Content-Type": "application/json"},
        json={"ids": ticket_ids},
    )
    response.raise_for_status()

    result = response.json()
    receipts_mapping = result.get("data", {})

    invalid_ticket_ids = set()
    for receipt_id, receipt in receipts_mapping.items():
        status = receipt["status"]
        if status == "error":
            error = receipt.get("details", {}).get("error")
            print(f"{receipt_id}: error -> {error}")

            if error == "DeviceNotRegistered":
                invalid_ticket_ids.add(receipt_id)

    return invalid_ticket_ids


def build_notifications(receiver_names):
    titles = []
    bodies = []
    for name in receiver_names:
        title = f"🔥 {name} ơi..."
        body = '"Cho tôi xem menu với" nói sao nhỉ?\nLuyện tí tiếng Anh nhé 🚀'
        titles.append(title)
        bodies.append(body)
    return (
        titles,
        bodies,
    )


def get_eligible_learner_ids(session: Session) -> list[int]:
    """
    Returns IDs of learners who have a push token and haven't
    been notified in the last 12 hours.
    """
    twelve_hours_ago = datetime.now(timezone.utc) - timedelta(hours=12)

    statement = (
        select(Learner.id)
        .join(PushToken)
        # Only learners where at least one token is "ready" to receive
        .where(
            or_(
                True,
                PushToken.last_sent_at.is_(None),
                PushToken.last_sent_at <= twelve_hours_ago,
            )
        )
        .distinct()
    )

    results = session.exec(statement).all()
    return list(results)


def chunk_list(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def send_notifications_to_learners(
    session: Session,
    learner_ids: list[int],
):
    # 1. Get all relevant tokens for these learners
    statement = (
        select(PushToken)
        .where(PushToken.learner_id.in_(learner_ids))
        .options(selectinload(PushToken.learner))
    )
    all_token_objs = session.exec(statement).all()

    if not all_token_objs:
        return

    # --- PHASE A: CLEAN BROKEN TOKENS FROM PREVIOUS RUN ---

    # Identify tokens that have a ticket_id waiting to be verified
    tokens_with_pending_tickets = [
        t for t in all_token_objs if t.last_ticket_id
    ]

    if tokens_with_pending_tickets:
        ticket_ids_to_check = [
            t.last_ticket_id for t in tokens_with_pending_tickets
        ]

        # check_push_receipts returns a list of ticket_ids that are 'DeviceNotRegistered'
        invalid_ticket_ids = check_push_receipts(ticket_ids_to_check)

        if invalid_ticket_ids:
            # Filter the objects to delete
            for t_obj in tokens_with_pending_tickets:
                if t_obj.last_ticket_id in invalid_ticket_ids:
                    print(f"Cleaning invalid token: {t_obj.token}")
                    session.delete(t_obj)

            session.commit()  # Commit deletions before sending new ones

            # Refresh our local list to exclude deleted tokens
            all_token_objs = [
                t for t in all_token_objs if t not in session.deleted
            ]

    # --- PHASE B: SEND NOTIFICATIONS TO REMAINING VALID TOKENS ---

    # Prepare data for remaining valid tokens
    token_strings = [t.token for t in all_token_objs]
    names = []
    for t in all_token_objs:
        name_words = t.learner.full_name.split()
        names.append(
            name_words[0]
            if len(name_words) < 2
            else name_words[0] + " " + name_words[-1]
        )

    titles, bodies = build_notifications(names)

    # Send in batches
    for batch_indices in chunk_list(
        range(len(token_strings)), PUSH_NOTI_SEND_BATCH_SIZE
    ):
        batch_tokens = [token_strings[j] for j in batch_indices]
        batch_titles = [titles[j] for j in batch_indices]
        batch_bodies = [bodies[j] for j in batch_indices]

        # send_push_notification returns: [{"ticket_id": "...", "token": "..."}]
        ticket_map = send_push_notification(
            tokens=batch_tokens,
            titles=batch_titles,
            bodies=batch_bodies,
        )

        if not ticket_map:
            continue

        # Update the database with the NEW ticket_ids to be checked in the next hour
        for entry in ticket_map:
            # Find the corresponding DB object for this token
            for t_obj in all_token_objs:
                if t_obj.token == entry["token"]:
                    t_obj.last_ticket_id = entry["ticket_id"]
                    t_obj.last_sent_at = datetime.now(timezone.utc)

    session.commit()
