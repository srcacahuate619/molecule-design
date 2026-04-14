"""
scripts/run_calibration_health_check.py

Script para ejecutar el health check de calibración localmente.

Uso:
  cd backend
  python -m scripts.run_calibration_health_check

  # Con benchmark y panel existentes:
  python -m scripts.run_calibration_health_check \
    --benchmark artifacts/benchmark_reference_report.json \
    --panel artifacts/bindingdb_5ht1a_panel.json

  # Con query a RCSB PDB (requiere internet):
  python -m scripts.run_calibration_health_check --online

Output:
  - artifacts/calibration_health_report.json
  - artifacts/sci_config_registry.json
  - Resumen en consola
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from scoring.sci_config_registry import SciConfigRegistry
from scoring.calibration_health import CalibrationHealthMonitor


def _print_report(report_dict: dict) -> None:
    """Imprime el reporte de salud en consola con formato legible."""
    print(f"\n{'='*60}")
    print("CALIBRATION HEALTH REPORT")
    print(f"{'='*60}")
    print(f"Generated: {report_dict['generated_at']}")
    print(f"Registry hash: {report_dict['registry_hash']}")
    print(f"Overall status: {report_dict['overall_status'].upper()}")
    print(f"Checks: {report_dict['n_checks']} total | "
          f"{report_dict['n_pass']} pass | "
          f"{report_dict['n_warning']} warning | "
          f"{report_dict['n_fail']} fail | "
          f"{report_dict['n_unable']} unable")

    for check in report_dict["checks"]:
        status_icon = {
            "pass": "[OK]",
            "warning": "[!]",
            "fail": "[X]",
            "unable_to_check": "[?]",
            "skipped": "[-]",
        }.get(check["status"], "[?]")

        print(f"\n  {status_icon} {check['check_name']} ({check['severity']})")
        print(f"      {check['message']}")
        if check.get("recommendation"):
            print(f"      >> {check['recommendation']}")


async def run_online(
    registry: SciConfigRegistry,
    benchmark_path: Path | None,
    panel_path: Path | None,
) -> dict:
    monitor = CalibrationHealthMonitor(registry, benchmark_path, panel_path)
    report = await monitor.run_all_checks()
    return report.to_dict()


def run_offline(
    registry: SciConfigRegistry,
    benchmark_path: Path | None,
    panel_path: Path | None,
) -> dict:
    monitor = CalibrationHealthMonitor(registry, benchmark_path, panel_path)
    report = monitor.run_local_checks()
    return report.to_dict()


def main() -> None:
    parser = argparse.ArgumentParser(description="MolDesign Calibration Health Check")
    parser.add_argument(
        "--benchmark",
        type=str,
        default=None,
        help="Path to benchmark results JSON",
    )
    parser.add_argument(
        "--panel",
        type=str,
        default=None,
        help="Path to calibration panel JSON",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="artifacts/calibration_health_report.json",
        help="Path to write the health report",
    )
    parser.add_argument(
        "--registry-output",
        type=str,
        default="artifacts/sci_config_registry.json",
        help="Path to save the scientific config registry",
    )
    parser.add_argument(
        "--online",
        action="store_true",
        help="Enable RCSB PDB query for better structures (requires internet)",
    )
    args = parser.parse_args()

    # Create default registry
    registry = SciConfigRegistry.create_default()

    # Resolve paths
    benchmark_path = Path(args.benchmark) if args.benchmark and Path(args.benchmark).exists() else None
    panel_path = Path(args.panel) if args.panel and Path(args.panel).exists() else None

    # Auto-discover artifacts
    if benchmark_path is None:
        candidates = [
            Path("artifacts/benchmark_reference_panel.json"),
            Path("artifacts/benchmark_reference_report.json"),
            Path("artifacts/external_calibration_report.json"),
        ]
        for c in candidates:
            if c.exists():
                benchmark_path = c
                print(f"Auto-discovered benchmark: {c}")
                break

    if panel_path is None:
        candidates = [
            Path("artifacts/bindingdb_5ht1a_panel.json"),
            Path("artifacts/chembl_5ht1a_panel.json"),
        ]
        for c in candidates:
            if c.exists():
                panel_path = c
                print(f"Auto-discovered panel: {c}")
                break

    # Run checks
    if args.online:
        report_dict = asyncio.run(run_online(registry, benchmark_path, panel_path))
    else:
        report_dict = run_offline(registry, benchmark_path, panel_path)

    # Save outputs
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report_dict, indent=2, ensure_ascii=False), encoding="utf-8")

    reg_path = Path(args.registry_output)
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    registry.save(reg_path)

    # Print report
    _print_report(report_dict)
    print(f"\nHealth report saved to: {out_path}")
    print(f"Registry saved to: {reg_path}")


if __name__ == "__main__":
    main()
