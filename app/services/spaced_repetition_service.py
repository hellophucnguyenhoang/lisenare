from fsrs import Rating


def convert_similarity_score_to_fsrs_rating(
    first_review_score: float, is_answer_revealed: bool
) -> Rating:
    if is_answer_revealed:
        return Rating.Again
    if first_review_score < 0.45:
        return Rating.Again
    elif first_review_score < 0.65:
        return Rating.Hard
    elif first_review_score < 0.85:
        return Rating.Good
    else:
        return Rating.Easy
