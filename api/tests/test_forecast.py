import random
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.insights import forecast as fc
from app.insights.models import ALL, Forecast
from app.intake.models import Delivery

MANILA = ZoneInfo("Asia/Manila")
START = date(2026, 9, 1)  # a Tuesday


def history(db, world, kg_for_day, days, start=START, category="Mixed household"):
    """One delivery a day at noon Manila time, weighing kg_for_day(day)."""
    db.add_all([Delivery(code=f"T-{category[:3]}{i}", source_area_id=world["purok1"], category_id=world["cat"][category],
                         weight_kg=kg_for_day(start + timedelta(days=i)), weighed_by="scale",
                         received_at=datetime.combine(start + timedelta(days=i), datetime.min.time(), MANILA).replace(hour=12))
                for i in range(days)])
    db.commit()


def weekly(day):  # Mondays are heavy, the rest steady
    return 30.0 if day.weekday() == 0 else 10.0


def test_the_baseline_carries_the_last_week_forward():
    assert fc.baseline([5, 5, 5, 10, 10, 10, 10, 10, 10, 10]) == [10.0] * 7


def test_ridge_learns_a_weekday_pattern_the_baseline_cannot():
    rnd = random.Random(3)
    days = [START + timedelta(days=i) for i in range(56)]
    y = [weekly(d) + rnd.gauss(0, 1) for d in days]
    ahead = [days[-1] + timedelta(days=h + 1) for h in range(7)]
    truth = [weekly(d) for d in ahead]
    ml, base = fc.ridge(y, days[-1]), fc.baseline(y)
    assert len(ml) == 7 and min(ml) >= 0
    err = lambda p: sum(abs(a - b) for a, b in zip(p, truth, strict=True))  # noqa: E731
    assert err(ml) < err(base) / 2
    monday = ahead.index(next(d for d in ahead if d.weekday() == 0))
    assert ml[monday] > 20 > max(ml[:monday] + ml[monday + 1:])


def test_ridge_never_predicts_negative_kg():
    y = [max(0.0, 40 - i * 1.5) for i in range(40)]  # falling fast towards zero
    assert min(fc.ridge(y, START + timedelta(days=39))) >= 0


def test_no_forecasts_before_enough_days_of_records(db, world):
    history(db, world, weekly, 20)
    assert not fc.ready(db, START + timedelta(days=20))
    assert fc.make_forecasts(db, START + timedelta(days=20)) == 0


def test_forecasts_are_saved_once_per_day_for_each_category_and_model(db, world):
    history(db, world, weekly, 35)
    made_on = START + timedelta(days=35)
    n = fc.make_forecasts(db, made_on)
    cats = len(fc.categories(db))
    assert n == cats * 2 * 7
    assert fc.make_forecasts(db, made_on) == 0  # running again changes nothing
    assert db.scalar(select(func.count(Forecast.id))) == n
    all_ml = db.scalars(select(Forecast.kg).where(Forecast.category_id == ALL, Forecast.model == "ml")
                        .order_by(Forecast.for_day)).all()
    assert len(all_ml) == 7 and all(kg >= 0 for kg in all_ml)


def test_errors_only_use_forecasts_made_before_the_day(db, world):
    history(db, world, weekly, 45)
    for i in range(35, 45):  # replay: each day forecast from the days before it
        fc.make_forecasts(db, START + timedelta(days=i))
    today = START + timedelta(days=45)
    rows = fc.comparison(db, ALL, "ml", today - timedelta(days=10), today - timedelta(days=1))
    assert len(rows) == 10 and all(actual == weekly(day) for day, _, actual in rows)
    errs = fc.errors(db, ALL, today, 7)
    assert errs["ml"] < errs["baseline"]  # the weekday pattern is learnable
    assert fc.best_model(errs) == "ml"


def test_the_baseline_stays_in_use_until_ml_beats_it():
    assert fc.best_model({"baseline": 9.0, "ml": None}) == "baseline"
    assert fc.best_model({"baseline": 9.0, "ml": 12.0}) == "baseline"
    assert fc.best_model({"baseline": 9.0, "ml": 6.0}) == "ml"
    assert fc.mape([(START, 12.0, 10.0), (START, 9.0, 10.0), (START, 5.0, 0.0)]) == 15.0  # zero-actual days skipped
