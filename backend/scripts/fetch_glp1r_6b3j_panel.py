from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import httpx


BINDINGDB_UNIPROT_GLP1R = "P43220"
BINDINGDB_URL = "https://bindingdb.org/rest/getLigandsByUniprot"


def _to_float(value: str | int | float | None) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _p_activity_from_nm(affinity_nm: float) -> float:
    return 9.0 - math.log10(affinity_nm)


def fetch_panel(limit: int, affinity_cutoff_nm: int, allowed_types: set[str]) -> dict:
    started_at = datetime.now(UTC)

    params = {
        "uniprot": f"{BINDINGDB_UNIPROT_GLP1R};{affinity_cutoff_nm}",
        "response": "application/json",
    }

    print(f"Fetching data from BindingDB for UniProt {BINDINGDB_UNIPROT_GLP1R}...")
    response = httpx.get(BINDINGDB_URL, params=params, timeout=120.0)
    response.raise_for_status()
    payload = response.json()

    root = payload.get("getLindsByUniprotResponse", {})
    affinities = root.get("bdb.affinities", [])
    if isinstance(affinities, dict):
        affinities = [affinities]

    selected_by_smiles: dict[str, dict] = {}
    skipped = {
        "missing_smiles": 0,
        "invalid_affinity": 0,
        "affinity_type_filtered": 0,
    }

    for row in affinities:
        smiles = row.get("bdb.smile")
        if not smiles:
            skipped["missing_smiles"] += 1
            continue

        affinity_type = str(row.get("bdb.affinity_type", "")).upper()
        if affinity_type not in allowed_types:
            skipped["affinity_type_filtered"] += 1
            continue

        affinity_nm = _to_float(row.get("bdb.affinity"))
        if affinity_nm is None or affinity_nm <= 0:
            skipped["invalid_affinity"] += 1
            continue

        record = {
            "source": "BindingDB",
            "uniprot": BINDINGDB_UNIPROT_GLP1R,
            "canonical_smiles": smiles,
            "bindingdb_monomerid": row.get("bdb.monomerid"),
            "affinity_type": affinity_type,
            "affinity_nm": affinity_nm,
            "p_activity": _p_activity_from_nm(affinity_nm),
        }

        existing = selected_by_smiles.get(smiles)
        if existing is None or affinity_nm < existing["affinity_nm"]:
            selected_by_smiles[smiles] = record

    # Stratified 3-tier sampling
    all_records = sorted(selected_by_smiles.values(), key=lambda x: x["affinity_nm"])
    strong = [r for r in all_records if r["affinity_nm"] <= 100.0]        # pIC50 >= 7.0
    moderate = [r for r in all_records if 100.0 < r["affinity_nm"] <= 10_000.0]  # pIC50 5.0-7.0
    weak = [r for r in all_records if r["affinity_nm"] > 10_000.0]        # pIC50 < 5.0

    print(f"Found: {len(strong)} strong, {len(moderate)} moderate, {len(weak)} weak.")

    n_per_tier = limit // 3
    n_extra = limit - (n_per_tier * 3)

    picked_strong = strong[:n_per_tier]
    picked_moderate = moderate[:n_per_tier + n_extra]
    picked_weak = weak[:n_per_tier]

    total_picked = len(picked_strong) + len(picked_moderate) + len(picked_weak)
    if total_picked < limit:
        deficit = limit - total_picked
        remaining = (
            [r for r in strong if r not in picked_strong]
            + [r for r in moderate if r not in picked_moderate]
            + [r for r in weak if r not in picked_weak]
        )
        for r in remaining[:deficit]:
            if r["affinity_nm"] <= 100.0:
                picked_strong.append(r)
            elif r["affinity_nm"] <= 10_000.0:
                picked_moderate.append(r)
            else:
                picked_weak.append(r)

    records = sorted(
        picked_strong + picked_moderate + picked_weak,
        key=lambda x: x["affinity_nm"],
    )
    finished_at = datetime.now(UTC)

    return {
        "panel_name": "bindingdb_glp1r_external_calibration",
        "target_uniprot": BINDINGDB_UNIPROT_GLP1R,
        "target_pdb_id": "6B3J",
        "n_selected": len(records),
        "records": records,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch curated external GLP-1R panel from BindingDB")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--output", type=str, default=str(Path("artifacts") / "bindingdb_glp1r_6b3j_panel.json"))
    args = parser.parse_args()

    report = fetch_panel(limit=args.limit, affinity_cutoff_nm=1000000, allowed_types={"KI", "KD", "IC50"})

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {report['n_selected']} molecules to {out_path}")


if __name__ == "__main__":
    main()
