"""Runs the alert checks every 30 seconds, and saves the day's intake forecasts once a Manila day.
Started by the worker service: python -m app.alerts.worker"""

import sys
import time
import traceback
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import update

from app.alerts.checks import run_checks
from app.core.config import settings
from app.core.db import SessionLocal
from app.insights.forecast import make_forecasts
from app.settings.models import Settings

EVERY_SECONDS = 30


def main() -> int:
    print(f"Alert checks every {EVERY_SECONDS} s; forecasts once a day.", flush=True)
    forecast_day = None
    while True:
        try:
            with SessionLocal() as db:
                counts = run_checks(db)
                db.execute(update(Settings).values(worker_seen_at=datetime.now(UTC)))
                db.commit()
                today = datetime.now(ZoneInfo(settings.timezone)).date()
                if today != forecast_day:  # make_forecasts skips rows that exist, so a restart doesn't duplicate
                    added = make_forecasts(db, today)
                    forecast_day = today
                    print(f"{datetime.now():%H:%M:%S} forecasts for {today}: {added} saved", flush=True)
            if any(counts.values()):
                print(f"{datetime.now():%H:%M:%S} alerts opened {counts['opened']}, resolved {counts['resolved']}", flush=True)
        except Exception:  # keep checking; the database may be restarting
            print(f"{datetime.now():%H:%M:%S} check failed", file=sys.stderr, flush=True)
            traceback.print_exc()
        time.sleep(EVERY_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
