"""Deterministic PuLP/CBC coal-allocation optimizer.

Objective
---------
Minimize total landed coal procurement cost, subject to:
  - Allocated Quantity <= Active Contract Monthly ACQ Cap  (per FSA/Bridge source)
  - Plant Allocation + Market Top-up >= Plant Monthly Demand  (per plant)

Variable Cost is intentionally NOT used here; only Landed Cost drives the
objective, per the platform's domain rules. Variable Cost is reporting-only.

Never invents suppliers, contracts, or costs: any contract source without a
resolvable landed cost is excluded from the model (and reported back as a
data-quality note) rather than assigned a made-up number. Only the market
top-up may use the configurable fallback cost, and only when no landed cost
figure exists at all for that plant.
"""

from dataclasses import dataclass, field

import pulp


@dataclass
class ContractSource:
    source_id: str  # FSAConstraint.id as str
    plant_id: str
    supplier_id: str | None
    monthly_cap_mt: float
    landed_cost_per_mt: float
    constraint_type: str  # "FSA" | "BRIDGE_LINKAGE"


@dataclass
class PlantDemand:
    plant_id: str
    monthly_demand_mt: float
    market_topup_cost_per_mt: float


@dataclass
class AllocationLine:
    plant_id: str
    supplier_id: str | None
    allocation_type: str  # fsa|bridge_linkage|market_topup
    quantity_mt: float
    unit_cost: float
    estimated_cost: float
    acq_utilization_pct: float | None


@dataclass
class SolveResult:
    status: str  # "optimal" | "infeasible" | "no_sources"
    total_estimated_cost: float
    allocations: list[AllocationLine] = field(default_factory=list)


def solve(demands: list[PlantDemand], sources: list[ContractSource]) -> SolveResult:
    if not demands:
        return SolveResult(status="no_sources", total_estimated_cost=0.0)

    problem = pulp.LpProblem("coal_allocation", pulp.LpMinimize)

    sources_by_plant: dict[str, list[ContractSource]] = {}
    for s in sources:
        sources_by_plant.setdefault(s.plant_id, []).append(s)

    allocation_vars: dict[str, pulp.LpVariable] = {}
    for s in sources:
        allocation_vars[s.source_id] = pulp.LpVariable(
            f"alloc_{s.source_id}", lowBound=0, upBound=max(s.monthly_cap_mt, 0)
        )

    topup_vars: dict[str, pulp.LpVariable] = {
        d.plant_id: pulp.LpVariable(f"topup_{d.plant_id}", lowBound=0) for d in demands
    }

    # Objective: minimize total landed cost across contract allocations + market top-up
    objective_terms = []
    for s in sources:
        objective_terms.append(allocation_vars[s.source_id] * s.landed_cost_per_mt)
    for d in demands:
        objective_terms.append(topup_vars[d.plant_id] * d.market_topup_cost_per_mt)
    problem += pulp.lpSum(objective_terms)

    # Demand satisfaction constraint per plant
    for d in demands:
        plant_sources = sources_by_plant.get(d.plant_id, [])
        supply_terms = [allocation_vars[s.source_id] for s in plant_sources]
        problem += (
            pulp.lpSum(supply_terms) + topup_vars[d.plant_id] >= d.monthly_demand_mt,
            f"demand_{d.plant_id}",
        )

    solver = pulp.PULP_CBC_CMD(msg=False)
    problem.solve(solver)

    pulp_status = pulp.LpStatus[problem.status]
    if pulp_status != "Optimal":
        return SolveResult(status=pulp_status.lower(), total_estimated_cost=0.0)

    allocations: list[AllocationLine] = []
    total_cost = 0.0

    for s in sources:
        qty = allocation_vars[s.source_id].value() or 0.0
        if qty <= 1e-6:
            continue
        cost = qty * s.landed_cost_per_mt
        total_cost += cost
        utilization = (qty / s.monthly_cap_mt * 100) if s.monthly_cap_mt > 0 else None
        allocations.append(
            AllocationLine(
                plant_id=s.plant_id,
                supplier_id=s.supplier_id,
                allocation_type=s.constraint_type.lower(),
                quantity_mt=qty,
                unit_cost=s.landed_cost_per_mt,
                estimated_cost=cost,
                acq_utilization_pct=utilization,
            )
        )

    for d in demands:
        qty = topup_vars[d.plant_id].value() or 0.0
        if qty <= 1e-6:
            continue
        cost = qty * d.market_topup_cost_per_mt
        total_cost += cost
        allocations.append(
            AllocationLine(
                plant_id=d.plant_id,
                supplier_id=None,
                allocation_type="market_topup",
                quantity_mt=qty,
                unit_cost=d.market_topup_cost_per_mt,
                estimated_cost=cost,
                acq_utilization_pct=None,
            )
        )

    return SolveResult(status="optimal", total_estimated_cost=total_cost, allocations=allocations)
