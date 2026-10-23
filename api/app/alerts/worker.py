"""Runs the alert checks every 30 seconds. Started by the worker service: python -m app.alerts.worker"""

import sys
import time
from datetime import datetime

from app.alerts.checks import run_checks
from app.core.db import SessionLocal

EVERY_SECONDS = 30


def main() -> int:
    print(f"Alert checks every {EVERY_SECONDS} s.", flush=True)
    while True:
        try:
            with SessionLocal() as db:
                counts = run_checks(db)
            if any(counts.values()):
                print(f"{datetime.now():%H:%M:%S} alerts opened {counts['opened']}, resolved {counts['resolved']}", flush=True)
        except Exception as e:  # keep checking; the database may be restarting
            print(f"{datetime.now():%H:%M:%S} {e}", file=sys.stderr, flush=True)
        time.sleep(EVERY_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
