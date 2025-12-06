# greyscrape/scrapers/store_common.py

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

# Global store-related state, initialized via init_store_logging(...)
STORE_NAME = "default"
STORE_LOGS_ROOT = os.path.join(_BASE_DIR, STORE_NAME, "logs")
EXECUTION_TS = None
EXECUTION_LOG_ROOT = None
_MAIN_LOG_PATH = None

# JSON and worker log dirs (derived from EXECUTION_TS)
LOG_DIR_NAME = None
WORKER_LOG_DIR_NAME = None


def init_store_logging(store_name: str) -> None:
    """
    Initialize logging paths for a specific store.

    Must be called once per process BEFORE any log_msg / EXECUTION_LOG_ROOT usage.
    """
    global STORE_NAME, STORE_LOGS_ROOT, EXECUTION_TS, EXECUTION_LOG_ROOT
    global _MAIN_LOG_PATH, LOG_DIR_NAME, WORKER_LOG_DIR_NAME

    STORE_NAME = store_name
    STORE_LOGS_ROOT = os.path.join(_BASE_DIR, STORE_NAME, "logs")

    EXECUTION_TS = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    EXECUTION_LOG_ROOT = os.path.join(STORE_LOGS_ROOT, EXECUTION_TS)

    _MAIN_LOG_PATH = os.path.join(EXECUTION_LOG_ROOT, "main.log")

    LOG_DIR_NAME = os.path.join(STORE_NAME, "logs", EXECUTION_TS, "json")
    WORKER_LOG_DIR_NAME = os.path.join(STORE_NAME, "logs", EXECUTION_TS)


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_file_line(path: str, line: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def log_msg(msg: str, worker_id: Optional[int] = None) -> None:
    """
    Thread-safe logger.

    Writes:
      - to stdout
      - to main log file for this execution
      - to per-worker log (if worker_id is not None)
    """
    if EXECUTION_LOG_ROOT is None:
        # Defensive: force init if someone esquece de chamar init_store_logging.
        init_store_logging("default")

    ts = datetime.now().strftime("%H:%M:%S")
    prefix = f"[{ts}] [Worker {worker_id}] " if worker_id is not None else f"[{ts}] "
    line = prefix + msg

    with _LOG_LOCK:
        print(line, flush=True)

        _ensure_dir(EXECUTION_LOG_ROOT)
        _write_file_line(_MAIN_LOG_PATH, line)

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
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)
