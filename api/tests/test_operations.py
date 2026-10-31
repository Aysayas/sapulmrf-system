from app.access.models import StaffAccess


def deliver(client, world, purok, condition, weight=10.0, dry=6.0):
    d = client.post("/deliveries", json={"source_area_id": world[purok], "category_id": world["cat"]["Mixed household"],
                                         "weight_kg": weight, "weighed_by": "manual"}).json()
    client.post(f"/deliveries/{d['id']}/segregation", json={"condition": condition, "wet_kg": weight - dry, "dry_kg": dry})
    return d


def sort(client, world, d, kg, material="Plastic", area="area_a"):
    rows = [{"material_id": world["mat"][material], "bags": 1, "kg": kg, "storage_area_id": world[area]}]
    assert client.post("/sorting", json={"delivery_id": d["id"], "rows": rows}).status_code == 201


def test_compliance_per_purok(client, world, as_operator):
    deliver(client, world, "purok1", "segregated")
    deliver(client, world, "purok1", "segregated")
    deliver(client, world, "purok1", "mixed", weight=10, dry=6)
    deliver(client, world, "purok2", "mixed", weight=8, dry=5)
    c = client.get("/operations/segregation?days=7").json()
    rows = {r["source_area"]: r for r in c["rows"]}
    assert rows["Purok 1"] == {"source_area": "Purok 1", "deliveries": 3, "segregated": 2, "pct": 67}
    assert rows["Purok 2"]["pct"] == 0
    assert c["deliveries"] == 4 and c["pct"] == 50
    assert c["wet_kg_separated"] == 4 + 3  # wet from the two mixed deliveries


def test_inventory_is_the_sum_of_the_ledger(client, world, as_operator):
    sort(client, world, deliver(client, world, "purok1", "mixed"), 4.0)
    sort(client, world, deliver(client, world, "purok2", "mixed"), 2.5)
    inv = client.get("/operations/inventory").json()
    area_a = next(a for a in inv["areas"] if a["name"] == "Area A")
    assert area_a["kg"] == 6.5 and area_a["pct"] == 1  # 6.5 of 500 kg
    plastic = next(r for r in inv["stock"] if r["material"] == "Plastic")
    assert plastic["kg"] == 6.5 and plastic["bags"] == 2


def test_intake_list_filters_and_searches(client, world, as_operator):
    deliver(client, world, "purok1", "mixed")
    d2 = deliver(client, world, "purok2", "mixed")
    items = client.get("/operations/intake?days=1").json()
    assert len(items) == 2 and items[0]["code"] == d2["code"]  # newest first
    assert [i["source_area"] for i in client.get("/operations/intake?q=purok 2").json()] == ["Purok 2"]
    assert len(client.get(f"/operations/intake?q={d2['code']}").json()) == 1


def test_overview_matches_the_records(client, world, as_operator):
    sort(client, world, deliver(client, world, "purok1", "segregated", weight=12, dry=7), 5)
    client.post("/deliveries", json={"source_area_id": world["purok2"], "category_id": world["cat"]["Residual"],
                                     "weight_kg": 3, "weighed_by": "manual"})
    o = client.get("/overview").json()
    assert o["today_deliveries"] == 2 and o["today_kg"] == 15
    assert o["awaiting_segregation"] == 1 and o["compliance_week_pct"] == 100
    assert o["in_storage_kg"] == 5 and len(o["intake_14d"]) == 14 and o["intake_14d"][-1]["kg"] == 15


def test_staff_need_the_grant_for_segregation_and_camera(client, world, make_user, login, db):
    staff = make_user("rreyes", role="staff")
    login("rreyes")
    assert client.get("/operations/intake").status_code == 200
    assert client.get("/operations/segregation").status_code == 403
    assert client.get("/operations/camera").status_code == 403
    db.add(StaffAccess(user_id=staff.id, screen="segregation", granted=True))
    db.commit()
    assert client.get("/operations/segregation").status_code == 200


def test_reads_need_a_session(client):
    assert client.get("/overview").status_code == 401
