from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, pstdev


@dataclass(frozen=True)
class ReferenceMolecule:
    name: str
    smiles: str


REFERENCE_PANEL: list[ReferenceMolecule] = [
    ReferenceMolecule(name="aspirin", smiles="CC(=O)Oc1ccccc1C(=O)O"),
    ReferenceMolecule(name="caffeine", smiles="Cn1cnc2n(C)c(=O)n(C)c(=O)c12"),
    ReferenceMolecule(name="ibuprofen", smiles="CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O"),
]


def _env_default(key: str, value: str) -> None:
    if key not in os.environ:
        os.environ[key] = value


def _setup_env_defaults() -> None:
    _env_default("SECRET_KEY", "a" * 64)
    _env_default("DATABASE_URL", "postgresql+asyncpg://admin:Johan619.@192.168.1.64:5432/moldesign_db")
    _env_default("MINIO_ACCESS_KEY", "admin")
    _env_default("MINIO_SECRET_KEY", "Johan619.")
    _env_default("MINIO_ENDPOINT", "192.168.1.64:9005")
    _env_default("REDIS_URL", "redis://192.168.1.64:6379/0")
    _env_default("VINA_EXECUTABLE_PATH", "vina")
    _env_default("MEEKO_PREPARE_RECEPTOR_PATH", "mk_prepare_receptor")
    _env_default("MEEKO_PREPARE_LIGAND_PATH", "mk_prepare_ligand")
    _env_default("MEEKO_EXPORT_PATH", "mk_export")


async def _run_single(smiles: str, target_pdb_id: str, target_chain: str) -> dict:
    from chem.conformer import generate_conformer
    from chem.properties import calculate_properties
    from chem.validator import validate_smiles_or_raise
    from scoring.engine import calculate_score_breakdown
    from services.docking.vina_service import run_vina_docking

    validation = validate_smiles_or_raise(smiles)
    await generate_conformer(smiles)
    docking = await run_vina_docking(
        smiles_hash=validation.smiles_hash,
        target_pdb_id=target_pdb_id,
        target_chain=target_chain,
        force_redock=True,
    )
    properties = calculate_properties(smiles)
    breakdown = calculate_score_breakdown(docking, properties)

    return {
        "smiles_hash": validation.smiles_hash,
        "canonical_smiles": validation.canonical_smiles,
        "best_affinity": docking.best_affinity,
        "parsing_source": docking.parsing_source,
        "vina_version": docking.vina_version,
        "vina_random_seed": docking.vina_random_seed,
        "scientific_warnings": docking.scientific_warnings,
        "score_total": breakdown.total_score,
        "score_affinity": breakdown.affinity_score,
        "score_adme": breakdown.adme_score,
        "score_druglikeness": breakdown.druglikeness_score,
    }


async def run_benchmark(repeats: int, output_path: Path) -> dict:
    from core.config import get_settings
    from utils.file_handlers import ensure_bucket_exists

    settings = get_settings()
    await ensure_bucket_exists(settings.minio_bucket_poses)

    started_at = datetime.now(UTC)
    rows: list[dict] = []

    for molecule in REFERENCE_PANEL:
        molecule_runs: list[dict] = []
        for run_idx in range(1, repeats + 1):
            result = await _run_single(
                smiles=molecule.smiles,
                target_pdb_id=settings.default_target_pdb_id,
                target_chain=settings.default_target_chain,
            )
            result["run"] = run_idx
            molecule_runs.append(result)
            rows.append({"name": molecule.name, **result})

        affinities = [r["best_affinity"] for r in molecule_runs]
        for r in molecule_runs:
            r["affinity_mean"] = mean(affinities)
            r["affinity_stddev"] = pstdev(affinities)

    finished_at = datetime.now(UTC)

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["name"], []).append(row)

    summary = {}
    for name, values in grouped.items():
        affinities = [v["best_affinity"] for v in values]
        std = pstdev(affinities)
        mu = mean(affinities)
        summary[name] = {
            "affinity_mean": mu,
            "affinity_stddev": std,
            "affinity_range": [min(affinities), max(affinities)],
            "deterministic_with_fixed_seed": std <= 1e-6,
            "n_runs": len(values),
            "parsing_sources": sorted({v["parsing_source"] for v in values}),
            "all_same_seed": len({v["vina_random_seed"] for v in values}) == 1,
        }

    report = {
        "benchmark": "moldesign_reference_panel",
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": (finished_at - started_at).total_seconds(),
        "protocol": {
            "target_pdb_id": settings.default_target_pdb_id,
            "target_chain": settings.default_target_chain,
            "vina_exhaustiveness": settings.vina_exhaustiveness,
            "vina_num_poses": settings.vina_num_poses,
            "vina_cpu": settings.vina_cpu,
            "vina_seed": settings.vina_seed,
            "vina_center": [settings.vina_center_x, settings.vina_center_y, settings.vina_center_z],
            "vina_size": [settings.vina_size_x, settings.vina_size_y, settings.vina_size_z],
        },
        "acceptance_criteria": {
            "determinism": "stddev(best_affinity) <= 1e-6 with fixed seed",
            "numeric_consistency": f"cross-parser best-affinity relative error <= {settings.docking_max_consistency_error_pct}%",
            "traceability": "parsing_source, vina_version, vina_random_seed must be present",
            "warnings_visibility": "scientific_warnings must be preserved",
        },
        "summary": summary,
        "runs": rows,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reproducible docking benchmark panel")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--output",
        type=str,
        default=str(Path("artifacts") / "benchmark_reference_panel.json"),
    )
    args = parser.parse_args()

    _setup_env_defaults()

    report = asyncio.run(run_benchmark(repeats=args.repeats, output_path=Path(args.output)))
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))

    from utils.file_handlers import close_minio_client

    asyncio.run(close_minio_client())


if __name__ == "__main__":
    main()
