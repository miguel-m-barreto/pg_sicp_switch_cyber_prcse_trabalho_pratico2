#!/usr/bin/env python3
"""
Supervisor that alternates between Auchan and Pingo Doce scrapers forever.

Flow:
    1) Run Auchan full scrape
    2) Sleep N minutes
    3) Run Pingo Doce full scrape
    4) Sleep N minutes
    5) Repeat forever

The supervisor never crashes, even if a scraper fails.
"""

import subprocess
import sys
import time
from pathlib import Path

# Sleep duration between runs (in seconds)
FINAL_WAIT_SECONDS = 30 * 60
SCRIPT_WAIT_SECONDS = 1 * 60

# Project root = folder where this script lives
PROJECT_ROOT = Path(__file__).resolve().parent

# Paths to the target scraper scripts
AUCHAN_SCRIPT = PROJECT_ROOT / "scrapers" / "auchan_all_sub_categories_parallel.py"
PINGO_SCRIPT = PROJECT_ROOT / "scrapers" / "pingo_all_sub_categories_parallel.py"


def run_script(label: str, path: Path) -> None:
    """Run a scraper script and log start/end times."""
    if not path.is_file():
        raise FileNotFoundError(f"[Supervisor] Script not found: {path}")

    start_ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[Supervisor] Starting: {label} at {start_ts}")

    try:
        result = subprocess.run(
            [sys.executable, str(path)],
            check=False,  # Never crash the supervisor
        )
        end_ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"[Supervisor] Finished: {label} at {end_ts} "
            f"(return code {result.returncode})"
        )
    except Exception as exc:
        print(f"[Supervisor] ERROR running {label}: {exc!r}")


def main() -> None:
    print("[Supervisor] CYCLIC MODE: Auchan <-> Pingo Doce forever\n")

    while True:
        # Run Auchan
        run_script("Auchan Scraper", AUCHAN_SCRIPT)

        # Script Sleep
        print(f"[Supervisor] Sleeping {SCRIPT_WAIT_SECONDS} seconds...\n")
        time.sleep(SCRIPT_WAIT_SECONDS)

        # Run Pingo Doce
        run_script("Pingo Doce Scraper", PINGO_SCRIPT)

        # Final Sleep
        print(f"[Supervisor] Sleeping {FINAL_WAIT_SECONDS} seconds...\n")
        time.sleep(FINAL_WAIT_SECONDS)


if __name__ == "__main__":
    main()
