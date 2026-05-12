# MolDesign Scientific Guardrails

---

## Estado de cumplimiento (2026-04-13)

**Guardrails científicos activos y auditados.**

Al 13 de abril de 2026, todos los guardrails científicos descritos en este documento están implementados y verificados en el MVP. El sistema rechaza inputs no reproducibles, nunca inventa resultados, y reporta explícitamente toda limitación, warning o degradación. La trazabilidad y honestidad metodológica están garantizadas en el pipeline actual.

---

## Propósito

Este documento existe para evitar desviaciones del proyecto hacia resultados engañosos, estética vacía o simplificaciones que comprometan la verdad científica.

MolDesign debe operar lo más cerca posible de la realidad computacional reproducible disponible en open source y cómputo accesible.

---

## Axiomas del sistema

### Axioma 1 — La evidencia computacional precede a la narrativa
Primero se calcula.
Luego se interpreta.
Nunca al revés.

### Axioma 2 — Los números no salen de la IA
Ningún valor científico puede originarse en un modelo generativo.

### Axioma 3 — El score no es verdad biológica
El score total sirve para priorización computacional, no para afirmar eficacia real.

### Axioma 4 — La incertidumbre debe verse
Toda aproximación, warning o limitación debe ser visible para usuario y desarrollador.

### Axioma 5 — Fallar honestamente es mejor que acertar ficticiamente
Si el sistema no puede sostener científicamente una salida, debe fallar o degradarse explícitamente.

---

## Fuente de verdad por capa

### `chem/`
Fuente de verdad para:
- validez estructural,
- canonicalización,
- propiedades fisicoquímicas,
- generación de conformer.

Tecnología esperada:
- RDKit.

### `services/docking/`
Fuente de verdad para:
- preparación de proteína,
- preparación del ligando para docking,
- ejecución de Vina,
- poses y afinidad primaria.

Tecnología esperada:
- AutoDock Vina + utilidades explícitas de preparación.

### `scoring/`
Fuente de verdad para:
- normalización,
- score compuesto,
- breakdown y improvement hints.

Restricción:
- toda función debe ser explícita, auditable y documentada.

### `services/ai/`
Fuente de verdad para:
- ninguna métrica.

Responsabilidad real:
- interpretación, explicación y contextualización.

### `services/blockchain/`
Fuente de verdad para:
- registro y certificación de autoría/timestamp.

No puede:
- alterar ciencia,
- redefinir score,
- validar química.

---

## Qué afirmaciones son científicamente aceptables

Aceptable:
- “la afinidad de docking calculada fue X kcal/mol”
- “el perfil es compatible/incompatible con ciertas heurísticas de drug-likeness”
- “el resultado sugiere una hipótesis de trabajo”
- “merece evaluación adicional”

No aceptable:
- “la molécula funciona”
- “la molécula cura”
- “se confirmó actividad biológica”
- “la IA descubrió un fármaco”
- “la certificación blockchain valida la ciencia”

---

## Reglas de implementación científica

### Validación
- Canonicalizar siempre el SMILES.
- Usar hash del canónico como identidad reproducible.
- Preservar errores y warnings relevantes.

### Propiedades
- Usar descriptores estándar y documentados.
- Evitar heurísticas opacas.
- Mantener consistencia con Lipinski/Veber documentada.

### Conformer
- Reportar si la optimización no converge.
- Reportar problemas con macrociclos o topologías difíciles.
- No asumir que una sola geometría resuelve toda la incertidumbre conformacional.

### Docking
- Persistir parámetros críticos del cálculo.
- Hacer caching solo cuando el input científico sea idéntico.
- Reportar claramente si el docking no fue ejecutado o fue degradado.

### Scoring
- Mantener funciones explícitas y justificables.
- Mostrar pesos y breakdown siempre que sea posible.
- Nunca presentar el total_score como equivalencia de eficacia biológica.

### IA
- Instrucciones obligatorias: no alterar números, no inventar propiedades, no reemplazar cálculo.
- Diferenciar observación vs interpretación vs hipótesis.

---

## Señales de desviación peligrosa

Si aparece cualquiera de estas señales, el cambio debe reconsiderarse:
- el output se ve “demasiado bonito” pero menos trazable,
- se ocultan warnings para mejorar UX,
- se reemplaza cómputo por texto plausible,
- se usa lenguaje más fuerte que la evidencia disponible,
- el score se describe como verdad final,
- blockchain se presenta como validación científica,
- el proyecto prioriza engagement sobre rigor.

---

## Criterios de aceptación por módulo

### Un módulo científico está aceptable solo si:
- sus entradas y salidas están claramente definidas,
- sus límites están documentados,
- su método es reproducible,
- sus fallos son explícitos,
- y su comportamiento puede probarse.

### Un módulo narrativo/UI está aceptable solo si:
- no cambia la verdad científica,
- no esconde incertidumbre,
- no induce conclusiones más fuertes que la evidencia.

---

## Guardrails específicos para ML Rescoring

> Documento de arquitectura completo: `docs/ML_RESCORING_ARCHITECTURE.md`

### El modelo ML NO es una fuente de verdad química
El modelo ML de rescoring es una **heurística estadística entrenada en datos experimentales**. No es un cálculo de primeros principios. Debe presentarse siempre como predicción ML con su incertidumbre, nunca como valor exacto.

### Criterios de aceptación obligatorios antes de deploy
1. **Ablation testing:** Features 3D deben contribuir significativamente más allá de descriptores moleculares simples
2. **Scaffold-split validation:** El modelo debe generalizar a scaffolds no vistos durante entrenamiento
3. **SHAP monitoring:** Las top features deben incluir interacciones 3D, no solo MW/LogP
4. **Si el modelo no pasa estos criterios, NO se deploya** — se documenta como intento fallido

### Prohibiciones específicas para ML en el pipeline
- El modelo ML **nunca** reemplaza al docking — lo complementa
- Los resultados ML **nunca** se presentan sin la afinidad raw de Vina junto a ellos
- El RMSE/error del modelo **siempre** se muestra al usuario
- Si el modelo no puede hacer predicción confiable para un target, degradación explícita a Vina raw

### Guardrails del Modelo NULL y Delta de Especificidad 3D

El sistema usa DOS modelos en paralelo: Modelo A (completo) y Modelo NULL (solo descriptores 1D/2D).

1. **El Modelo NULL es obligatorio** — no se puede deployar Modelo A sin su control negativo
2. **Delta = pKd_A - pKd_NULL** — debe calcularse y mostrarse al usuario para CADA molécula evaluada
3. **Si Delta ≈ 0** — warning obligatorio: "El score depende de propiedades genéricas, no de interacciones específicas con el receptor"
4. **Si Delta < 0** — warning obligatorio: "Incompatibilidad geométrica 3D detectada"
5. **Los umbrales de Delta** se calibran empíricamente desde la distribución en PDBbind y se almacenan en `artifacts/delta_distribution.json`
6. **El Modelo NULL solo puede usar features escalares** (MW, LogP, TPSA, HBD, HBA, QED, num_rings, num_aromatic_rings, rotatable bonds). NO fingerprints topológicos ni descriptores que codifiquen forma
7. **Ambos modelos deben predecir en la misma escala** (pKd) para que Delta sea interpretable
8. **El Delta NO modifica el score compuesto** — es un warning visual (semáforo) independiente. Hasta que no esté calibrado y validado externamente, no puede alterar la calificación numérica principal
9. **Los umbrales del semáforo (🟢🟡🔴) vienen de datos empíricos** (percentiles 25 y 60 de la distribución en PDBbind), nunca de números arbitrarios

### Guardrails del Filtro Geométrico de Poses

1. **El filtro se aplica antes de feature extraction** — features de una pose inválida son ruido
2. **Los 3 checks son binarios** — pass/fail, sin excepciones ni umbrales ajustables por el usuario
3. **Si las 9 poses de Vina fallan** — se reporta "docking no confiable" con warning explícito. NO se procede a ML rescoring con una pose que falló todos los checks
4. **Se registra qué pose se seleccionó** (top-1, top-2, ..., top-9) y cuántas pasaron el filtro — metadata de confianza

### Guardrails de Auditoría de Datos (PDBbind "Solo Casos VIP")

1. **Solo complejos que pasen los 5 checks** de calidad se usan para entrenamiento
2. **Los rechazados se documentan con motivo** — nunca se descartan silenciosamente
3. **El reporte de auditoría se revisa** antes de proceder a entrenamiento — no es automático
4. **El ratio aceptados/rechazados se monitorea** — si más del 40% es rechazado, investigar causa sistémica

### Guardrails de Clasificación por Familia Estructural

1. **La clasificación es por familia de proteínas** (GPCRs, kinasas, proteasas, etc.) — **NUNCA por sistema biológico** (nervioso, digestivo, etc.)
2. **La razón es científica:** la física del binding depende de la estructura 3D del bolsillo de unión, no del órgano donde opera la proteína
3. **Performance por familia se reporta siempre** en el training report
4. **Si una familia sub-representada tiene performance peor que random** → warning explícito al usuario cuando el target sea de esa familia

### Guardrails de Auto-actualización del Modelo

1. **El modelo NUNCA se entrena con sus propias predicciones** — solo datos experimentales de PDBbind
2. **El test set congelado es inmutable** — definido una vez, nunca se incluye en entrenamiento
3. **Deploy automático solo si TODAS las métricas mejoran** — si alguna empeora, el modelo antiguo se mantiene
4. **Rollback automático** si el nuevo modelo degrada en producción
5. **Cada actualización queda documentada** en `artifacts/model_update_history.json`

### Guardrails de Likelihood Ratios (Comunicación al Usuario)

1. **NUNCA presentar solo un score numérico** (e.g. "78/100") sin contexto interpretativo LR
2. **El Likelihood Ratio (LR+) se calcula contra panel experimental real** (BindingDB, 40+ moléculas)
3. **SIEMPRE incluir intervalo de confianza** (IC 95% bootstrap) — con n=40, los ICs serán amplios; esto es honesto, no un defecto
4. **El LR NO modifica el score compuesto** — es una capa interpretativa adicional sobre el score existente
5. **Reportar siempre la prevalencia base** del drug discovery (~1% de candidatos computacionales muestran actividad) para contextualizar el LR+
6. **Prohibido reemplazar "LR+ = 0.4" por lenguaje más optimista** — si la evidencia desfavorece la molécula, se dice directamente
7. **A medida que el panel crezca**, los ICs se estrecharán; documentar el tamaño de muestra en cada reporte
8. **Los archivos de calibración** (`artifacts/likelihood_ratios.json`) se regeneran solo con datos experimentales, nunca con predicciones del modelo

### Guardrails de Applicability Domain (Dominio de Aplicabilidad)

1. **OBLIGATORIO verificar Applicability Domain** para CADA molécula antes de predicción ML
2. **La distancia de Mahalanobis** se calcula contra la distribución del training set (PDBbind)
3. **Si la molécula está fuera del dominio** (distancia > umbral p99): NO generar predicción ML → devolver solo Vina raw + warning explícito
4. **Nunca suprimir el warning** de fuera-de-dominio por razones cosméticas o de UX
5. **El artefacto** (`artifacts/applicability_domain.json`) contiene media, covarianza inversa y umbral — se regenera solo al re-entrenar
6. **Reportar al usuario:** la distancia, el umbral, y qué descriptores están fuera de rango (MW, LogP, etc.)
7. **Si la covarianza es singular** (features colineales), usar pseudo-inversa y documentar el warning

### Guardrails de Incertidumbre de Poses (9 Poses Existentes)

1. **Usar las 9 poses que Vina ya genera** de un solo run como fuente de incertidumbre — costo extra: 0 segundos
2. **NUNCA multiplicar runs de Vina** generando 3-5 conformers × docking independiente — esto es una trampa arquitectural que colapsaría Celery (10 min vs 2 min por molécula)
3. **Calcular como features de incertidumbre:** varianza de scores entre las 9 poses, RMSD clustering de las 9 poses, número de poses que pasan el filtro geométrico
4. **La varianza alta indica incertidumbre** — se reporta al usuario como confianza degradada, sin alterar el score
5. **Si las 9 poses son muy divergentes** (alta varianza), el resultado es intrínsecamente menos confiable — documentar esto

### Problemas abiertos documentados (actualizado 2026-04-05)

**6 de 6 problemas con mitigación diseñada. 0 pendientes.**
**+ 3 innovaciones integradas del análisis interdisciplinario (LTR, LR, Applicability Domain)**

1. ~~Feature extraction~~ — **MITIGADO**: pipeline de auditoría "Solo Casos VIP" diseñado (pendiente implementar)
2. ~~Calidad de poses~~ — **MITIGADO**: filtro geométrico automático diseñado (pendiente implementar)
3. ~~Sesgo de ligando~~ — **MITIGADO**: Modelo NULL + Delta de Especificidad 3D diseñado (pendiente implementar)
4. ~~Python 3.14 compat~~ — **MITIGADO**: microservicio de rescoring en contenedor Docker con Python 3.12 (feature extraction + modelo + Delta en contenedor separado; backend 3.14 solo orquesta). Ver ML_RESCORING_ARCHITECTURE.md Problema 4.
5. ~~PDBbind almacenamiento~~ — **MITIGADO**: artefactos del modelo (~10 MB) incluidos en repo; datos crudos (~5-20 GB) bajo demanda vía `scripts/setup_pdbbind.py` con fallbacks (ODDT mirror → RCSB+BindingDB → manual). PDBbind sub-representa GPCRs: clasificación por familia + métricas por familia + warnings. Ver ML_RESCORING_ARCHITECTURE.md Problema 5.
6. ~~Generalización a targets nuevos~~ — **MITIGADO**: clasificación por familia + degradación explícita diseñada (pendiente implementar)

**Innovaciones integradas (análisis interdisciplinario, 2026-04-05):**
7. **Learning to Rank** (de Recuperación de Información) — optimizar ranking directo con `rank:pairwise`, no regresión MSE
8. **Applicability Domain** (de Banca / Basilea III) — detección automática de moléculas fuera del dominio de entrenamiento
9. **Likelihood Ratios** (de Medicina Clínica) — comunicación calibrada al usuario con LR+ e IC95%
10. **Descartado: Ensemble de conformers** — corregido a varianza de 9 poses existentes (0 CPU extra)

Estos problemas están documentados en detalle en `docs/ML_RESCORING_ARCHITECTURE.md` secciones 5 y 6 (Decisiones 8-10).

---

## Juramento operativo del proyecto

Cada cambio debe respetar esta idea:

> MolDesign debe ayudar a la humanidad no por parecer inteligente, sino por mantener la mayor honestidad científica posible dentro de sus límites computacionales.

---

## Auditoría de recalibración (2026-04-04)

> Documentación completa: `docs/RECALIBRATION_AUDIT.md`

Se ejecutó una auditoría exhaustiva del pipeline de scoring el **2026-04-04 ~15:00 UTC-6** con los siguientes resultados:

### Precisión matemática verificada
- **0.000000% de error** en todas las funciones de normalización y scoring.
- 58+ casos de prueba con valores esperados calculados a mano.
- Restricción de <1% de error formalizada en **92 tests permanentes** (`test_recalibration_precision.py`).

### Consistencia de parámetros verificada
- 14 parámetros del `SciConfigRegistry` alineados con código ejecutable.
- Pesos de scoring suman exactamente 1.0 (validator en `config.py`).
- Grid box, target PDB y rango de normalización consistentes entre registry, config y hardcoded.

### Artefactos inválidos identificados y marcados
- `external_calibration_report.json` — INVALIDATED (docking contra 3RZY/FABP4 en vez de 7E2Y/5-HT1A).
- `recalibration_proposal.json` — INVALIDATED (basada en datos de 3RZY).

---

## Calibración externa contra 7E2Y (2026-04-05)

> Documentación completa: `docs/EXTERNAL_CALIBRATION_5HT1A.md`

Calibración re-ejecutada contra el target correcto **PDB 7E2Y** (5-HT1A real, cadena R):

### Protocolo
- 40 moléculas de BindingDB (muestreo estratificado 3-tier, rango 3.778 log units)
- Exhaustiveness = 32 (4× producción)
- Seed = 42, CPU = 1, determinista

### Resultados
- **Spearman ρ = 0.020** (target ≥ 0.3 NO alcanzado)
- Pearson r = -0.136
- 40/40 moléculas aceptadas, 0 rechazadas
- Afinidades en rango correcto para GPCR: -6.86 a -10.80 kcal/mol

### Diagnóstico
Los promedios de afinidad por tier están invertidos (débiles experimentales ≈ -8.59, fuertes experimentales ≈ -8.29). Causa: Vina's scoring function no discrimina entre ligandos estructuralmente diversos para este GPCR. Esto es consistente con la literatura (Warren 2006, Gaieb 2019).

### Implicación
El score de docking es útil para filtrado grueso y generación de poses, no para ranking fino de compuestos diversos. Esta limitación se comunica al usuario.

---

## Validación de infraestructura (2026-04-04, actualizada 2026-04-05)

> Sesión de validación operativa completa.

### Servicios verificados y corriendo
- **PostgreSQL 17.9** — usuario `moldesign`, DB `moldesign_db` + `moldesign_test`, 4 tablas, 3 migraciones aplicadas
- **Redis 3.0.504** — puerto 6379, sano
- **MinIO** — puerto 9000, bucket `docking-poses` creado, retry con exponential backoff implementado
- **FastAPI** — puerto 8000, health check: todos los componentes healthy (PG, Redis, MinIO, RDKit 2025.09.6, Vina)
- **Celery worker** — `--pool=solo --concurrency=1`, procesando jobs de docking end-to-end
- **Next.js frontend** — puerto 3000, todas las páginas verificadas (/, /evaluation, /history, /login)

### Test suite completa
- **484 tests pasando** (455 unit + 29 integration), 1 skipped, 0 fallos
- Los 92 tests de precisión están incluidos dentro de los 455 unit tests
- Los 29 integration tests usan DB real (`moldesign_test`) con SAVEPOINT rollback

### Smoke test end-to-end
- SMILES → validación → propiedades (MW, LogP, TPSA, QED, Lipinski, Veber) → auth → evaluation submission → history
- Todos los endpoints respondiendo correctamente
