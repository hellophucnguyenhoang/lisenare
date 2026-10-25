from config import logger
from fsrs import Optimizer, ReviewLog


def optimize_parameters(
    review_logs_dict: list[dict],
) -> tuple[list[float], float]:
    """
    Train FSRS optimizer on review logs to find optimal weights and retention.
    Returns:
        (optimal_params, optimal_retention)
    """
    fsrs_logs = []
    for d in review_logs_dict:
        if not d:
            continue
        try:
            fsrs_logs.append(ReviewLog.from_dict(d))
        except Exception as e:
            logger.warning(f"Skipping invalid review log dict: {e}")

    log_count = len(fsrs_logs)
    if log_count < 100:
        raise ValueError(
            f"Not enough logs for optimization ({log_count} < 100)"
        )

    optimizer = Optimizer(fsrs_logs)
    optimal_params = optimizer.compute_optimal_parameters()

    optimal_retention = 0.9
    if log_count >= 512:
        try:
            optimal_retention = optimizer.compute_optimal_retention(
                optimal_params
            )
        except ValueError as e:
            logger.warning(
                f"Retention optimization failed, falling back to 0.9: {e}"
            )

    return optimal_params, optimal_retention
