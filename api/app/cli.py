"""Admin commands. Run inside the api container:

docker compose exec api python -m app.cli create-admin
"""

import argparse
import csv
import getpass
import re
import sys
from pathlib import Path

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.activity.service import log
from app.alerts.models import Alert, ProblemReport
from app.approvals.models import AdjustmentRequest, Outgoing
from app.compost.models import CompostBatch
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.devices.models import Device
from app.intake.models import Delivery, DeliveryPhoto
from app.masterdata.models import Buyer, Material, SourceArea, StorageArea, WasteCategory
from app.sorting.models import Classification, StockMovement
from app.users.models import User


def create_admin(db: Session, name: str, username: str, password: str) -> User:
    username = username.strip().lower()  # same rule as the Users screen
    if not re.fullmatch(r"[a-z0-9._-]{3,60}", username):
        raise ValueError("Usernames are 3–60 characters: letters, numbers, dot, dash or underscore.")
    if not name.strip():
        raise ValueError("Enter a full name.")
    if len(password) < 8:
        raise ValueError("Use at least 8 characters.")
    if db.scalar(select(User).where(User.username == username)):
        raise ValueError(f"The username {username!r} is already taken.")
    user = User(name=name, username=username, password_hash=hash_password(password), role="admin")
    db.add(user)
    db.flush()
    log(db, None, "Created first administrator", f"{name} ({username})")
    db.commit()
    return user


def remove_test_users(db: Session) -> int:
    """Deletes accounts made by the e2e tests (e2e.<role>.<id>). Keeps e2e.admin and every real account."""
    users = db.scalars(select(User).where(User.username.like("e2e.%.%"))).all()
    for u in users:
        db.delete(u)
    db.commit()
    return len(users)


def remove_test_data(db: Session) -> dict[str, int]:
    """Deletes what the e2e tests create: e2e.<role>.<id> users, 'e2e …' source areas with their deliveries,
    'e2e …' storage areas with their stock, requests and alerts, E2E-… devices, and problem reports about E2E-… devices
    or about those e2e deliveries, camera suggestions from E2E-… devices or about those e2e deliveries,
    and compost batches started by e2e users with their alerts."""
    e2e_batches = select(CompostBatch.id).where(CompostBatch.started_by.in_(select(User.id).where(User.username.like("e2e.%.%"))))
    batch_alerts = db.execute(delete(Alert).where(Alert.kind == "compost", Alert.subject_id.in_(e2e_batches))).rowcount
    # Before the users go: deleting them clears started_by.
    counts = {"compost batches": db.execute(delete(CompostBatch).where(CompostBatch.id.in_(e2e_batches))).rowcount}
    counts["users"] = remove_test_users(db)
    e2e_puroks = select(SourceArea.id).where(func.lower(SourceArea.name).like("e2e %"))
    e2e_areas = select(StorageArea.id).where(func.lower(StorageArea.name).like("e2e %"))
    e2e_devices = select(Device.id).where(Device.code.like("E2E-%"))
    e2e_codes = select(Delivery.code).where(Delivery.source_area_id.in_(e2e_puroks))  # before the deliveries go
    counts["problem reports"] = db.execute(
        delete(ProblemReport).where(or_(ProblemReport.record_ref.like("E2E-%"), ProblemReport.record_ref.in_(e2e_codes),
                                        ProblemReport.device_id.in_(e2e_devices)))
    ).rowcount
    e2e_deliveries = select(Delivery.id).where(Delivery.source_area_id.in_(e2e_puroks))
    counts["camera suggestions"] = db.execute(
        delete(Classification).where(
            or_(Classification.device_id.in_(e2e_devices), Classification.delivery_id.in_(e2e_deliveries))
        )
    ).rowcount
    counts["deliveries"] = db.execute(delete(Delivery).where(Delivery.source_area_id.in_(e2e_puroks))).rowcount
    counts["stock movements"] = db.execute(delete(StockMovement).where(StockMovement.storage_area_id.in_(e2e_areas))).rowcount
    counts["requests"] = sum(
        db.execute(delete(m).where(m.storage_area_id.in_(e2e_areas))).rowcount for m in (Outgoing, AdjustmentRequest)
    )
    counts["alerts"] = batch_alerts + db.execute(
        delete(Alert).where(
            or_(
                and_(Alert.kind == "storage", Alert.subject_id.in_(e2e_areas)),
                and_(Alert.kind == "device", Alert.subject_id.in_(e2e_devices)),
            )
        )
    ).rowcount
    for label, model in (("source areas", SourceArea), ("storage areas", StorageArea), ("buyers", Buyer)):
        counts[label] = db.execute(delete(model).where(func.lower(model.name).like("e2e %"))).rowcount
    counts["devices"] = db.execute(delete(Device).where(Device.code.like("E2E-%"))).rowcount
    db.commit()
    return counts


def export_photos(db: Session, out: Path) -> int:
    """Every stored drop-off photo, plus labels.csv: what was recorded and what operators confirmed. For labelling
    a waste model (see the kiosk's pc_bridge/TRAINING.md)."""
    out.mkdir(parents=True, exist_ok=True)
    mats = dict(db.execute(select(Material.id, Material.name)).all())
    rows = db.execute(
        select(Delivery, WasteCategory.name, DeliveryPhoto.jpeg)
        .join(DeliveryPhoto, DeliveryPhoto.delivery_id == Delivery.id)
        .join(WasteCategory, WasteCategory.id == Delivery.category_id)
        .order_by(Delivery.id)
    ).all()
    with open(out / "labels.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "code", "received_at", "category", "camera_category", "camera_confidence", "materials"])
        for d, category, jpeg in rows:
            (out / f"{d.code}.jpg").write_bytes(jpeg)
            confirmed = db.execute(
                select(Classification.final_material_id, Classification.suggested_material_id,
                       Classification.not_recyclable)
                .where(Classification.delivery_id == d.id, Classification.confirmed_at.is_not(None))
            ).all()
            materials = sorted({"not recyclable" if nr else mats.get(final or sug, "?") for final, sug, nr in confirmed})
            w.writerow([f"{d.code}.jpg", d.code, d.received_at.isoformat(timespec="seconds"), category,
                        d.cv_category or "", d.cv_confidence if d.cv_confidence is not None else "", ";".join(materials)])
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    ca = sub.add_parser("create-admin", help="create a Barangay Administrator account")
    ca.add_argument("--name", default=None)
    ca.add_argument("--username", default=None)
    sub.add_parser("remove-test-data", help="delete the users, areas and devices the browser tests created")
    ex = sub.add_parser("export-photos", help="write every drop-off photo and labels.csv, for labelling a waste model")
    ex.add_argument("--out", default="exports/photos")
    args = parser.parse_args(argv)

    if args.command == "export-photos":
        with SessionLocal() as db:
            n = export_photos(db, Path(args.out))
        print(f"Exported {n} photos to {Path(args.out).resolve()} (labels.csv lists what each one is)")
        return 0

    if args.command == "remove-test-data":
        with SessionLocal() as db:
            counts = remove_test_data(db)
        print("Removed test data: " + ", ".join(f"{n} {what}" for what, n in counts.items()))
        return 0

    name = args.name or input("Full name: ").strip()
    username = args.username or input("Username: ").strip()
    password = getpass.getpass("Password (8+ characters): ")
    if password != getpass.getpass("Repeat password: "):
        print("The passwords don't match.", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        try:
            create_admin(db, name, username, password)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 1
    print(f"Administrator {username!r} created. Log in at http://127.0.0.1:5174")
    return 0


if __name__ == "__main__":
    sys.exit(main())
