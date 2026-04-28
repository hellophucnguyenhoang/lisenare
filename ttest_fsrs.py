from datetime import datetime, timedelta, timezone

from fsrs import Card, Rating, ReviewLog, Scheduler

scheduler = Scheduler(learning_steps=(), relearning_steps=())

# NOTE: all new cards are due immediately upon creation
card = Card()
print(card.stability)

rating = Rating.Again

card, review_log = scheduler.review_card(card, rating)

print(card.stability)
print(card.to_json())
print(f"Card rated {review_log.rating} at {review_log.review_datetime}")

due = card.due
print(f"Card due on {due}")

time_delta = due - review_log.review_datetime
total_seconds = time_delta.total_seconds()
print(f"Total seconds: {total_seconds}")
print(f"Total minutes: {total_seconds / 60}")
print(f"Total hours: {total_seconds / 3600}")
print(f"Total days: {total_seconds / 86400}")


# > Card due on 2024-11-30 18:42:36.070712+00:00
# > Card due in 599 seconds
retrievability = scheduler.get_card_retrievability(
    card, current_datetime=datetime.now(timezone.utc) + timedelta(days=1)
)
print(f"{retrievability = }")

# serialize
scheduler_json = scheduler.to_json()
card_json = card.to_json()
review_log_json = review_log.to_json()

# deserialize
scheduler = Scheduler.from_json(scheduler_json)
card = Card.from_json(card_json)
review_log = ReviewLog.from_json(review_log_json)
