from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path


def _env_default(key: str, value: str) -> None:
    if key not in os.environ:
        os.environ[key] = value


def _setup_env_defaults() -> None:
    _env_default("SECRET_KEY", "a" * 64)
    _env_default("DATABASE_URL", "postgresql+asyncpg://admin:your_db_password@localhost:5432/moldesign_db")
    _env_default("MINIO_ACCESS_KEY", "admin")
    _env_default("MINIO_SECRET_KEY", "your_minio_password")
    _env_default("MINIO_ENDPOINT", "localhost:9005")
    _env_default("REDIS_URL", "redis://localhost:6379/0")
    _env_default("VINA_EXECUTABLE_PATH", "vina")
    _env_default("MEEKO_PREPARE_RECEPTOR_PATH", "mk_prepare_receptor")
    _env_default("MEEKO_PREPARE_LIGAND_PATH", "mk_prepare_ligand")
    _env_default("MEEKO_EXPORT_PATH", "mk_export")


def _rank(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda x: x[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        avg_rank = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def _pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n == 0:
        return float("nan")
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y, strict=True))
    den_x = math.sqrt(sum((xi - mx) ** 2 for xi in x))
    den_y = math.sqrt(sum((yi - my) ** 2 for yi in y))
    if den_x == 0 or den_y == 0:
        return float("nan")
    return num / (den_x * den_y)


def _spearman(x: list[float], y: list[float]) -> float:
    return _pearson(_rank(x), _rank(y))


def _mean_abs_pct_error(y_true: list[float], y_pred: list[float]) -> float:
    errors: list[float] = []
    for yt, yp in zip(y_true, y_pred, strict=True):
        denom = max(abs(yt), 1e-12)
        errors.append(abs(yt - yp) / denom * 100.0)
    return sum(errors) / len(errors) if errors else float("nan")


async def run_calibration(panel_path: Path, output_path: Path, pchembl_active_threshold: float) -> dict:
    from chem.conformer import generate_conformer
    from chem.validator import validate_smiles
    from core.config import get_settings
    from services.docking.vina_service import run_vina_docking
    from utils.file_handlers import ensure_bucket_exists

    settings = get_settings()
    await ensure_bucket_exists(settings.minio_bucket_poses)

    panel = json.loads(panel_path.read_text(encoding="utf-8"))
    records = panel.get("records", [])

    started_at = datetime.now(UTC)
    accepted: list[dict] = []
    rejected: list[dict] = []

    sem = asyncio.Semaphore(4)  # Ryzen 3 has 4 cores/threads usually, let's use 4 concurrent dockings

    async def dock_molecule(row):
        async with sem:
            smiles = row["canonical_smiles"]
            activity_value = row.get("pchembl_value")
            if activity_value is None:
                activity_value = row.get("p_activity")
            if activity_value is None:
                return {"rejected": {
                        "molecule_id": row.get("molecule_chembl_id") or row.get("bindingdb_monomerid"),
                        "smiles": smiles,
                        "reason": "missing_activity_value",
                    }}

            activity_value = float(activity_value)
            validation = validate_smiles(smiles)
            if not validation.is_valid:
                return {"rejected": {
                        "molecule_id": row.get("molecule_chembl_id") or row.get("bindingdb_monomerid"),
                        "smiles": smiles,
                        "reason": "validation_failed",
                        "errors": validation.errors,
                    }}

            try:
                await generate_conformer(smiles)
                center = (settings.vina_center_x, settings.vina_center_y, settings.vina_center_z)
                size = (settings.vina_size_x, settings.vina_size_y, settings.vina_size_z)
                docking = await run_vina_docking(
                    smiles_hash=validation.smiles_hash,
                    target_pdb_id=settings.default_target_pdb_id,
                    target_chain=settings.default_target_chain,
                    target_center=center,
                    target_size=size,
                    force_redock=True,
                )
                return {"accepted": {
                    "molecule_id": row.get("molecule_chembl_id") or row.get("bindingdb_monomerid"),
                    "canonical_smiles": smiles,
                    "activity_value": activity_value,
                    "predicted_affinity_kcal": float(docking.best_affinity),
                    "predicted_positive_kcal": float(-docking.best_affinity),
                    "parsing_source": docking.parsing_source,
                    "vina_version": docking.vina_version,
                    "vina_random_seed": docking.vina_random_seed,
                    "scientific_warnings": docking.scientific_warnings,
                    "active_label": activity_value >= pchembl_active_threshold,
                }}
            except Exception as docking_exc:
                return {"rejected": {
                    "molecule_id": row.get("molecule_chembl_id") or row.get("bindingdb_monomerid"),
                    "smiles": smiles,
                    "reason": "docking_failed",
                    "error": f"{type(docking_exc).__name__}: {docking_exc}",
                }}

    tasks = [dock_molecule(row) for row in records]
    results = await asyncio.gather(*tasks)

    for res in results:
        if "accepted" in res:
            accepted.append(res["accepted"])
        else:
            rejected.append(res["rejected"])

    y_true = [x["activity_value"] for x in accepted]
    y_pred = [x["predicted_positive_kcal"] for x in accepted]
    metric_spearman = _spearman(y_true, y_pred) if len(accepted) >= 3 else float("nan")
    metric_pearson = _pearson(y_true, y_pred) if len(accepted) >= 3 else float("nan")
    metric_mape = _mean_abs_pct_error(y_true, y_pred) if accepted else float("nan")

    p_range = (max(y_true) - min(y_true)) if len(y_true) >= 2 else 0.0
    panel_criteria = panel.get("criteria", {})

    parsing_sources = sorted({x["parsing_source"] for x in accepted})

    finished_at = datetime.now(UTC)
    report = {
        "calibration": "external_panel_5ht1a",
        "panel_file": str(panel_path),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": (finished_at - started_at).total_seconds(),
        "protocol": {
            "target_pdb_id": settings.default_target_pdb_id,
            "target_chain": settings.default_target_chain,
            # Record actual calibration exhaustiveness, not the restored production value
            "vina_exhaustiveness": settings.vina_calibration_exhaustiveness,
            "vina_num_poses": settings.vina_num_poses,
            "vina_seed": settings.vina_seed,
            "vina_cpu": settings.vina_cpu,
            "strict_science_mode": settings.strict_science_mode,
            "max_consistency_error_pct": settings.docking_max_consistency_error_pct,
        },
        "dataset": {
            "n_input": len(records),
            "n_accepted": len(accepted),
            "n_rejected": len(rejected),
            "pchembl_active_threshold": pchembl_active_threshold,
            "p_activity_range_log_units": round(p_range, 3),
            "p_activity_min": round(min(y_true), 3) if y_true else None,
            "p_activity_max": round(max(y_true), 3) if y_true else None,
            "stratified_sampling": panel_criteria.get("stratified_sampling"),
        },
        "metrics": {
            "spearman_activity_vs_minus_affinity": metric_spearman,
            "pearson_activity_vs_minus_affinity": metric_pearson,
            "mape_pct_activity_vs_minus_affinity": metric_mape,
        },
        "quality_gates": {
            "internal_numeric_consistency_pct": settings.docking_max_consistency_error_pct,
            "primary_metric": "spearman_activity_vs_minus_affinity",
            "spearman_target": ">= 0.3 (weak positive correlation is expected for docking-only)",
            "spearman_target_met": bool(metric_spearman >= 0.3) if not math.isnan(metric_spearman) else False,
            "note": (
                "Spearman es la métrica primaria: mide si el rankeado relativo de moléculas por docking "
                "coincide con el rankeado experimental. MAPE no es indicador primario porque "
                "pIC50 y kcal/mol tienen unidades distintas. "
                "Una calibración con docking puro sin QSAR/MM-GBSA rara vez supera Spearman=0.5 en la literatura."
            ),
        },
        "parsing_sources": parsing_sources,
        "accepted": accepted,
        "rejected": rejected,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate MolDesign docking against external 5-HT1A panel")
    parser.add_argument(
        "--panel",
        type=str,
        default=str(Path("artifacts") / "chembl_5ht1a_panel.json"),
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(Path("artifacts") / "external_calibration_report.json"),
    )
    parser.add_argument("--active-threshold", type=float, default=6.0)
    args = parser.parse_args()

    _setup_env_defaults()
    report = asyncio.run(
        run_calibration(
            panel_path=Path(args.panel),
            output_path=Path(args.output),
            pchembl_active_threshold=args.active_threshold,
        )
    )
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))

    from utils.file_handlers import close_minio_client

    asyncio.run(close_minio_client())


if __name__ == "__main__":
    main()
