"""Master data uniqueness and alias-normalization tests."""


def test_duplicate_plant_code_rejected(client):
    resp1 = client.post("/api/v1/plants", json={"plant_code": "MD01", "plant_name": "Plant One"})
    assert resp1.status_code == 201
    resp2 = client.post("/api/v1/plants", json={"plant_code": "MD01", "plant_name": "Plant Duplicate"})
    assert resp2.status_code == 409


def test_alias_must_reference_existing_plant(client):
    resp = client.post(
        "/api/v1/plants/aliases",
        json={"plant_id": "00000000-0000-0000-0000-000000000000", "alias_name": "Ghost Plant"},
    )
    assert resp.status_code == 404


def test_duplicate_alias_rejected(client):
    plant = client.post("/api/v1/plants", json={"plant_code": "MD02", "plant_name": "Plant Two"}).json()
    resp1 = client.post(
        "/api/v1/plants/aliases", json={"plant_id": plant["id"], "alias_name": "Plant Two Alt"}
    )
    assert resp1.status_code == 201
    resp2 = client.post(
        "/api/v1/plants/aliases", json={"plant_id": plant["id"], "alias_name": "Plant Two Alt"}
    )
    assert resp2.status_code == 409


def test_alias_static_route_not_shadowed_by_plant_id_route(client):
    """Regression test: GET /plants/aliases must not be swallowed by the
    dynamic GET /plants/{plant_id} route (which would try to parse "aliases"
    as a UUID and fail validation).
    """
    plant = client.post("/api/v1/plants", json={"plant_code": "MD03", "plant_name": "Plant Three"}).json()
    client.post("/api/v1/plants/aliases", json={"plant_id": plant["id"], "alias_name": "Plant Three Alt"})

    resp = client.get("/api/v1/plants/aliases", params={"plant_id": plant["id"]})
    assert resp.status_code == 200
    assert resp.json()[0]["alias_name"] == "Plant Three Alt"

    resp_unfiltered = client.get("/api/v1/plants/aliases")
    assert resp_unfiltered.status_code == 200
