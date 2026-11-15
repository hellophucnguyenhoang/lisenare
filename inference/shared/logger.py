import logging

from .constants import LOG_DIR


def setup_logger(
    name: str,
    prefix: str,
    is_production: bool,
) -> logging.Logger:
    log_suffix = "" if is_production else ".dev"
    log_file_path = LOG_DIR / f"{name}{log_suffix}.log"

    logger = logging.getLogger(name)

    # prevent duplicate handlers
    # the case this get called more than once
    if logger.handlers:
        logger.warning("Setup logger more than once")
        return logger

    logger.setLevel(logging.INFO)

    # prevent propagate to the system logger
    # application logs only
    logger.propagate = False

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
        )
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter(f"[{prefix}] %(levelname)s - %(message)s")
    )

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
