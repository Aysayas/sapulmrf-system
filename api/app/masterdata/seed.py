"""Starting values, used by the Alembic migration and the test database. Puroks and storage areas are real Sapul
facts, so they start empty and the administrator enters them."""

from sqlalchemy import Connection, insert, select

from app.masterdata.models import Material, WasteCategory

# RA 9003 categories, plus one for deliveries that arrive unsegregated.
CATEGORIES = ["Biodegradable", "Recyclable", "Residual", "Special waste", "Mixed household"]
# The four materials the approved CV scope covers.
MATERIALS = ["Plastic", "Paper", "Cardboard", "Metal"]


def seed(conn: Connection) -> None:
    for model, names in ((WasteCategory, CATEGORIES), (Material, MATERIALS)):
        existing = set(conn.scalars(select(model.name)))
        rows = [{"name": n} for n in names if n not in existing]
        if rows:
            conn.execute(insert(model), rows)
