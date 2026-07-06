"""Coal-allocation optimization engine tests: demand proxy, ACQ cap, market
top-up, and missing-data handling.
"""


def _setup_plant_with_stock(client, code, *, closing_stock, consumption):
    plant = client.post("/api/v1/plants", json={"plant_code": code, "plant_name": f"Plant {code}"}).json()
    client.post(
        "/api/v1/daily-stock",
        json={
            "plant_id": plant["id"],
            "report_date": "2026-01-15",
            "opening_stock_mt": closing_stock + consumption,
            "receipt_mt": 0,
            "consumption_mt": consumption,
            "closing_stock_mt": closing_stock,
        },
    )
    return plant["id"]


def test_optimization_allocates_from_fsa_using_landed_cost(client):
    # demand = max(0, 30*100 - 500) = 2500 MT
    plant_id = _setup_plant_with_stock(client, "OPT01", closing_stock=500, consumption=100)

    client.post(
        "/api/v1/fsa-constraints",
        json={
            "constraint_type": "FSA",
            "plant_id": plant_id,
            "annual_contract_quantity_mt": 365000,  # -> monthly cap 30000, plenty
            "contract_start_date": "2026-01-01",
            "contract_end_date": "2026-12-31",
        },
    )
    client.post(
        "/api/v1/landed-costs",
        json={
            "plant_id": plant_id,
            "basic_cost": 1000,
            "freight": 200,
            "taxes": 100,
            "other_cost": 0,
            "effective_from": "2026-01-01",
        },
    )

    resp = client.post("/api/v1/optimization/run", json={"plant_ids": [plant_id]})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "completed"
    assert body["solver_status"] == "optimal"

    fsa_allocations = [a for a in body["allocations"] if a["allocation_type"] == "fsa"]
    assert len(fsa_allocations) == 1
    assert fsa_allocations[0]["quantity_mt"] == 2500.0
    assert fsa_allocations[0]["unit_cost"] == 1300.0  # total landed cost
    assert body["total_estimated_cost"] == 2500.0 * 1300.0


def test_market_topup_used_when_acq_cap_insufficient(client):
    # demand = max(0, 30*100 - 500) = 2500 MT, but monthly cap far smaller.
    plant_id = _setup_plant_with_stock(client, "OPT02", closing_stock=500, consumption=100)

    client.post(
        "/api/v1/fsa-constraints",
        json={
            "constraint_type": "FSA",
            "plant_id": plant_id,
            "annual_contract_quantity_mt": 12000,  # -> monthly cap ~986 MT
            "contract_start_date": "2026-01-01",
            "contract_end_date": "2026-12-31",
        },
    )
    client.post(
        "/api/v1/landed-costs",
        json={
            "plant_id": plant_id,
            "basic_cost": 1000,
            "freight": 0,
            "taxes": 0,
            "other_cost": 0,
            "effective_from": "2026-01-01",
        },
    )

    resp = client.post("/api/v1/optimization/run", json={"plant_ids": [plant_id]})
    assert resp.status_code == 201
    body = resp.json()

    topup = [a for a in body["allocations"] if a["allocation_type"] == "market_topup"]
    assert len(topup) == 1
    assert topup[0]["unit_cost"] == 1000 * 1.20
    fsa = [a for a in body["allocations"] if a["allocation_type"] == "fsa"][0]
    assert fsa["acq_utilization_pct"] == 100.0


def test_incomplete_data_when_no_landed_cost_and_no_fallback(client):
    plant_id = _setup_plant_with_stock(client, "OPT03", closing_stock=500, consumption=100)
    client.post(
        "/api/v1/fsa-constraints",
        json={
            "constraint_type": "FSA",
            "plant_id": plant_id,
            "annual_contract_quantity_mt": 365000,
            "contract_start_date": "2026-01-01",
            "contract_end_date": "2026-12-31",
        },
    )
    # No landed cost created at all, and fallback defaults to 0 in test settings.

    resp = client.post("/api/v1/optimization/run", json={"plant_ids": [plant_id]})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "incomplete_data"


def test_no_shortfall_returns_completed_with_no_allocation(client):
    # closing stock covers 30 days of consumption easily -> demand is 0.
    plant_id = _setup_plant_with_stock(client, "OPT04", closing_stock=100000, consumption=10)

    resp = client.post("/api/v1/optimization/run", json={"plant_ids": [plant_id]})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "completed"
    assert body["allocations"] == []
