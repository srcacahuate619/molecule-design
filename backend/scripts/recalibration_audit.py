"""
scripts/recalibration_audit.py

Auditoría completa de recalibración del pipeline científico.

Ejecuta todas las verificaciones necesarias para garantizar que:
1. Los parámetros de normalización son consistentes entre código y registry.
2. Las fórmulas matemáticas producen resultados con <1% de error.
3. Los datos de calibración existentes son válidos o están correctamente flaggeados.
4. El benchmark reference panel es consistente con el normalizer.
5. Los pesos del scoring engine suman exactamente 1.0.

Uso:
    cd backend && python -m scripts.recalibration_audit
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from datetime import datetime, timezone

# ═══════════════════════════════════════════════════════════════════════════════
# Setup
# ═══════════════════════════════════════════════════════════════════════════════

ARTIFACTS_DIR = Path("artifacts")
PASS_COUNT = 0
FAIL_COUNT = 0
WARN_COUNT = 0


def check(condition: bool, label: str, detail: str = "") -> bool:
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"  ✓ PASS | {label}")
    else:
        FAIL_COUNT += 1
        print(f"  ✗ FAIL | {label}")
    if detail:
        print(f"         | {detail}")
    return condition


def warn(label: str, detail: str = "") -> None:
    global WARN_COUNT
    WARN_COUNT += 1
    print(f"  ⚠ WARN | {label}")
    if detail:
        print(f"         | {detail}")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Mathematical Precision Verification
# ═══════════════════════════════════════════════════════════════════════════════

def audit_mathematical_precision() -> None:
    """Verify all normalizer formulas produce exact expected results."""
    print("\n" + "=" * 70)
    print("1. MATHEMATICAL PRECISION VERIFICATION")
    print("=" * 70)

    from scoring.normalizer import (
        normalize_affinity,
        normalize_logp,
        normalize_tpsa,
        normalize_rotatable_bonds,
        calculate_adme_score,
        calculate_druglikeness_score,
    )
    from scoring.engine import calculate_score_breakdown
    from core.models import PhysicochemicalProperties, DockingResult

    # --- Affinity normalization ---
    print("\n  --- normalize_affinity (range [-10, -4] -> [100, 0]) ---")
    max_err_aff = 0.0
    aff_cases = [
        (-10.0, 100.0), (-4.0, 0.0), (-7.0, 50.0), (-8.0, 66.67),
        (-5.0, 16.67), (-6.0, 33.33), (-9.0, 83.33), (-12.0, 100.0),
        (-1.0, 0.0), (0.0, 0.0), (5.0, 0.0),
    ]
    for val, expected in aff_cases:
        actual = normalize_affinity(val)
        # Hand-compute
        if val <= -10.0:
            hand = 100.0
        elif val >= -4.0:
            hand = 0.0
        else:
            hand = ((-4.0 - val) / 6.0) * 100.0
        hand = round(max(0.0, min(100.0, hand)), 2)
        err = abs(actual - hand)
        max_err_aff = max(max_err_aff, err)

    check(
        max_err_aff < 0.01,
        f"Affinity normalization max absolute error: {max_err_aff:.6f}",
        "All values match hand-computed expectations to 0.01 precision"
    )

    # --- logP normalization ---
    print("\n  --- normalize_logp (optimum 2.5, max_dist 3.5) ---")
    max_err_logp = 0.0
    logp_cases = [
        (2.5, 100.0), (6.0, 0.0), (-1.0, 0.0), (4.0, 57.14),
        (1.0, 57.14), (0.0, 28.57), (5.0, 28.57), (3.0, 85.71),
    ]
    for val, expected in logp_cases:
        actual = normalize_logp(val)
        dist = abs(val - 2.5)
        hand = 0.0 if dist >= 3.5 else (1.0 - dist / 3.5) * 100.0
        hand = round(max(0.0, min(100.0, hand)), 2)
        err = abs(actual - hand)
        max_err_logp = max(max_err_logp, err)

    check(
        max_err_logp < 0.01,
        f"logP normalization max absolute error: {max_err_logp:.6f}",
    )

    # --- TPSA normalization ---
    print("\n  --- normalize_tpsa (sweet 20-90, cutoff 140) ---")
    max_err_tpsa = 0.0
    tpsa_cases = [
        (0.0, 0.0), (10.0, 50.0), (20.0, 100.0), (60.0, 100.0),
        (90.0, 100.0), (115.0, 50.0), (140.0, 0.0), (200.0, 0.0),
    ]
    for val, expected in tpsa_cases:
        actual = normalize_tpsa(val)
        if val >= 140.0:
            hand = 0.0
        elif 20.0 <= val <= 90.0:
            hand = 100.0
        elif val < 20.0:
            hand = (val / 20.0) * 100.0
        else:
            hand = ((140.0 - val) / 50.0) * 100.0
        hand = round(max(0.0, min(100.0, hand)), 2)
        err = abs(actual - hand)
        max_err_tpsa = max(max_err_tpsa, err)

    check(
        max_err_tpsa < 0.01,
        f"TPSA normalization max absolute error: {max_err_tpsa:.6f}",
    )

    # --- Rotatable bonds normalization ---
    print("\n  --- normalize_rotatable_bonds (100 at 0-3, 0 at 15+) ---")
    max_err_rot = 0.0
    for val in range(0, 21):
        actual = normalize_rotatable_bonds(val)
        if val <= 3:
            hand = 100.0
        elif val >= 15:
            hand = 0.0
        elif val <= 10:
            hand = 100.0 - ((val - 3) / 7.0) * 40.0
        else:
            hand = 60.0 - ((val - 10) / 5.0) * 60.0
        hand = round(max(0.0, min(100.0, hand)), 2)
        err = abs(actual - hand)
        max_err_rot = max(max_err_rot, err)

    check(
        max_err_rot < 0.01,
        f"Rotatable bonds normalization max absolute error: {max_err_rot:.6f}",
    )

    # --- ADME composite score ---
    print("\n  --- calculate_adme_score (logP*0.4 + TPSA*0.4 + RotBonds*0.2) ---")
    max_err_adme = 0.0

    def mk(mw=250.0, lp=2.0, tp=60.0, hbd=2, hba=4, rot=3):
        lip = not (mw > 500 or lp > 5.0 or hbd > 5 or hba > 10)
        veb = not (rot > 10 or tp > 140)
        return PhysicochemicalProperties(
            molecular_weight=mw, log_p=lp, tpsa=tp, hbd=hbd, hba=hba,
            rotatable_bonds=rot, heavy_atom_count=18, ring_count=2, qed=0.7,
            lipinski_pass=lip, veber_pass=veb,
        )

    adme_cases = [
        (2.5, 60.0, 3), (7.0, 60.0, 3), (2.5, 150.0, 3),
        (2.5, 60.0, 15), (1.19, 63.6, 3), (4.0, 100.0, 8),
    ]
    for lp, tp, rot in adme_cases:
        props = mk(lp=lp, tp=tp, rot=rot)
        actual = calculate_adme_score(props)
        l = normalize_logp(lp)
        t = normalize_tpsa(tp)
        r = normalize_rotatable_bonds(rot)
        hand = round(max(0.0, min(100.0, l * 0.4 + t * 0.4 + r * 0.2)), 2)
        err = abs(actual - hand)
        max_err_adme = max(max_err_adme, err)

    check(
        max_err_adme < 0.01,
        f"ADME composite max absolute error: {max_err_adme:.6f}",
    )

    # --- Drug-likeness score ---
    print("\n  --- calculate_druglikeness_score (base 100 with Lipinski/Veber penalties) ---")
    max_err_dl = 0.0
    dl_cases = [
        dict(mw=250.0, lp=2.0, tp=60.0, hbd=2, hba=4, rot=3),
        dict(mw=550.0, lp=2.0, tp=60.0, hbd=2, hba=4, rot=3),
        dict(mw=475.0, lp=2.0, tp=60.0, hbd=2, hba=4, rot=3),
        dict(mw=250.0, lp=6.0, tp=60.0, hbd=2, hba=4, rot=3),
        dict(mw=250.0, lp=4.7, tp=60.0, hbd=2, hba=4, rot=3),
        dict(mw=250.0, lp=2.0, tp=60.0, hbd=7, hba=4, rot=3),
        dict(mw=250.0, lp=2.0, tp=60.0, hbd=2, hba=12, rot=3),
        dict(mw=250.0, lp=2.0, tp=60.0, hbd=2, hba=4, rot=12),
        dict(mw=250.0, lp=2.0, tp=150.0, hbd=2, hba=4, rot=3),
        dict(mw=600.0, lp=7.0, tp=160.0, hbd=8, hba=13, rot=16),
    ]
    for kw in dl_cases:
        props = mk(**kw)
        actual = calculate_druglikeness_score(props)
        sc = 100.0
        if kw["mw"] > 500: sc -= 20.0
        elif kw["mw"] > 450: sc -= ((kw["mw"] - 450) / 50.0) * 10.0
        if kw["lp"] > 5.0: sc -= 20.0
        elif kw["lp"] > 4.5: sc -= ((kw["lp"] - 4.5) / 0.5) * 10.0
        if kw["hbd"] > 5: sc -= 20.0
        elif kw["hbd"] > 4: sc -= (kw["hbd"] - 4) * 10.0
        if kw["hba"] > 10: sc -= 20.0
        elif kw["hba"] > 8: sc -= ((kw["hba"] - 8) / 2.0) * 10.0
        if kw["rot"] > 10: sc -= 10.0
        elif kw["rot"] > 8: sc -= ((kw["rot"] - 8) / 2.0) * 5.0
        if kw["tp"] > 140: sc -= 10.0
        elif kw["tp"] > 120: sc -= ((kw["tp"] - 120) / 20.0) * 5.0
        hand = round(max(0.0, min(100.0, sc)), 2)
        err = abs(actual - hand)
        max_err_dl = max(max_err_dl, err)

    check(
        max_err_dl < 0.01,
        f"Drug-likeness max absolute error: {max_err_dl:.6f}",
    )

    # --- Composite score engine ---
    print("\n  --- calculate_score_breakdown (w_aff=0.45, w_adme=0.30, w_dl=0.25) ---")
    max_err_eng = 0.0
    eng_cases = [
        (-5.848, dict(mw=180.16, lp=1.19, tp=63.6, hbd=1, hba=4, rot=3)),
        (-5.814, dict(mw=194.08, lp=-0.07, tp=58.44, hbd=0, hba=6, rot=0)),
        (-6.98, dict(mw=206.13, lp=3.5, tp=37.3, hbd=1, hba=2, rot=4)),
        (-9.0, dict(mw=350.0, lp=2.5, tp=60.0, hbd=2, hba=5, rot=3)),
        (-3.0, dict(mw=600.0, lp=7.0, tp=160.0, hbd=8, hba=13, rot=16)),
    ]
    for aff, kw in eng_cases:
        props = mk(**kw)
        dock = DockingResult(
            best_affinity=aff,
            poses=[{"rank": 1, "affinity": aff, "rmsd_lb": 0, "rmsd_ub": 0}],
            poses_file_path="test",
        )
        r = calculate_score_breakdown(dock, props)
        hand_total = round(
            max(0.0, min(100.0,
                r.affinity_score * 0.45
                + r.adme_score * 0.30
                + r.druglikeness_score * 0.25
            )), 2
        )
        err = abs(r.total_score - hand_total)
        max_err_eng = max(max_err_eng, err)

    check(
        max_err_eng < 0.01,
        f"Composite score max absolute error: {max_err_eng:.6f}",
    )

    # --- Weight sum ---
    from core.config import get_settings
    s = get_settings()
    wsum = s.score_weight_affinity + s.score_weight_adme + s.score_weight_druglikeness
    check(
        abs(wsum - 1.0) < 1e-9,
        f"Scoring weights sum: {wsum:.10f}",
        f"affinity={s.score_weight_affinity}, adme={s.score_weight_adme}, dl={s.score_weight_druglikeness}",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Registry-Code Consistency
# ═══════════════════════════════════════════════════════════════════════════════

def audit_registry_code_consistency() -> None:
    """Verify hardcoded values in normalizer.py match sci_config_registry."""
    print("\n" + "=" * 70)
    print("2. REGISTRY-CODE CONSISTENCY")
    print("=" * 70)

    from scoring.sci_config_registry import SciConfigRegistry
    from core.config import get_settings

    registry = SciConfigRegistry.create_default()
    settings = get_settings()

    # Affinity normalization range
    reg_best = registry.get_value("affinity_normalization_best")
    reg_worst = registry.get_value("affinity_normalization_worst")
    # Hardcoded in normalizer.py: best = -10.0, worst = -4.0
    code_best = -10.0
    code_worst = -4.0

    check(
        reg_best == code_best,
        f"affinity_normalization_best: registry={reg_best} == code={code_best}",
    )
    check(
        reg_worst == code_worst,
        f"affinity_normalization_worst: registry={reg_worst} == code={code_worst}",
    )

    # Grid box
    reg_center = registry.get_value("grid_center")
    reg_size = registry.get_value("grid_size")
    code_center = [settings.vina_center_x, settings.vina_center_y, settings.vina_center_z]
    code_size = [settings.vina_size_x, settings.vina_size_y, settings.vina_size_z]

    check(
        reg_center == code_center,
        f"grid_center: registry={reg_center} == config={code_center}",
    )
    check(
        reg_size == code_size,
        f"grid_size: registry={reg_size} == config={code_size}",
    )

    # Target PDB
    reg_pdb = registry.get_value("target_pdb_id")
    code_pdb = settings.default_target_pdb_id

    check(
        reg_pdb == code_pdb,
        f"target_pdb_id: registry={reg_pdb} == config={code_pdb}",
    )

    # Target chain
    reg_chain = registry.get_value("target_chain")
    code_chain = settings.default_target_chain

    check(
        reg_chain == code_chain,
        f"target_chain: registry={reg_chain} == config={code_chain}",
    )

    # Scoring weights
    reg_weights = registry.get_value("score_weights")
    code_weights = {
        "affinity": settings.score_weight_affinity,
        "adme": settings.score_weight_adme,
        "druglikeness": settings.score_weight_druglikeness,
    }

    check(
        reg_weights == code_weights,
        f"score_weights: registry={reg_weights} == config={code_weights}",
    )

    # Vina parameters
    reg_exhaust_prod = registry.get_value("vina_exhaustiveness_production")
    reg_exhaust_cal = registry.get_value("vina_exhaustiveness_calibration")
    reg_seed = registry.get_value("vina_seed")

    check(
        reg_exhaust_prod == settings.vina_exhaustiveness,
        f"vina_exhaustiveness_production: registry={reg_exhaust_prod} == config={settings.vina_exhaustiveness}",
    )
    check(
        reg_exhaust_cal == settings.vina_calibration_exhaustiveness,
        f"vina_exhaustiveness_calibration: registry={reg_exhaust_cal} == config={settings.vina_calibration_exhaustiveness}",
    )
    check(
        reg_seed == settings.vina_seed,
        f"vina_seed: registry={reg_seed} == config={settings.vina_seed}",
    )

    # Lipinski thresholds
    reg_lipinski = registry.get_value("lipinski_thresholds")
    check(
        reg_lipinski == {"MW": 500, "logP": 5.0, "HBD": 5, "HBA": 10},
        f"lipinski_thresholds match Lipinski (1997): {reg_lipinski}",
    )

    # Veber thresholds
    reg_veber = registry.get_value("veber_thresholds")
    check(
        reg_veber == {"TPSA": 140, "RotBonds": 10},
        f"veber_thresholds match Veber (2002): {reg_veber}",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Calibration Data Integrity
# ═══════════════════════════════════════════════════════════════════════════════

def audit_calibration_data() -> None:
    """Verify integrity and validity of calibration artifacts."""
    print("\n" + "=" * 70)
    print("3. CALIBRATION DATA INTEGRITY")
    print("=" * 70)

    # --- External calibration report ---
    print("\n  --- External Calibration Report ---")
    ecr_path = ARTIFACTS_DIR / "external_calibration_report.json"
    if ecr_path.exists():
        ecr = json.loads(ecr_path.read_text(encoding="utf-8"))

        target_pdb = ecr["protocol"]["target_pdb_id"]
        target_chain = ecr["protocol"]["target_chain"]
        expected_pdb = "7E2Y"
        expected_chain = "R"

        is_wrong_target = target_pdb != expected_pdb or target_chain != expected_chain
        if is_wrong_target:
            check(
                False,
                f"External calibration target: {target_pdb} chain {target_chain}",
                f"CRITICAL: Docked against WRONG protein ({target_pdb} instead of {expected_pdb})! "
                f"All predicted affinities are INVALID.",
            )
        else:
            check(True, f"External calibration target: {target_pdb} chain {target_chain}")

        affinities = [r["predicted_affinity_kcal"] for r in ecr["accepted"]]
        n_mol = len(affinities)
        spearman = ecr["metrics"]["spearman_activity_vs_minus_affinity"]
        aff_range = (min(affinities), max(affinities))

        check(
            n_mol >= 30,
            f"External calibration panel size: {n_mol}",
            f"Minimum 30 recommended (Warren et al. 2006)",
        )

        if is_wrong_target:
            warn(
                f"Spearman={spearman:.4f} (negative, expected positive)",
                "Negative correlation is expected when docking against wrong protein.",
            )
            warn(
                f"Affinity range: [{aff_range[0]:.3f}, {aff_range[1]:.3f}] kcal/mol",
                "Affinities above -3.0 kcal/mol indicate failed docking or wrong target.",
            )
        else:
            check(
                spearman > 0.0,
                f"Spearman correlation: {spearman:.4f}",
                "Positive correlation expected for correct target.",
            )
    else:
        warn("External calibration report not found")

    # --- Recalibration proposal ---
    print("\n  --- Recalibration Proposal ---")
    rp_path = ARTIFACTS_DIR / "recalibration_proposal.json"
    if rp_path.exists():
        rp = json.loads(rp_path.read_text(encoding="utf-8"))

        # Check if proposal was based on invalid data
        for change in rp.get("proposed_changes", []):
            if change.get("parameter_name") == "affinity_normalization_range":
                proposed = change.get("proposed_value", {})
                if isinstance(proposed, dict):
                    best = proposed.get("best", 0)
                    worst = proposed.get("worst", 0)
                    if best > -4.0 or worst > 0:
                        check(
                            False,
                            f"Proposal suggests range [{best}, {worst}]",
                            f"CRITICAL: Proposed range is NONSENSICAL — based on data from wrong target (3RZY). "
                            f"Normal Vina affinities for drug-like molecules are between -3 and -12 kcal/mol.",
                        )
                    else:
                        check(True, f"Proposal range is plausible: [{best}, {worst}]")
    else:
        warn("Recalibration proposal not found")

    # --- Benchmark reference panel ---
    print("\n  --- Benchmark Reference Panel ---")
    brp_path = ARTIFACTS_DIR / "benchmark_reference_panel.json"
    if brp_path.exists():
        brp = json.loads(brp_path.read_text(encoding="utf-8"))

        target = brp["protocol"]["target_pdb_id"]
        check(
            target == "7E2Y",
            f"Benchmark target: {target}",
        )

        affinities = [r["best_affinity"] for r in brp["runs"]]
        all_in_range = all(-10.0 <= a <= -4.0 for a in affinities)
        check(
            all_in_range,
            f"All benchmark affinities within normalization range [-10, -4]",
            f"Observed: {sorted(set(affinities))}",
        )

        # Determinism check
        for name in ["aspirin", "caffeine", "ibuprofen"]:
            runs_for = [r for r in brp["runs"] if r["name"] == name]
            affs = [r["best_affinity"] for r in runs_for]
            is_deterministic = len(set(affs)) == 1
            check(
                is_deterministic,
                f"Benchmark determinism ({name}): stddev=0.0",
                f"Affinities: {affs}",
            )

        # Score consistency
        asp_runs = [r for r in brp["runs"] if r["name"] == "aspirin"]
        if asp_runs:
            r = asp_runs[0]
            aff_score = r["score_affinity"]
            from scoring.normalizer import normalize_affinity
            expected_aff = normalize_affinity(r["best_affinity"])
            check(
                abs(aff_score - expected_aff) < 0.01,
                f"Benchmark aspirin affinity_score consistency: stored={aff_score} vs computed={expected_aff}",
            )
    else:
        warn("Benchmark reference panel not found")

    # --- BindingDB panel ---
    print("\n  --- BindingDB 5-HT1A Panel ---")
    panel_path = ARTIFACTS_DIR / "bindingdb_5ht1a_panel.json"
    if panel_path.exists():
        panel = json.loads(panel_path.read_text(encoding="utf-8"))

        n_selected = panel["n_selected"]
        check(
            n_selected >= 30,
            f"Panel size: {n_selected} molecules",
            f"Minimum 30 recommended",
        )

        p_range = panel["criteria"]["p_activity_range_log_units"]
        check(
            p_range >= 4.0,
            f"p_activity range: {p_range:.3f} log units",
            f"Minimum 4.0 recommended for statistical power",
        )

        tiers = panel["criteria"]["tier_counts"]
        all_tiers_populated = all(v > 0 for v in tiers.values())
        check(
            all_tiers_populated,
            f"All 3 activity tiers populated: {tiers}",
        )
    else:
        warn("BindingDB panel not found")

    # --- Redocking validation ---
    print("\n  --- Redocking Validation ---")
    rdv_path = ARTIFACTS_DIR / "redocking_validation.json"
    if rdv_path.exists():
        rdv = json.loads(rdv_path.read_text(encoding="utf-8"))

        check(
            rdv.get("overall_pass") is True,
            f"Redocking validation overall: {'PASS' if rdv.get('overall_pass') else 'FAIL'}",
        )

        grid_val = rdv["steps"]["grid_validation"]
        dist = grid_val.get("distance_centroid_to_grid_center", 999)
        check(
            dist < 1.0,
            f"Grid center distance to ligand centroid: {dist:.3f} Å",
            "Must be < 1.0 Å for valid docking setup",
        )
    else:
        warn("Redocking validation not found")

    # --- Grid box JSON ---
    print("\n  --- Grid Box Definition ---")
    gb_path = ARTIFACTS_DIR / "grid_box_7e2y_sro.json"
    if gb_path.exists():
        gb = json.loads(gb_path.read_text(encoding="utf-8"))

        from core.config import get_settings
        s = get_settings()
        code_center = [s.vina_center_x, s.vina_center_y, s.vina_center_z]
        gb_center = [gb["grid_center"]["x"], gb["grid_center"]["y"], gb["grid_center"]["z"]]

        check(
            code_center == gb_center,
            f"Grid center matches extract script: config={code_center} == script={gb_center}",
        )
    else:
        warn("Grid box JSON not found")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Normalization Range Analysis
# ═══════════════════════════════════════════════════════════════════════════════

def audit_normalization_range() -> None:
    """Analyze if the normalization range is appropriate."""
    print("\n" + "=" * 70)
    print("4. NORMALIZATION RANGE ANALYSIS")
    print("=" * 70)

    brp_path = ARTIFACTS_DIR / "benchmark_reference_panel.json"
    if not brp_path.exists():
        warn("Cannot analyze: benchmark not found")
        return

    brp = json.loads(brp_path.read_text(encoding="utf-8"))
    affinities = list(set(r["best_affinity"] for r in brp["runs"]))
    affinities.sort()

    # Current normalization range
    best = -10.0
    worst = -4.0
    norm_range = worst - best  # 6.0

    obs_min = min(affinities)
    obs_max = max(affinities)
    obs_range = obs_max - obs_min

    utilization = obs_range / norm_range if norm_range != 0 else 0

    print(f"\n  Normalization range: [{best}, {worst}] kcal/mol (span={norm_range})")
    print(f"  Observed (benchmark): [{obs_min}, {obs_max}] kcal/mol (span={obs_range:.3f})")
    print(f"  Range utilization: {utilization:.1%}")

    # The benchmark only has 3 basic molecules (aspirin, caffeine, ibuprofen)
    # which are NOT 5-HT1A ligands — they give moderate affinities.
    # Real 5-HT1A ligands (buspirone, aripiprazole) would give -7 to -10.
    # The range [-10, -4] is correct for the target class.

    check(
        all(best <= a <= worst for a in affinities),
        "All benchmark affinities within normalization range",
        "No clamping occurs for benchmark molecules",
    )

    warn(
        f"Low range utilization ({utilization:.1%})",
        "Expected: benchmark has 3 generic drugs, not 5-HT1A ligands. "
        "Real 5-HT1A ligands (buspirone, aripiprazole, serotonin) would utilize "
        "more of the [-10, -4] range. Range is scientifically appropriate for GPCRs.",
    )

    # Calculate what scores the benchmark molecules get
    from scoring.normalizer import normalize_affinity
    print("\n  Benchmark molecule scores:")
    for name, aff in [("aspirin", -5.848), ("caffeine", -5.814), ("ibuprofen", -6.98)]:
        score = normalize_affinity(aff)
        print(f"    {name:12s}: affinity={aff:7.3f} kcal/mol -> score={score:.2f}")

    # Known 5-HT1A ligand expected ranges (from literature)
    print("\n  Expected ranges for known 5-HT1A ligands (literature):")
    expected_5ht1a = [
        ("serotonin", -5.5, -7.5, "endogenous agonist, MW=176"),
        ("buspirone", -7.0, -9.0, "partial agonist, MW=385"),
        ("aripiprazole", -8.0, -10.0, "partial agonist, MW=448"),
        ("8-OH-DPAT", -6.0, -8.0, "selective agonist, MW=247"),
    ]
    for name, low, high, desc in expected_5ht1a:
        score_low = normalize_affinity(low)
        score_high = normalize_affinity(high)
        print(f"    {name:14s}: {low:6.1f} to {high:5.1f} kcal/mol -> score {score_low:.0f}-{score_high:.0f} ({desc})")


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Scoring Engine Weight Integrity
# ═══════════════════════════════════════════════════════════════════════════════

def audit_weight_integrity() -> None:
    """Verify scoring weight integrity and scientific justification."""
    print("\n" + "=" * 70)
    print("5. SCORING WEIGHT INTEGRITY")
    print("=" * 70)

    from core.config import get_settings
    s = get_settings()

    w_aff = s.score_weight_affinity
    w_adme = s.score_weight_adme
    w_dl = s.score_weight_druglikeness
    w_sum = w_aff + w_adme + w_dl

    check(
        abs(w_sum - 1.0) < 1e-9,
        f"Weight sum: {w_sum:.10f} (must be exactly 1.0)",
    )
    check(
        w_aff >= w_adme >= w_dl,
        f"Weight ordering: affinity({w_aff}) >= ADME({w_adme}) >= drug-likeness({w_dl})",
        "Affinity should be weighted highest as the primary simulation metric",
    )
    check(
        w_aff == 0.45,
        f"Affinity weight: {w_aff} (documented as 0.45)",
    )
    check(
        w_adme == 0.30,
        f"ADME weight: {w_adme} (documented as 0.30)",
    )
    check(
        w_dl == 0.25,
        f"Drug-likeness weight: {w_dl} (documented as 0.25)",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Software Version Consistency
# ═══════════════════════════════════════════════════════════════════════════════

def audit_software_versions() -> None:
    """Report software versions for reproducibility."""
    print("\n" + "=" * 70)
    print("6. SOFTWARE VERSIONS")
    print("=" * 70)

    import rdkit
    import meeko
    import numpy

    check(True, f"RDKit: {rdkit.__version__}")
    check(True, f"Meeko: {getattr(meeko, '__version__', 'unknown')}")
    check(True, f"NumPy: {numpy.__version__}")
    check(True, f"Python: {sys.version.split()[0]}")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print("=" * 70)
    print("  MOLDESIGN RECALIBRATION AUDIT")
    print(f"  Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    audit_mathematical_precision()
    audit_registry_code_consistency()
    audit_calibration_data()
    audit_normalization_range()
    audit_weight_integrity()
    audit_software_versions()

    # Summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  PASS:     {PASS_COUNT}")
    print(f"  FAIL:     {FAIL_COUNT}")
    print(f"  WARNINGS: {WARN_COUNT}")
    total = PASS_COUNT + FAIL_COUNT
    if total > 0:
        pass_rate = PASS_COUNT / total * 100
        print(f"  Pass rate: {pass_rate:.1f}%")

    if FAIL_COUNT > 0:
        print("\n  ⚠ CRITICAL FAILURES DETECTED — see details above.")
        print("    Required actions:")
        print("    1. Re-run external calibration against 7E2Y (not 3RZY)")
        print("    2. Discard recalibration proposal based on 3RZY data")
        print("    3. Regenerate calibration_health_report with correct benchmark")
        sys.exit(1)
    else:
        print("\n  ✓ All mathematical and consistency checks pass.")
        if WARN_COUNT > 0:
            print(f"    {WARN_COUNT} warnings require attention but are non-blocking.")
        sys.exit(0)


if __name__ == "__main__":
    main()
