"""Idempotent seed script for master data.

Run manually (never invoked automatically at application startup):

    cd backend
    python -m scripts.seed

Safe to run multiple times: every insert first checks whether the record
already exists (by plant_code / alias_name / company name / supplier name)
and skips it if so.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal  # noqa: E402
from app.modules.master_data import repository  # noqa: E402

# A representative (non-exhaustive) set of UPRVUNL generating stations.
# Extend this list as needed; the script is idempotent, so re-running after
# adding entries only inserts the new ones.
PLANTS = [
    {"plant_code": "ANPARA-A", "plant_name": "Anpara-A Thermal Power Station"},
    {"plant_code": "ANPARA-B", "plant_name": "Anpara-B Thermal Power Station"},
    {"plant_code": "ANPARA-C", "plant_name": "Anpara-C Thermal Power Station"},
    {"plant_code": "ANPARA-D", "plant_name": "Anpara-D Thermal Power Station"},
    {"plant_code": "OBRA-B", "plant_name": "Obra-B Thermal Power Station"},
    {"plant_code": "OBRA-C", "plant_name": "Obra-C Thermal Power Station"},
    {"plant_code": "HARDUAGANJ", "plant_name": "Harduaganj Thermal Power Station"},
    {"plant_code": "HARDUAGANJ-EXT", "plant_name": "Harduaganj Ext. Thermal Power Station"},
    {"plant_code": "HARDUAGANJ-EXT-II", "plant_name": "Harduaganj Ext. II Thermal Power Station"},
    {"plant_code": "PARICHHA-EXT", "plant_name": "Parichha - Ext. Thermal Power Station"},
    {"plant_code": "PARICHHA-EXT-STG-II", "plant_name": "Parichha - Ext. Stage - II Thermal Power Station"},
    {"plant_code": "PANKI", "plant_name": "Panki Thermal Power Station"},
    {"plant_code": "JAWAHARPUR", "plant_name": "Jawaharpur Thermal Power Station"},
]

PLANT_ALIASES = {
    "ANPARA-A": [
        "Anpara - A", "Anpara-A", "Anpara 'A'"
    ],
    "ANPARA-B": [
        "Anpara - B", "Anpara-B", "Anpara 'B'"
    ],
    "ANPARA-C": [
        "Anpara-C", "Anpara - C", "Anpara 'C'"
    ],
    "ANPARA-D": [
        "Anpara-D", "Anpara - D", "Anpara 'D'"
    ],
    "OBRA-B": [
        "OBRA-B", "OBRA - B", "Obra B", "Obra-B"
    ],
    "OBRA-C": [
        "OBRA-C", "OBRA - C", "Obra C", "Obra-C", "Obra 'C'"
    ],
    "HARDUAGANJ": [
        "Harduaganj", "Harduaganj TPS", "Kasimpur"
    ],
    "HARDUAGANJ-EXT": [
        "Harduaganj Ext.", "Harduaganj Ext"
    ],
    "HARDUAGANJ-EXT-II": [
        "Harduaganj Ext. II TPS", "Harduaganj Extn II"
    ],
    "PARICHHA-EXT": [
        "Parichha - Ext.", "Parichha Ext.", "Parichha Ext"
    ],
    "PARICHHA-EXT-STG-II": [
        "Parichha - Ext. Stage - II"
    ],
    "PANKI": [
        "Panki", "Panki TPS"
    ],
    "JAWAHARPUR": [
        "JAWAHARPUR", "Jawaharpur", "Jawaharpur TPS"
    ],
}

COAL_COMPANIES = [
    {"name": "Northern Coalfields Limited", "code": "NCL"},
    {"name": "Central Coalfields Limited", "code": "CCL"},
]

SUPPLIERS = [
    {"name": "NCL Direct Linkage", "code": "NCL-DL", "coal_company_code": "NCL"},
    {"name": "CCL Direct Linkage", "code": "CCL-DL", "coal_company_code": "CCL"},
]


def seed_plants(db):
    plant_by_code = {}
    for entry in PLANTS:
        existing = repository.get_plant_by_code(db, entry["plant_code"])
        if existing:
            print(f"  [skip] plant '{entry['plant_code']}' already exists")
            plant_by_code[entry["plant_code"]] = existing
            continue
        plant = repository.create_plant(
            db, plant_code=entry["plant_code"], plant_name=entry["plant_name"], is_active=True
        )
        print(f"  [created] plant '{entry['plant_code']}'")
        plant_by_code[entry["plant_code"]] = plant
    return plant_by_code


def seed_aliases(db, plant_by_code):
    for plant_code, aliases in PLANT_ALIASES.items():
        plant = plant_by_code.get(plant_code)
        if not plant:
            continue
        for alias_name in aliases:
            if repository.get_alias_by_name(db, alias_name):
                print(f"  [skip] alias '{alias_name}' already exists")
                continue
            repository.create_alias(db, plant_id=plant.id, alias_name=alias_name)
            print(f"  [created] alias '{alias_name}' -> {plant_code}")


def seed_coal_companies(db):
    company_by_code = {}
    for entry in COAL_COMPANIES:
        existing = next(
            (
                c
                for c in repository.list_coal_companies(db, limit=500, offset=0)[0]
                if c.code == entry["code"]
            ),
            None,
        )
        if existing:
            print(f"  [skip] coal company '{entry['code']}' already exists")
            company_by_code[entry["code"]] = existing
            continue
        company = repository.create_coal_company(db, name=entry["name"], code=entry["code"])
        print(f"  [created] coal company '{entry['code']}'")
        company_by_code[entry["code"]] = company
    return company_by_code


def seed_suppliers(db, company_by_code):
    for entry in SUPPLIERS:
        existing = next(
            (s for s in repository.list_suppliers(db, limit=500, offset=0)[0] if s.code == entry["code"]),
            None,
        )
        if existing:
            print(f"  [skip] supplier '{entry['code']}' already exists")
            continue
        company = company_by_code.get(entry["coal_company_code"])
        repository.create_supplier(
            db,
            name=entry["name"],
            code=entry["code"],
            coal_company_id=company.id if company else None,
        )
        print(f"  [created] supplier '{entry['code']}'")


def main():
    db = SessionLocal()
    try:
        print("Seeding plants...")
        plant_by_code = seed_plants(db)
        print("Seeding plant aliases...")
        seed_aliases(db, plant_by_code)
        print("Seeding coal companies...")
        company_by_code = seed_coal_companies(db)
        print("Seeding suppliers...")
        seed_suppliers(db, company_by_code)
        db.commit()
        print("Seed completed successfully.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
