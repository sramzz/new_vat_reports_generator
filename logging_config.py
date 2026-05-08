import logging
import os
import time
from datetime import datetime

LOG_RETENTION_DAYS = 10
_RUN_LOG_PATH = None
_HANDLER_MARKER = "_vat_reports_file_handler"


def _get_config():
    global config
    try:
        return config
    except NameError:
        import config as loaded_config

        config = loaded_config
        return config


def _configured_log_level(cfg) -> int:
    level_name = getattr(cfg, "LOG_LEVEL", os.environ.get("LOG_LEVEL", "INFO")).upper()
    return getattr(logging, level_name, logging.INFO)


def _cleanup_old_logs(log_dir: str) -> None:
    if not os.path.isdir(log_dir):
        return

    cutoff = time.time() - (LOG_RETENTION_DAYS * 86400)
    for root, _, files in os.walk(log_dir):
        for filename in files:
            if not filename.endswith(".log"):
                continue
            path = os.path.join(root, filename)
            if os.path.getmtime(path) < cutoff:
                os.remove(path)


def _run_log_path(log_dir: str) -> str:
    global _RUN_LOG_PATH
    if _RUN_LOG_PATH:
        return _RUN_LOG_PATH

    now = datetime.now()
    day = now.strftime("%Y-%m-%d")
    day_dir = os.path.join(log_dir, day)
    os.makedirs(day_dir, exist_ok=True)

    stamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    path = os.path.join(day_dir, f"{stamp}_run.log")
    counter = 1
    while os.path.exists(path):
        path = os.path.join(day_dir, f"{stamp}_{counter}_run.log")
        counter += 1

    _RUN_LOG_PATH = path
    return path


def setup_logging() -> logging.Logger:
    cfg = _get_config()
    log_dir = cfg.LOG_DIR if hasattr(cfg, "LOG_DIR") else os.path.dirname(cfg.LOG_PATH)
    os.makedirs(log_dir, exist_ok=True)
    _cleanup_old_logs(log_dir)

    logger = logging.getLogger("vat_reports")
    logger.setLevel(_configured_log_level(cfg))

    managed_handlers = [
        handler for handler in logger.handlers if getattr(handler, _HANDLER_MARKER, False)
    ]
    if not managed_handlers:
        file_handler = logging.FileHandler(_run_log_path(log_dir), encoding="utf-8")
        setattr(file_handler, _HANDLER_MARKER, True)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(message)s"
            )
        )
        logger.addHandler(file_handler)

    return logger
