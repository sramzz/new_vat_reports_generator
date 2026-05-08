import logging
import os
import time
from datetime import datetime
from types import SimpleNamespace

import logging_config


def _reset_vat_logger():
    logger = logging.getLogger("vat_reports")
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    logging_config._RUN_LOG_PATH = None


def test_setup_logging_creates_date_folder_and_run_log(tmp_path, monkeypatch):
    _reset_vat_logger()
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(logging_config, "config", SimpleNamespace(LOG_DIR=str(log_dir), LOG_LEVEL="INFO"), raising=False)

    logger = logging_config.setup_logging()
    logger.info("hello")

    today = datetime.now().strftime("%Y-%m-%d")
    run_logs = list((log_dir / today).glob(f"{today}_*_run.log"))
    assert len(run_logs) == 1
    assert run_logs[0].read_text(encoding="utf-8")


def test_setup_logging_reuses_handler_on_repeated_calls(tmp_path, monkeypatch):
    _reset_vat_logger()
    monkeypatch.setattr(
        logging_config,
        "config",
        SimpleNamespace(LOG_DIR=str(tmp_path / "logs"), LOG_LEVEL="INFO"),
        raising=False,
    )

    logger = logging_config.setup_logging()
    handler_count = len(logger.handlers)
    same_logger = logging_config.setup_logging()

    assert same_logger is logger
    assert len(logger.handlers) == handler_count


def test_setup_logging_removes_old_log_files(tmp_path, monkeypatch):
    _reset_vat_logger()
    log_dir = tmp_path / "logs"
    old_day = log_dir / "2026-04-01"
    old_day.mkdir(parents=True)
    old_file = old_day / "2026-04-01_09-00-00_run.log"
    old_file.write_text("old", encoding="utf-8")
    old_time = time.time() - ((logging_config.LOG_RETENTION_DAYS + 1) * 86400)
    os.utime(old_file, (old_time, old_time))
    monkeypatch.setattr(logging_config, "config", SimpleNamespace(LOG_DIR=str(log_dir), LOG_LEVEL="INFO"), raising=False)

    logging_config.setup_logging()

    assert not old_file.exists()
