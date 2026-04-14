# External Calibration — 5-HT1A

> Ultima ejecucion: **2026-04-06** (ML Rescoring validation)  
> Estado: **COMPLETADA** — Tres evaluaciones ejecutadas. Vina puro ρ=0.020, ML rescoring ρ=0.176 (p=0.278, NO significativo).  
> Calibración anterior (3RZY): INVALIDADA — ver `docs/RECALIBRATION_AUDIT.md`.  
> ML Rescoring validation: ver `docs/ML_RESCORING_VALIDATION.md` para reporte completo.

---

## Historial de calibraciones

| Fecha | Target | N moléculas | Método | Spearman | Estado |
|---|---|---|---|---|---|
| 2026-04-03 | 3RZY (FABP4 — **ERROR**) | 16 | Vina | -0.233 | INVALIDADA |
| 2026-04-05 | 7E2Y (5-HT1A real) | 40 | Vina (exhaust=32) | 0.020 | COMPLETADA |
| **2026-04-06** | **7E2Y** (5-HT1A real) | **40** | **ML v4 Rescoring** | **0.176** (p=0.278) | **COMPLETADA — NO significativo** |

---

## Objetivo

Medir si MolDesign predice correctamente el **orden relativo** de moléculas según su actividad experimental contra 5-HT1A.

La métrica principal es **Spearman rank correlation** entre:
- `pActivity` experimental (de BindingDB, derivado de IC50/Ki)
- `-affinity (kcal/mol)` predicho por AutoDock Vina (negado para que mayor = mejor)

---

## Target actual: PDB 7E2Y

- **Proteína:** Serotonin 1A (5-HT1A) receptor-Gi protein complex
- **Cadena:** R
- **Ligando co-cristalizado:** Serotonina (SRO)
- **Conformación:** Activa
- **Resolución:** 3.0 Å (Cryo-EM)
- **Referencia:** Xu et al. (2021) Nature 592:469-473. DOI:10.1038/s41586-021-03376-8
- **Grid box:** Centro (103.03, 114.79, 108.36) Å, tamaño 25×25×25 Å — derivado del ligando co-cristalizado
- **Redocking validation:** PASS, Δ < 0.005 Å (ver `artifacts/redocking_validation.json`)

---

## Pipeline de calibración

### Paso 1: Obtener panel desde BindingDB

```bash
cd backend/
python scripts/fetch_bindingdb_5ht1a_panel.py --limit 40 --affinity-cutoff-nm 100000
# Salida: artifacts/bindingdb_5ht1a_panel.json
```

**Muestreo estratificado (3 tiers):**
- Compuestos fuertes (IC50 < 100 nM, pIC50 ≈ 8.0–8.7)
- Compuestos moderados (100 nM – 10 µM, pIC50 ≈ 5.0–8.0)
- Compuestos débiles (> 10 µM, pIC50 ≈ 4.9–5.0)
- Rango dinámico resultante: **3.778 log units** (4.921 – 8.699)

### Paso 2: Ejecutar calibración

```bash
cd backend/
$env:PYTHONPATH="."
python scripts/calibrate_external_panel.py \
  --panel artifacts/bindingdb_5ht1a_panel.json \
  --output artifacts/external_calibration_report.json
```

Nota: el script usa `vina_calibration_exhaustiveness=32` automáticamente (vs 8 en producción).

---

## Resultados de la calibración actual (2026-04-05, contra 7E2Y)

| Parámetro | Valor |
|---|---|
| Target | PDB 7E2Y, cadena R |
| Moléculas dockadas | **40/40 aceptadas, 0 rechazadas** |
| Rango dinámico (pActivity) | **3.778 log units** (4.921 – 8.699) |
| Duración total | 5,771 s (~96 min) |
| Exhaustiveness | **32** (calibración) |
| Fuente de parsing | pdbqt (REMARK VINA RESULT) |
| Vina version | 1.2.7 |
| Semilla | 42 |
| CPU | 1 |

### Métricas de correlación

| Métrica | Valor | Interpretación |
|---|---|---|
| **Spearman ρ** (principal) | **0.020** | Esencialmente sin correlación de ranking |
| Pearson r | -0.136 | Correlación lineal débil negativa |
| MAPE | 33.86% | No es indicador primario (unidades distintas) |

### Estadísticas por tier de actividad

| Tier | N | Avg afinidad (kcal/mol) | Rango | Avg heavy atoms |
|---|---|---|---|---|
| **Fuerte** (pIC50 ≥ 8) | 13 | -8.290 | [-8.698, -7.770] | 25.4 |
| **Moderado** (6 – 8) | 14 | -8.555 | [-10.022, -6.789] | 26.4 |
| **Débil** (< 6) | 13 | -8.592 | [-10.804, -6.864] | 24.5 |

**Observación crítica:** Los promedios de afinidad están **invertidos** — las moléculas experimentalmente más débiles obtienen scores de docking ligeramente mejores (más negativos). Las distribuciones se superponen completamente entre los tres tiers.

### Caso extremo notable

La molécula con **peor actividad experimental** (pIC50 = 4.924, IC50 ≈ 12 µM) obtuvo el **mejor score de docking** (-10.804 kcal/mol). Molécula: C₂₁H₁₅F₃N₂O₃S (trifluorometanosulfonamida naftiloxi-quinolínica, 30 heavy atoms).

### Sesgo por tamaño molecular

Spearman(heavy_atoms, -affinity) = 0.093 — bajo, por lo que el sesgo por tamaño no es la causa principal del fallo de correlación.

---

## Interpretación científica honesta

### ¿Por qué Spearman ≈ 0?

El resultado es consistente con la literatura y tiene causas científicas bien documentadas:

**1. Limitación inherente del scoring function de Vina.**
Vina utiliza una función de scoring empírica que optimiza predicción de **pose** (geometría de unión), no **ranking de afinidad** entre compuestos diversos. Para ranking robusto se requieren métodos como MM-GBSA, FEP o QSAR (Warren et al., 2006; Wang et al., 2015).

**2. Receptor rígido.**
Se utiliza una sola conformación del receptor (7E2Y, estado activo). GPCRs como 5-HT1A exhiben alta flexibilidad conformacional. Ligandos diferentes pueden preferir estados conformacionales distintos del receptor. Docking rígido no captura esto (Katritch et al., 2013).

**3. Diversidad estructural del panel.**
El panel de 40 moléculas incluye quimiotipos muy diversos (indoles, sulfonamidas, naftalenos, heterociclos fusionados). Vina no captura bien diferencias de afinidad entre scaffolds estructuralmente muy distintos — funciona mejor para congeneric series (Gaieb et al., 2019).

**4. Factores no modelados.**
La afinidad experimental (IC50/Ki) incluye contribuciones de: entropía conformacional, desolvación, interacciones con agua estructural, flexibilidad proteica — ninguna de las cuales está modelada adecuadamente por Vina rigid-body.

**5. El rango dinámico de Vina es comprimido.**
Las afinidades predichas (rango -6.86 a -10.80) no discriminan entre el rango experimental de 3.778 log units (factor ~6000x en concentración). Vina comprime la heterogeneidad real en un rango estrecho.

### Qué NO es una limitación del código

El pipeline técnico funciona correctamente:
- Validación química (RDKit, strict mode): 40/40, cero rechazos
- Generación de conformers (ETKDG/MMFF94, seed=42, determinista): 40/40 convergidos
- Preparación de receptor (Meeko): correcta
- Ejecución de Vina (exhaustiveness=32, seed=42, cpu=1): determinista
- Parsing de resultados (PDBQT fallback, cross-validado ≤ 1%)
- Manejo robusto de errores: try/except per-molecule para Vina crashes
- Trazabilidad completa (parsing_source, vina_version, scientific_warnings)
- Afinidades en rango esperado para GPCR (-6 a -11 kcal/mol), a diferencia del -0.9 a -1.5 con 3RZY

---

## Pasos completados

1. ✅ **Validar grid box** (2026-04-03): grid centrado en serotonina (SRO) cristalográfica, centro (103.03, 114.79, 108.36), 25×25×25 Å.
2. ✅ **Re-docking de serotonina** (2026-04-03): redocking_validation.json, PASS, Δ < 0.005 Å.
3. ✅ **Auditoría de recalibración** (2026-04-04): 0.000000% error matemático, 92 tests de precisión, artefactos inválidos marcados.
4. ✅ **Re-ejecutar calibración externa** (2026-04-05): 40 moléculas BindingDB contra 7E2Y/R, exhaustiveness=32, Spearman=0.020.

## Próximos pasos: ML Rescoring (VALIDADO — resultados mixtos)

> Documento completo: `docs/ML_RESCORING_VALIDATION.md`

El modelo XGBoost v4 entrenado en PDBbind v2020 (CV Spearman 0.601±0.040) fue evaluado en dos pruebas críticas:

**Test 1 — Re-evaluación del panel 5-HT1A:**
- ML Rescoring ρ = 0.176 (p=0.278) — mejora direccional desde Vina ρ=0.020 pero **NO estadísticamente significativo**
- Model NULL (solo 1D/2D) ρ = 0.022 — confirma que la mejora viene de features 3D

**Test 2 — Degradación Crystal→Docked:**
- Crystal ρ = 0.585 (p=2e-5), Docked ρ = 0.555 (p=6e-5) — Δρ = -0.030
- Predicciones crystal vs docked: ρ = 0.946 (excelente consistencia)
- El modelo tolera bien el cambio de poses cristalográficas a poses docked

**Conclusión:** El modelo ML funciona bien en el dominio de PDBbind (holdout ρ=0.555) pero la transferencia a 5-HT1A específico no es estadísticamente significativa. Esto es consistente con la subrepresentación de GPCRs en PDBbind.

### Próximos pasos adicionales (post-ML rescoring)

1. **Ensemble docking** — usar múltiples conformaciones del receptor (7E2Y, 7E2X, 7E2Z) para capturar flexibilidad.
2. **Congeneric series** — limitar calibración a una sola serie química como validación adicional.
3. **Ampliar panel** — incluir >100 compuestos con mayor cobertura del espacio químico.
4. **Prueba con otro target** — evaluar si la falta de correlación es específica de 5-HT1A o general del setup.

---

## Gates de calidad

| Gate | Umbral | Status |
|---|---|---|
| Consistencia numérica interna (SDF vs PDBQT) | ≤ 1% | ✅ Cumplido |
| Determinismo del docking (stddev = 0) | stddev ≤ 1e-6 | ✅ Confirmado |
| Afinidades en rango esperado para GPCRs | [-12, -4] kcal/mol | ✅ Cumplido (-6.86 a -10.80) |
| 0 moléculas rechazadas por fallo de docking | 0/40 | ✅ Cumplido |
| Spearman externo ≥ 0.3 | Aspiracional | ❌ No alcanzado (0.020) |

El gate de Spearman ≥ 0.3 es aspiracional para docking rígido puro. No alcanzarlo no invalida el pipeline — **documenta una limitación real y bien conocida de AutoDock Vina para ranking de compuestos diversos**. Esta transparencia es parte integral de la validez científica del proyecto.

> **Implicación para el producto:** El score de docking de MolDesign es útil para:
> - filtrado grueso (eliminar moléculas que no caben en el sitio activo),
> - comparación dentro de series congénericas (mismo scaffold, variaciones menores),
> - generación de poses 3D para visualización.
>
> **No es confiable para:** ranking fino de moléculas estructuralmente diversas por afinidad.
> Esta limitación se comunica al usuario en `MethodDisclaimer.tsx`.

---

## Trazabilidad del artefacto

`backend/artifacts/external_calibration_report.json`

Por cada molécula: canonical_smiles, activity_value (pIC50), predicted_affinity_kcal (Vina), parsing_source, vina_version, vina_random_seed, scientific_warnings, active_label.

---

## Referencias

- Trott & Olson (2010). AutoDock Vina. J Comput Chem 31(2):455-461.
- Katritch et al. (2013). Structure-based discovery. Trends Pharmacol Sci 34(1):9-26.
- Warren et al. (2006). Critical assessment of docking programs. J Med Chem 49(20):5912-5931.
- Wang et al. (2015). Accurate and reliable prediction of relative ligand binding potency. J Am Chem Soc 137(7):2695-2703.
- Gaieb et al. (2019). D3R Grand Challenge 3: Blind prediction of protein-ligand poses. J Comput Aided Mol Des 33:1-18.
- BindingDB (2024). bindingdb.org — Uniprot P35355, 5-HT1A.
