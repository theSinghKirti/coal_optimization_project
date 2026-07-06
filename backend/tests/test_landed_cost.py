"""Landed Cost calculation and validation tests."""


def _create_plant(client, code):
    return client.post("/api/v1/plants", json={"plant_code": code, "plant_name": f"Plant {code}"}).json()[
        "id"
    ]


def test_total_landed_cost_is_computed(client):
    plant_id = _create_plant(client, "LC01")
    resp = client.post(
        "/api/v1/landed-costs",
        json={
            "plant_id": plant_id,
            "basic_cost": 1000,
            "freight": 200,
            "taxes": 100,
            "other_cost": 50,
            "effective_from": "2026-01-01",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["total_landed_cost"] == 1350.0


def test_negative_cost_rejected(client):
    plant_id = _create_plant(client, "LC02")
    resp = client.post(
        "/api/v1/landed-costs",
        json={
            "plant_id": plant_id,
            "basic_cost": -100,
            "freight": 200,
            "taxes": 100,
            "other_cost": 0,
            "effective_from": "2026-01-01",
        },
    )
    assert resp.status_code == 422


def test_effective_to_before_effective_from_rejected(client):
    plant_id = _create_plant(client, "LC03")
    resp = client.post(
        "/api/v1/landed-costs",
        json={
            "plant_id": plant_id,
            "basic_cost": 100,
            "freight": 20,
            "taxes": 10,
            "other_cost": 0,
            "effective_from": "2026-02-01",
            "effective_to": "2026-01-01",
        },
    )
    assert resp.status_code == 422
