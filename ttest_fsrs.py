from datetime import datetime, timezone

from fsrs import Card, Rating, ReviewLog, Scheduler

scheduler = Scheduler()

# NOTE: all new cards are due immediately upon creation
card = Card()

# Rating.Again (==1) forgot the card
# Rating.Hard (==2) remembered the card with serious difficulty
# Rating.Good (==3) remembered the card after a hesitation
# Rating.Easy (==4) remembered the card easily
rating = Rating.Good

card, review_log = scheduler.review_card(card, rating)

print(f"Card rated {review_log.rating} at {review_log.review_datetime}")
# > Card rated 3 at 2024-11-30 17:46:58.856497+00:00

due = card.due

# how much time between when the card is due and now
time_delta = due - datetime.now(timezone.utc)

print(f"Card due on {due}")
print(f"Card due in {time_delta.seconds} seconds")
print(f"Card due in {time_delta.seconds / 60} mins")


# > Card due on 2024-11-30 18:42:36.070712+00:00
# > Card due in 599 seconds
scheduler.get_card_retrievability(card)


# serialize
scheduler_json = scheduler.to_json()
card_json = card.to_json()
review_log_json = review_log.to_json()

# deserialize
scheduler = Scheduler.from_json(scheduler_json)
card = Card.from_json(card_json)
review_log = ReviewLog.from_json(review_log_json)
