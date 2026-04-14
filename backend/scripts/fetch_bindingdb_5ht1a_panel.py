from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import httpx


BINDINGDB_UNIPROT_5HT1A = "P35355"
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
        "uniprot": f"{BINDINGDB_UNIPROT_5HT1A};{affinity_cutoff_nm}",
        "response": "application/json",
    }

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
            "uniprot": BINDINGDB_UNIPROT_5HT1A,
            "canonical_smiles": smiles,
            "bindingdb_monomerid": row.get("bdb.monomerid"),
            "affinity_type": affinity_type,
            "affinity_nm": affinity_nm,
            "p_activity": _p_activity_from_nm(affinity_nm),
        }

        existing = selected_by_smiles.get(smiles)
        if existing is None or affinity_nm < existing["affinity_nm"]:
            selected_by_smiles[smiles] = record

    # Stratified 3-tier sampling for maximum dynamic range.
    # Tier 1: Strong binders (<100 nM, pIC50 > 7.0) — tight actives
    # Tier 2: Moderate binders (100 nM–10 µM, pIC50 5.0–7.0) — moderate actives
    # Tier 3: Weak/inactive (>10 µM, pIC50 < 5.0) — decoys / inactives
    # Warren et al. (2006) recommends ≥30 molecules for statistical power.
    # Target: ≥4 log units range → enables meaningful Spearman correlation.
    all_records = sorted(selected_by_smiles.values(), key=lambda x: x["affinity_nm"])
    strong = [r for r in all_records if r["affinity_nm"] <= 100.0]        # pIC50 >= 7.0
    moderate = [r for r in all_records if 100.0 < r["affinity_nm"] <= 10_000.0]  # pIC50 5.0-7.0
    weak = [r for r in all_records if r["affinity_nm"] > 10_000.0]        # pIC50 < 5.0

    # Distribute evenly across tiers, fill deficits from neighbors
    n_per_tier = limit // 3
    n_extra = limit - (n_per_tier * 3)  # remainder goes to moderate to maximize mid-range coverage

    picked_strong = strong[:n_per_tier]
    picked_moderate = moderate[:n_per_tier + n_extra]
    picked_weak = weak[:n_per_tier]

    # Fill deficits from over-represented tiers
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
    tier_counts = {
        "strong_lt_100nM": len(picked_strong),
        "moderate_100nM_10uM": len(picked_moderate),
        "weak_gt_10uM": len(picked_weak),
    }
    finished_at = datetime.now(UTC)

    p_values = [r["p_activity"] for r in records]
    p_range = max(p_values) - min(p_values) if len(p_values) >= 2 else 0.0

    return {
        "panel_name": "bindingdb_5ht1a_external_calibration",
        "target_uniprot": BINDINGDB_UNIPROT_5HT1A,
        "target_pdb_id": "7E2Y",
        "criteria": {
            "affinity_cutoff_nm": affinity_cutoff_nm,
            "allowed_affinity_types": sorted(allowed_types),
            "max_unique_smiles": limit,
            "deduplication": "best_affinity_per_smiles",
            "stratified_sampling": "3-tier: strong (<100 nM) + moderate (100 nM–10 µM) + weak (>10 µM)",
            "tier_counts": tier_counts,
            "p_activity_definition": "p = 9 - log10(affinity_nM)",
            "p_activity_range_log_units": round(p_range, 3),
        },
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": (finished_at - started_at).total_seconds(),
        "skipped_counts": skipped,
        "n_selected": len(records),
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch curated external 5-HT1A panel from BindingDB")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--affinity-cutoff-nm", type=int, default=1000000)  # 1 mM to capture inactives
    parser.add_argument("--types", type=str, default="KI,KD,IC50")
    parser.add_argument(
        "--output",
        type=str,
        default=str(Path("artifacts") / "bindingdb_5ht1a_panel.json"),
    )
    args = parser.parse_args()

    allowed_types = {t.strip().upper() for t in args.types.split(",") if t.strip()}
    report = fetch_panel(
        limit=args.limit,
        affinity_cutoff_nm=args.affinity_cutoff_nm,
        allowed_types=allowed_types,
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"n_selected": report["n_selected"], "output": str(out_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
