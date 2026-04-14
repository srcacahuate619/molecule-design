# ML Rescoring Validation Report

> **Date:** 2026-04-06  
> **Model:** v4 XGBoost (176 features: 164 3D + 1D/2D + Vina + pose + log_mw)  
> **Training:** PDBbind v2020 refined set, 3384 train, 500 holdout  
> **CV Spearman:** 0.601 ± 0.040 (5-fold)  
> **Holdout Spearman:** 0.527  
> **Status:** VALIDATED — Two critical tests completed  
> **Rule:** Everything here is subordinate to `docs/SCIENTIFIC_GUARDRAILS.md`

---

## Summary of Findings

| Metric | Value | Interpretation |
|---|---|---|
| **Test 1:** 5-HT1A panel ML ρ | **0.176** (p=0.278) | Improvement from Vina ρ=0.020, but NOT statistically significant |
| **Test 2:** Crystal→Docked Δρ | **-0.030** (0.585→0.555) | Minimal degradation, both highly significant |
| **Test 2:** Crystal-Docked agreement | **ρ = 0.946** | Predictions are highly consistent |
| **Test 2:** Prediction RMSD | **0.42 pKd units** | Acceptable noise from pose differences |
| **Raw Vina vs exp (PDBbind holdout)** | **ρ = 0.113** (p=0.455) | Raw Vina scoring is unreliable for ranking |

### Verdict

The ML rescoring model shows **genuine learning of protein-ligand interaction patterns** (ρ ≈ 0.55-0.59 on PDBbind holdout) and **tolerates docked-pose degradation well** (Δρ = -0.030). However, its improvement on the specific 5-HT1A panel is **not statistically significant** with n=40 molecules. This is an honest assessment consistent with the known limitations of cross-target generalization from PDBbind models.

---

## Test 1: ML Rescoring of 5-HT1A Calibration Panel

### Purpose
Re-evaluate the 40-molecule BindingDB panel (previously Spearman ρ=0.020 with raw Vina) using the v4 ML rescoring model to measure improvement.

### Method
- Target: PDB 7E2Y (5-HT1A receptor, chain R)
- Panel: 40 BindingDB molecules (pIC50 range: 4.92–8.70, dynamic range: 3.78 log units)
- Docking: AutoDock Vina 1.2.7, exhaustiveness=32, seed=42
- Grid: center (103.03, 114.79, 108.36), size 25×25×25 Å
- ML features: Vina pose → meeko → RDKit → SDF → feature_extractor.extract_from_files()
- Models tested: Model A (full 3D), Model NULL (1D/2D only), Delta (A - NULL)

### Results

| Method | Spearman ρ | p-value | Significant? |
|---|---|---|---|
| Original Vina (calibration) | 0.020 | 0.902 | NO |
| New Vina (fresh docking) | 0.012 | 0.940 | NO |
| **ML Model A (3D features)** | **0.176** | **0.278** | **NO** |
| ML Model NULL (1D/2D only) | 0.022 | 0.891 | NO |
| ML Delta (A - NULL) | 0.078 | 0.633 | NO |

### Reproducibility check
- Vina-to-Vina reproducibility: ρ = 0.871, MAE = 0.201 kcal/mol (excellent)
- 40/40 molecules successfully processed

### Interpretation

ML rescoring improved from ρ=0.020 → ρ=0.176 — a 9x improvement in effect size — but this **is not statistically significant** at p=0.278 with only 40 molecules. The Model NULL (1D/2D features only) shows ρ=0.022, confirming that the marginal improvement comes from 3D interaction features, not from molecular descriptors.

**Why the improvement is modest:**
1. **Cross-target transfer gap:** The model was trained on PDBbind (diverse protein families) but tested on a single GPCR (5-HT1A). GPCRs are underrepresented in PDBbind.
2. **Receptor quality:** 7E2Y is a cryo-EM structure at 3.0 Å resolution — lower than most PDBbind crystal structures (median ~2.0 Å).
3. **Conformational limitation:** Single rigid receptor, but 5-HT1A has high conformational flexibility.
4. **Panel size:** n=40 provides limited statistical power to detect moderate correlations (power ≈ 0.25 for ρ=0.2 at α=0.05).
5. **Scoring function fundamentals:** Vina poses (input to ML) carry systematic errors that ML partially corrects but cannot fully overcome.

### What it means for the product

The ML rescoring provides a **directionally correct** improvement but cannot currently be presented as a validated predictor for 5-HT1A ranking. We should:
- NOT claim "ML rescoring solves the ranking problem"
- DO present it as an additional signal alongside Vina
- DO communicate uncertainty honestly
- Consider the p-value requirement: achieving significance would require either a larger panel or a larger effect size

### Artifacts
- Report: `data/test_5ht1a_rescore/test_5ht1a_rescore_report.json`
- Per-molecule data: `data/test_5ht1a_rescore/{smiles_hash}/`
- Script: `rescoring/scripts/test_5ht1a_ml_rescore.py`

---

## Test 2: Crystal-vs-Docked Pose Degradation

### Purpose
Measure how much the ML model's predictions degrade when using Vina-docked poses (production scenario) instead of crystal complex poses (training scenario). This is the **most critical validation** for the practical deployment of the model.

### Method
- **Source:** PDBbind v2020 holdout set (500 frozen test complexes, seed=42)
- **Selection:** 50 complexes stratified by pKd (evenly spaced across the affinity range 2.13–12.66)
- **For each complex:**
  1. Extract 3D features from **crystal** complex (pocket PDB + ligand SDF from PDBbind)
  2. Re-dock the ligand into the protein using AutoDock Vina (center at ligand centroid, 24×24×24 Å box)
  3. Extract 3D features from **docked** pose (same pocket PDB + Vina best pose SDF)
  4. Compare crystal and docked predictions
- Docking: AutoDock Vina 1.2.7, exhaustiveness=8, seed=42
- Receptor PDBQT: OpenBabel PDB→PDBQT with `-r` flag (rigid, hydrogens added)
- Ligand PDBQT: meeko from crystal SDF via RDKit
- Feature extraction: `InteractionFeatureExtractor.extract_from_files(pocket_pdb, sdf_path)`

### Results

| Metric | Crystal pose | Docked pose | Δ |
|---|---|---|---|
| **Spearman ρ vs experimental** | **0.585** (p=2e-5) | **0.555** (p=6e-5) | **-0.030** |
| RMSE vs experimental | 2.07 pKd | 2.12 pKd | +0.05 |
| Mean predicted pKd | 7.62 | 7.62 | 0.00 |
| Mean non-zero 3D features | 61.0 ± 16.4 | 60.5 ± 15.8 | -0.5 |
| Raw Vina ρ vs experimental | — | 0.113 (p=0.455) | — |

#### Crystal-vs-Docked agreement
| Metric | Value |
|---|---|
| Spearman(crystal_pred, docked_pred) | **0.946** (p ≈ 4e-23) |
| Prediction RMSD | 0.42 pKd units |
| Feature RMSD | 6.4 ± 8.4 |

#### Success rate
- 46/50 complexes completed successfully (92%)
- 4 failures: 2 PDBQT→SDF conversion, 1 ligand PDBQT preparation, 1 Vina timeout

### Per-complex |Δpred| distribution

| Statistic | |Δpred| (pKd units) |
|---|---|
| Mean | 0.34 |
| Median | 0.24 |
| Std | 0.30 |
| Min | 0.008 (2psu) |
| Max | 1.28 (5u0e) |
| Q25 | 0.09 |
| Q75 | 0.49 |

### Key observations

1. **Degradation is minimal (Δρ = -0.030).** The model loses only ~3% of its correlation when switching from crystal to docked poses. This is remarkably stable.

2. **Both correlations are highly significant.** Crystal ρ = 0.585 (p = 2e-5) and Docked ρ = 0.555 (p = 6e-5). The model captures real signal even from Vina poses.

3. **Raw Vina does NOT correlate with experimental values** (ρ = 0.113, p = 0.455) on this same holdout set. The ML layer adds substantial value.

4. **Predictions are highly consistent between crystal and docked** (ρ = 0.946). The model assigns similar relative rankings regardless of pose source.

5. **Feature vectors are similar between crystal and docked.** Non-zero feature count is nearly identical (61.0 vs 60.5). The model's 3D interaction features are robust to pose perturbation.

6. **A few outliers exist.** Complex 5u0e shows |Δpred| = 1.28 (Feature RMSD = 11.4), and 3n3g shows |Δpred| = 0.96. These likely correspond to cases where Vina placed the ligand in a significantly different orientation.

### Interpretation

This test provides **strong evidence** that the ML rescoring model is deployment-viable for production:

- **The training-deployment gap is small.** The model was trained on PDBbind crystal complexes but will be used on Vina-docked poses in production. A Δρ of -0.030 means this distributional shift causes minimal performance loss.

- **The model is robust to pose noise.** Even with exhaustiveness=8 (lower quality docking), the 3D interaction features are sufficiently preserved. Higher exhaustiveness (32 in production) would likely reduce this gap further.

- **ML adds clear value over raw Vina.** On the exact same complexes and poses, ML achieves ρ=0.555 vs Vina's ρ=0.113. The ML layer captures genuine protein-ligand affinity patterns beyond what Vina's scoring function provides.

### Limitations (must be communicated)

1. **Training bias:** PDBbind over-represents crystallizable complexes (kinases, proteases) — GPCRs, membrane proteins, and intrinsically disordered targets are underrepresented.
2. **Receptor preparation:** OpenBabel PDB→PDBQT without proper protonation state optimization (no reduce/H++). Production should use better preparation.
3. **Grid box quality:** Auto-centered on crystal ligand centroid. In production, grid comes from co-crystallized ligand or user specification — may be less optimal.
4. **RMSE is high (2.1 pKd units).** The model's absolute predictions have significant error. It should be used for **ranking** (Spearman), not absolute pKd prediction.
5. **n=46:** The test is reasonably powered for the effect sizes observed but is not exhaustive. A full 500-complex holdout test would be more definitive.

### Artifacts
- Report: `data/test_crystal_vs_docked/test_crystal_vs_docked_report.json`
- Per-complex data: `data/test_crystal_vs_docked/{pdb_id}/`
- Script: `rescoring/scripts/test_crystal_vs_docked.py`

---

## Combined Assessment

### What works

| Aspect | Evidence |
|---|---|
| ML captures real affinity signal | ρ = 0.555-0.585 on diverse PDBbind holdout (p < 0.0001) |
| Crystal→Docked transfer | Δρ = -0.030 (acceptable) |
| ML > raw Vina (same data) | 0.555 vs 0.113 on holdout |
| Feature robustness | Crystal-docked prediction ρ = 0.946 |
| Pipeline integrity | 46/50 (92%) success rate on automated pipeline |

### What doesn't work (yet)

| Aspect | Evidence |
|---|---|
| 5-HT1A-specific ranking | ρ = 0.176 (p = 0.278, not significant) |
| Absolute pKd accuracy | RMSE = 2.1 pKd units |
| Cross-target generalization | Untested beyond PDBbind → 5-HT1A |
| High-affinity extreme | Some high-pKd outliers (5u0e: |Δpred| = 1.28) |

### Recommendations for production

1. **Deploy ML rescoring as an additional layer**, not a replacement for Vina.
2. **Present ML score alongside Vina score** with clear labeling of what each represents.
3. **Do NOT present ML pKd as absolute binding affinity** — present it as a "rescored ranking metric."
4. **Add confidence indicators** based on applicability domain (how similar is the query complex to training data).
5. **Document that 5-HT1A ranking improvement is not statistically validated** for this specific target.
6. **Plan target-specific evaluations** for other targets of interest.

---

## Reproducibility Information

| Parameter | Value |
|---|---|
| Model version | v4 |
| XGBoost version | 2.1.4 |
| RDKit version | 2024.09.6 |
| meeko version | 0.7.1 |
| Vina version | 1.2.7 |
| OpenBabel version | 3.1.1 |
| Python version | 3.14 |
| PDBbind version | v2020 refined |
| Training samples | 3,384 |
| Holdout samples | 500 |
| Random seed | 42 |
| OS | Windows |

---

## References

- Su et al. (2019). Comparative assessment of scoring functions: the CASF-2016. J Chem Inf Model 59(2):895-913.
- Wang et al. (2004). The PDBbind Database. J Med Chem 47(12):2977-2980.
- Trott & Olson (2010). AutoDock Vina. J Comput Chem 31(2):455-461.
- Li et al. (2019). Classical scoring functions for docking. J Chem Inf Model 59(5):2188-2198.
