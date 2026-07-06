"""FSA / Bridge Linkage constraint validation tests."""


def _create_plant(client, code):
    return client.post("/api/v1/plants", json={"plant_code": code, "plant_name": f"Plant {code}"}).json()[
        "id"
    ]


def test_end_date_before_start_date_rejected(client):
    plant_id = _create_plant(client, "FSA01")
    resp = client.post(
        "/api/v1/fsa-constraints",
        json={
            "constraint_type": "FSA",
            "plant_id": plant_id,
            "annual_contract_quantity_mt": 100000,
            "contract_start_date": "2026-06-01",
            "contract_end_date": "2026-01-01",
        },
    )
    assert resp.status_code == 422


def test_valid_constraint_created(client):
    plant_id = _create_plant(client, "FSA02")
    resp = client.post(
        "/api/v1/fsa-constraints",
        json={
            "constraint_type": "FSA",
            "plant_id": plant_id,
            "annual_contract_quantity_mt": 100000,
            "contract_start_date": "2026-01-01",
            "contract_end_date": "2026-12-31",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["is_active"] is True
