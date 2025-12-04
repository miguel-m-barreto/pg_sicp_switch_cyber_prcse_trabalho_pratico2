import os
import threading
import time
from datetime import datetime
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Global lock for thread-safe logging
_LOG_LOCK = threading.Lock()

# Base directory for this package (greyscrape/scrapers)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Timestamp for THIS PROCESS / THIS EXECUTION
_EXECUTION_TS = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# Root folder for this execution:
# greyscrape/scrapers/auchan/logs/<timestamp>/
_EXECUTION_LOG_ROOT = os.path.join(
    _BASE_DIR, "auchan", "logs", _EXECUTION_TS
)

# Main log file for the execution
_MAIN_LOG_PATH = os.path.join(_EXECUTION_LOG_ROOT, "main.log")

# Directory for JSON logs for this execution
# (used by _save_json_log em auchan_DB.py)
LOG_DIR_NAME = os.path.join("auchan", "logs", _EXECUTION_TS, "json")

# Base dir for worker logs for this execution.
# Worker final path:
# greyscrape/scrapers/auchan/logs/<ts>/Worker_<id>/worker_logs/worker.log
WORKER_LOG_DIR_NAME = os.path.join("auchan", "logs", _EXECUTION_TS)


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_file_line(path: str, line: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_msg(msg: str, worker_id: Optional[int] = None) -> None:
    """
    Thread-safe logger.

    Writes:
      - to stdout (with optional [Worker X] prefix)
      - to main log file for this execution
      - to per-worker log file if worker_id is not None
    """
    prefix = f"[Worker {worker_id}] " if worker_id is not None else ""
    line = f"{prefix}{msg}"

    with _LOG_LOCK:
        # stdout
        print(line, flush=True)

        # Ensure base execution log dir exists
        _ensure_dir(_EXECUTION_LOG_ROOT)

        # Main log for this execution
        _write_file_line(_MAIN_LOG_PATH, line)

        # Per-worker log
        if worker_id is not None:
            worker_root = os.path.join(
                _BASE_DIR,
                WORKER_LOG_DIR_NAME,
                f"Worker_{worker_id}",
                "worker_logs",
            )
            _ensure_dir(worker_root)
            worker_log_path = os.path.join(worker_root, "worker.log")
            _write_file_line(worker_log_path, line)


def format_elapsed_time(start_ts: float) -> str:
    """
    Format a wall clock elapsed time nicely for logging.
    """
    elapsed = time.time() - start_ts

    if elapsed < 60:
        return f"{elapsed:.1f} seconds"
    elif elapsed < 3600:
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        return f"{minutes}m {seconds}s"
    else:
        hours = int(elapsed // 3600)
        rem = elapsed % 3600
        minutes = int(rem // 60)
        seconds = int(rem % 60)
        return f"{hours}h {minutes}m {seconds}s"


def build_headless_chrome() -> webdriver.Chrome:
    """
    Build a headless Chrome WebDriver with sane defaults.

    Reuse this across all store scrapers.
    """
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)
