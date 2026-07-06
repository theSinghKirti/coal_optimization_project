"""Business-rule tests for the Daily Stock module."""


def _create_plant(client, code="TST1"):
    resp = client.post("/api/v1/plants", json={"plant_code": code, "plant_name": f"Test Plant {code}"})
    assert resp.status_code == 201
    return resp.json()["id"]


def test_reconciliation_ok_within_tolerance(client):
    plant_id = _create_plant(client, "DS01")
    resp = client.post(
        "/api/v1/daily-stock",
        json={
            "plant_id": plant_id,
            "report_date": "2026-01-01",
            "opening_stock_mt": 1000,
            "receipt_mt": 100,
            "consumption_mt": 200,
            "closing_stock_mt": 900,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["validation_status"] == "ok"
    assert body["expected_closing_stock_mt"] == 900.0
    assert body["reconciliation_difference_mt"] == 0.0


def test_warning_requires_remarks(client):
    plant_id = _create_plant(client, "DS02")
    resp = client.post(
        "/api/v1/daily-stock",
        json={
            "plant_id": plant_id,
            "report_date": "2026-01-01",
            "opening_stock_mt": 1000,
            "receipt_mt": 100,
            "consumption_mt": 200,
            "closing_stock_mt": 800,  # expected 900, diff -100 -> warning
        },
    )
    assert resp.status_code == 422

    resp2 = client.post(
        "/api/v1/daily-stock",
        json={
            "plant_id": plant_id,
            "report_date": "2026-01-01",
            "opening_stock_mt": 1000,
            "receipt_mt": 100,
            "consumption_mt": 200,
            "closing_stock_mt": 800,
            "remarks": "Manual recount pending",
        },
    )
    assert resp2.status_code == 201
    assert resp2.json()["validation_status"] == "warning"


def test_duplicate_plant_and_date_rejected(client):
    plant_id = _create_plant(client, "DS03")
    payload = {
        "plant_id": plant_id,
        "report_date": "2026-02-01",
        "opening_stock_mt": 500,
        "receipt_mt": 50,
        "consumption_mt": 100,
        "closing_stock_mt": 450,
    }
    first = client.post("/api/v1/daily-stock", json=payload)
    assert first.status_code == 201
    second = client.post("/api/v1/daily-stock", json=payload)
    assert second.status_code == 409


def test_unknown_plant_rejected(client):
    resp = client.post(
        "/api/v1/daily-stock",
        json={
            "plant_id": "00000000-0000-0000-0000-000000000000",
            "report_date": "2026-01-01",
            "opening_stock_mt": 1,
            "receipt_mt": 1,
            "consumption_mt": 1,
            "closing_stock_mt": 1,
        },
    )
    assert resp.status_code == 404


def test_negative_values_rejected(client):
    plant_id = _create_plant(client, "DS04")
    resp = client.post(
        "/api/v1/daily-stock",
        json={
            "plant_id": plant_id,
            "report_date": "2026-01-01",
            "opening_stock_mt": -10,
            "receipt_mt": 1,
            "consumption_mt": 1,
            "closing_stock_mt": 1,
        },
    )
    assert resp.status_code == 422
