# Análisis Interdisciplinario — Mejoras Científicas para MolDesign

> **Fecha:** 2026-04-05  
> **Premisa:** Otros campos científicos y técnicos han enfrentado problemas análogos a los de MolDesign. Este documento identifica 8 soluciones probadas en otras disciplinas que podrían mejorar la validez científica del proyecto.  
> **Nota:** Todas las propuestas están subordinadas a `docs/SCIENTIFIC_GUARDRAILS.md`. Ninguna justifica inventar datos o simular precisión.

---

## 🎯 TRIAGE DEL TECH LEAD (2026-04-05)

### IMPLEMENTAR AHORA (Sprint Actual del ML Rescoring)

| # | Propuesta | Razón |
|---|---|---|
| P1 | **Learning to Rank** | Por el costo de cambiar una línea (`objective='rank:pairwise'`), se multiplica la utilidad clínica del modelo ×10. Optimiza directamente Spearman / NDCG — que es lo que MolDesign necesita. |
| P5 | **Likelihood Ratios** | Un "score 78/100" es un número mágico que viola el espíritu de SCIENTIFIC_GUARDRAILS. Un LR+ con IC95% es radicalmente más honesto y respetado por PhD en farmacología. |
| P2 | **Applicability Domain (Mahalanobis)** | Sin esto, XGBoost alucinará un resultado con total seguridad para moléculas fuera de su training distribution. Irresponsable no implementarlo. |

### CORREGIR (Trampa Arquitectural)

| # | Propuesta | Corrección |
|---|---|---|
| P7 | **Ensemble de Conformers** → **Varianza de 9 Poses Existentes** | **NO multiplicar runs de Vina** (3-5 conformers × docking = 10 min, colapsa Celery). Vina ya genera 9 poses por run → usar su varianza geométrica (RMSD clustering, spread de scores) como feature de incertidumbre. Costo extra: **0 segundos**. |

### BACKLOG (Documentar en `FUTURE_ARCHITECTURE.md`, No Implementar)

| # | Propuesta | Razón del backlog |
|---|---|---|
| P3 | Bühlmann (Credibilidad) | Sólida pero prematura — primero necesitamos el modelo base entrenado y validado |
| P4 | CUSUM / SPC | Requiere datos de producción longitudinal que aún no existen |
| P6 | DAGs Causales | Marco teórico valioso pero no bloquea implementación actual |
| P8 | G×E / AMMI | Requiere multi-target que es post-MVP |

> **Regla:** No escribir una sola línea de código sobre propuestas de backlog esta semana.

### Dónde se documentan las decisiones

- **P1, P2, P5 (implementar):** Integradas en `ML_RESCORING_ARCHITECTURE.md` como Decisiones 8, 9, 10
- **P7 (corregida):** Varianza de 9 poses integrada en `ML_RESCORING_ARCHITECTURE.md` Fase 3
- **P3, P4, P6, P8 (backlog):** Documentadas en `FUTURE_ARCHITECTURE.md`
- **Guardrails nuevos:** Integrados en `SCIENTIFIC_GUARDRAILS.md` (LR, Applicability Domain, Pose Variance)

---

## Resumen de problemas actuales de MolDesign y sus análogos interdisciplinarios

| Problema en MolDesign | Disciplina análoga | Solución probada |
|---|---|---|
| Spearman = 0.020 (Vina no rankea bien) | Recuperación de Información (Google, Bing) | Learning to Rank — optimizar ranking, no regresión |
| Modelo aplicado fuera de su dominio de entrenamiento | Finanzas (Basilea III, credit scoring) | Population Stability Index (PSI) + Applicability Domain |
| GPCRs sub-representados en PDBbind (~50-100 de ~5,000) | Ciencias Actuariales (seguros) | Teoría de Credibilidad de Bühlmann |
| Detección de degradación del modelo en producción | Manufactura (Six Sigma, Toyota) | Control Estadístico de Procesos (SPC) |
| Score presentado como número absoluto sin contexto | Medicina Clínica (diagnóstico) | Likelihood Ratios + Valor Predictivo |
| Modelo NULL como "control negativo" sin marco formal | Epidemiología (estudios observacionales) | DAGs Causales (Pearl, 2000) |
| Incertidumbre no cuantificada en predicciones | Meteorología (pronóstico de huracanes) | Ensemble Prediction Systems |
| Interacción Ligando × Familia de proteínas no modelada | Agronomía (mejoramiento de cultivos) | Modelos de Interacción Genotipo × Ambiente (G×E) |

---

## Propuesta 1: Learning to Rank (de Recuperación de Información)

### El problema análogo en otra disciplina

Los motores de búsqueda (Google, Bing) no intentan predecir un "score absoluto de relevancia" para cada página web. En cambio, optimizan directamente el **ranking relativo** — que la página más relevante aparezca primero. La diferencia es fundamental: un sistema de ranking puede dar scores absolutos incorrectos pero ranking perfecto, o viceversa.

La industria de búsqueda invirtió décadas desarrollando **Learning to Rank (LTR)**, una familia de algoritmos ML diseñados específicamente para optimizar métricas de ranking, no de regresión.

### El paralelo con MolDesign

MolDesign necesita **ranking**, no predicción absoluta de pKd. El Spearman ρ es una métrica de ranking. Sin embargo, el diseño actual del ML Rescoring entrena XGBoost como **regresor** (minimiza MSE de pKd). Esto es un desacoplamiento entre el objetivo del entrenamiento y la métrica de evaluación.

Es exactamente como si Google entrenara su algoritmo para predecir el número exacto de visitas a cada página (regresión), cuando lo que necesita es que las mejores aparezcan primero (ranking).

### La solución probada

**LambdaMART / LambdaRank** — extensiones de árboles de gradiente (como XGBoost) diseñadas para optimizar ranking directamente:

| Enfoque actual | Enfoque LTR propuesto |
|---|---|
| Pérdida: MSE de pKd | Pérdida: LambdaRank (pairwise) |
| Optimiza: predicción absoluta | Optimiza: orden relativo correcto |
| Métrica: R², RMSE | Métrica: NDCG, Spearman directamente |
| Cada molécula es un ejemplo independiente | Pares de moléculas: "¿cuál es mejor?" |

**NDCG@K** (Normalized Discounted Cumulative Gain) — métrica que pondera más los errores en las posiciones TOP del ranking. Esto es exactamente lo que queremos: que las mejores moléculas estén arriba, aunque el orden de las mediocres sea imperfecto.

### Implementación concreta

1. **Reformular el dataset de PDBbind como pares:**  
   Para cada par de complejos (i, j) del mismo target, crear ejemplo:  
   `features_i, features_j, label = sign(pKd_i - pKd_j)`

2. **Usar XGBoost con `objective='rank:pairwise'` o `rank:ndcg'`:**  
   XGBoost ya incluye LambdaMART. No requiere cambio de librería.

3. **Evaluar con NDCG@10 + Spearman** (no solo RMSE):  
   NDCG@10 mide: "de las 10 mejores moléculas predichas, ¿cuántas son realmente buenas?"

4. **El Modelo NULL también se entrena como ranker** — para que Delta siga siendo comparable.

### Impacto estimado

En la literatura de ML para scoring, reformular de regresión a ranking típicamente mejora Spearman en 0.05-0.15 unidades para el mismo dataset y features. No es trivial — la diferencia entre Spearman 0.25 y 0.40 puede hacer que el sistema sea útil vs. inútil para priorización real.

### Referencia

- Burges C. "From RankNet to LambdaRank to LambdaMART: An Overview." Microsoft Research Technical Report MSR-TR-2010-82, 2010.
- Liu TY. "Learning to Rank for Information Retrieval." Foundations and Trends in IR, 2009.
- Ashtawy H, Mahapatra N. "A Comparative Assessment of Ranking Accuracies of Conventional and Machine-Learning-Based Scoring Functions for Protein-Ligand Binding Affinity Prediction." IEEE/ACM Trans Comput Biol Bioinform. 2012;9(5):1301-1313.

### Evaluación de viabilidad

| Criterio | Evaluación |
|---|---|
| Complejidad de implementación | BAJA — XGBoost ya soporta `rank:pairwise` nativo |
| Riesgo científico | BAJO — LTR es estándar en ML, bien fundamentado |
| Impacto potencial | ALTO — ataca directamente Spearman=0.020 |
| Compatible con diseño actual | SÍ — misma arquitectura, distinta función de pérdida |
| Compatible con Modelo NULL | SÍ — ambos modelos se entrenan como rankers |

---

## Propuesta 2: Population Stability Index + Applicability Domain (de Banca / Basilea III)

### El problema análogo en otra disciplina

Los bancos usan modelos de credit scoring para decidir a quién prestar dinero. Un modelo entrenado en 2020 puede degradarse silenciosamente en 2024 si la demografía de los solicitantes cambia. Los reguladores (Basilea III / OCC / Fed) exigen que los bancos monitoreen si la **distribución de inputs** al modelo ha cambiado vs. la distribución de entrenamiento. La métrica estándar es el **PSI (Population Stability Index)**.

```
PSI = Σ (p_actual_i - p_expected_i) × ln(p_actual_i / p_expected_i)
```

Donde `p_actual` es la distribución de una feature en producción y `p_expected` es la distribución durante entrenamiento. Un PSI > 0.25 indica que el modelo está operando en territorio desconocido.

### El paralelo con MolDesign

El modelo ML de rescoring se entrena en PDBbind (~5,000 complejos). Cuando un usuario dibuja una molécula completamente diferente a las del training set (ej. un péptido macrocíclico de 1,200 Da cuando PDBbind tiene mayoritariamente moléculas de 200-600 Da), el modelo predice con confianza un pKd... pero esa predicción no vale nada.

El proyecto actualmente tiene clasificación por familia de proteínas (Problema 6) y SHAP monitoring, pero **no tiene detección automática de que el INPUT está fuera del dominio de entrenamiento**. El concepto existe en QSAR como "Applicability Domain", pero la implementación bancaria (regulada, auditada, con umbrales definidos) es más madura.

### La solución probada

**Para cada molécula nueva, calcular:**

1. **PSI por feature:** Comparar los descriptores moleculares de la molécula vs. la distribución de PDBbind.  
   - Si MW, LogP, TPSA, HBD, HBA, etc. de la molécula caen en bins con frecuencia baja en PDBbind → warning.

2. **Distancia de Mahalanobis multivariada:** Una sola métrica que combina todas las features en un solo número, considerando correlaciones entre ellas.  
   - Si la distancia > umbral (calibrado en PDBbind con cross-validation) → "fuera del dominio".

3. **Warning al usuario:**
   ```
   ⚠️ Dominio de Aplicabilidad: FUERA DE RANGO
   Esta molécula tiene {MW=1,250 Da, LogP=8.3}, significativamente diferente 
   del rango de entrenamiento del modelo (MW: 150-750 Da, LogP: -2 a 6).
   La predicción pKd puede no ser confiable.
   Confianza del modelo: BAJA
   ```

4. **Monitoreo temporal (como lo hace la banca):** Cada semana/mes, calcular PSI global de todas las moléculas evaluadas vs. PDBbind. Si PSI > 0.25 → alerta de que los usuarios están evaluando moléculas "fuera de rango" frecuentemente → posible necesidad de re-entrenamiento con datos más diversos.

### Implementación concreta

```python
# Pseudocódigo — no inventar números, calcular de PDBbind real
class ApplicabilityDomain:
    def __init__(self, training_descriptors: np.ndarray):
        self.mean = training_descriptors.mean(axis=0)
        self.cov_inv = np.linalg.inv(np.cov(training_descriptors.T))
        # Umbral = percentil 99 de distancias en training set
        distances = [mahalanobis(x, self.mean, self.cov_inv) for x in training_descriptors]
        self.threshold = np.percentile(distances, 99)
    
    def is_in_domain(self, molecule_descriptors: np.ndarray) -> tuple[bool, float]:
        d = mahalanobis(molecule_descriptors, self.mean, self.cov_inv)
        return d <= self.threshold, d
```

### Impacto estimado

No mejora directamente el Spearman, pero **previene predicciones silenciosamente incorrectas** — que es peor que no predecir nada. En banca, el PSI ha prevenido pérdidas de miles de millones por modelos degradados.

### Referencia

- Yurdakul B. "Statistical Properties of Population Stability Index." Western Michigan University, 2018.
- Sahlin U. "The Applicability Domain in QSAR Modeling — A Practical Approach." QSAR & Combinatorial Science, 2008.
- Basel Committee on Banking Supervision. "Principles for the Sound Management of Operational Risk." BIS, 2011.

### Evaluación de viabilidad

| Criterio | Evaluación |
|---|---|
| Complejidad de implementación | BAJA — estadística básica (media, covarianza, distancia) |
| Riesgo científico | MUY BAJO — solo agrega warnings, no altera predicciones |
| Impacto potencial | ALTO — previene predicciones falsamente confiables |
| Compatible con diseño actual | SÍ — se agrega como check extra en el microservicio de rescoring |
| Compatible con Modelo NULL | SÍ — se aplica independientemente a ambos modelos |

---

## Propuesta 3: Teoría de Credibilidad de Bühlmann (de Ciencias Actuariales)

### El problema análogo en otra disciplina

En seguros, un actuario necesita estimar la prima de un seguro de auto para un grupo específico (ej. "conductores de 18 años en Guadalajara"). Si tiene 500 siniestros de ese grupo, confía en la estadística del grupo. Pero si solo tiene 3 siniestros, no puede confiar — necesita "prestar" información del promedio general de la población.

La **Teoría de Credibilidad de Bühlmann** formaliza esto:

```
Estimación = Z × (promedio del grupo) + (1 - Z) × (promedio de la población)
```

Donde **Z** (factor de credibilidad) depende del tamaño de la muestra del grupo:
- Z → 1 si hay muchos datos del grupo (confiar en la experiencia propia)
- Z → 0 si hay pocos datos (confiar en la estimencia general)

### El paralelo con MolDesign

El Problema 6 identifica que **GPCRs están sub-representados en PDBbind** (~50-100 de ~5,000 complejos). La solución actual es: "si la performance en GPCRs es mala → caer back a Vina raw." Pero esto es binario — todo o nada. No hay gradualidad.

Es exactamente el problema del actuario: para kinasas (800+ ejemplos), confiamos en el modelo específico. Para GPCRs (50 ejemplos), necesitamos "prestar" del modelo general pero no ignorar completamente los 50 datos que sí tenemos.

### La solución probada

**Para cada familia de proteínas f:**

```
pKd_final(f) = Z(f) × pKd_modelo_familia(f) + (1 - Z(f)) × pKd_modelo_general
```

Donde:

```
Z(f) = n(f) / (n(f) + k)
```

- `n(f)` = número de complejos de la familia f en el training set
- `k` = constante de credibilidad (se calibra empíricamente — típicamente k ≈ varianza entre familias / varianza dentro de familias)

**Ejemplo concreto:**

| Familia | n(f) | k=100 | Z(f) | Interpretación |
|---|---|---|---|---|
| Kinasas | 800 | 100 | 0.89 | 89% modelo específico, 11% general |
| Proteasas | 600 | 100 | 0.86 | 86% específico, 14% general |
| GPCRs | 50 | 100 | 0.33 | 33% específico, 67% general |
| Receptores nucleares | 150 | 100 | 0.60 | 60% específico, 40% general |
| Familia desconocida | 0 | 100 | 0.00 | 100% modelo general |

**Ventaja sobre el diseño actual (fallback binario):** Para GPCRs, en vez de descartar el modelo completo, usamos la tercera parte de información GPCR-específica que SÍ tenemos, complementada con el patrón general. A medida que PDBbind crece en GPCRs, Z(GPCR) aumentará automáticamente.

### Implementación concreta

1. **Durante entrenamiento:** Entrenar un modelo general + modelos por familia (o un solo modelo con la familia como feature de agrupación)
2. **Calcular k empíricamente** usando leave-one-family-out cross-validation
3. **En cada predicción:** Calcular Z(f) y ponderar
4. **Reportar Z(f) al usuario:**
   ```
   Credibilidad del modelo para GPCRs: 33%
   (basado en 50 complejos de entrenamiento de esta familia)
   ```

### Impacto estimado

No es una mejora de Spearman global, sino una **mejora de calibración por familia**. Las predicciones para GPCRs serán menos sobreconfiadas, y las predicciones para kinasas mantendrán su precisión. La honestidad científica mejora directamente.

### Referencia

- Bühlmann H. "Experience Rating and Credibility." ASTIN Bulletin, 1967;4(3):199-207.
- Klugman SA, Panjer HH, Willmot GE. "Loss Models: From Data to Decisions." Wiley, 5th ed., 2019. (Cap. 16-17 sobre credibilidad.)

### Evaluación de viabilidad

| Criterio | Evaluación |
|---|---|
| Complejidad de implementación | MEDIA — requiere modelos por familia + calibración de k |
| Riesgo científico | BAJO — teoría actuarial con 60+ años de uso |
| Impacto potencial | MEDIO-ALTO — mejora calibración donde más se necesita (familias raras) |
| Compatible con diseño actual | SÍ — encaja en el flujo post-predicción, antes de reportar al usuario |
| Compatible con Modelo NULL | SÍ — se aplica a Modelo A y NULL independientemente |

---

## Propuesta 4: Control Estadístico de Procesos (de Manufactura / Six Sigma)

### El problema análogo en otra disciplina

En manufactura (Toyota, Motorola/Six Sigma), un proceso de producción tiene variabilidad natural. El problema es distinguir entre **variabilidad normal** (causa común) y **variabilidad anormal** (causa asignable — algo se rompió). Walter Shewhart inventó las **cartas de control** en 1924 en Bell Labs para resolver esto.

Una carta de control grafica una métrica en el tiempo con:
- **Línea central (CL):** promedio esperado
- **UCL / LCL:** límites de control superior e inferior (típicamente ± 3σ)
- **Reglas de alerta:** punto fuera de límites, 7 puntos consecutivos del mismo lado, tendencia de 6 puntos crecientes/decrecientes, etc.

### El paralelo con MolDesign

El diseño actual del protocolo de auto-actualización (Decisión 7) tiene una regla de rollback: "si el nuevo modelo genera más de X% de Delta ≈ 0 → rollback". Pero esto es una sola regla binaria. No detecta:

- Degradación gradual (drift lento)
- Cambios en la distribución de Delta que no cruzan el umbral binario
- Patrones temporales (todas las moléculas del lunes fallan, las del viernes no)
- Shifts en subgrupos (el modelo funciona bien en general pero degradó solo para moléculas con anillos aromáticos)

### La solución probada

**Implementar cartas de control CUSUM y EWMA para el modelo en producción:**

1. **Carta CUSUM para Delta promedio:**
   - Acumula desviaciones incrementales de Delta vs. su media esperada
   - Detecta shifts pequeños pero persistentes que una carta Shewhart no ve
   - Si CUSUM cruza umbral h → alerta: "el modelo está prediciendo Deltas consistentemente menores de lo esperado"

2. **Carta EWMA para varianza de predicciones:**
   - Media exponencialmente ponderada de la dispersión de pKd_A
   - Si la varianza de predicciones crece → el modelo está "confundido" por inputs nuevos

3. **Western Electric Rules adaptadas:**
   - 1 punto fuera de 3σ → investigar inmediato
   - 2 de 3 puntos fuera de 2σ → alerta temprana
   - 8 puntos consecutivos del mismo lado de la media → drift confirmado
   - 6 puntos con tendencia monotónica → investigar

4. **Stratified monitoring (como Seis Sigma usa estratificación):**
   - Monitoreo separado por familia de proteínas
   - Un proceso puede estar "en control" globalmente pero "fuera de control" para un estrato — exactamente como puede pasar con GPCRs

### Implementación concreta

```python
# Pseudocódigo — para el servicio de monitoreo en producción
class DeltaControlChart:
    def __init__(self, baseline_mean: float, baseline_std: float):
        self.cl = baseline_mean      # Línea central (de PDBbind)
        self.ucl = baseline_mean + 3 * baseline_std   # Límite superior
        self.lcl = baseline_mean - 3 * baseline_std   # Límite inferior
        self.cusum_pos = 0.0
        self.cusum_neg = 0.0
        self.k = 0.5 * baseline_std  # Slack del CUSUM
        self.h = 5.0 * baseline_std  # Umbral de decisión
    
    def update(self, delta: float) -> list[str]:
        alerts = []
        deviation = delta - self.cl
        # Shewhart
        if delta > self.ucl or delta < self.lcl:
            alerts.append("SHEWHART: punto fuera de límites de control")
        # CUSUM
        self.cusum_pos = max(0, self.cusum_pos + deviation - self.k)
        self.cusum_neg = max(0, self.cusum_neg - deviation - self.k)
        if self.cusum_pos > self.h or self.cusum_neg > self.h:
            alerts.append("CUSUM: drift persistente detectado")
        return alerts
```

### Impacto estimado

No mejora la predicción, pero mejora **la detección temprana de degradación**. En manufactura, SPC ha prevenido millones de piezas defectuosas. Para MolDesign, previene miles de predicciones silenciosamente incorrectas.

La diferencia con el diseño actual es la sensibilidad: la regla actual (>X% de Delta ≈ 0) solo detecta degradación catastrófica. CUSUM detecta degradación gradual semanas antes.

### Referencia

- Montgomery DC. "Introduction to Statistical Quality Control." Wiley, 8th ed., 2019.
- Shewhart WA. "Economic Control of Quality of Manufactured Product." ASQ Press, 1931 (reimpresión 1980).
- Page ES. "Continuous Inspection Schemes." Biometrika, 1954;41:100-115. (CUSUM original)

### Evaluación de viabilidad

| Criterio | Evaluación |
|---|---|
| Complejidad de implementación | BAJA — matemáticas simples (sumas acumuladas, promedios móviles) |
| Riesgo científico | MUY BAJO — solo monitoreo, no altera predicciones |
| Impacto potencial | MEDIO — mejora la gobernanza del modelo, no la precisión |
| Compatible con diseño actual | SÍ — complementa el protocolo de auto-actualización existente |
| Mejor que diseño actual | SÍ — detecta drift gradual, no solo catastrófico |

---

## Propuesta 5: Likelihood Ratios y Valor Predictivo (de Medicina Clínica / Diagnóstico)

### El problema análogo en otra disciplina

Cuando un médico ordena una prueba diagnóstica (ej. PSA para cáncer de próstata), el resultado NO es binario-verdad. Un valor de PSA = 5.0 ng/mL tiene diferente significado dependiendo de:
- La prevalencia de la enfermedad en la población del paciente
- La sensibilidad y especificidad de la prueba
- La historia clínica del paciente

La medicina resolvió esto con **Likelihood Ratios (LR):**

```
LR+ = sensibilidad / (1 - especificidad)
```

Un LR+ de 5 significa: "un resultado positivo es 5 veces más probable en un enfermo que en un sano." Esto es masivamente más informativo que decir "PSA = 5.0."

Los **nomogramas de Fagan** permiten visualizar cómo el resultado de la prueba actualiza la probabilidad pre-test a probabilidad post-test. Es Bayes aplicado, pero visual e intuitivo.

### El paralelo con MolDesign

MolDesign presenta un `total_score` de 0-100. Un score de 75 no tiene contexto: ¿qué tan probable es que una molécula con score 75 realmente tenga actividad biológica in vitro? El sistema actualmente no puede responder esta pregunta.

El score funciona como una "prueba diagnóstica" para actividad biológica. Tiene sensibilidad (¿qué fracción de las moléculas realmente activas reciben score alto?) y especificidad (¿qué fracción de las inactivas reciben score bajo?). Pero actualmente no se mide ninguna de las dos.

### La solución probada

1. **Calcular sensibilidad y especificidad del score compuesto usando el panel de BindingDB:**
   - Definir "activa" = pIC50 ≥ 7 (por ejemplo)
   - Para cada umbral de score (50, 60, 70, 80...): ¿cuántas activas detecta? ¿cuántas inactivas descarta?
   - Construir curva ROC del score compuesto

2. **Reportar Likelihood Ratios en vez de scores absolutos:**
   ```
   Score: 78/100
   
   Interpretación calibrada:
   Un score de 78 ocurre 3.2× más frecuentemente en moléculas con actividad 
   experimental comprobada (pIC50 ≥ 7) que en moléculas inactivas.
   (Basado en calibración contra 40 compuestos de BindingDB para 5-HT1A)
   
   ⚠️ Esto NO confirma actividad. Solo indica que la evidencia computacional 
   es moderadamente consistente con actividad.
   ```

3. **Intervalos de confianza del LR** (porque con solo 40 moléculas de calibración, el LR tiene incertidumbre):
   ```
   LR+ = 3.2 (IC 95%: 1.1 – 9.7)
   La incertidumbre es alta porque la calibración se basa en solo 40 compuestos.
   ```

4. **Valor Predictivo Positivo/Negativo (PPV/NPV) — con prevalencia del dominio:**
   - En la química medicinal, la "prevalencia de hits" (moléculas que realmente funcionan) es típicamente 0.1-1% de las evaluadas.
   - Con prevalencia tan baja, incluso un LR+ de 3 da un PPV muy bajo.
   - Esto es una realidad que la medicina entiende bien: una prueba con especificidad del 95% da 50% de falsos positivos si la prevalencia es 5%.
   - **Reportarlo honestamente** es más valioso que ocultarlo.

### Impacto estimado

El impacto principal es en **honestidad y comunicación científica**. No mejora el modelo, pero transforma cómo se presenta. Un LR con IC95% es radicalmente más honesto que un "score de 78/100" sin contexto. Algunos usuarios quizá abandonen el sistema al ver la incertidumbre real — pero los que se queden tomarán decisiones mejores.

### Referencia

- Fagan TJ. "Nomogram for Bayes' Theorem." N Engl J Med. 1975;293(5):257.
- McGee S. "Simplifying Likelihood Ratios." J Gen Intern Med. 2002;17(8):647-650.
- Deeks JJ, Altman DG. "Diagnostic tests 4: likelihood ratios." BMJ. 2004;329:168-169.

### Evaluación de viabilidad

| Criterio | Evaluación |
|---|---|
| Complejidad de implementación | BAJA — requiere el panel de calibración que ya existe (40 moléculas) |
| Riesgo científico | MUY BAJO — solo mejora la presentación, no inventa datos |
| Impacto potencial | ALTO — transforma fundamentalmente la honestidad de la comunicación |
| Compatible con diseño actual | SÍ — se agrega como capa de interpretación sobre el score existente |
| Prerequisito | Requiere calibración externa (ya realizada contra 7E2Y) |
| Limitación | 40 moléculas es poco para LRs robustos — ICs serán amplios (hay que comunicarlo) |

---

## Propuesta 6: DAGs Causales (de Epidemiología)

### El problema análogo en otra disciplina

En epidemiología, la pregunta "¿el café causa cáncer?" parece simple, pero está llena de confounders: los bebedores de café fuman más, duermen menos, trabajan más horas. Un estudio observacional que encuentre correlación café→cáncer puede estar midiendo tabaco→cáncer con café como proxy.

Judea Pearl formalizó la solución con **DAGs Causales (Directed Acyclic Graphs)** — diagramas que explicitan la estructura causal de un sistema. Permiten identificar:
- **Confounders** (causan tanto la exposición como el outcome)
- **Mediadores** (están en el camino causal)
- **Colliders** (condicionados, abren puertas causales espurias)

### El paralelo con MolDesign

El Modelo NULL y Delta de Especificidad 3D son, conceptualmente, un **ajuste por confounders**. MW y LogP son confounders (correlacionan con pKd en PDBbind Y con las features 3D). Pero el diseño actual no formaliza qué variables son confounders, cuáles mediadores y cuáles colliders.

### La solución probada

**Construir un DAG causal explícito del sistema de scoring:**

```
                    ┌─────────────┐
                    │ Propiedades │
                    │  moleculares│
                    │ (MW, LogP,  │
                    │  TPSA...)   │
                    └──────┬──────┘
                           │
                    ┌──────┼──────────────────────────┐
                    │      │                          │
                    ▼      │                          ▼
          ┌─────────────┐  │               ┌──────────────────┐
          │  Score Vina  │  │               │  Binding real    │
          │  (complejo)  │  │               │  (pKd verdadero) │
          └──────┬───────┘  │               └────────┬─────────┘
                 │          │                        │
                 │          │                        │ (no observable
                 ▼          ▼                        │  computacionalmente)
          ┌──────────────────────┐                   │
          │ Features 3D          │                   │
          │ (H-bonds, contacts,  │───────────────────┘
          │  π-stacking, burial) │
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │ pKd_A predicho       │
          │ (Modelo A)           │
          └──────────────────────┘
```

**Lo que el DAG revela:**

1. **Propiedades moleculares son confounders:** Afectan TANTO al Score Vina COMO al binding real, a través de caminos distintos. El Delta = pKd_A - pKd_NULL ajusta parcialmente por este confounder — pero quizá no completamente.

2. **El Score Vina es un mediador parcial:** El pipeline actual pasa por Vina antes de llegar a features 3D. Si Vina produce una pose incorrecta, corrompe las features 3D → el DAG muestra que hay una **puerta de error** en Vina → justifica el filtro geométrico de poses.

3. **¿Qué pasa con la flexibilidad conformacional?** El conformer generado por ETKDG afecta al docking, pero la energía del conformer en solución (no acoplada al receptor) es otro confounder no modelado actualmente. El DAG lo haría visible.

4. **¿Hay colliders?** Si condicionar en "molécula pasa Lipinski" induce correlación espuria entre MW y LogP residual — eso afectaría al Modelo NULL. El DAG permite identificar esto.

### Implementación concreta

1. **Documentar el DAG causal completo** como parte de `ML_RESCORING_ARCHITECTURE.md`
2. **Verificar los supuestos de ajuste:** ¿El Modelo NULL ajusta todos los confounders identificados, o faltan variables?
3. **Evaluar mediación:** ¿Cuánto del efecto de "buenas propiedades moleculares" en pKd_A pasa a través de features 3D (vía pose) vs. directamente?
4. **Si se identifican confounders no controlados:** Agregar las variables al Modelo NULL o implementar ajuste formal (ej. inverse probability weighting)

### Impacto estimado

El impacto es en rigor **metodológico y detección de sesgos no contemplados**. No mejora directamente la predicción, pero puede revelar que el Delta actual no ajusta completamente por confounders — lo que invalidaría su interpretación.

### Referencia

- Pearl J. "Causality: Models, Reasoning, and Inference." Cambridge University Press, 2nd ed., 2009.
- Hernán MA, Robins JM. "Causal Inference: What If." Chapman & Hall/CRC, 2020. (Libro gratuito online)
- Greenland S, Pearl J, Robins JM. "Causal Diagrams for Epidemiologic Research." Epidemiology, 1999;10(1):37-48.

### Evaluación de viabilidad

| Criterio | Evaluación |
|---|---|
| Complejidad de implementación | BAJA (el DAG es un ejercicio de modelado, no de código) |
| Riesgo científico | MUY BAJO — es análisis, no cambio de sistema |
| Impacto potencial | MEDIO — puede revelar sesgos ocultos en el diseño del Delta |
| Compatible con diseño actual | SÍ — informa al diseño, no lo reemplaza |
| Cuándo hacerlo | ANTES de implementar el ML rescoring (Fase 1) |

---

## Propuesta 7: Ensemble Prediction Systems (de Meteorología)

> **⚠️ CORREGIDA POR TECH LEAD (2026-04-05)**  
> La propuesta original proponía generar 3-5 conformers × docking independiente (~15-30 seg extra).  
> **Corrección:** Esto es una trampa arquitectural. Vina ya genera 9 poses por run. Usar la varianza  
> de esas 9 poses proporciona la misma información de incertidumbre a **costo cero**.  
> La propuesta original se preserva tachada por transparencia histórica.

### El problema análogo en otra disciplina

Un solo modelo meteorológico, con condiciones iniciales ligeramente diferentes, puede predecir "sol" o "tormenta" para el mismo día. La meteorología resolvió esto en los años 90 con **Ensemble Prediction Systems (EPS):** ejecutar el MISMO modelo 50 veces con perturbaciones mínimas en las condiciones iniciales. El resultado no es "va a llover" sino "70% de probabilidad de lluvia."

El "cono de incertidumbre" de los huracanes (NOAA) es literalmente las trayectorias de 50+ corridas del modelo superpuestas. Es la incertidumbre hecha visible.

### El paralelo con MolDesign

MolDesign genera UN conformer (ETKDG, seed=42), una sesión de docking (Vina, 9 poses), y produce UN score. El usuario no tiene idea de cuánto variaría el resultado con un conformer ligeramente diferente, una seed diferente, o parámetros de docking diferentes.

### ~~Solución original (DESCARTADA)~~

~~Generar 3-5 conformers (ETKDG con seeds diferentes) y dockear CADA conformer independientemente.~~

**Razón del descarte:** Multiplicar runs de Vina es una trampa arquitectural:
- 5 conformers × ~40-60 seg = **3-5 minutos adicionales** por molécula
- Colapsa el worker de Celery (`--pool=solo --concurrency=1`)
- El usuario esperaría 10 min en vez de 2 min
- Completamente innecesario dado que Vina YA genera 9 poses

### Solución corregida: Varianza de las 9 Poses Existentes

Vina ya genera **9 poses** ordenadas por score en cada run. Estas 9 poses contienen información de incertidumbre gratuita:

1. **Varianza de scores entre las 9 poses:**
   - Si las 9 poses tienen scores similares (-8.3 a -8.0) → predicción estable
   - Si los scores varían mucho (-8.3 a -5.1) → predicción inestable, incertidumbre alta

2. **RMSD clustering de las 9 poses:**
   - Si las 9 poses son geométricamente similares → binding mode consistente
   - Si se agrupan en 3-4 clusters → múltiples modos de unión competitivos

3. **Número de poses que pasan el filtro geométrico:**
   - 9/9 pasan → alta confianza
   - 2/9 pasan → el binding es frágil, confianza baja

4. **Reportar al usuario:**
   ```
   Afinidad estimada: -8.3 kcal/mol (mejor pose, AutoDock Vina)
   Estabilidad de poses: ALTA (9/9 poses dentro de 0.5 kcal/mol)
   
   ✔️ Las 9 poses generadas por Vina son consistentes,
      lo que sugiere un modo de unión bien definido.
   ```
   o:
   ```
   Afinidad estimada: -8.3 kcal/mol (mejor pose, AutoDock Vina)
   Estabilidad de poses: BAJA (solo 3/9 poses dentro de 1.0 kcal/mol)
   
   ⚠️ Las poses son divergentes — el modo de unión no es único.
      La predicción es intrínsecamente menos confiable.
   ```

5. **Como features para ML rescoring:**
   - `pose_score_variance` — varianza de los 9 scores de Vina
   - `pose_rmsd_spread` — RMSD promedio entre las 9 poses
   - `poses_passing_filter` — número que pasan filtro geométrico
   - Costo computacional adicional: **0 segundos** (los datos ya existen)

### Referencia

- Palmer TN. "The economic value of ensemble forecasts as a tool for risk assessment." Q J R Meteorol Soc. 2002;128:747-774.
- Leutbecher M, Palmer TN. "Ensemble forecasting." J Comput Phys. 2008;227:3515-3539.
- Gneiting T, Raftery AE. "Weather Forecasting with Ensemble Methods." Science. 2005;310:248-249.

### Evaluación de viabilidad (CORREGIDA)

| Criterio | Evaluación |
|---|---|
| Complejidad de implementación | **BAJA** — extraer varianza de datos que ya existen |
| Riesgo científico | MUY BAJO — son las poses legítimas de Vina |
| Impacto potencial | ALTO — cuantifica incertidumbre que actualmente es invisible |
| Compatible con diseño actual | SÍ — procesamiento post-hoc de datos existentes |
| Trade-off | Ninguno — 0 segundos de cómputo extra |
| Costo computacional | **0 seg adicionales** (vs 15-30 seg de la propuesta original) |

---

## Propuesta 8: Modelos de Interacción Genotipo × Ambiente (de Agronomía / Mejoramiento de Cultivos)

### El problema análogo en otra disciplina

En agricultura, una variedad de maíz puede rendir 12 ton/ha en suelo arcilloso húmedo y 4 ton/ha en suelo arenoso seco. Pero otra variedad puede rendir 8 ton/ha en ambos. La primera es "específica" (alta interacción G×E), la segunda es "estable" (baja interacción).

El modelo **AMMI (Additive Main effects and Multiplicative Interaction)** descompone el rendimiento en:

```
Y_ij = μ + G_i + E_j + Σ(λ_k × α_ik × γ_jk) + ε_ij
```

Donde:
- μ = media general
- G_i = efecto del genotipo i
- E_j = efecto del ambiente j
- Σ(λ_k × α_ik × γ_jk) = **interacción** G×E (lo que el genotipo "le hace" al ambiente y viceversa)

### El paralelo con MolDesign

El rendimiento Y_ij es análogo al pKd_ij (afinidad del ligando i por la proteína j):

```
pKd_ij = μ + L_i + P_j + Interacción(L_i, P_j) + ε_ij
```

- L_i = "efecto del ligando" = propiedades moleculares intrínsecas (MW, LogP, etc.) — **esto es lo que mide el Modelo NULL**
- P_j = "efecto de la proteína" = druggability general del target
- **Interacción(L_i, P_j)** = **esto es lo que Delta intenta capturar** — cómo de bien encaja ESTE ligando en ESTE bolsillo

**El Delta de Especificidad 3D es conceptualmente idéntico al término de interacción G×E.** Pero la agronomía tiene 40+ años de refinamiento estadístico para modelar este término.

### La solución probada

**Lo que la agronomía añade al diseño actual:**

1. **Descomposición explícita con SVD/PCA (modelo AMMI):**
   - En vez de un solo "Delta", descomponer la interacción en componentes principales
   - Componente 1: "encaje por forma" (steric complementarity)
   - Componente 2: "encaje por electrostática" (H-bonds, charge)
   - Componente 3: "encaje por hidrofobicidad" (burial de superficie no polar)
   - Cada componente tiene una interpretación farmacológica concreta

2. **Biplots de interacción (GGE biplot / AMMI biplot):**
   - Visualizar qué moléculas son "específicas" para qué familias de proteínas
   - Una molécula en el centro del biplot = estable para todos los targets
   - Una molécula en la periferia = altamente específica (bueno si es para TU target, malo si es para otro)
   - Esto le daría al usuario un mapa visual de selectividad computacional

3. **Estabilidad de Finlay-Wilkinson:**
   - Para cada molécula, medir su "sensibilidad" al tipo de proteína
   - Sensibilidad = pendiente de la regresión de pKd contra promedio del target
   - Moléculas con pendiente ≈ 1.0: "se adaptan" al target (como un pesticida de amplio espectro)
   - Moléculas con pendiente >> 1.0: "rinden más en buenos targets" (selectivas)
   - Moléculas con pendiente << 1.0: "estables pero mediocres" (promiscuas)

### Implementación concreta

Esto solo es implementable en la **fase multi-target** (post-MVP), porque requiere pKd predicho contra MÚLTIPLES proteínas para la misma molécula. Pero el diseño puede prepararse ahora:

1. **Almacenar pKd por (molécula, target) en la DB** — el schema ya soporta esto parcialmente
2. **Cuando haya ≥ 3 targets evaluados para la misma molécula:** calcular estabilidad de Finlay-Wilkinson
3. **Biplot de interacción en el frontend:** solo cuando hay datos suficientes

### Impacto estimado

No aplica al MVP (single target), pero prepara la plataforma multi-target con una metodología estadística probada en campo. La agronomía produce miles de variedades × decenas de localidades → la escala es comparable a drug discovery multi-target.

**Innovación conceptual:** El biplot de interacción L×P sería una visualización única en drug discovery — la agronomía la ha refinado durante décadas pero no se ha transferido a esta área.

### Referencia

- Gauch HG. "Statistical Analysis of Regional Yield Trials: AMMI Analysis of Factorial Designs." Elsevier, 1992.
- Yan W, Kang MS. "GGE Biplot Analysis: A Graphical Tool for Breeders, Geneticists, and Agronomists." CRC Press, 2003.
- Finlay KW, Wilkinson GN. "The Analysis of Adaptation in a Plant-Breeding Programme." Australian Journal of Agricultural Research, 1963;14:742-754.

### Evaluación de viabilidad

| Criterio | Evaluación |
|---|---|
| Complejidad de implementación | MEDIA — requiere multi-target funcional (post-MVP) |
| Riesgo científico | MUY BAJO — matemáticas establecidas (AMMI tiene 30+ años) |
| Impacto potencial | ALTO — para fase multi-target, diferenciador de producto |
| Compatible con diseño actual | SÍ — se prepara almacenando pKd × target en DB |
| Cuándo implementar | Post-MVP, cuando multi-target esté activo |

---

## Matriz de priorización

| # | Propuesta | Impacto científico | Esfuerzo | Cuándo | Prioridad |
|---|---|---|---|---|---|
| 1 | Learning to Rank | 🔴 ALTO — ataca Spearman directamente | BAJO | **Fase 2 del ML rescoring** | **P0 — CRÍTICA** |
| 2 | Applicability Domain (PSI) | 🔴 ALTO — previene predicciones inválidas | BAJO | Fase 3 del ML rescoring | **P1 — ALTA** |
| 5 | Likelihood Ratios | 🟡 MEDIO-ALTO — honestidad científica | BAJO | Post-calibración ML | **P1 — ALTA** |
| 7 | Ensemble Prediction | 🔴 ALTO — cuantifica incertidumbre | MEDIO | Fase 3 (configurable) | **P1 — ALTA** |
| 4 | SPC / Control Charts | 🟡 MEDIO — gobernanza del modelo | BAJO | Fase 4 del ML rescoring | **P2 — MEDIA** |
| 6 | DAG Causal | 🟡 MEDIO — revela sesgos ocultos | BAJO | **Antes de Fase 1** (es análisis) | **P2 — MEDIA** |
| 3 | Credibilidad Bühlmann | 🟡 MEDIO-ALTO — calibración por familia | MEDIO | Fase 3-4 del ML rescoring | **P2 — MEDIA** |
| 8 | G×E / AMMI biplot | 🔴 ALTO — pero solo multi-target | MEDIO | Post-MVP, multi-target | **P3 — FUTURA** |

---

## Regla de integración

Ninguna de estas propuestas puede:
- inventar datos,
- ocultar incertidumbre,
- presentar heurísticas como certezas,
- o contradecir `docs/SCIENTIFIC_GUARDRAILS.md`.

Cada propuesta se evalúa con la misma pregunta del checklist obligatorio:

> ¿Este cambio acerca el producto a una herramienta científica real o solo a una demo más vistosa?

Las 8 propuestas acercan al producto a una herramienta científica real. Ninguna es cosmética.

---

## Conexión con el diseño existente

| Propuesta | Estado | Se integra en... | Documento de referencia |
|---|---|---|---|
| P1: Learning to Rank | ✅ IMPLEMENTAR | `ml_training/train.py` — `rank:pairwise` | `ML_RESCORING_ARCHITECTURE.md` Decisión 8, Fase 2 |
| P2: Applicability Domain | ✅ IMPLEMENTAR | `rescoring/applicability.py` | `ML_RESCORING_ARCHITECTURE.md` Decisión 9, Fase 3 |
| P3: Credibilidad Bühlmann | 📅 BACKLOG | `FUTURE_ARCHITECTURE.md` | Requiere modelo base + datos de producción |
| P4: SPC / CUSUM | 📅 BACKLOG | `FUTURE_ARCHITECTURE.md` | Requiere datos longitudinales de producción |
| P5: Likelihood Ratios | ✅ IMPLEMENTAR | `scoring/likelihood_ratios.py` | `ML_RESCORING_ARCHITECTURE.md` Decisión 10, Fase 3 |
| P6: DAGs Causales | 📅 BACKLOG | `FUTURE_ARCHITECTURE.md` | Marco teórico, no bloquea |
| P7: Ensemble → 9 Poses | ⚠️ CORREGIDA | Varianza de 9 poses existentes | `ML_RESCORING_ARCHITECTURE.md` Fase 3 |
| P8: G×E / AMMI | 📅 BACKLOG | `FUTURE_ARCHITECTURE.md` | Requiere multi-target (post-MVP) |

---

> **Nota final:** Este análisis interdisciplinario no sugiere que MolDesign reinvente la rueda. Todo lo contrario — sugiere que la rueda ya fue inventada en otras disciplinas y que MolDesign puede adoptarla con rigor. La meteorología, la banca, la agronomía y la medicina clínica han enfrentado exactamente los mismos problemas (ranking incierto, modelos fuera de dominio, datos desbalanceados, comunicación de incertidumbre) y han invertido décadas en soluciones robustas. MolDesign puede beneficiarse directamente de ese trabajo.
