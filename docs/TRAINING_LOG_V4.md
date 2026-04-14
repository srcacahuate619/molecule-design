# ML Rescoring Training Log — v4 (Shell + ECIF + Size Normalization)

> **Fecha**: 2026-04-06 06:41 UTC  
> **Pipeline**: `rescoring/train_orchestrator.py`  
> **Datos**: PDBbind v2020 refined set  
> **Hardware**: Windows 11, Python 3.14, 12 CPU cores  
> **Duración total**: 1,080.1 seconds (~18 minutos)

---

## 1. Resumen ejecutivo

Entrenamiento v4 con 176 features (vs 20 en v3). Incorpora shell atom counts (RF-Score), ECIF-lite, y normalización de tamaño. **MW ya no domina el modelo.**

| Métrica | v3 (ProLIF) | v4 (Shell+ECIF) | Mejora |
|---|---|---|---|
| Spearman (CV mean) | 0.435 ± 0.060 | **0.601 ± 0.040** | **+38%** |
| Pearson (CV mean) | 0.443 ± 0.052 | **0.599 ± 0.033** | **+35%** |
| RMSE (CV mean) | 2.279 ± 0.075 | **2.031 ± 0.098** | **-11%** |
| Holdout Spearman | 0.352 | **0.527** | **+50%** |
| SHAP MW dominance | 0.468 (#1) | **0.176 (#2)** | **-62%** |
| 3D features in top-5 SHAP | 4/5 | **4/5** | Maintained |
| Top SHAP feature | mw (0.468) | **shell_C_C_8_12 (0.305)** | 3D dominates! |
| Total features | 20 | **176** | +780% |
| Acceptance criteria | 6/6 PASS | **7/7 PASS** | — |

---

## 2. Nuevas features v4

### Group A_EXT (8 features) — Fisicoquímicas + normalización
- **mw, logp, tpsa, hbd, hba, rotatable_bonds, qed** (heredados de v3)
- **log_mw** (NUEVO) — log(MW) para romper no-linealidad del sesgo de tamaño

### Group B (4 features) — Vina re-docking
- **vina_best_score, pose_score_variance, pose_score_range, poses_passing_ratio**
- Todos = 0.0 (requiere re-docking, ~42 horas de cómputo pendiente)

### Group C_EXT (12 features) — Interacciones 3D (ProLIF + contactos)
- 9 interacciones ProLIF originales
- **contacts_per_ha_4A, contacts_per_ha_6A** (NUEVO) — contactos normalizados por heavy atoms
- **heavy_atom_count** (NUEVO) — tamaño molecular explícito

### Group D (96 features) — Shell atom counts (NUEVO)
- Basado en RF-Score (Li et al., 2009)
- 4 protein elements (C, N, O, S) × 8 ligand elements (C, N, O, S, F, P, Cl, Br) × 3 distance bins ((0,4), (4,8), (8,12) Å)
- Puramente geométricas, universales para cualquier complejo proteína-ligando

### Group E (56 features) — ECIF-lite (NUEVO)
- Basado en ECIF (Sánchez-Cruz et al., 2021)
- 8 protein extended types (C_ali, C_aro, N_don, N_acc, O_don, O_acc, S, other) × 7 ligand element types (C, N, O, S, F, Hal, other)
- Cutoff: 6.0 Å
- Ligando usa element-only types para consistencia train/inference (PDBQT en inferencia carece de info de aromaticidad)

---

## 3. Datos de entrenamiento

Idénticos a v3 (pipeline de curación estable):
```
3,884 complejos (INDEX refined)
  → -54  binding_precision
  → -364 binding_type (solo Ki, Kd)
  → -25  affinity_range
  = 3,441 complejos curados
  → -422 ligand_unparseable (VIP audit)
  = 3,019 complejos VIP aceptados (87.7%)
```

Feature extraction v4:
- **2,911/3,019 exitosos** (96.4%, +0.2% vs v3)
- **108 fallos** (7 más que v3, por errores de ProLIF en complejos nuevos)
- Tiempo de extracción: **17.5 minutos** (0.3s/complejo promedio)
- Cache: `feature_cache_v4/` con formato versionado `{"version": 4, "features": {...}}`

---

## 4. Resultados del modelo

### Model A (176 features, XGBoost LambdaMART)

#### Holdout set (500 complejos)
| Métrica | Valor |
|---|---|
| **Spearman** | **0.5267** |
| **Pearson** | **0.5367** |
| **NDCG@10** | **0.6421** |
| **R²** | **0.2724** |
| **RMSE** | **2.167** |
| Best iteration | 165 |

#### Cross-validation (5-fold scaffold split)
| Métrica | Mean ± Std | Min | Max |
|---|---|---|---|
| **Spearman** | **0.601 ± 0.040** | 0.527 | 0.639 |
| **Pearson** | **0.599 ± 0.033** | 0.537 | 0.634 |
| **NDCG@10** | **0.609 ± 0.065** | 0.508 | 0.698 |
| **R²** | **0.354 ± 0.044** | 0.272 | 0.401 |
| **RMSE** | **2.031 ± 0.098** | 1.917 | 2.167 |

Per-fold Spearman: [0.527, 0.639, 0.629, 0.601, 0.609]

### Model NULL (8 features, solo 1D/2D)
| Métrica | Mean ± Std |
|---|---|
| Spearman | 0.265 ± 0.036 |
| Pearson | 0.277 ± 0.033 |

**Delta 3D: +0.336 Spearman** (más del doble de las features 1D/2D solas)

---

## 5. SHAP Feature Importance (top 20)

| Rank | Feature | SHAP |SHAP| | Group | Tipo |
|---|---|---|---|---|
| 1 | **shell_C_C_8_12** | **0.305** | D (shell) | Contactos C-C 8-12Å |
| 2 | mw | 0.176 | A | Peso molecular |
| 3 | **ecif_O_acc_C** | **0.147** | E (ECIF) | O aceptor prot — C ligando |
| 4 | **ecif_C_aro_O** | **0.136** | E (ECIF) | C aromático prot — O ligando |
| 5 | **shell_C_C_4_8** | **0.099** | D (shell) | Contactos C-C 4-8Å |
| 6 | ecif_N_acc_C | 0.093 | E (ECIF) | N aceptor prot — C ligando |
| 7 | shell_N_C_8_12 | 0.088 | D (shell) | Contactos N-C 8-12Å |
| 8 | shell_N_S_8_12 | 0.079 | D (shell) | Contactos N-S 8-12Å |
| 9 | shell_O_O_4_8 | 0.078 | D (shell) | Contactos O-O 4-8Å |
| 10 | shell_N_N_0_4 | 0.078 | D (shell) | Contactos N-N 0-4Å |
| 11 | shell_C_S_8_12 | 0.074 | D (shell) | Contactos C-S 8-12Å |
| 12 | ecif_C_aro_C | 0.067 | E (ECIF) | C aromático prot — C ligando |
| 13 | shell_S_C_4_8 | 0.067 | D (shell) | Contactos S-C 4-8Å |
| 14 | shell_O_S_8_12 | 0.066 | D (shell) | Contactos O-S 8-12Å |
| 15 | shell_C_N_0_4 | 0.060 | D (shell) | Contactos C-N 0-4Å |
| 16 | contacts_per_ha_6A | 0.059 | C_EXT | Contactos/HA a 6Å |
| 17 | ecif_O_don_O | 0.059 | E (ECIF) | O donor prot — O ligando |
| 18 | shell_N_O_4_8 | 0.058 | D (shell) | Contactos N-O 4-8Å |
| 19 | log_mw | 0.058 | A_EXT | log(MW) |
| 20 | contacts_per_ha_4A | 0.055 | C_EXT | Contactos/HA a 4Å |

### Interpretación SHAP
- **MW ya no domina**: bajó de SHAP 0.468 (#1) a 0.176 (#2) — una reducción del 62%
- **Features 3D dominan completamente**: 4 de top 5, 18 de top 20 son features 3D
- **Shell C-C (8-12Å) es la top feature**: captura contexto de binding site extendido
- **ECIF features proveen complemento químico**: O_acc_C y C_aro_O capturan interacciones polares y aromáticas específicas
- **Normalización por heavy atoms**: contacts_per_ha aportan, confirmando que el sesgo de tamaño se mitiga

### Features con SHAP = 0.0 (38/176)
- Group B completo (4 features): esperado, todos = 0.0 sin re-docking
- 6 features 1D/2D: logp, tpsa, hbd, hba, rotatable_bonds, qed (XGBoost usa mw/log_mw como proxy)
- salt_bridges: muy escaso (< 1% de complejos)
- 14 shell raros: combinaciones halógeno-halógeno o fósforo poco frecuentes
- 13 ECIF raros: combinaciones con Hal, other poco frecuentes

---

## 6. Ablation testing (11 configuraciones)

| Config | Features | Spearman | Pearson | NDCG@10 | RMSE |
|---|---|---|---|---|---|
| A_ext_only | 8 | 0.272 | 0.275 | 0.356 | 2.510 |
| B_only | 4 | 0.000 | 0.000 | 0.034 | 2.541 |
| C_ext_only | 12 | 0.317 | 0.353 | 0.495 | 2.410 |
| **D_only_shell** | **96** | **0.445** | **0.458** | **0.648** | **2.280** |
| **E_only_ecif** | **56** | **0.489** | **0.500** | **0.629** | **2.224** |
| A_ext+C_ext | 20 | 0.366 | 0.391 | 0.336 | 2.368 |
| A_ext+D | 104 | 0.466 | 0.477 | 0.532 | 2.255 |
| **A_ext+E** | **64** | **0.537** | **0.549** | **0.605** | **2.151** |
| A_ext+D+E | 160 | 0.531 | 0.535 | 0.663 | 2.173 |
| **A_ext+C_ext+D+E** | **172** | **0.539** | **0.547** | **0.608** | **2.153** |
| ALL_v4 | 176 | 0.527 | 0.537 | 0.642 | 2.167 |

### Observaciones clave de ablación
1. **ECIF solo (56 features) alcanza Spearman 0.489** — ya supera v3 completo (0.435)
2. **Shell solo (96 features) alcanza 0.445** — también supera v3
3. **A_ext+E (64 features) es el mejor par: 0.537** — ECIF + fisicoquímicas = combinación óptima
4. **A_ext+C_ext+D+E (172) es la mejor ablación: 0.539** — apenas mejor que A_ext+E
5. **Group B no aporta** (todo zeros) — esperado, confirma que Group B necesita re-docking
6. **ALL_v4 (176) = 0.527** ≤ A_ext+C_ext+D+E (0.539) — Group B añade ruido marginal

### Implicación
El modelo A_ext+E podría ser un modelo más parsimonioso (64 features, Spearman 0.537). Sin embargo, el modelo ALL_v4 (176) se mantiene como producción porque:
- Incluye infraestructura para Group B cuando re-docking esté disponible
- La diferencia es marginal (0.527 vs 0.539)
- Cross-validation muestra 0.601 con ALL_v4

---

## 7. Delta distribution (semáforo 3D)

| Métrica | Valor |
|---|---|
| Mean delta | 0.0411 |
| Std delta | 1.6645 |
| Median | 0.1082 |
| Min / Max | -5.847 / 5.138 |
| Green threshold (p60) | 0.578 |
| Red threshold (p25) | -1.051 |

Delta = score_model_A - score_model_null. Positivo = las features 3D mejoran la predicción para ese complejo.

---

## 8. Applicability domain

| Parámetro | Valor |
|---|---|
| Distancia Mahalanobis | 176 features |
| Threshold p99 | 29.129 |
| n_samples | 2,015 |

---

## 9. Acceptance criteria — ALL PASSED

| Criterio | Resultado |
|---|---|
| ablation_3d_contributes | ✅ True |
| ablation_improvement | ✅ 0.255 (>0.05 threshold) |
| scaffold_split_spearman_positive | ✅ True |
| scaffold_split_ndcg_positive | ✅ True |
| shap_3d_in_top5 | ✅ True (4/5) |
| delta_mean_positive | ✅ True |
| **all_passed** | ✅ **True** |

---

## 10. Family performance (test set)

| Familia | N | Spearman |
|---|---|---|
| other | 499 | 0.646 |
| protease | 1 | — (insufficient) |

Nota: La clasificación por familia está dominada por "other" (3,017/3,019) porque `structural_family.py` aún no implementa clasificación UniProt/EC completa.

---

## 11. Artefactos generados

| Archivo | Ubicación | Descripción |
|---|---|---|
| model_a.joblib | `backend/artifacts/` | Modelo XGBoost producción (176 features) |
| model_null.joblib | `backend/artifacts/` | Modelo baseline (8 features 1D/2D) |
| training_report.json | `backend/artifacts/` | Reporte completo con todas las métricas |
| shap_summary.json | `backend/artifacts/` | SHAP mean |values| para todas las features |
| delta_distribution.json | `backend/artifacts/` | Distribución delta para semáforo 3D |
| applicability_domain.json | `backend/artifacts/` | Dominio de aplicabilidad Mahalanobis |

Artefactos originales de entrenamiento: `data/pdbbind/artifacts_v4/`

---

## 12. Reproducibilidad

```bash
cd rescoring
python train_orchestrator.py \
  --data-dir /path/to/pdbbind \
  --output-dir /path/to/output/artifacts_v4

# Requisitos:
# - PDBbind v2020 refined set en --data-dir
# - Python 3.14 con RDKit, ProLIF, XGBoost, MDAnalysis, scikit-learn, structlog
# - ~18 minutos en 12 cores
# - CACHE_VERSION = 4 (feature_cache_v4/)
```

### Versiones de software clave
- RDKit: 2024.09+
- ProLIF: 2.1.0 (n_jobs=1)
- XGBoost: 2.1.4
- MDAnalysis: 2.8+
- scikit-learn: 1.6+

---

## 13. Limitaciones conocidas

1. **Group B = zeros**: Sin re-docking, las 4 features de Vina score no aportan. Re-docking requiere ~42 horas.
2. **Family classification limitada**: 99.9% clasificado como "other". Necesita clasificación UniProt/EC.
3. **MW residual**: Aunque MW bajó de #1 (0.468) a #2 (0.176), sigue siendo la 2da feature. Esto puede deberse a correlación legítima entre tamaño molecular y afinidad en PDBbind.
4. **ProLIF warnings frecuentes**: "molecule is tagged as 2D" en muchos complejos. No afecta resultados pero genera ruido en logs.
5. **Shell features dispersas**: 14 de 96 shell features tienen SHAP = 0. Combinaciones atómicas raras (halógenos, fósforo) no tienen datos suficientes.
6. **ECIF ligand types simplificados**: Usamos element-only para ligando (no aromaticidad) para garantizar consistencia train/inference con PDBQT.
7. **No hay re-docking validation**: Las poses usadas son cristalográficas. El rendimiento real con poses de docking puede diferir.

---

## 14. Próximos pasos

1. **P3: Re-docking de PDBbind** — poplar Group B features (~42 horas). Script listo: `scripts/redock_pdbbind.py`
2. **Retrain v5** — con Group B features reales, target Spearman ≥ 0.65+
3. **Feature selection**: El modelo A_ext+E (64 features, Spearman 0.537) sugiere que un modelo más compacto podría ser casi igual de bueno.
4. **Family-aware splitting**: Cuando la clasificación UniProt/EC esté implementada, evaluar performance por familia de proteínas.
5. **Integration testing**: Verificar que el backend `model_manager.py` carga v4 correctamente y produce scores coherentes.
