# greyscrape/scrapers/store_common.py

import os
import threading
import time
from datetime import datetime
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# ----------------------------------------------------------------------
# Log level handling
# ----------------------------------------------------------------------

_LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARN": 30,
    "ERROR": 40,
}

_CURRENT_LOG_LEVEL = _LOG_LEVELS["INFO"]

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


def _load_log_level_from_env() -> None:
    """
    Initialize global log level from LOG_LEVEL environment variable.

    Accepted values: DEBUG, INFO, WARN, ERROR (case-insensitive).
    Defaults to INFO if not set or invalid.
    """
    global _CURRENT_LOG_LEVEL
    name = os.getenv("LOG_LEVEL", "INFO").upper()
    _CURRENT_LOG_LEVEL = _LOG_LEVELS.get(name, _LOG_LEVELS["INFO"])


def init_store_logging(store_name: str) -> None:
    """
    Initialize logging paths for a specific store.

    Must be called once per process BEFORE any log_* usage.
    """
    global STORE_NAME, STORE_LOGS_ROOT, EXECUTION_TS, EXECUTION_LOG_ROOT
    global _MAIN_LOG_PATH, LOG_DIR_NAME, WORKER_LOG_DIR_NAME

    STORE_NAME = store_name

    # Root for this store: <scrapers>/<store_name>
    store_root = os.path.join(_BASE_DIR, STORE_NAME)

    # Logs root: <scrapers>/<store_name>/logs
    STORE_LOGS_ROOT = os.path.join(store_root, "logs")

    # Execution folder: <scrapers>/<store_name>/logs/<timestamp>
    EXECUTION_TS = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    EXECUTION_LOG_ROOT = os.path.join(STORE_LOGS_ROOT, EXECUTION_TS)

    # Main log file: <scrapers>/<store_name>/logs/<timestamp>/main.log
    _MAIN_LOG_PATH = os.path.join(EXECUTION_LOG_ROOT, "main.log")

    # Relative dirs (from store_root), shared by all stores
    # JSON logs: <scrapers>/<store_name>/logs/<timestamp>/json
    LOG_DIR_NAME = os.path.join("logs", EXECUTION_TS, "json")

    # Worker logs base: <scrapers>/<store_name>/logs/<timestamp>/
    WORKER_LOG_DIR_NAME = os.path.join("logs", EXECUTION_TS)

    # Initialize log level once per execution
    _load_log_level_from_env()


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _write_file_line(path: str, line: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _log(level_name: str, msg: str, worker_id: Optional[int] = None) -> None:
    """
    Internal log function with level filtering and file/stdout write.

    This is the single place where we decide whether a log line is printed.
    """
    if EXECUTION_LOG_ROOT is None:
        # Defensive: force init if someone forgot to call init_store_logging.
        init_store_logging("default")

    if msg is None:
        msg = ""

    level_name = level_name.upper()
    level_value = _LOG_LEVELS.get(level_name, _LOG_LEVELS["INFO"])

    # Filter by current log level
    if level_value < _CURRENT_LOG_LEVEL:
        return

    ts = datetime.now().strftime("%H:%M:%S")

    # Prefix includes timestamp, log level and optional worker
    if worker_id is not None:
        prefix = f"[{ts}] [{level_name}] [Worker {worker_id}] "
    else:
        prefix = f"[{ts}] [{level_name}] "

    line = prefix + msg

    with _LOG_LOCK:
        print(line, flush=True)

        _ensure_dir(EXECUTION_LOG_ROOT)
        _write_file_line(_MAIN_LOG_PATH, line)

        if worker_id is not None:
            # Store root: <scrapers>/<STORE_NAME>
            store_root = os.path.join(_BASE_DIR, STORE_NAME)

            # Worker logs: <scrapers>/<STORE_NAME>/logs/<ts>/Worker_X/worker_logs
            worker_root = os.path.join(
                store_root,
                WORKER_LOG_DIR_NAME,
                f"Worker_{worker_id}",
                "worker_logs",
            )
            _ensure_dir(worker_root)
            worker_log_path = os.path.join(worker_root, "worker.log")
            _write_file_line(worker_log_path, line)


# ----------------------------------------------------------------------
# Public logging API
# ----------------------------------------------------------------------

def log_msg(msg: str, worker_id: Optional[int] = None) -> None:
    """
    Backwards-compatible logger, behaves like an INFO log.

    All existing calls in the codebase keep working.
    """
    _log("INFO", msg, worker_id)


def log_debug(msg: str, worker_id: Optional[int] = None) -> None:
    """Debug-level log (very verbose, only printed if LOG_LEVEL=DEBUG)."""
    _log("DEBUG", msg, worker_id)


def log_info(msg: str, worker_id: Optional[int] = None) -> None:
    """Info-level log (default level)."""
    _log("INFO", msg, worker_id)


def log_warn(msg: str, worker_id: Optional[int] = None) -> None:
    """Warning-level log (always shown for LOG_LEVEL <= WARN)."""
    _log("WARN", msg, worker_id)


def log_error(msg: str, worker_id: Optional[int] = None) -> None:
    """Error-level log."""
    _log("ERROR", msg, worker_id)


# ----------------------------------------------------------------------
# Misc helpers
# ----------------------------------------------------------------------

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
