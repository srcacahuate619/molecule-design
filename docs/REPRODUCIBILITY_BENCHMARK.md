# Reproducibility Benchmark (Docking)

Este benchmark formaliza una validación reproducible del pipeline de docking del MVP.

## Objetivo

Verificar que, con protocolo fijo y semilla fija de Vina, múltiples corridas sobre el mismo panel molecular producen los mismos resultados numéricos y trazabilidad completa.

## Panel de referencia actual

- Aspirin
- Caffeine
- Ibuprofen

## Protocolo congelado

- Target: `7E2Y` cadena `R` (5-HT1A receptor con serotonina, Xu et al. 2021)
- Grid box: centro (103.03, 114.79, 108.36), tamaño 25×25×25 Å (centrado en serotonina cristalográfica)
- Vina: `exhaustiveness`, `num_modes`, `cpu`, `seed` definidos en `core.config`
- Parsing jerárquico: `SDF -> PDBQT REMARK -> tabla stdout`

> **Nota histórica:** El target anterior era 3RZY/A, que resultó ser FABP4 (no 5-HT1A). Corregido 2026-04-03.

## Criterios de aceptación

1. Determinismo con semilla fija: `stddev(best_affinity) <= 1e-6` por molécula.
2. Consistencia numérica entre parsers: error relativo de afinidad mejor pose `<= 1%`.
3. Trazabilidad obligatoria: cada resultado debe incluir `parsing_source`, `vina_version`, `vina_random_seed`.
4. Transparencia: `scientific_warnings` no se ocultan.

## Gate de plausibilidad molecular (modo estricto)

El validador rechaza entradas con:

- elementos no defendibles para el pipeline Vina,
- radicales electrónicos,
- cargas formales extremas,
- múltiples fragmentos desconectados (sales/mezclas), salvo que se desactive explícitamente.

## Ejecución

Desde `backend/`:

`../.venv/Scripts/python.exe scripts/benchmark_reference_panel.py --repeats 3`

Archivo de salida por defecto:

- `backend/artifacts/benchmark_reference_panel.json`

## Auditoría de precisión (2026-04-04)

Se verificó que los scores almacenados en el benchmark coinciden exactamente con los recalculados por las funciones de normalización. Error: 0.000000%. Formalizado en `tests/unit/test_recalibration_precision.py::TestBenchmarkIntegrity` (4 tests).

Ver `docs/RECALIBRATION_AUDIT.md` para documentación completa.

## Interpretación

- Si una molécula no cumple determinismo, no se considera calibrada para comparaciones externas.
- Si `parsing_source` cae a `vina_stdout`, revisar exportación Meeko (`mk_export`) y conservar logs.
- Afinidades débiles (por ejemplo > -3 kcal/mol) deben reportarse como baja evidencia de unión, no como éxito.
