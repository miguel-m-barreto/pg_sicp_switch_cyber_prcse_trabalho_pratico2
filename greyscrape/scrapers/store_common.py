# greyscrape/scrapers/store_common.py

import os
import threading
import time
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

LOG_DIR_NAME = "auchan/logs"
WORKER_LOG_DIR_NAME = "auchan/worker_logs"

_LOG_LOCK = threading.Lock()

def log_msg(msg: str, worker_id: Optional[int] = None) -> None:
    """
    Thread-safe logger: writes to stdout with optional worker prefix
    and, if worker_id is provided, also to a per-worker log file.
    """
    prefix = f"[Worker {worker_id}] " if worker_id is not None else ""
    line = f"{prefix}{msg}"

    with _LOG_LOCK:
        # stdout
        print(line, flush=True)

        # per-worker log file
        if worker_id is not None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            log_dir = os.path.join(base_dir, WORKER_LOG_DIR_NAME)
            os.makedirs(log_dir, exist_ok=True)
            path = os.path.join(log_dir, f"worker_{worker_id}.log")
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")


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
