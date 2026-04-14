# ML Rescoring Training Log — v3 (ProLIF + RDKit-direct)

> **Fecha**: 2026-04-06 05:26 UTC  
> **Pipeline**: `rescoring/train_orchestrator.py`  
> **Datos**: PDBbind v2020 refined set  
> **Hardware**: Windows 11, Python 3.14, 12 CPU cores  
> **Duración total**: 963.72 seconds (~16 minutos)

---

## 1. Resumen ejecutivo

Primer entrenamiento exitoso del modelo ML rescoring con features de interacción 3D reales.

| Métrica | v1 (baseline) | v3 (ProLIF) | Mejora |
|---|---|---|---|
| Spearman (CV mean) | 0.275 | **0.435** | **+58%** |
| Features contribuyendo | 1 (solo MW) | 6 (MW + 5 features 3D) | +5 features |
| Features 3D en top-5 SHAP | 0 | 4 | — |
| Criterios de aceptación | N/A | **6/6 PASS** | — |

---

## 2. Datos de entrenamiento

### Pipeline de curación

```
3,884 complejos (INDEX refined)
  → -54  binding_precision (datos no exactos)
  → -364 binding_type (IC50, EC50 removidos; solo Ki, Kd)
  → -25  affinity_range (pKi fuera de [2, 13])
  = 3,441 complejos curados
  → -422 ligand_unparseable (VIP audit)
  = 3,019 complejos VIP aceptados (87.7%)
```

### Distribución de afinidades
- pKi curado: media=8.101, std=2.554, rango=[2.087, 12.658]
- Solo Ki y Kd (datos termodinámicamente interpretables)
- Outliers de pKi removidos por IQR

### Scaffold split
- 5 folds con frozen test set (500 complejos)
- 1,467 scaffolds únicos de 2,519 complejos training
- 1,158 singletons (scaffold único)
- Grupo más grande: 195 complejos

---

## 3. Feature extraction

### Arquitectura v3 (feature_extractor.py)
- **Proteína**: RDKit `Chem.MolFromPDBFile()` con sanitización relajada (0.08s)
  - Fallback: removeHs=True si falla con H
- **Ligando**: RDKit `SDMolSupplier` (robusto)
- **Interacciones**: ProLIF 2.1.0 `Fingerprint(interactions=TARGETED_INTERACTIONS)`
  - 11 tipos de interacción solicitados (excluye VdWContact)
  - Binding site: residuos con átomos a < 10Å del ligando (numpy distances)
  - `n_jobs=1` obligatorio (evitar fork bomb en Windows)
- **Close contacts**: numpy pairwise distances vectorizado (<0.01s)
  - Shells: 4Å y 6Å

### Bug crítico resuelto: ProLIF fork bomb
- ProLIF `run_from_iterable()` tiene parámetro `n_jobs=None` por defecto
- `n_jobs=None` → `get_n_jobs()` → 12 (número de CPU cores)
- Con 6 workers de ProcessPoolExecutor × 12 sub-jobs = 72 procesos
- En Windows (spawn, no fork), cada sub-proceso intenta re-importar el módulo principal
- Resultado: deadlock total, 0 cache files, ~55 procesos congelados
- **Fix**: `fp.run_from_iterable(..., n_jobs=1)` en ambas llamadas
- Bonus: 10x más rápido (2s/complejo vs 25s) porque no hay overhead de multiprocessing para 1 ligando

### Resultados de extracción
| Feature | Media | Nonzero % | Max |
|---|---|---|---|
| hbond_donor_count | 1.8 | 75.9% | 17 |
| hbond_acceptor_count | 1.7 | 77.8% | 13 |
| hydrophobic_contacts | 2.9 | 82.2% | 13 |
| salt_bridges | 0.0 | 0.3% | 2 |
| pi_stacking | 0.6 | 23.5% | 9 |
| pi_cation | 0.1 | 6.2% | 3 |
| metal_coordination | 0.1 | 10.0% | 4 |
| close_contacts_4A | 100.1 | 96.4% | 322 |
| close_contacts_6A | 241.2 | 96.4% | 689 |

- 2,911/3,019 complejos (96.4%) con features no-zero
- 108 complejos (3.6%) retornaron zeros (ligando SDF ilegible)

### Paralelización
- `ProcessPoolExecutor(max_workers=6)` en `train_orchestrator.py`
- JSON cache por complejo en `data/pdbbind/feature_cache/`
- 120s timeout por complejo
- Progress reporting cada 100 complejos con ETA
- Extracción completa: ~15 minutos para 3,019 complejos

---

## 4. Modelo y métricas

### Configuración XGBoost
```python
objective = "reg:squarederror"
max_depth = 6
learning_rate = 0.05
n_estimators = 500
subsample = 0.8
colsample_bytree = 0.8
min_child_weight = 5
gamma = 0.1
early_stopping_rounds = 50
```

### Cross-validation (5-fold scaffold-split)

**Model A (20 features — todos los grupos):**

| Fold | Spearman | Pearson | NDCG@10 | RMSE |
|---|---|---|---|---|
| 0 | 0.352 | 0.380 | 0.353 | 2.388 |
| 1 | 0.426 | 0.420 | 0.481 | 2.255 |
| 2 | **0.537** | **0.535** | 0.312 | 2.279 |
| 3 | 0.444 | 0.449 | 0.336 | 2.159 |
| 4 | 0.417 | 0.430 | 0.330 | 2.312 |
| **Mean** | **0.435** | **0.443** | **0.362** | **2.279** |
| Std | 0.060 | 0.052 | 0.061 | 0.075 |

**Model NULL (7 features — solo 1D/2D):**

| Fold | Spearman | Pearson | RMSE |
|---|---|---|---|
| 0 | 0.273 | 0.275 | 2.504 |
| 1 | 0.196 | 0.222 | 2.431 |
| 2 | 0.287 | 0.306 | 2.565 |
| 3 | 0.289 | 0.308 | 2.296 |
| 4 | 0.295 | 0.297 | 2.435 |
| **Mean** | **0.268** | **0.281** | **2.446** |

### Delta de especificidad 3D
- Mean: 0.025
- Std: 1.009
- Semáforo: green > 0.346, red < -0.544

### Applicability domain
- Threshold (p99 Mahalanobis): 7.2365
- 20 features usados para cálculo

---

## 5. Ablation testing

| Config | Features | Spearman | Interpretación |
|---|---|---|---|
| A_only | 7 | 0.273 | Baseline 1D/2D (MW domina) |
| B_only | 4 | 0.000 | Vina features = 0 siempre (no re-docked) |
| C_only | 9 | 0.216 | Solo 3D: menor que MW sola, pero captura info diferente |
| A+B | 11 | 0.276 | +B no ayuda (todo cero) |
| **A+C** | **16** | **0.362** | **Mejor combo sin B** |
| B+C | 13 | 0.223 | Sin MW, 3D contribuye menos |
| A+B+C | 20 | 0.352 | Ligeramente peor que A+C (B es ruido) |

**Conclusión**: A+C (sin Group B) es el mejor subset actual. Group B necesita datos reales de re-docking.

---

## 6. Problemas identificados y plan de mejora

### P1: Sesgo de MW (CRÍTICO para generalización)
- MW SHAP = 0.468, 1.8x mayor que el siguiente feature
- PDBbind tiene sesgo: moléculas más grandes → más contactos → mayor afinidad
- En producción, usuarios nuevos podrían diseñar moléculas pequeñas excelentes que el modelo subestima
- **Solución**: log-transform MW, o usar MW/surface area, o penalizar MW extremo

### P2: Pobreza de features (MAYOR impacto en Spearman)
- Solo 9 conteos globales: "5 H-bonds" sin saber dónde ni a qué distancia
- Modelos top usan ~800 features: atom-pair fingerprints por shell de distancia
- **Solución**: Shell atom counts (RF-Score) + ECIF → esperable +0.10-0.20

### P3: Group B inútil (mismatch train/inference)
- Training: Vina features = 0 (cristales, no docking)
- Producción: Vina features ≠ 0 (docking real)
- El modelo nunca aprendió a usar estos features → los ignora en inference
- **Solución**: Re-docking de cristales PDBbind con Vina → llenar Group B

### P4: Interacciones raras
- salt_bridges: 0.3% → indetectable
- pi_cation: 6.2% → apenas contribuye
- **Causa probable**: protonación heurística de RDKit no genera cargas correctas en muchos casos
- **Mitigación**: ECIF no depende de asignación de interacciones

---

## 7. Artefactos producidos

| Archivo | Ubicación | Descripción |
|---|---|---|
| `model_a.joblib` | `backend/artifacts/` | Modelo A (20 features, XGBoost) |
| `model_null.joblib` | `backend/artifacts/` | Modelo NULL (7 features, control) |
| `training_report.json` | `backend/artifacts/` | Reporte completo con todas las métricas |
| `applicability_domain.json` | `backend/artifacts/` | Mahalanobis threshold |
| `delta_distribution.json` | `backend/artifacts/` | Semáforo verde/rojo |
| `shap_summary.json` | `backend/artifacts/` | Feature importance |
| `split_config.json` | `data/pdbbind/artifacts/` | Scaffold split reproducible |
| `pdbbind_audit_report.json` | `data/pdbbind/artifacts/` | VIP audit detallado |
| `data_curation_report.json` | `data/pdbbind/artifacts/` | Filtros de curación |
| `feature_cache/*.json` | `data/pdbbind/feature_cache/` | 3,019 archivos de features 3D |
| `training_log_v5.txt` | `data/pdbbind/` | Log completo de la corrida |

---

## 8. Reproducibilidad

Para reproducir exactamente estos resultados:

```bash
cd rescoring/
python train_orchestrator.py \
  --data-dir /path/to/pdbbind \
  --output-dir /path/to/pdbbind/artifacts \
  --seed 42 \
  --n-folds 5 \
  --test-size 500
```

Requisitos:
- PDBbind v2020 refined set con INDEX_refined_data.2020
- Python 3.14 con ProLIF 2.1.0, RDKit, XGBoost, numpy, scikit-learn
- ~16 minutos en máquina de 12 cores

Semilla fija (`seed=42`) garantiza:
- Mismo scaffold split
- Mismo frozen test set
- Misma inicialización de XGBoost
- Features de cache deterministas (ProLIF es determinista dado el mismo input)
