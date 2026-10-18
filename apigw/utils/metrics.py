import time
from functools import wraps

from config import logger


def measure_time(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"Function '{func.__name__}' completed in {elapsed_ms:.2f} ms"
        )
        return result

    return wrapper
