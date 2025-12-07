#!/usr/bin/env python3
"""
Run auchan_all_sub_categories_parallel.py in an infinite loop.

- After each run (success or crash), sleep 5 minutes.
- Never crash because of the child script failing.
"""

import subprocess
import sys
import time
from pathlib import Path

# Path to the target script (assuming this file is in the project root)
PROJECT_ROOT = Path(__file__).resolve().parent
TARGET_SCRIPT = PROJECT_ROOT / "scrapers" / "auchan_all_sub_categories_parallel.py"

# Sleep duration between runs (in seconds)
SLEEP_SECONDS = 5 * 60  # 5 minutes


def main() -> None:
    """Main supervision loop."""
    if not TARGET_SCRIPT.is_file():
        # If this fails, your repo structure is wrong. Fix it.
        raise FileNotFoundError(f"Target script not found: {TARGET_SCRIPT}")

    print(f"[Supervisor] Watching script: {TARGET_SCRIPT}")

    while True:
        start_ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[Supervisor] Starting run at {start_ts}...")

        try:
            # Run the target script with the same Python interpreter
            # check=False -> we do not raise on non-zero exit codes
            result = subprocess.run(
                [sys.executable, str(TARGET_SCRIPT)],
                check=False,
            )

            end_ts = time.strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"[Supervisor] Run finished at {end_ts} "
                f"with return code {result.returncode}"
            )

        except Exception as exc:
            # Catch anything ugly from subprocess itself
            print(f"[Supervisor] ERROR while running child script: {exc!r}")

        # Sleep regardless of success or failure
        print(f"[Supervisor] Sleeping {SLEEP_SECONDS} seconds before next run...")
        try:
            time.sleep(SLEEP_SECONDS)
        except KeyboardInterrupt:
            # If you want this truly unkillable, remove this block.
            print("[Supervisor] Received KeyboardInterrupt, exiting cleanly.")
            break


if __name__ == "__main__":
    main()
