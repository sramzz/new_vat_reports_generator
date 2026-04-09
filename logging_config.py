import logging
import os
import time

LOG_RETENTION_DAYS = 10


def setup_logging() -> logging.Logger:
    import config

    if os.path.exists(config.LOG_PATH):
        age_days = (time.time() - os.path.getmtime(config.LOG_PATH)) / 86400
        if age_days > LOG_RETENTION_DAYS:
            os.remove(config.LOG_PATH)

    logger = logging.getLogger("vat_reports")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        file_handler = logging.FileHandler(config.LOG_PATH, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(file_handler)

    return logger
