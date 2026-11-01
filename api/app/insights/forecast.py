"""Intake forecasts: a moving-average baseline and a Ridge regression, side by side, scored on saved forecasts.

A forecast made on day D only uses deliveries up to D-1, and predicts D..D+6. Its error is measured later from the
forecast made on the day itself (1 day ahead), so scores are never computed with hindsight."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Literal

import numpy as np
from sklearn.linear_model import Ridge
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session as DbSession

from app.core.config import settings
from app.insights.models import ALL, Forecast
from app.intake.models import Delivery
from app.masterdata.models import WasteCategory
from app.settings import service as ranges

HORIZON = 7
TRAIN_DAYS = 90  # history used to fit each forecast
MODELS = ("baseline", "ml")
RIDGE_MIN_DAYS = 28  # with fewer, its weekday and trend inputs swing wildly
PICK_MIN_DAYS = 5  # scored days a model needs before it can be chosen


def _local_day():
    return func.date(func.timezone(settings.timezone, Delivery.received_at))


def daily_kg(db: DbSession, category_id: int, start: date, end: date) -> list[float]:
    """kg received per Manila day from start to end (inclusive); days with no deliveries are 0."""
    day = _local_day()
    # The received_at bounds let the index narrow it down, a day wider than Manila's offset; the day filter is exact.
    first = datetime.combine(start, time.min, UTC) - timedelta(days=1)
    last = datetime.combine(end, time.min, UTC) + timedelta(days=2)
    q = (select(day, func.sum(Delivery.weight_kg)).where(Delivery.received_at >= first, Delivery.received_at < last, day >= start,
                                                         day <= end).group_by(day))
    if category_id != ALL:
        q = q.where(Delivery.category_id == category_id)
    got = {d: float(kg) for d, kg in db.execute(q)}
    return [got.get(start + timedelta(days=i), 0.0) for i in range((end - start).days + 1)]


def days_of_records(db: DbSession, upto: date) -> int:
    """Distinct Manila days with at least one delivery, up to and including upto."""
    day = _local_day()
    return db.scalar(select(func.count(func.distinct(day))).where(day <= upto)) or 0


def first_day(db: DbSession) -> date | None:
    return db.scalar(select(func.min(_local_day())))


# ---- the two models (pure functions on a daily series, oldest first, ending the day before the first prediction)


def capped(y: list[float]) -> list[float]:
    """Holds down a day far above the same weekday in nearby weeks, so one typo can't throw off a week of forecasts.
    Comparing like with like keeps a busy Saturday, and a lasting rise passes once it fills most of the window."""
    out = []
    for i, v in enumerate(y):
        near = np.array(y[max(i % 7, i - 28) : i + 29 : 7])
        middle = float(np.median(near))
        spread = max(float(np.median(np.abs(near - middle))), 0.1 * middle)
        out.append(min(v, middle + 5 * spread) if len(near) >= 3 and middle > 0 else v)
    return out


def baseline(y: list[float], horizon: int = HORIZON) -> list[float]:
    """7-day moving average, carried forward."""
    level = float(np.mean(y[-7:])) if y else 0.0
    return [round(level, 2)] * horizon


def _features(series: list[float], t: int, day: date) -> list[float]:
    """Day t's inputs: weekday (one-hot), the 7- and 28-day averages before it, and a trend index (months)."""
    dow = [0.0] * 7
    dow[day.weekday()] = 1.0
    ma7 = float(np.mean(series[max(0, t - 7) : t]))
    ma28 = float(np.mean(series[max(0, t - 28) : t]))
    return [*dow, ma7, ma28, t / 30]


def ridge(y: list[float], last_day: date, horizon: int = HORIZON) -> list[float]:
    """Ridge regression on weekday, recent averages and trend; predicts one day at a time, feeding predictions back."""
    if len(y) < RIDGE_MIN_DAYS:
        return baseline(y, horizon)
    first = last_day - timedelta(days=len(y) - 1)
    rows = range(7, len(y))
    x = np.array([_features(y, t, first + timedelta(days=t)) for t in rows])
    model = Ridge(alpha=1.0).fit(x, np.array([y[t] for t in rows]))
    series, out = list(y), []
    for _ in range(horizon):
        t = len(series)
        kg = max(0.0, float(model.predict(np.array([_features(series, t, first + timedelta(days=t))]))[0]))
        series.append(kg)
        out.append(round(kg, 2))
    return out


# ---- saving and scoring


def categories(db: DbSession) -> list[int]:
    return [ALL, *db.scalars(select(WasteCategory.id).where(WasteCategory.active).order_by(WasteCategory.id))]


def ready(db: DbSession, made_on: date) -> bool:
    return days_of_records(db, made_on - timedelta(days=1)) >= ranges.get(db).prediction_min_days


def make_forecasts(db: DbSession, made_on: date) -> int:
    """Saves both models' next-7-day forecasts for every category. Does nothing for rows that already exist."""
    if not ready(db, made_on):
        return 0
    end = made_on - timedelta(days=1)
    start = max(first_day(db) or end, end - timedelta(days=TRAIN_DAYS - 1))
    rows = []
    for cat in categories(db):
        y = capped(daily_kg(db, cat, start, end))
        for model, kgs in (("baseline", baseline(y)), ("ml", ridge(y, end))):
            rows += [
                {"made_on": made_on, "for_day": made_on + timedelta(days=h), "category_id": cat, "model": model, "kg": kg}
                for h, kg in enumerate(kgs)
            ]
    added = db.scalars(
        insert(Forecast).values(rows).on_conflict_do_nothing(constraint="uq_forecasts").returning(Forecast.id)
    ).all()
    db.commit()
    return len(added)


def comparison(db: DbSession, category_id: int, model: str, start: date, end: date) -> list[tuple[date, float, float]]:
    """(day, predicted 1 day ahead, actual) for the days from start to end that have a forecast."""
    predicted = dict(tuple(r) for r in
        db.execute(
            select(Forecast.for_day, Forecast.kg).where(
                Forecast.made_on == Forecast.for_day,
                Forecast.category_id == category_id,
                Forecast.model == model,
                Forecast.for_day >= start,
                Forecast.for_day <= end,
            )
        ).all()
    )
    actual = daily_kg(db, category_id, start, end)
    return [
        (start + timedelta(days=i), predicted[start + timedelta(days=i)], kg)
        for i, kg in enumerate(actual)
        if start + timedelta(days=i) in predicted
    ]


def mape(rows: list[tuple[date, float, float]]) -> float | None:
    """Mean absolute % error, skipping days with no actual intake (a % of zero means nothing)."""
    errs = [abs(p - a) / a for _, p, a in rows if a > 0]
    return round(float(np.mean(errs)) * 100, 1) if errs else None


def wape(rows: list[tuple[date, float, float]]) -> float | None:
    """Total kg error over total kg, so closed days count and a small day can't outweigh a big one."""
    actual = sum(a for _, _, a in rows)
    return round(sum(abs(p - a) for _, p, a in rows) / actual * 100, 1) if actual > 0 else None


def pick_model(db: DbSession, category_id: int, today: date) -> Literal["baseline", "ml"]:
    """Chosen on days 8 to 14 back, so the last 7 days shown are a fair test of the choice."""
    start, end = today - timedelta(days=14), today - timedelta(days=8)
    rows = {m: comparison(db, category_id, m, start, end) for m in MODELS}
    return best_model({m: wape(r) if len(r) >= PICK_MIN_DAYS else None for m, r in rows.items()})


def errors(db: DbSession, category_id: int, today: date, days: int) -> dict[str, float | None]:
    """Each model's MAPE over the `days` full days before today."""
    start, end = today - timedelta(days=days), today - timedelta(days=1)
    return {m: mape(comparison(db, category_id, m, start, end)) for m in MODELS}


def best_model(errs: dict[str, float | None]) -> Literal["baseline", "ml"]:
    """The model with the lower error; the baseline until the ML model has a score that beats it."""
    ml, base = errs.get("ml"), errs.get("baseline")
    return "ml" if ml is not None and (base is None or ml < base) else "baseline"
