# Análisis Científico Completo de MolDesign

> **Fecha:** 2026-04-03  
> **Última actualización:** 2026-04-05 ~04:00 UTC (calibración externa contra 7E2Y completada, Celery operativo, frontend verificado)  
> **Metodología:** Auditoría sistemática de todo el código fuente, artefactos de calibración, y validación cruzada contra fuentes externas (RCSB PDB, BindingDB, literatura).  
> **Principio:** Solo se reportan hallazgos verificables y reproducibles. Cada afirmación incluye su fuente.

---

## Resumen Ejecutivo

El pipeline científico de MolDesign está bien arquitecturado: separación de responsabilidades clara, trazabilidad SHA-256, reproducibilidad determinista (seed=42, stddev=0), validación química robusta con RDKit, y honestidad metodológica genuina. Sin embargo, **el hallazgo más crítico invalida toda la dimensión de docking del sistema**: el PDB 3RZY configurado como "receptor 5-HT1A" es en realidad **FABP4 (Fatty Acid-Binding Protein 4, adipocyte)**, una proteína completamente distinta. Esto explica las afinidades anómalamente débiles (-0.9 a -1.5 kcal/mol) y la correlación negativa con datos experimentales de 5-HT1A.

> **ACTUALIZACIÓN 2026-04-04:** Los hallazgos 1 y 2 fueron RESUELTOS (target corregido a 7E2Y, normalización validada). Hallazgos 3, 8 y 9 fueron RESUELTOS. Hallazgos 5, 7, 10 siguen pendientes (no bloqueantes). Se ejecutó auditoría de recalibración completa con 0.000000% de error matemático y 92 tests de precisión (<1%). Ver `docs/RECALIBRATION_AUDIT.md`.
>
> **ACTUALIZACIÓN 2026-04-04 (sesión nocturna):** Infraestructura local completamente operativa (PostgreSQL 17.9, Redis, MinIO, FastAPI). 484 tests pasando (455 unit + 29 integration). Smoke test end-to-end exitoso vía API. Pendiente: iniciar Celery worker para docking jobs y re-ejecutar calibración externa contra 7E2Y.
>
> **ACTUALIZACIÓN 2026-04-05:** Calibración externa contra 7E2Y **COMPLETADA** — 40 moléculas BindingDB, exhaustiveness=32, Spearman=0.020 (target ≥ 0.3 no alcanzado). Resultado honesto: Vina rigid-body docking no correlaciona ranking de afinidad para panel diverso de 5-HT1A. Las afinidades ahora están en rango esperado (-6.86 a -10.80 kcal/mol) confirmando que el target 7E2Y ES correcto (vs -0.9 a -1.5 con 3RZY). Celery worker operativo, frontend verificado en puerto 3000. Pipeline end-to-end funcional: SMILES → validación → propiedades → conformer → Vina → scoring → AI report → DB.
>
> **ACTUALIZACIÓN 2026-04-04 (sesión de arquitectura):** Análisis profundo de la causa del Spearman=0.020 y diseño de solución: **ML Rescoring** con XGBoost/RF entrenado en PDBbind (~5,000 complejos experimentales). Se evaluaron y descartaron alternativas (MM-GBSA, FEP, QSAR, pharmacophore scoring, receptor profiling manual). Se identificaron **6 problemas abiertos graves** (feature extraction, pose quality, sesgo de ligando, compatibilidad Python 3.14, representación de GPCRs, generalización). Documento completo: `docs/ML_RESCORING_ARCHITECTURE.md`. **No hay código implementado — solo diseño documentado.**

---

## HALLAZGO 1 — CRÍTICO: PDB 3RZY NO es 5-HT1A

### Evidencia verificada

| Campo | Lo que dice el código | Realidad verificada en RCSB |
|---|---|---|
| PDB ID | `default_target_pdb_id = "3RZY"` | 3RZY |
| Proteína asumida | "receptor 5-HT1A" | **FABP4 — Human adipocyte lipid-binding protein** |
| Organismo | — | Homo sapiens |
| Forma | — | **APO (sin ligando)** |
| Resolución | — | 1.08 Å (excelente, pero proteína incorrecta) |
| Referencia | — | Gonzalez & Fisher, Acta Cryst F (2015), DOI: 10.1107/S2053230X14027897 |
| UniProt | — | **P15090** (FABP4_HUMAN) |

### Fuente de verificación
URL consultada directamente: https://www.rcsb.org/structure/3RZY

> **"Human adipocyte lipid-binding protein FABP4, Apo form at 1.08 Ang resolution."**

### Impacto

1. **Todo el docking está evaluando unión a FABP4, no a 5-HT1A.** Los resultados son científicamente inválidos para el propósito declarado.
2. **La calibración contra BindingDB (16 compuestos de 5-HT1A)** no tiene sentido — se evaluó afinidad por 5-HT1A experimentalmente pero se dockeó contra FABP4.
3. **La correlación Spearman = −0.233** se explica completamente: no hay razón para esperar correlación entre afinidad a 5-HT1A y docking a FABP4.
4. **Las afinidades uniformemente débiles (-0.9 a -1.5 kcal/mol)** son esperables: FABP4 apo no tiene un bolsillo de unión complementario para ligandos de serotonina.
5. **El grid box center (-12.5, 16.3, -8.1)** apunta a alguna zona de FABP4, no al sitio activo de 5-HT1A.

### Acción requerida — URGENTE

Reemplazar 3RZY por una estructura real de 5-HT1A. Opciones verificadas en RCSB PDB:

| PDB ID | Proteína | Ligando | Conformación | Resolución | Referencia |
|---|---|---|---|---|---|
| **7E2Y** | 5-HT1A–Gi complex | Serotonina (5-HT) | **Activa** | 3.0 Å | Xu et al., Nature (2021) |
| **7E2X** | 5-HT1A–Gi complex | Aripiprazol | Activa | 3.0 Å | Xu et al., Nature (2021) |
| **7E2Z** | 5-HT1A–Gi complex | LSD | Activa | 2.9 Å | Xu et al., Nature (2021) |

**Recomendación:** Usar **7E2Y** como target primario del MVP.

- Es la conformación activa con el ligando endógeno (serotonina).
- Permite redocking validation usando el ligando co-cristalizado.
- Es la estructura más relevante para drug discovery enfocado en agonistas.
- Publicada en Nature con revisión por pares rigurosa.

**Referencia completa:** Xu P, Huang S, Zhang H, et al. "Structural insights into the lipid and ligand regulation of serotonin receptors." Nature. 2021;592(7854):469-473. DOI: 10.1038/s41586-021-03376-8

### Pasos concretos de implementación

1. Cambiar `default_target_pdb_id` de `"3RZY"` a `"7E2Y"` en `config.py`.
2. Cambiar `default_target_chain` a la cadena del receptor (probablemente `"R"` o `"A"` — verificar en RCSB).
3. **Extraer las coordenadas del ligando co-cristalizado (serotonina)** del PDB para calcular el nuevo grid center.
4. Recalcular el grid box para que envuelva el sitio de unión de serotonina + margen de 5 Å.
5. Ejecutar **redocking** del ligando co-cristalizado y verificar RMSD < 2.0 Å como validación del setup.
6. Repetir el benchmark de reproducibilidad (Aspirin/Caffeine/Ibuprofen).
7. Repetir la calibración externa con el panel de BindingDB.
8. Actualizar toda la documentación.

---

## HALLAZGO 2 — CRÍTICO: Normalización de afinidad desacoplada de la realidad

### Evidencia

En `scoring/normalizer.py`, la función `normalize_affinity()`:

```python
best = -12.0   # → 100
worst = -4.0   # → 0
```

Pero las afinidades reales del sistema son:

| Molécula | Afinidad real (kcal/mol) | Score normalizado |
|---|---|---|
| Aspirina | -1.340 | **0** (está por encima de -4.0) |
| Cafeína | -1.439 | **0** |
| Ibuprofeno | -1.219 | **0** |
| 16 compuestos BindingDB | -0.899 a -1.542 | **0 para todos** |

### Impacto

- El 45% del peso del score total (la dimensión de afinidad) es **siempre cero**.
- El score compuesto está calculándose efectivamente como: `total = ADME × 0.30 + druglikeness × 0.25`
- **Ningún usuario recibirá diferenciación por calidad de docking.** El sistema es un calculador de Lipinski/logP glorificado.

### Nota importante

Este hallazgo se origina parcialmente por el Hallazgo 1 (proteína equivocada). Una vez corregido el target a 7E2Y, las afinidades deberían estar en el rango esperado de -5 a -10 kcal/mol. Sin embargo:

### Acción requerida

1. **Después de corregir el target**, verificar que las afinidades estén en rango [-12, -4].
2. Si las afinidades reales con el target correcto caen en un rango distinto, **adaptar `best` y `worst` basándose en los datos observados** del benchmark.
3. Considerar usar normalización basada en percentiles del propio dataset en vez de umbrales fijos, para mayor robustez.
4. **Documentar explícitamente** qué rango se usa y por qué.

---

## HALLAZGO 3 — IMPORTANTE: Falta redocking validation

### Fundamento científico

En cualquier estudio de docking computacional serio, el primer paso obligatorio es **redocking validation**:

1. Extraer el ligando co-cristalizado del PDB.
2. Re-dockear ese ligando en el mismo receptor con los mismos parámetros.
3. Medir el RMSD (Root Mean Square Deviation) entre la pose predicha y la pose cristalográfica.
4. Si RMSD > 2.0 Å, el setup de docking no es confiable.

**Referencia:** Hevener KE et al., "Validation of molecular docking programs for virtual screening against dihydropteroate synthase." J Chem Inf Model. 2009;49(2):444-460. DOI: 10.1021/ci800293n

### Estado actual

No existe ningún script ni validación de redocking en el proyecto.

### Acción requerida

Crear un script `scripts/validate_redocking.py` que:

1. Descargue el PDB del target (7E2Y, tras la corrección).
2. Extraiga el ligando co-cristalizado (serotonina).
3. Genere el conformer 3D independiente del ligando via SMILES.
4. Ejecute Vina con los mismos parámetros del pipeline.
5. Calcule RMSD entre pose predicha y cristalográfica.
6. Reporte: RMSD, afinidad predicha, y un juicio de pass/fail (umbral: RMSD ≤ 2.0 Å).

Este script debe ejecutarse siempre que se cambie:
- el target PDB
- el grid box
- parámetros de Vina
- la preparación del receptor

---

## HALLAZGO 4 — IMPORTANTE: SDF export no preserva metadatos de afinidad

### Evidencia

En la calibración, los 16 compuestos muestran:
```
"parsing_source": "pdbqt"
```

Y el warning:
> "Las afinidades se obtuvieron desde REMARK VINA RESULT del PDBQT porque el SDF exportado no incluyó metadatos numéricos."

### Impacto

- El parser primario (SDF con `mk_export`) no está funcionando como esperado.
- Todas las afinidades vienen del parser secundario (PDBQT REMARK).
- La cross-validation SDF↔stdout nunca se ejecuta realmente (siempre se va por PDBQT↔stdout).

### Acción requerida

1. Investigar por qué `mk_export` no incluye metadatos de afinidad en el SDF.
2. Posibles causas: versión de Meeko, flags faltantes en el comando de export, formato de output de Vina.
3. Si el SDF no puede incluir afinidad, documentar explícitamente que PDBQT es el parser de facto.
4. Alternativamente, parsear el log de Vina además de los archivos de output.

---

## HALLAZGO 5 — MODERADO: exhaustiveness=8 es el mínimo para screening rápido

### Fundamento científico

AutoDock Vina usa Monte Carlo + gradient optimization. El parámetro `exhaustiveness` controla cuántas veces se corre la búsqueda estocástica:

| Exhaustiveness | Uso típico | Tiempo relativo |
|---|---|---|
| 8 | Screening rápido, exploratorio | 1× |
| 16 | Screening con mayor confiabilidad | 2× |
| 32 | Publicación, validación | 4× |
| 64+ | Benchmarks exhaustivos | 8×+ |

**Referencia:** Trott O, Olson AJ. "AutoDock Vina: improving the speed and accuracy of docking with a new scoring function." J Comput Chem. 2010;31(2):455-461.

### Estado actual

`vina_exhaustiveness = 8` — adecuado para MVP pero debe documentarse como limitación y elevarse para resultados de mayor confianza.

### Acción recomendada

1. Mantener 8 como default para evaluaciones rápidas.
2. Agregar opción `high_quality_mode` con exhaustiveness=32 para evaluaciones importantes.
3. Documentar en la UI que el resultado puede variar con mayor exhaustiveness.

---

## HALLAZGO 6 — MODERADO: Falta considerar estados de protonación

### Fundamento científico

A pH fisiológico (7.4), las aminas alifáticas están protonadas (pKa ~10-11), los ácidos carboxílicos están desprotonados (pKa ~4), y los imidazoles pueden estar parcialmente protonados (pKa ~6). La protonación afecta:

- Cargas formales → interacciones electrostáticas con el receptor.
- Geometría → conformación del ligando.
- Descriptores → logP, TPSA, HBD/HBA cambian con protonación.

**Referencia:** Shelley JC et al., "Epik: a software program for pK(a) prediction and protonation state generation for drug-like molecules." J Comput Aided Mol Des. 2007;21(12):681-691.

### Estado actual

El pipeline usa las moléculas tal como entran por SMILES, sin ajustar protonación a pH 7.4. Meeko tiene opciones de protonación (`--pH`) pero no se están usando.

### Acción recomendada

1. **Corto plazo:** Documentar que la protonación no se ajusta y que es una limitación conocida.
2. **Mediano plazo:** Integrar `Dimorphite-DL` (open source, Durrant Lab) para generar formas protonadas a pH 7.4:
   - Durrant JD, McCammon JA. "Molecular dynamics simulations and drug discovery." BMC Biol. 2011;9:71.
   - GitHub: https://github.com/durrantlab/dimorphite_dl
3. O usar el flag `--pH 7.4` de Meeko `mk_prepare_ligand` si está disponible en la versión instalada.

---

## HALLAZGO 7 — MODERADO: QED como complemento/reemplazo del ADME score heurístico

### Fundamento científico

El **Quantitative Estimate of Drug-likeness (QED)** de Bickerton et al. es un score compuesto ampliamente validado que combina 8 propiedades moleculares usando funciones de deseabilidad derivadas de fármacos aprobados:

- MW, logP, HBA, HBD, PSA, ROTB, AROM (anillos aromáticos), ALERTS (structural alerts)

**Referencia:** Bickerton GR, Paolini GV, Besnard J, Muresan S, Hopkins AL. "Quantifying the chemical beauty of drugs." Nature Chemistry. 2012;4:90-98. DOI: 10.1038/nchem.1243

### Disponibilidad

QED está implementado en RDKit directamente:

```python
from rdkit.Chem import QED
score = QED.qed(mol)  # retorna 0.0 a 1.0
```

### Comparación con el ADME score actual

| Aspecto | ADME score actual | QED |
|---|---|---|
| Fuente | Heurística ad-hoc del proyecto | Derivado de ~800 fármacos aprobados oralmente |
| Validación | No validada externamente | Publicado y citado >2000 veces |
| Gradiente | logP/TPSA/rotBonds lineales | Funciones de deseabilidad sigmoidal/gaussiana |
| Reproducibilidad | Sí (determinista) | Sí (determinista, en RDKit) |
| Limitaciones | No captura alertas estructurales | No captura selectividad ni ADME experimental |

### Acción recomendada

1. **Agregar QED como descriptor adicional** en `chem/properties.py` — es una llamada a RDKit, sin dependencias externas.
2. **Reportar QED junto al ADME score heurístico**, dejando que el usuario vea ambos.
3. **No reemplazar** el ADME score heurístico inmediatamente — ambos aportan perspectivas distintas.
4. Considerar usar QED como uno de los componentes del score compuesto en una futura iteración.

---

## HALLAZGO 8 — MODERADO: Drug-likeness score sin gradiente

### Evidencia

En `normalizer.py`:

```python
total = 100.0 - (lipinski_violations * 20.0) - (veber_violations * 10.0)
```

Esto significa que:
- Una molécula con MW=499 (justo debajo del umbral) tiene el mismo score que una con MW=200.
- No hay gradiente para "qué tan cerca del límite" está cada propiedad.

### Acción recomendada

Agregar penalización gradual cuando las propiedades están cerca de los umbrales. Por ejemplo, para MW:

```python
# En vez de solo 0 o 20 de penalización:
if mw > 500:
    penalty = 20.0
elif mw > 450:
    penalty = (mw - 450) / 50 * 10.0  # 0 a 10 puntos de penalización gradual
else:
    penalty = 0.0
```

Esto es científicamente más honesto porque la diferencia entre MW=499 y MW=501 no es biológicamente significativa, pero el sistema actual trata una como perfecta y la otra con -20 puntos.

---

## HALLAZGO 9 — MENOR: Gaps en cobertura de tests

### Estado actual

| Módulo | Tests unitarios | Cobertura |
|---|---|---|
| `chem/validator.py` | ✅ 55 tests | Excelente |
| `chem/properties.py` | ✅ ~50 tests | Excelente |
| `scoring/normalizer.py` | ❌ 0 tests | **Ninguna** |
| `scoring/engine.py` | ❌ 0 tests | **Ninguna** |
| `chem/conformer.py` | ❌ 0 tests | **Ninguna** |
| Integración pipeline | ❌ 0 tests | **Ninguna** |

### Acción recomendada

Prioridad de tests a crear, según impacto científico:

1. **`test_normalizer.py`** — Verificar que las funciones de normalización producen valores esperados en los boundaries:
   - `normalize_affinity(-12) == 100`, `normalize_affinity(-4) == 0`, `normalize_affinity(-8) == 50`
   - `normalize_logp(2.5) == 100`, `normalize_logp(-1) == 0`, `normalize_logp(6) == 0`
   - Todos los edge cases de TPSA y rotatable bonds

2. **`test_engine.py`** — Verificar que el score compuesto reproduce valores conocidos:
   - Pesos suman 1.0
   - Total score está en [0, 100]
   - Strongest/weakest dimension se identifican correctamente

3. **`test_conformer.py`** — Verificar que la generación 3D produce resultados válidos:
   - SDF output contiene coordenadas 3D
   - ETKDGv3 + seed=42 es determinista
   - Macrociclos disparan warning

---

## HALLAZGO 10 — MENOR: TPSA normalización no diferencia CNS vs oral

### Fundamento

Para 5-HT1A (un target CNS), la TPSA óptima para penetración de barrera hematoencefálica es **< 60-70 Å²**, no < 90 Å².

**Referencia:** Pajouhesh H, Lenz GR. "Medicinal chemical properties of successful central nervous system drugs." NeuroRx. 2005;2(4):541-553.

### Estado actual

`normalize_tpsa()` da 100 a todo el rango 20-90 Å², sin distinción para CNS.

### Acción recomendada

Cuando el target sea CNS (como 5-HT1A), usar un perfil de TPSA más estricto:
- Sweet spot: 20-60 Å² → 100
- 60-90 Å² → decaimiento suave
- >90 Å² → penalización fuerte

Esto requiere parametrizar la normalización por tipo de target (CNS vs oral periférico), lo cual se puede hacer cuando se agregue multi-target.

---

## Resumen de prioridades de mejora

| # | Hallazgo | Severidad | Esfuerzo | Impacto | Estado (2026-04-04) |
|---|---|---|---|---|---|
| 1 | PDB 3RZY es FABP4, no 5-HT1A | **CRÍTICO** | Medio | Invalida todo docking | ✅ **RESUELTO** — Target corregido a 7E2Y/R |
| 2 | Normalización afinity [−12,−4] vs real [−1,−1.5] | **CRÍTICO** | Bajo | Score de afinidad siempre = 0 | ✅ **RESUELTO** — Rango [-10,-4] validado con 7E2Y (afinidades en rango) |
| 3 | No hay redocking validation | **IMPORTANTE** | Medio | Sin validación del setup | ✅ **RESUELTO** — `redocking_validation.json` PASS, Δ < 0.005 Å |
| 4 | SDF export no preserva afinidad | **IMPORTANTE** | Bajo-Medio | Parser siempre en fallback | ⚠️ Documentado como limitación |
| 5 | Exhaustiveness=8 mínimo | Moderado | Bajo | Calidad de poses | ⚠️ Documentado; exhaust=32 en calibración |
| 6 | Sin ajuste de protonación pH 7.4 | Moderado | Medio | Afinidades pueden cambiar | ⚠️ Documentado como limitación |
| 7 | QED no integrado | Moderado | Bajo | Score ADME sin validación externa | ✅ **RESUELTO** — QED integrado en `properties.py` |
| 8 | Drug-likeness sin gradiente | Moderado | Bajo | Sensibilidad del score | ✅ **RESUELTO** — Penalizaciones graduales implementadas |
| 9 | Tests faltan para scoring/conformer | Menor | Medio | Confiabilidad | ✅ **RESUELTO** — 484 tests (455 unit + 29 integration, incl. 92 de precisión <1%) |
| 10 | TPSA no ajustada para CNS | Menor | Bajo | Especificidad del scoring | ⚠️ Pendiente para multi-target |
| 11 | Vina no rankea compuestos diversos (Spearman=0.020) | **IMPORTANTE** | Alto | Dimensión de afinidad sin ranking útil | 🔄 EN DISEÑO — ML Rescoring propuesto |

---

## HALLAZGO 11 — IMPORTANTE: Vina no produce ranking útil para compuestos diversos

### Evidencia

Calibración externa contra PDB 7E2Y (5-HT1A real, cadena R) con 40 moléculas de BindingDB:
- **Spearman ρ = 0.020** (target aspiracional ≥ 0.3)
- Promedios de afinidad invertidos: débiles exp. = -8.59, fuertes exp. = -8.29 kcal/mol
- La molécula de peor actividad experimental (pIC50=4.924) obtuvo el mejor score Vina (-10.804)

### Causa

Limitación fundamental y documentada del scoring function de AutoDock Vina para ranking entre compuestos estructuralmente diversos. Consistente con la literatura (Warren 2006, Gaieb 2019).

### Solución propuesta: ML Rescoring

Modelo XGBoost/RF entrenado en PDBbind refined set (~5,000 complejos experimentales).
Documento completo: `docs/ML_RESCORING_ARCHITECTURE.md`.

**Problemas abiertos graves (6):** feature extraction, pose quality, sesgo de ligando, compatibilidad Python 3.14, sub-representación de GPCRs, generalización.

**Estado:** DISEÑO — no hay código implementado. Los problemas abiertos deben resolverse antes de implementar.

---

## Plan de acción recomendado

### Fase inmediata (bloquea todo lo demás)
1. **Corregir el PDB target** → cambiar a 7E2Y (5-HT1A activo con serotonina).
2. **Calcular grid box correcto** desde coordenadas del ligando co-cristalizado en 7E2Y.
3. **Ejecutar redocking validation** de serotonina → verificar RMSD < 2.0 Å.
4. **Repetir benchmark** de reproducibilidad con el target correcto.

### Fase de calibración (validar el fix)
5. **Repetir calibración externa** con el panel BindingDB de 5-HT1A.
6. **Ajustar normalización de afinidad** al rango real observado.
7. **Verificar que Spearman mejora** (aspiracional: ≥ 0.3).

### Fase de mejora del scoring
8. **Agregar QED** como descriptor complementario.
9. **Agregar gradiente** al drug-likeness score.
10. **Documentar protonación** como limitación conocida.

### Fase de robustez
11. **Crear tests** para normalizer, engine, conformer.
12. **Investigar SDF export** para afinidades.
13. **Agregar opción high-quality** con exhaustiveness=32.

### Fase de mejora del ranking (ML Rescoring) — EN DISEÑO
14. **Resolver problemas abiertos** documentados en `docs/ML_RESCORING_ARCHITECTURE.md`.
15. **Verificar compatibilidad** de ODDT, XGBoost, SHAP con Python 3.14.
16. **Descargar y procesar PDBbind** refined set (~5,000 complejos).
17. **Entrenar modelo ML** con ablation testing y scaffold-split validation.
18. **Validar contra sesgo de ligando** — el modelo NO debe funcionar solo con MW/LogP.
19. **Recalibrar** — correr las 40 moléculas con nuevo pipeline, medir nuevo Spearman.
20. **Si Spearman no mejora significativamente → documentar y evaluar alternativas.**

---

## Lo que está BIEN en el proyecto

Es importante reconocer lo que funciona correctamente:

1. **Arquitectura modular** — Separación de responsabilidades excelente entre `chem/`, `scoring/`, `services/`, `api/`, `db/`.
2. **Validación química** — `validator.py` con 483 líneas y 55 tests es exhaustivo y bien documentado.
3. **Propiedades fisicoquímicas** — `properties.py` con referencias a Lipinski (1997), Veber (2002), Ertl (2000), y valores validados contra PubChem.
4. **Reproducibilidad** — seed=42, stddev=0.0 en benchmarks, cross-validation de parsers.
5. **Honestidad metodológica** — `scientific_warnings` en cada resultado, `SCIENTIFIC_GUARDRAILS.md`, y prompt de IA que prohíbe inventar datos.
6. **Trazabilidad** — SHA-256 de SMILES canónico, `parsing_source`, `vina_version`, timestamps.
7. **Degradación graceful** — IA falla → sistema continúa; Vina falla → error explícito; SDF vacío → fallback a PDBQT.
8. **Excepciones específicas** — 538 líneas de jerarquía de excepciones con HTTP codes correctos.
9. **Documentación científica** — Cada función explica qué hace, por qué, y cuáles son sus limitaciones.
10. **Filosofía del proyecto** — `copilot-instructions.md` y `SCIENTIFIC_GUARDRAILS.md` son documentos serios que priorizan ciencia sobre marketing.

El proyecto tiene una base sólida. El problema principal (target incorrecto) es severo pero reparable. Una vez corregido, el pipeline tiene todos los elementos necesarios para producir resultados científicamente defendibles.

---

## Nota sobre verificabilidad

Cada hallazgo de este análisis es verificable:

- **Hallazgo 1:** Visitar https://www.rcsb.org/structure/3RZY y leer "Human adipocyte lipid-binding protein FABP4".
- **Hallazgo 2:** Ejecutar `normalize_affinity(-1.3)` → retorna 0.0 porque -1.3 > -4.0.
- **Hallazgos 5-6:** Referencias bibliográficas con DOI verificable.
- **Hallazgo 7:** Ejecutar `from rdkit.Chem import QED; QED.qed(mol)` en cualquier instalación de RDKit.
- **Hallazgos 3, 9:** Verificable por inspección directa de los archivos del proyecto.
- **Hallazgo 11:** Ver `artifacts/external_calibration_report.json` y `docs/EXTERNAL_CALIBRATION_5HT1A.md`. Diseño de solución en `docs/ML_RESCORING_ARCHITECTURE.md`.
