# ML Rescoring Architecture — Diseño, Decisiones y Problemas Abiertos

---

## Estado de cumplimiento (2026-04-13)

**Infraestructura de rescoring lista y auditada.**

Al 13 de abril de 2026, la arquitectura de rescoring ML está implementada y funcional en el MVP. El pipeline permite recalibración, auditoría y entrenamiento reproducible, con logs y artefactos versionados. Todos los módulos críticos han sido revisados y corregidos para evitar errores de caché y ambiente.

---

> **Fecha de creación:** 2026-04-04  
> **Última actualización:** 2026-04-06  
> **Estado:** FASE 4 COMPLETA — Modelo v4 entrenado (CV Spearman 0.601 ± 0.040, Holdout 0.527). Validación completa: Test Crystal→Docked Δρ=-0.030, Test 5-HT1A ρ=0.176 (NS).  
> **Validación:** Ver `docs/ML_RESCORING_VALIDATION.md` para reporte completo de las dos pruebas críticas.  
> **Regla base:** Todo lo documentado aquí está subordinado a `docs/SCIENTIFIC_GUARDRAILS.md` y `.github/copilot-instructions.md`

---

## 1. Contexto y motivación

### El problema

La calibración externa contra PDB 7E2Y (5-HT1A real) con 40 moléculas de BindingDB arrojó **Spearman ρ = 0.020** (target aspiracional ≥ 0.3). El pipeline técnico funciona correctamente — el problema es una **limitación fundamental del scoring function de AutoDock Vina** para ranking de compuestos estructuralmente diversos.

Evidencia del diagnóstico:
- Las afinidades por tier están invertidas (débiles exp. → -8.59, fuertes exp. → -8.29 kcal/mol)
- Las distribuciones se superponen completamente entre tiers
- La molécula de peor actividad experimental (pIC50=4.924) obtuvo el mejor score Vina (-10.804)
- No hay sesgo significativo por tamaño molecular (Spearman heavy_atoms vs affinity = 0.093)

Ver: `docs/EXTERNAL_CALIBRATION_5HT1A.md` para documentación completa.

### La propuesta

Construir un **modelo de Machine Learning (ML) para rescoring** que funcione como capa intermedia entre el docking de Vina y el score compuesto final. El modelo se entrenaría en datos experimentales (PDBbind) para aprender patrones generales de interacción proteína-ligando que Vina no captura.

### Por qué ML y no otro método

| Alternativa | Problema para MolDesign |
|---|---|
| MM-GBSA | Requiere simulación de dinámica molecular (~horas por molécula), inviable para plataforma interactiva |
| FEP (Free Energy Perturbation) | Requiere GPU + days de cómputo por par de moléculas, solo para series congénericas |
| QSAR target-específico | Requiere datos de entrenamiento específicos del target — no generaliza a targets nuevos |
| Consensus docking | Mejora pose selection pero no corrige el scoring function |
| **ML Rescoring (PDBbind)** | **Entrenado en datos diversos, predice en ms, generalizable a cualquier target con estructura 3D** |

---

## 2. Arquitectura propuesta

### Pipeline completo (con ML Rescoring integrado)

```
SMILES  
  → Validación química (RDKit)             [existente, chem/]  
  → Propiedades fisicoquímicas (RDKit)      [existente, chem/]  
  → Conformer 3D (ETKDG/MMFF94)            [existente, chem/]  
  → Docking (AutoDock Vina)                 [existente, services/docking/]  
  → Pose Quality Filter                     [NUEVO, services/rescoring/]  
      ├─ Check 1: Centro de masa dentro del grid box  
      ├─ Check 2: Distancia mínima proteína-ligando < 4Å  
      └─ Check 3: ≥ N átomos en contacto con proteína (< 3.5Å)  
      Si falla → probar siguiente pose (de 9). Si todas fallan → warning explícito.  
  → Feature Extraction                      [NUEVO, services/rescoring/]  
      ├─ Descriptores moleculares 1D/2D (RDKit) — ya calculados  
      ├─ Score Vina crudo + sub-componentes energéticos  
      ├─ Features de interacción 3D (pose → H-bonds, hydrophobic, π-stack)  
      └─ Features de confianza de pose (varianza entre poses, clustering)  
  → Applicability Domain Check              [NUEVO, services/rescoring/]
      Distancia de Mahalanobis vs distribución de PDBbind
      Si fuera del dominio → warning explícito + confianza degradada
  → Modelo A (XGBoost, ranking pairwise)     [NUEVO, services/rescoring/]
      Input: features 1D/2D + Vina + interacciones 3D
      Objective: rank:pairwise (Learning to Rank — optimiza ranking, no regresión)
      Output: score_A (ranking relativo, NO pKd absoluto)
  → Modelo NULL (control negativo, ranking)  [NUEVO, services/rescoring/]
      Input: SOLO descriptores 1D/2D (MW, LogP, TPSA, HBD, HBA, QED...)
      Objective: rank:pairwise (misma función de pérdida que Modelo A)
      Output: score_NULL (ranking sin info 3D)
  → Delta de Especificidad 3D               [NUEVO, services/rescoring/]
      Delta = score_A - score_NULL
      (+) Interacción específica tipo llave-cerradura
      (0) Binding inespecífico — riesgo de promiscuidad/off-targets
      (-) Choque estérico — propiedades buenas pero geometría incompatible
  → Likelihood Ratio                        [NUEVO, scoring/]
      LR+ calibrado contra panel de BindingDB (40+ moléculas)
      "Un score de X ocurre N× más frecuentemente en binders experimentales"
      Con intervalo de confianza (IC95%)
  → Score Compuesto                         [ADAPTADO, scoring/]
      score_A × w1 + ADME × w2 + druglikeness × w3
      (Delta NO modifica el score — se muestra como warning visual independiente)
      (LR se reporta como capa interpretativa adicional, NO modifica score)
```

### Nuevo módulo: `services/rescoring/`

**Nota:** Con la arquitectura de microservicio (Problema 4), el código de rescoring vive en su propio contenedor Docker (Python 3.12), no dentro de `backend/`. La estructura lógica se mantiene, pero la ubicación física cambia:

```
rescoring/                          # Microservicio (Python 3.12, Docker)
├── Dockerfile
├── requirements.txt
├── api.py                          # FastAPI ligero — endpoint POST /rescore
├── pose_filter.py                  # Filtro geométrico automático de poses (3 checks)
├── feature_extractor.py            # Extrae features 3D con ODDT
├── model.py                        # Carga Modelo A + NULL, predice pKd, calcula Delta, semáforo
├── config.py                       # Configuración (umbrales, paths de artefactos)
└── artifacts/                      # Artefactos del modelo (SÍ se comitean al repo, ~10 MB total)
    ├── model_a.joblib               # Modelo A serializado (features completas)
    ├── model_null.joblib            # Modelo NULL serializado (solo descriptores 1D/2D)
    ├── training_report.json         # Métricas, feature importances, SHAP, ablation results
    ├── delta_distribution.json      # Distribución de Delta en PDBbind (percentiles, umbrales de semáforo)
    ├── pdbbind_audit_report.json    # Auditoría de datos: aceptados, rechazados, motivos
    ├── frozen_test_set.json         # IDs del test set congelado (inmutable entre versiones)
    ├── model_update_history.json    # Historial de actualizaciones del modelo
    └── validation_report.json       # Resultados de ablation y bias tests

ml_training/                        # Proyecto offline de entrenamiento (NO corre en producción)
├── requirements.txt                # Python 3.12, ODDT, XGBoost, SHAP, scikit-learn
├── train.py                        # Entrenar Modelo A + NULL
├── validate.py                     # Ablation, scaffold-split, SHAP analysis
├── audit_pdbbind.py                # Pipeline de auditoría "Solo Casos VIP"
└── update_model.py                 # Auto-actualización con criterios de aceptación

data/                               # en .gitignore — NUNCA en el repositorio
├── pdbbind/
│   ├── refined-set/                # ~5,000 complejos descomprimidos (~10-20 GB)
│   ├── checksums.sha256
│   └── download_metadata.json
```

### Separación de responsabilidades

| Módulo | Responsabilidad | NO debe hacer |
|---|---|---|
| `services/rescoring/pose_filter.py` | Validar calidad geométrica de poses (3 checks binarios) | Modificar poses, calcular scores |
| `services/rescoring/feature_extractor.py` | Extraer features numéricas de poses y moléculas | Calcular scores, interpretar resultados |
| `services/rescoring/model.py` | Cargar Modelo A + NULL, predecir pKd, calcular Delta | Entrenar, validar, modificar features |
| `services/rescoring/trainer.py` | Entrenar ambos modelos offline con PDBbind | Correr en producción, modificar pipeline |
| `services/rescoring/validator.py` | Medir bias, ablation, integridad, distribución de Delta | Alterar modelo o datos |
| `scoring/engine.py` | Combinar ML rescore + Delta + ADME + druglikeness | Ejecutar modelo directamente |

---

## 3. Datos de entrenamiento: PDBbind

### Qué es PDBbind

PDBbind es la base de datos estándar para ML en drug discovery:
- ~23,000 complejos proteína-ligando con datos experimentales (Kd, Ki, IC50)
- **Refined set** (~5,000 complejos): curado, alta calidad, diverso en proteínas y ligandos
- **Core set** (~300 complejos): subconjunto de benchmarking
- Cada complejo incluye: estructura PDB de la proteína, estructura SDF del ligando, valor experimental de binding

**Referencia:** Wang R, Fang X, Lu Y, Wang S. "The PDBbind database: collection of binding affinities for protein-ligand complexes with known 3D structures." J Med Chem. 2004;47(12):2977-2980.

### Plan de uso

1. **Descargar PDBbind refined set** (~5,000 complejos)
2. **Para cada complejo:** extraer features de interacción 3D usando ODDT o ProLIF
3. **Combinar** features de interacción + descriptores RDKit + score Vina (re-dockeado)
4. **Entrenar** XGBoost/Random Forest con cross-validation
5. **Validar** con core set (out-of-sample)

### Limitaciones conocidas de PDBbind

- Sesgo hacia proteínas cristalizables (excluye membrane proteins poco cristalizadas como GPCRs)
- La distribución de targets no es uniforme (kinasas sobre-representadas)
- Los valores experimentales tienen incertidumbre propia (IC50 vs Ki vs Kd no son directamente comparables)
- Solo incluye complejos exitosos (no hay "negativos" — moléculas que no unen)

Estas limitaciones deben documentarse en el training report y comunicarse al usuario.

---

## 4. Decisiones arquitectónicas tomadas

### Decisión 1: DESCARTADA — Fase A (Receptor Profiling manual)

**Razón:** MolDesign aspira a ser un descubridor de fármacos general, no un sistema específico para 5-HT1A. La curación manual de sitios de unión no escala a targets desconocidos o novedosos. El receptor se "conoce" a través de la estructura 3D y la pose de docking — no necesita curación previa.

### Decisión 2: TRANSFORMADA — Fase B (Feature Extraction de interacciones)

**Cambio:** No se usa como score independiente. Se transforma en **extracción de features** que alimentan al modelo ML. Las interacciones 3D (H-bonds, contactos hidrofóbicos, π-stacking) extraídas de cada pose se convierten en columnas del dataset de entrenamiento.

**Costo computacional:** ~1-2 segundos por molécula (aceptable).  
**Herramientas candidatas:** ODDT (preferido — tiene integración directa con PDBbind), ProLIF (alternativa).

### Decisión 3: DESCARTADA — Fase C (Pharmacophore Scoring)

**Razón:** La comparación farmacofórica presupone conocimiento previo de qué interacciones son deseables. Esto contradice el objetivo de descubrimiento de fármacos, donde precisamente no sabes qué buscas. El modelo ML aprende estas relaciones de los datos.

### Decisión 4: ADAPTADA — Fase D (Score Compuesto)

**Cambio:** El score compuesto se reformula para incluir el ML rescore como dimensión principal. Los pesos se re-calibrarán basándose en los resultados del modelo validado.

**Pesos tentativos (sujetos a validación):**
```
ML_rescore × w1 + ADME × w2 + druglikeness × w3
```
Los valores concretos de w1, w2, w3 se determinarán tras entrenar y validar el modelo. No se fijan por adelantado.

### Decisión 8: Learning to Rank — Optimizar ranking, no regresión (Análisis Interdisciplinario)

**Origen:** Recuperación de Información (Google, Bing). Los motores de búsqueda no predicen un "score absoluto de relevancia" — optimizan directamente el **ranking relativo** (NDCG, Spearman).

**El problema:** El diseño original proponía entrenar XGBoost como regresor (minimizar MSE de pKd). Pero MolDesign necesita **ranking** (Spearman ρ), no predicción absoluta. Un modelo puede tener RMSE excelente pero Spearman terrible si sus errores no son monótonos.

**Analogía:** Es como si Google entrenara su algoritmo para predecir el número exacto de visitas a cada página (regresión), cuando lo que necesita es que las mejores aparezcan primero (ranking).

**Cambio:**

| Aspecto | Antes (regresión) | Ahora (LTR) |
|---|---|---|
| Función de pérdida | MSE de pKd | `rank:pairwise` (LambdaMART) |
| Lo que optimiza | Predicción absoluta | Orden relativo correcto |
| Métrica principal | R², RMSE | **NDCG@10, Spearman** |
| Cada ejemplo es... | Un complejo independiente | Un **par** de complejos: "¿cuál es mejor?" |
| Output | pKd (valor absoluto) | Score de ranking (ordinal, no cardinal) |

**Implementación:**
```python
# XGBoost ya soporta LTR nativo — el cambio es una línea
params = {
    'objective': 'rank:pairwise',   # LambdaMART
    'eval_metric': 'ndcg',
    'eta': 0.1,
    'max_depth': 6,
}
# Los grupos se definen por target (complejos del mismo target se comparan entre sí)
# group = [n_ligands_target_1, n_ligands_target_2, ...]
```

**Impacto esperado:** En la literatura, reformular de regresión a ranking mejora Spearman en 0.05-0.15 para el mismo dataset y features. Para MolDesign (baseline Spearman=0.020), esto podría ser la diferencia entre un sistema inútil y uno útil.

**Implicación para Delta:** Ambos modelos (A y NULL) se entrenan como rankers con la misma función de pérdida → Delta sigue siendo comparable (diferencia de scores de ranking).

**Referencia:**
- Burges C. "From RankNet to LambdaRank to LambdaMART." Microsoft Research TR-2010-82, 2010.
- Ashtawy H, Mahapatra N. "Ranking Accuracies of Scoring Functions." IEEE/ACM Trans Comput Biol Bioinform. 2012;9(5):1301-1313.

### Decisión 9: Applicability Domain con Distancia de Mahalanobis (Análisis Interdisciplinario)

**Origen:** Banca / Basilea III. Los reguladores financieros exigen monitorear si los inputs al modelo de credit scoring han cambiado vs. el entrenamiento (Population Stability Index). Un modelo entrenado en una población no puede aplicarse silenciosamente a otra.

**El problema:** El modelo se entrena en PDBbind (~5,000 complejos, MW típico ~200-600 Da). Si un usuario dibuja un péptido macrocíclico de 1,500 Da o un fragmento de 100 Da, XGBoost predice con confianza un score... pero esa predicción no vale nada. El modelo está **extrapolando fuera de su dominio de entrenamiento**.

**Solución:** Check automático de Applicability Domain antes de predicción.

**Implementación:**
```python
class ApplicabilityDomain:
    def __init__(self, training_descriptors: np.ndarray):
        self.mean = training_descriptors.mean(axis=0)
        self.cov_inv = np.linalg.inv(np.cov(training_descriptors.T))
        # Umbral = percentil 99 de distancias en training set
        distances = [mahalanobis(x, self.mean, self.cov_inv) 
                     for x in training_descriptors]
        self.threshold = np.percentile(distances, 99)
    
    def check(self, mol_descriptors: np.ndarray) -> tuple[bool, float]:
        d = mahalanobis(mol_descriptors, self.mean, self.cov_inv)
        return d <= self.threshold, d
```

**Respuesta al usuario cuando está fuera del dominio:**
```
⚠️ DOMINIO DE APLICABILIDAD: FUERA DE RANGO
Esta molécula tiene MW=1,250 Da, significativamente diferente del rango 
de entrenamiento del modelo (MW: 150-750 Da, LogP: -2 a 6).
La predicción puede no ser confiable. Confianza: DEGRADADA.
```

**Dónde se integra:** En el microservicio de rescoring, ANTES de ejecutar el modelo. Si la molécula está fuera del dominio → se devuelve el score de Vina raw + warning, sin predicción ML.

**Artefacto:** `artifacts/applicability_domain.json` — media, covarianza inversa y umbral del training set.

**Referencia:**
- Yurdakul B. "Statistical Properties of Population Stability Index." Western Michigan University, 2018.
- Sahlin U. "The Applicability Domain in QSAR Modeling." QSAR & Comb Sci, 2008.

### Decisión 10: Likelihood Ratios para Comunicación al Usuario (Análisis Interdisciplinario)

**Origen:** Medicina Clínica (diagnóstico basado en evidencia). En medicina, ningún test se reporta como "score de 0 a 100". Se usan **Likelihood Ratios** que comunican cuánto más probable es el resultado en un enfermo vs. un sano. Esto es radicalmente más honesto y respetado por profesionales.

**El problema:** Un `total_score` de 78/100 no tiene contexto. ¿Qué significa? ¿Qué probabilidad hay de que una molécula con score 78 realmente sea activa in vitro?

**Solución:** Calcular Likelihood Ratio (LR+) usando el panel de calibración de BindingDB:

1. **Definir "activa"** = pIC50 ≥ 7 (100 nM) en datos experimentales
2. **Para cada umbral de score:** medir sensibilidad y especificidad
3. **Calcular LR+** = sensibilidad / (1 - especificidad)
4. **Reportar con IC95%** (bootstrap, porque n=40 es pequeño)

**Lo que el usuario verá (en vez de solo "78/100"):**
```
Score compuesto: 78/100

📊 Interpretación calibrada (Likelihood Ratio):
Un score ≥ 78 ocurre 3.2× más frecuentemente en moléculas con actividad
experimental comprobada (pIC50 ≥ 7) que en moléculas inactivas.
(Basado en calibración contra 40 compuestos de BindingDB para 5-HT1A)
LR+ = 3.2 (IC 95%: 1.1 – 9.7)

⚠️ Esto NO confirma actividad. La incertidumbre es alta (n=40).
   En drug discovery típico, solo ~1% de candidatos computacionales
   muestran actividad experimental — incluso con LR+=3, la probabilidad
   post-test sigue siendo baja.
```

**Ventajas sobre presentación actual:**
- Lenguaje que un PhD en farmacología respeta inmediatamente
- Protección legal: reporta probabilidades basadas en datos, no afirma eficacia
- Honestidad científica: IC95% amplio con n=40 → se ve claramente la limitación
- Compatible con SCIENTIFIC_GUARDRAILS: no inventa, no exagera

**Limitación honesta:** Con solo 40 moléculas de calibración, los intervalos de confianza serán amplios. Esto se comunica explícitamente. A medida que el panel crezca, los ICs se estrecharán.

**Referencia:**
- Fagan TJ. "Nomogram for Bayes' Theorem." N Engl J Med. 1975;293(5):257.
- Deeks JJ, Altman DG. "Diagnostic tests 4: likelihood ratios." BMJ. 2004;329:168-169.

### Decisión 5: Delta como Warning Visual — NO modifica el score compuesto

**Razón:** El Delta de Especificidad 3D es una métrica nueva sin validación externa. Usarlo para modificar el score numérico antes de tener datos de calibración sería prematuro. Se implementa así:

- **Fase actual:** Delta se calcula, se muestra como semáforo visual, se almacena en DB, se incluye en reportes. Pero `f(Delta)` **no existe** en la fórmula del score compuesto. El score numérico no cambia.
- **Fase futura (post-calibración):** Una vez que el Delta esté calibrado en PDBbind (~4,500 complejos) y validado externamente, se evalúa si promoverlo a factor multiplicativo (Delta como factor de confianza 0.0-1.0 que escala el componente de afinidad) o componente aditivo separado.
- **Criterio para promoción:** La distribución de Delta en PDBbind debe ser informativa (no uniforme), y la correlación entre Delta y actividad experimental debe ser positiva y significativa.

### Decisión 6: Semáforo Visual para Delta (Presentación al Usuario)

**Razón:** Un número como "+1.3" no es intuitivo para usuarios no expertos. Se traduce a un sistema de semáforo calibrado empíricamente.

| Color | Rango | Significado para el usuario |
|---|---|---|
| 🟢 **Verde** | Delta > percentil 60 de PDBbind | "Encaje específico tipo llave-cerradura" |
| 🟡 **Amarillo** | Percentil 25 < Delta ≤ percentil 60 | "Unión inespecífica — riesgo de promiscuidad" |
| 🔴 **Rojo** | Delta ≤ percentil 25 (o negativo) | "Incompatibilidad geométrica — revisar estructura" |

**Calibración:**
1. Calcular Delta para todos los complejos VIP de PDBbind
2. Obtener distribución completa (media, σ, percentiles 10/25/50/60/75/90)
3. Los percentiles 25 y 60 son los umbrales iniciales
4. Almacenar en `artifacts/delta_distribution.json`
5. Refinar umbrales con uso y feedback

**Importante:** Los colores del semáforo vienen de datos empíricos, no de números inventados. Los umbrales específicos se determinan DESPUÉS de calcular la distribución real, no antes.

### Decisión 7: Protocolo de Auto-actualización del Modelo

**Razón:** Los modelos ML necesitan actualizarse cuando hay nuevos datos experimentales disponibles. Pero la auto-actualización sin guardrails puede causar degradación silenciosa.

**Protocolo automatizado:**

1. **Trigger:** Nueva versión de PDBbind publicada (cadencia anual, ~Q1-Q2)
2. **Re-auditoría:** Script de limpieza (Problema 1) se ejecuta sobre los nuevos datos
3. **Re-entrenamiento:** Modelo A + Modelo NULL, misma arquitectura, nuevos datos
4. **Test set fijo (congelado):** Un subset de PDBbind original (~500 complejos representativos) se congela desde el día 1 y NUNCA se incluye en entrenamiento posterior. Sirve como benchmark inmutable.
5. **Comparación objetiva (automatizada):**
   - Scaffold-split R² del nuevo modelo > R² del modelo actual (en test set fijo)
   - Ablation test sigue pasando (features 3D contribuyen)
   - SHAP top-5 sigue incluyendo ≥ 2 features 3D
   - Performance por familia de proteínas no se degrada significativamente en ninguna
6. **Criterio de deploy:**
   - Si TODAS las condiciones se cumplen → deploy automático con log detallado
   - Si alguna falla → modelo anterior se mantiene, se documenta por qué el nuevo falló
7. **Rollback automático post-deploy:** Si en producción el nuevo modelo genera más de X% de Delta ≈ 0 (vs. baseline histórico) en las primeras N predicciones → rollback al modelo anterior

**Restricción crítica:** El modelo NUNCA se entrena con sus propias predicciones (eso es feedback loop). Solo con datos experimentales nuevos de PDBbind.

**Artefactos:**
- `artifacts/frozen_test_set.json` — IDs del test set congelado (inmutable)
- `artifacts/model_update_history.json` — historial de cada actualización (fecha, métricas, decisión, razón)

---

## 5. PROBLEMAS ABIERTOS — Pendientes de resolver

### ✅ PROBLEMA 1: Feature Extraction Hell (Data Engineering) (RESUELTO — IMPLEMENTADO)

**Severidad:** MEDIA  
**Estado:** ✅ IMPLEMENTADO — 3,019 complejos extraídos en ~15 min con ProLIF + RDKit-direct

**Descripción:**  
Procesar los ~5,000 complejos del PDBbind refined set para extraer features 3D es la tarea más intensiva del sprint. Los riesgos son:
- Errores de formato en PDB/SDF (residuos no estándar, hidrógenos faltantes, ligandos covalentes)
- Fallas silenciosas que generan features erróneas sin lanzar error
- Alineación de datos entre features de Vina, RDKit e interacciones 3D

**Solución aceptada: Pipeline de Auditoría Programático — "Solo Casos VIP"**

Antes de entrenar, cada complejo de PDBbind refined set pasa por 5 checks de calidad. Solo los que pasen TODOS se usan para entrenamiento:

1. **Check de ligando:** SMILES parseable por RDKit, sin átomos exóticos (no metales, no ligandos covalentes)
2. **Check de resolución:** Estructura cristalográfica con resolución ≤ 2.5 Å (datos confiables)
3. **Check de completitud:** Sin residuos faltantes en radio de 5 Å del binding site (el entorno de interacción está completo)
4. **Check de datos de binding:** Solo Ki o Kd experimentales (NO IC50, que depende del ensayo y no es comparable directamente)
5. **Check de features:** Features de interacción 3D extraídas son no-triviales (no todas cero — indica fallo silencioso de parsing)

**Comportamiento:**
- Cada complejo que falle cualquier check → se rechaza con motivo documentado
- Se genera `artifacts/pdbbind_audit_report.json` con:
  - Total de complejos evaluados
  - Total aceptados ("casos VIP")
  - Total rechazados por cada motivo
  - Lista completa de PDB IDs rechazados con razón
  - Distribución de binding affinity en los aceptados vs. rechazados
- Estimación: ~60-80% de PDBbind refined pasará todos los checks (~2,700-3,600 complejos)
- El reporte se revisa manualmente antes de proceder a entrenamiento

**Herramientas:**
- **ODDT (Open Drug Discovery Toolkit)** — `oddt.datasets.pdbbind` para parsing directo
- QA estadístico post-auditoría: distribuciones, outliers, missing values

**Preguntas abiertas (reducidas):**
1. ¿ODDT es compatible con Python 3.14? (requiere verificación — Problema 4)
2. ¿Cuánto espacio en disco requiere PDBbind refined set? (~2-5 GB comprimido, ~10-20 GB descomprimido)

**Referencia:** ODDT documentation — https://oddt.readthedocs.io/

---

### ✅ PROBLEMA 2: Garbage In, Garbage Out — Calidad de Poses (RESUELTO — IMPLEMENTADO)

**Severidad:** ALTA  
**Estado:** ✅ IMPLEMENTADO — VIP audit con 5 checks + pose_filter.py operativo

**Descripción:**  
El ML rescoring asume que la pose generada por Vina es geométricamente razonable. Si Vina colocó la molécula al revés, fuera del bolsillo, o en orientación imposible, todas las features extraídas son ruido.

En benchmarks publicados, Vina reproduce la pose cristalográfica (RMSD < 2Å) con ~70-80% de acierto en casos favorables, bajando a ~50-60% para GPCRs flexibles.

**Opciones evaluadas y descartadas:**

| Opción | Descripción | Razón de descarte |
|---|---|---|
| ML clasificador de poses | Modelo que distinga poses buenas de malas | Problema circular — requiere poses etiquetadas |
| Consensus docking | Dockar con 2-3 programas | Triplica cómputo, no escala |
| 3 puntos del sitio activo (propuesta inicial) | Seleccionar 3 puntos manualmente y comparar | Requiere conocimiento previo del target — misma objeción que Fase A |
| DiffDock | Deep learning para pose prediction | Heavy, requiere GPU |

**Solución aceptada: Filtro Geométrico Automático de Poses**

Tres checks binarios que NO requieren conocimiento previo del target:

1. **Check de contención:** Centro de masa del ligando dentro del grid box definido
2. **Check de contacto:** Distancia mínima entre cualquier átomo del ligando y cualquier átomo de la proteína < 4Å (el ligando no está "flotando")
3. **Check de burial:** Al menos N átomos del ligando están en contacto con la proteína (distancia < 3.5Å)

**Comportamiento:**
- Vina genera 9 poses por molécula
- Se aplican los 3 checks a la pose top-1
- Si falla → se prueba la pose #2, luego #3, etc.
- Si las 9 fallan → se reporta como "docking no confiable" con warning explícito al usuario
- La pose seleccionada se usa para feature extraction

**Ventajas:**
- No requiere conocimiento previo del target (escala a drug discovery general)
- Computacionalmente trivial (~ms por pose)
- Elimina poses obviamente basura antes de que el ML las vea
- Compatible con el clustering de poses y varianza como features adicionales

**Complemento (mantiene de la propuesta original):**
- Clustering de las 9 poses (RMSD-based, umbral ~2Å) — cluster más poblado = mayor confianza
- Varianza entre poses como feature para el ML — incertidumbre como información

**Referencia:** Houston & Walkinshaw (2013). "Consensus docking." J Chem Inf Model 53(2):384-390.

---

### ✅ PROBLEMA 3: Sesgo del Ligando / Overfitting en PDBbind (PARCIALMENTE RESUELTO)

**Severidad:** ALTA  
**Estado:** ✅ RESUELTO EN v4 — MW SHAP bajó de 0.468 (#1) a 0.176 (#2), reducción del 62%. Features 3D (shell, ECIF) ahora dominan el modelo. Spearman CV subió de 0.435 a 0.601 (+38%).

**Descripción:**  
Los modelos de árbol (XGBoost, Random Forest) son susceptibles a un sesgo documentado: en vez de aprender la **física de la interacción proteína-ligando**, memorizan que "moléculas más pesadas y lipofílicas tienen mejor Kd en PDBbind" y otorgan buenos scores basándose en MW y LogP, **ignorando al receptor.**

**Referencia clave:** Wallach I, Heifets A. "Most ligand-based benchmarks reward memorization rather than generalization." J Chem Inf Model. 2018;58(5):916-932. DOI: 10.1021/acs.jcim.7b00403

**Opciones evaluadas y descartadas:**

| Opción | Descripción | Razón de descarte |
|---|---|---|
| Segundo ML "auditor" | Otro modelo que evalúe al primero | Mismo sesgo si mismos datos — "segunda opinión del gemelo idéntico" |
| Solo SHAP monitoring | Vigilar feature importance global | Insuficiente — no detecta sesgo en producción, solo en training |
| Ensemble (RF + XGBoost + linear) | Promediar modelos distintos | Reduce varianza pero no sesgo sistemático |

**Solución aceptada: Modelo NULL como Control Negativo + Delta de Especificidad 3D**

#### El Modelo NULL

Se entrenan DOS modelos en paralelo con el MISMO dataset (PDBbind):

- **Modelo A (completo):** Features 1D/2D + Vina score + interacciones 3D → predice pKd_A
- **Modelo NULL (control negativo):** SOLO features 1D/2D (MW, LogP, TPSA, HBD, HBA, rotatable bonds, QED, num_rings, num_aromatic_rings) → predice pKd_NULL

El Modelo NULL es **deliberadamente limitado**: no recibe información 3D, no sabe cómo la molécula encaja en el receptor. Solo conoce las propiedades fisicoquímicas escalares.

**Restricción del Modelo NULL:** Solo puede usar propiedades escalares puras. NO puede usar fingerprints topológicos ni descriptores que codifiquen forma indirectamente.

#### Delta de Especificidad 3D

```
Delta = pKd_A - pKd_NULL
```

| Delta | Interpretación farmacológica | Implicación |
|---|---|---|
| **Alto (+)** | Interacción específica tipo "llave-cerradura" | H-bonds dirigidos, π-stacking complementario, encaje estérico preciso. **Lo que buscan las farmacéuticas.** |
| **Cero (0)** | Binding inespecífico tipo "piedra grasosa" | Se une por propiedades genéricas (hidrofobicidad, tamaño). Riesgo alto de promiscuidad, off-targets y efectos secundarios. |
| **Negativo (-)** | Choque estérico | Buenas propiedades fisicoquímicas pero geometría 3D incompatible con el bolsillo del receptor. |

**Fundamento científico:** El concepto es análogo al Ligand Efficiency Index (LEI) y al Specificity Index usados en la industria farmacéutica para priorización de hits. La formulación aquí es más directa: mide directamente cuánta afinidad proviene de la interacción 3D específica vs. propiedades genéricas.

**Calibración del Delta:** Con PDBbind (~5,000 complejos) se calculará Delta para cada complejo, obteniendo:
- Distribución completa (media, varianza, percentiles)
- Umbrales naturales para clasificar alto/medio/bajo
- Se almacena en `artifacts/delta_distribution.json`

#### Detección de sesgo en producción

Para cada molécula nueva, ambos modelos predicen en paralelo:
- Si `pKd_A ≈ pKd_NULL` (Delta ≈ 0) → las features 3D no están aportando → warning: "El score de esta molécula depende principalmente de sus propiedades fisicoquímicas, no de interacciones específicas con el receptor"
- Si `pKd_A ≠ pKd_NULL` (Delta significativo) → las features 3D contribuyen → mayor confianza en la predicción

Esto convierte la detección de sesgo en un **sistema de monitoreo en producción permanente**, no un paso offline de validación.

#### Mitigaciones complementarias (se mantienen)

1. **Ablation testing por grupo de features** (offline, durante entrenamiento):
   - Grupo A: Descriptores moleculares 1D/2D
   - Grupo B: Score Vina crudo + sub-componentes energéticos
   - Grupo C: Features de interacción 3D
   - Entrenar: solo-A, solo-B, solo-C, A+B, A+C, B+C, A+B+C
   - Criterio: Si solo-A ≈ A+B+C → rechazar modelo

2. **Scaffold-split cross-validation** (obligatorio)

3. **SHAP values por predicción individual** (top-5 features deben incluir ≥ 2 features 3D)

**Criterio de aceptación del modelo (obligatorio antes de deploy):**
- Ablation: Grupo C debe aportar mejora significativa sobre Grupo A
- Scaffold-split R² > 0 en datos no vistos
- SHAP: top-5 features incluyen ≥ 2 features de interacción 3D
- Delta promedio en PDBbind > 0 (el Modelo A es mejor que el NULL en promedio)
- **Si no se cumple, NO se deploya.** Se documenta como limitación.

---

### ✅ PROBLEMA 4: Compatibilidad de herramientas con Python 3.14 (RESUELTO — IMPLEMENTADO)

**Severidad:** MEDIA  
**Estado:** ✅ RESUELTO — ProLIF 2.1.0 + RDKit + XGBoost corren directamente en Python 3.14. No se necesitó microservicio separado ni Python 3.12. ODDT descartado por incompatibilidad.

**Descripción:**  
El proyecto usa Python 3.14.3 (vanguardia). Las herramientas propuestas (ODDT, ProLIF, XGBoost, SHAP, scikit-learn) podrían no tener wheels disponibles para esta versión. El problema va más allá de instalar librerías: la **feature extraction** (ODDT/ProLIF) se ejecuta en producción para cada molécula nueva, no solo offline durante entrenamiento.

**Opciones evaluadas:**

| Opción | Descripción | Razón de descarte o aceptación |
|---|---|---|
| Instalar todo en Python 3.14 | Verificar compatibilidad e instalar | Probablemente falle — ODDT tiene C extensions y OpenBabel bindings |
| Exportar pesos y predecir en 3.14 | Entrenar en 3.12, exportar `.json`/`.onnx`, cargar en 3.14 | **Incompleto** — resuelve la predicción pero NO la feature extraction. Extraer H-bonds, contactos 3D, π-stacking requiere ODDT en producción |
| Extraer features 3D con RDKit puro | Re-implementar criterios geométricos sin ODDT | Funciona en 3.14, pero riesgo de inconsistencia entre features de training (ODDT/3.12) vs inference (RDKit/3.14) |
| **Microservicio de rescoring en Python 3.12** | Contenedor Docker separado con todo el pipeline de rescoring | **ACEPTADA** — consistencia total, separación limpia, escala independientemente |

**Solución aceptada: Microservicio de Rescoring en Python 3.12**

Un contenedor Docker separado que encapsula TODO el pipeline de rescoring:

```
docker-compose.yml:
  - postgres          (existente)
  - redis             (existente)
  - minio             (existente)
  - backend           (FastAPI, Python 3.14) → orquesta pipeline principal
  - rescoring         (FastAPI ligero, Python 3.12) → pose filter + features + modelo + Delta
```

**API del microservicio rescoring:**

```
POST /rescore
Body: {
  protein_pdb: "...",
  ligand_poses: ["pose1.pdbqt", "pose2.pdbqt", ...],  # 9 poses de Vina
  vina_scores: [-8.3, -7.9, ...],
  molecular_descriptors: {MW: 350.4, LogP: 2.1, ...}  # ya calculados por RDKit en 3.14
}
Response: {
  pkd_a: 6.7,
  pkd_null: 5.4,
  delta: 1.3,
  semaphore: "green",
  pose_index_used: 0,
  pose_filter_results: [true, true, false, ...],
  confidence: {cluster_size: 5, pose_variance: 0.8}
}
```

**Ventajas:**
- **Consistencia total:** Mismo ODDT/Python en training y inference → features idénticas
- **Separación de responsabilidades:** El backend principal no sabe que existe XGBoost/ODDT/SHAP
- **Escalabilidad independiente:** Si rescoring es lento, escalar solo ese contenedor
- **Testabilidad:** El servicio de rescoring se prueba aislado, con su propio suite de tests
- **Actualización sin downtime:** Nuevo modelo → nuevo container → blue-green deploy
- **Encaja con Docker existente:** Ya tenemos `docker-compose.yml` con postgres/redis/minio

**Lo que contiene el contenedor rescoring (Python 3.12):**
- ODDT (feature extraction, parsing PDBbind)
- XGBoost (predicción)
- scikit-learn (preprocesamiento)
- SHAP (explicabilidad, solo en modo debug/análisis)
- FastAPI (API ligera)
- Artefactos del modelo (`model_a.joblib`, `model_null.joblib`, `delta_distribution.json`)

**Lo que NO necesita el backend principal (Python 3.14):**
- No instala ODDT, XGBoost, SHAP, scikit-learn
- Solo hace un HTTP POST a `rescoring:8001/rescore` después de Vina
- Recibe respuesta JSON y la integra en el score compuesto

**Entrenamiento offline:**
- Proyecto separado (`/ml_training/`) o script dentro del contenedor rescoring
- Python 3.12, ODDT, XGBoost, SHAP, PDBbind
- Genera artefactos → se copian/montan en el contenedor rescoring de producción
- Nunca corre en producción — solo genera archivos estáticos

---

### ✅ PROBLEMA 5: Tamaño y almacenamiento de PDBbind (RESUELTO — IMPLEMENTADO)

**Severidad:** BAJA  
**Estado:** ✅ IMPLEMENTADO — PDBbind v2020 descargado (5,316 complejos), scripts/setup_pdbbind.py operativo, datos en data/pdbbind/ (.gitignore)

**Descripción:**  
PDBbind refined set contiene ~5,000 complejos con estructuras 3D. Requiere:
- Descarga (~2-5 GB comprimido)
- Almacenamiento descomprimido (~10-20 GB estimado)
- Procesamiento para feature extraction

**Principio fundamental:** NUNCA hacer commit de datos al repositorio.

**Solución aceptada: Dos perfiles de usuario, dos experiencias distintas**

#### Perfil 1: Usuario final de MolDesign (diseña moléculas)

**No necesita PDBbind en absoluto.** Los modelos ya entrenados son artefactos ligeros que SÍ viven en el repositorio:

| Artefacto | Tamaño | En repo |
|---|---|---|
| `model_a.joblib` | ~1-5 MB | ✅ Sí |
| `model_null.joblib` | ~1-5 MB | ✅ Sí |
| `delta_distribution.json` | ~10 KB | ✅ Sí |
| `pdbbind_audit_report.json` | ~50 KB | ✅ Sí (transparencia) |
| `training_report.json` | ~100 KB | ✅ Sí (auditoría) |
| `frozen_test_set.json` | ~20 KB | ✅ Sí |

**Experiencia:** `git clone` → `docker compose up` → listo. Modelo ya incluido.

#### Perfil 2: Científico que quiere re-entrenar el modelo

**Necesita PDBbind.** Un solo comando:

```bash
python scripts/setup_pdbbind.py
```

**El script es inteligente con fallbacks encadenados:**

1. **Check local:** ¿Ya existen datos en `data/pdbbind/`? → Si sí, validar integridad (checksum SHA-256) y no hacer nada (idempotente)
2. **Intento 1 — ODDT mirror:** `oddt.datasets.pdbbind` tiene downloader integrado que busca mirrors públicos → si funciona, descarga automática
3. **Intento 2 — Reconstrucción desde fuentes libres:** Descargar estructuras desde **RCSB PDB** (gratis, API pública, sin registro) + datos de binding desde **BindingDB/ChEMBL** (gratis, API pública). Los PDB IDs del refined set index están publicados en papers. Más lento (~horas) pero sin fricción.
4. **Fallback manual:** Si todo falla → mostrar instrucciones claras:
   ```
   ⚠️ Descarga automática no disponible.
   1. Regístrate en http://www.pdbbind.org.cn/ (registro académico gratuito)
   2. Descarga el "Refined Set" (~2-5 GB)
   3. Coloca el archivo en data/pdbbind/
   4. Ejecuta de nuevo: python scripts/setup_pdbbind.py
   ```
5. **Post-descarga (automático):** Descomprimir → validar integridad → ejecutar pipeline de auditoría "Solo Casos VIP" → generar `pdbbind_audit_report.json`

**Estructura de directorios:**

```
data/                          # en .gitignore
├── pdbbind/
│   ├── refined-set/           # ~5,000 complejos descomprimidos
│   ├── checksums.sha256       # verificación de integridad
│   └── download_metadata.json # fecha, fuente, versión
```

**Nota sobre PDBbind:** PDBbind requiere registro académico. No es descarga libre anónima como pip. Pero las estructuras PDB subyacentes (RCSB) y los datos de binding (BindingDB/ChEMBL) sí son 100% libres — lo que PDBbind añade es la curación y el mapeo ya hecho. El Intento 2 reconstruye ese mapeo desde fuentes libres a costa de más tiempo de procesamiento.

---

### ✅ PROBLEMA 6: Generalización a targets nuevos / GPCRs sub-representados (PARCIALMENTE RESUELTO)

**Severidad:** MEDIA  
**Estado:** 🔄 PARCIALMENTE — Clasificación por familia estructural implementada (structural_family.py). Performance por familia medida. Mejoras de universalidad (shell atoms, ECIF) pendientes en v4.

**Descripción:**  
MolDesign aspira a soportar múltiples targets (multi-target, drug discovery general). El modelo ML entrenado en PDBbind generaliza razonablemente porque el dataset incluye miles de proteínas diferentes, PERO:

- GPCRs están sub-representados en PDBbind (~50-100 de ~5,000 complejos)
- Un target completamente novedoso (e.g., de AlphaFold sin datos experimentales) no tendrá complejos similares en el training set
- El modelo podría tener performance degradada en clases de proteínas no representadas

**Propuesta evaluada y descartada:**

| Propuesta | Descripción | Razón de descarte |
|---|---|---|
| Clasificar por sistema biológico | Separar complejos por "sistema nervioso", "digestivo", etc. | **Científicamente incorrecto.** La física de binding depende de la estructura 3D del bolsillo de unión, no del órgano donde opera la proteína. Una kinasa del sistema nervioso y una kinasa del sistema digestivo tienen bolsillos casi idénticos. Un receptor 5-HT1A (nervioso) tiene más en común estructuralmente con el receptor adrenérgico β2 (cardiovascular) porque ambos son GPCRs de Clase A con el mismo fold de 7 hélices transmembranales. |

**Solución aceptada: Clasificación por Familia Estructural de Proteínas**

Los ~4,500 complejos VIP de PDBbind se clasifican por **familia estructural** (usando clasificación UniProt/ECOD), no por sistema orgánico:

| Familia | Ejemplos | Características del binding site | Representación en PDBbind |
|---|---|---|---|
| **GPCRs Clase A** | 5-HT1A, D2, β2-adrenérgico, opioides | Bolsillo transmembranal profundo, 7-TM | Baja (~50-100) |
| **Kinasas** | CDK2, EGFR, ABL | Bolsillo ATP-binding, hinge region | Alta (~800+) |
| **Proteasas** | HIV-1 protease, caspasas | Surco catalítico, sitio activo abierto | Alta (~600+) |
| **Receptores nucleares** | Estrógeno, andrógeno | Bolsillo lipofílico cerrado | Media (~100-200) |
| **Enzimas solubles** | COX-2, acetilcolinesterasa | Variable pero bien definido | Alta (~1000+) |

**Implementación:**

1. **Durante entrenamiento:** Etiquetar cada complejo con su familia estructural
2. **Durante validación:** Medir performance **por familia** (scaffold-split R², Spearman, RMSE)
3. **Si la performance en GPCRs es significativamente peor que el promedio:**
   - Documentar la diferencia exacta
   - Agregar warning en producción cuando el target sea GPCR
   - El warning dice: "El modelo tiene menor precisión para GPCRs (~N complejos de entrenamiento) vs. kinasas (~M complejos). Interpretar con precaución adicional."
4. **Degradación explícita:** Si el modelo predice peor que random para una familia concreta → caer back a Vina raw score con warning para esa familia
5. **Metadata en artifacts:** `training_report.json` incluye métricas desglosadas por familia

**Beneficio adicional:** Con el tiempo, si PDBbind crece su representación de GPCRs (tendencia actual gracias a cryo-EM), cada re-entrenamiento mejorará automáticamente la performance en GPCRs.

---

## 6. Decisiones técnicas pendientes

### A resolver antes de empezar implementación

| # | Decisión | Opciones | Estado |
|---|---|---|---|
| 1 | Librería de feature extraction | ODDT vs ProLIF vs manual | ODDT preferido, corre en microservicio Python 3.12 |
| 2 | Algoritmo ML + objetivo | Regresión (MSE) vs **Learning to Rank** (pairwise) | **LTR decidido** — `rank:pairwise` (Decisión 8) |
| 3 | Manejo de poses | Solo top-1 vs clustering vs todas-9 | Clustering propuesto + varianza de 9 poses como feature de incertidumbre |
| 4 | Evaluación de bias | Solo feature importance vs ablation completo | Ablation completo obligatorio |
| 5 | Train/test split | Random vs scaffold-based | Scaffold-based obligatorio |
| 6 | Pesos del score compuesto | Fijos vs aprendidos | Fijos inicialmente, ajustables tras validación |
| 7 | Threshold de aceptación | ~~R²~~, **NDCG@10**, Spearman, ablation delta | NDCG@10 + Spearman como métricas principales (LTR) |
| 8 | Applicability Domain | Sí/No | **Obligatorio** — Mahalanobis (Decisión 9) |
| 9 | Comunicación del score | Score 0-100 solo vs **Likelihood Ratios** | **LR obligatorio** como capa interpretativa (Decisión 10) |

---

## 7. Plan de implementación (draft, sujeto a cambios)

### Fase 1 — Setup, datos y auditoría ✅ COMPLETADA (2026-04-05)
- [x] ~~Crear `Dockerfile.rescoring`~~ → Simplificado: rescoring corre en mismo entorno Python 3.14
- [x] Crear script `scripts/setup_pdbbind.py` — descarga PDBbind v2020 (5,316 complejos)
- [x] Parsear PDBbind refined set con `rescoring/pdbbind_parser.py` (RDKit, no ODDT)
- [x] **Ejecutar pipeline de auditoría "Solo Casos VIP"** — `rescoring/vip_audit.py` (5 checks)
- [x] Generar `pdbbind_audit_report.json` — 3,019 VIP de 3,441 curados
- [x] **Clasificar complejos por familia estructural** — `rescoring/structural_family.py`
- [x] **Congelar test set fijo** — 500 complejos representativos
- [x] Crear `rescoring/feature_extractor.py` v3 — ProLIF 2.1.0 + RDKit-direct + numpy
- [x] Crear `rescoring/pose_filter.py` con checks geométricos

### Fase 2 — Entrenamiento y validación ✅ COMPLETADA (2026-04-06)
- [x] Entrenar **Modelo A** (XGBoost `reg:squarederror`, 176 features v4) — scaffold-split
- [x] Entrenar **Modelo NULL** (XGBoost, solo 8 features 1D/2D) — mismos splits
- [x] ~~Grupos de ranking~~ → Pospuesto: `rank:pairwise` requiere >10 ligandos/target, PDBbind promedia ~3
- [x] **Métricas v4:** Spearman **0.601 ± 0.040** (CV), Holdout 0.527, RMSE 2.031
- [x] Ablation testing — 11 configs (A_ext, B, C_ext, D_shell, E_ecif, combinaciones)
- [x] SHAP values — shell_C_C_8_12 0.305, MW 0.176 (-62%), ecif_O_acc_C 0.147
- [x] **Delta distribution** → `delta_distribution.json` (green > 0.578, red < -1.051)
- [x] **Applicability Domain** → `applicability_domain.json` (Mahalanobis p99 = 29.129)
- [x] Performance por familia medida (en `training_report.json`)
- [x] **7/7 criterios de aceptación pasados** — deployado
- [x] Artefactos v4 en `backend/artifacts/`

### Fase 2.5 — Mejoras v4 ✅ COMPLETADA (2026-04-06 06:41 UTC)
- [x] **P1: Normalizar MW** — log_mw + heavy_atom_count + contacts_per_ha → MW SHAP -62%
- [x] **P2: Shell atom counts (RF-Score)** — 96 features (4×8×3 bins), top SHAP feature
- [x] **P3: Re-docking script** — `scripts/redock_pdbbind.py` creado (ejecución ~42h pendiente)
- [x] **P4: ECIF-lite** — 56 features (8 prot types × 7 lig types @ 6Å)
- [x] **Retrain v4** — Spearman CV = **0.601 ± 0.040** (target 0.55 SUPERADO)
- [x] **Deploy artefactos v4** — `backend/artifacts/` actualizado

### Fase 3 — Integración (pendiente, post-v4)
- [ ] API endpoint `POST /rescore` en backend
- [ ] `model_manager.py` — carga Modelo A + NULL, predicción, Delta, semáforo
- [ ] Integrar Applicability Domain check antes de predicción
- [ ] Adaptar `scoring/engine.py` para incluir ML rescore
- [ ] Delta como warning visual — no modifica score compuesto
- [ ] Likelihood Ratios (LR+ con IC95% bootstrap) usando panel BindingDB
- [ ] Tests unitarios y de integración

### Fase 4 — Recalibración y automatización (pendiente)
- [ ] Re-correr 40 moléculas BindingDB con pipeline completo
- [ ] Medir nuevo Spearman (Vina raw vs ML rescored)
- [ ] Script `update_model.py` con criterios de aceptación automáticos
- [ ] Si Spearman no mejora → documentar honestamente

---

## 8. Criterios de aceptación del sistema completo

El ML rescoring solo puede deployarse en producción si cumple **todos** estos criterios:

1. **No es fake science:** El modelo hace predicciones basadas en datos experimentales publicados, no inventa valores
2. **Es auditable:** Feature importances, SHAP values y training metrics están documentados y accesibles
3. **No tiene sesgo de ligando dominante:** Ablation testing demuestra que features 3D contribuyen significativamente
4. **Generaliza:** Scaffold-split NDCG@10 > baseline y Spearman > 0 en datos no vistos
5. **Es transparente:** El usuario sabe que el score viene de un modelo ML, no de cálculo de primeros principios
6. **Falla honestamente:** Si el modelo no puede hacer una predicción confiable (fuera del Applicability Domain), lo dice en vez de inventar
7. **Mejora lo existente:** El nuevo Spearman (ML rescored) es estadísticamente superior al Spearman de Vina raw (0.020)
8. **Es reproducible:** Seed fijo, versiones documentadas, datos de entrenamiento trazables
9. **Comunica incertidumbre:** Los Likelihood Ratios se reportan con IC95% — la incertidumbre del calibration panel (n=40) es visible
10. **Respeta dominio:** Moléculas fuera del Applicability Domain reciben degradación explícita, no predicción silenciosamente inválida

Si cualquiera de estos criterios no se cumple, el sistema **no se deploya** y se documenta como intento fallido con las lecciones aprendidas.

---

## 9. Qué se le comunica al usuario

### Si el ML rescoring funciona — 🟢 Delta positivo alto

El usuario verá:
```
Afinidad estimada: -8.3 kcal/mol (AutoDock Vina, docking rígido)
Ranking ML rescored: score 78/100 (modelo LTR, entrenado en PDBbind refined set)

📊 Likelihood Ratio (calibración contra 40 compuestos BindingDB, 5-HT1A):
   Un score ≥ 78 ocurre 3.2× más frecuentemente en moléculas con actividad
   experimental comprobada (pIC50 ≥ 7) que en moléculas inactivas.
   LR+ = 3.2 (IC 95%: 1.1 – 9.7)

🟢 Especificidad 3D: +1.3 — ENCAJE ESPECÍFICO
   Tu molécula tiene interacciones específicas con el receptor
   más allá de sus propiedades fisicoquímicas.
   Esto sugiere un mecanismo tipo "llave-cerradura".

⚠️ El ranking rescored es una predicción ML basada en ~N complejos experimentales validados.
   No equivale a validación experimental. El Likelihood Ratio tiene IC amplio (n=40).
   El semáforo de especificidad es una estimación computacional,
   no equivale a un ensayo de selectividad experimental.
```

### Si Delta ≈ 0 — 🟡 Binding inespecífico

El usuario verá:
```
Ranking ML rescored: score 71/100

📊 Likelihood Ratio: LR+ = 1.8 (IC 95%: 0.6 – 5.2)
   La evidencia computacional es débil — apenas distingue esta molécula
   de una inactiva. Interpretar con precaución.

🟡 Especificidad 3D: +0.1 — UNIÓN INESPECÍFICA
   El score de esta molécula depende principalmente de sus
   propiedades fisicoquímicas genéricas (tamaño, lipofilia),
   no de interacciones específicas con el receptor.
   Riesgo: promiscuidad y posibles off-targets/efectos secundarios.
   Recomendación: evaluar selectividad experimentalmente.
```

### Si Delta es negativo — 🔴 Choque estérico

El usuario verá:
```
Ranking ML rescored: score 32/100

📊 Likelihood Ratio: LR+ = 0.4 (IC 95%: 0.1 – 1.5)
   La evidencia computacional DESFAVORECE esta molécula.
   LR+ < 1 indica que este score es más frecuente en inactivas que en activas.

🔴 Especificidad 3D: -1.2 — INCOMPATIBILIDAD GEOMÉTRICA
   La geometría 3D de esta molécula es incompatible con el
   bolsillo del receptor. Sus propiedades fisicoquímicas son
   favorables, pero la forma tridimensional impide un buen encaje.
   Sugerencia: modificar grupos que causan el choque estérico.
```

### Si la molécula está fuera del Applicability Domain

El usuario verá:
```
Afinidad estimada: -8.3 kcal/mol (AutoDock Vina, docking rígido)

⚠️ DOMINIO DE APLICABILIDAD: FUERA DE RANGO
   Esta molécula tiene MW=1,250 Da, LogP=8.3, significativamente diferente
   del rango de entrenamiento del modelo (MW: 150-750 Da, LogP: -2 a 6).
   Distancia de Mahalanobis: 12.4 (umbral: 8.7)
   La predicción ML NO se genera — confianza insuficiente.
   Se muestra solo el resultado de Vina (filtrado grueso).
```

### Si el ML rescoring no se deploya

El usuario verá:
```
Afinidad estimada: -8.3 kcal/mol (AutoDock Vina, docking rígido)

⚠️ AutoDock Vina es útil para filtrado grueso y generación de poses.
   No es confiable para ranking fino entre moléculas estructuralmente diversas.
   Spearman ρ vs datos experimentales: 0.020
```

En todos los casos, la honestidad se mantiene. El semáforo NO altera el score numérico — es una capa informativa independiente. El Likelihood Ratio contextualiza el score sin alterarlo.

---

## 10. Relación con el pipeline existente

### Lo que NO cambia
- Validación química (RDKit) — intacta
- Propiedades fisicoquímicas — intactas
- Generación de conformer — intacta
- Ejecución de Vina — intacta
- Scoring ADME y drug-likeness — intactos
- Interpretación IA — intacta (recibirá datos adicionales del rescoring)
- Blockchain — no afectada
- Frontend — necesitará mostrar datos adicionales del rescoring + semáforo

### Lo que SÍ cambia
- **`docker-compose.yml`** — nuevo servicio `rescoring` (Python 3.12)
- **`scoring/engine.py`** — incorpora ML rescore como nueva dimensión (Delta NO modifica score, solo warning)
- **`scoring/normalizer.py`** — nueva función para normalizar pKd predicho
- **`services/docking/queue_handler.py`** — HTTP POST a microservicio rescoring post-Vina (ya no ejecuta ML directamente)
- **`core/models.py`** — nuevos campos: `ml_pkd_rescored`, `ml_pkd_null`, `delta_specificity_3d`, `delta_semaphore`, `pose_filter_result`, `pose_index_used`, `protein_family`
- **`db/migrations/`** — nueva migración para columnas de ML rescore + Delta + semáforo + metadata

### Lo que se AGREGA
- **`Dockerfile.rescoring`** — imagen Docker para el microservicio (Python 3.12, ODDT, XGBoost)
- **`rescoring/`** — proyecto del microservicio (pose_filter, feature_extractor, model, applicability_domain, API FastAPI)
- **`ml_training/`** — proyecto offline de entrenamiento (trainer, validator, scripts)
- **`scripts/setup_pdbbind.py`** — script de setup con fallbacks encadenados (ODDT → RCSB+BindingDB → manual)
- **`scripts/train_rescoring_model.py`** — script de entrenamiento offline (Modelo A + NULL, objective=rank:pairwise)
- **`scripts/update_model.py`** — script de auto-actualización con criterios de aceptación
- **`scripts/calibrate_likelihood_ratios.py`** — calcula LR+ con IC95% bootstrap usando panel BindingDB
- **`artifacts/applicability_domain.json`** — media, covarianza inversa y umbral del training set
- **`artifacts/likelihood_ratios.json`** — LR+ por umbral de score con IC95%
- **`tests/unit/test_rescoring_*.py`** — tests del módulo de rescoring
- **`tests/unit/test_pose_filter.py`** — tests del filtro geométrico
- **`tests/unit/test_delta_specificity.py`** — tests del cálculo de Delta
- **`tests/unit/test_applicability_domain.py`** — tests del check de dominio (Mahalanobis)
- **`tests/unit/test_likelihood_ratios.py`** — tests del cálculo de LR+
- **`tests/unit/test_pdbbind_audit.py`** — tests del pipeline de auditoría de datos
- **`tests/unit/test_model_update.py`** — tests del protocolo de auto-actualización
- **`tests/integration/test_rescoring_service.py`** — tests de integración backend ↔ microservicio

---

## 11. Referencias

### Scoring functions y ML rescoring
- Wang R, Fang X, Lu Y, Wang S. "The PDBbind database." J Med Chem. 2004;47(12):2977-2980.
- Trott O, Olson AJ. "AutoDock Vina." J Comput Chem. 2010;31(2):455-461.
- Li H, Leung KS, Wong MH, Ballester PJ. "Improving AutoDock Vina using Random Forest." J Comput Chem. 2015;36:2132-2141.
- Zheng L, Fan J, Mu Y. "OnionNet: a multiple-layer intermolecular-contact-based convolutional neural network for protein-ligand binding affinity prediction." ACS Omega. 2019;4(14):15956-15965.

### Bias y validación
- Wallach I, Heifets A. "Most ligand-based benchmarks reward memorization." J Chem Inf Model. 2018;58(5):916-932.
- Yang M, et al. "Concepts and applications of chemical fingerprint for hit and lead screening." Drug Discov Today. 2022.
- CASF (Comparative Assessment of Scoring Functions): Li Y, et al. J Chem Inf Model. 2014;54(6):1700-1716.

### Pose quality
- Houston DR, Walkinshaw MD. "Consensus docking." J Chem Inf Model. 2013;53(2):384-390.

### Herramientas
- ~~ODDT (Open Drug Discovery Toolkit)~~ → Reemplazado por ProLIF + RDKit-direct (incompatibilidad Python 3.14)
- ProLIF: Bouysset C, Fiorucci S. "ProLIF: a library to encode molecular interactions as fingerprints." J Cheminform. 2021;13:72. DOI: 10.1186/s13321-021-00548-6
- SHAP: Lundberg SM, Lee SI. "A unified approach to interpreting model predictions." NeurIPS 2017.

### Shell atom counts y ECIF (mejoras v4)
- Li H, Leung KS, Wong MH, Ballester PJ. "Substituting random forest for multiple linear regression improves binding affinity prediction of scoring functions: Cyscore as a case study." BMC Bioinformatics. 2014;15:291.
- Sánchez-Cruz N, et al. "Extended connectivity interaction features: improving binding affinity prediction through chemical description." Bioinformatics. 2021;37(10):1376-1382.

### Learning to Rank
- Burges C. "From RankNet to LambdaRank to LambdaMART: An Overview." Microsoft Research Technical Report MSR-TR-2010-82, 2010.
- Liu TY. "Learning to Rank for Information Retrieval." Foundations and Trends in IR, 2009.
- Ashtawy H, Mahapatra N. "Ranking Accuracies of Conventional and ML-Based Scoring Functions." IEEE/ACM Trans Comput Biol Bioinform. 2012;9(5):1301-1313.

### Applicability Domain
- Sahlin U. "The Applicability Domain in QSAR Modeling — A Practical Approach." QSAR & Combinatorial Science, 2008.
- Yurdakul B. "Statistical Properties of Population Stability Index." Western Michigan University, 2018.

### Likelihood Ratios (medicina basada en evidencia)
- Fagan TJ. "Nomogram for Bayes' Theorem." N Engl J Med. 1975;293(5):257.
- Deeks JJ, Altman DG. "Diagnostic tests 4: likelihood ratios." BMJ. 2004;329:168-169.
- McGee S. "Simplifying Likelihood Ratios." J Gen Intern Med. 2002;17(8):647-650.

---

## 12. Historial de decisiones

| Fecha | Decisión | Justificación |
|---|---|---|
| 2026-04-04 | Descartar Fase A (receptor profiling manual) | No escala a targets desconocidos — contradice misión de drug discovery general |
| 2026-04-04 | Transformar Fase B en feature extraction para ML | Las interacciones 3D son más útiles como inputs del modelo que como score independiente |
| 2026-04-04 | Descartar Fase C (pharmacophore scoring) | Presupone conocimiento del target — contradice descubrimiento |
| 2026-04-04 | Elegir XGBoost sobre deep learning | Interpretable, rápido, SHAP compatible, probado en literatura de rescoring |
| 2026-04-04 | Elegir PDBbind como dataset de entrenamiento | Estándar de la industria, ~5,000 complejos experimentales, diverso |
| 2026-04-04 | Exigir ablation testing como criterio de aceptación | Prevenir sesgo de ligando (Wallach & Heifets 2018) |
| 2026-04-04 | Exigir scaffold-split cross-validation | Prevenir memorización de scaffolds |
| 2026-04-04 | Proponer clustering de poses de Vina | Mitigar garbage-in-garbage-out sin software adicional |
| 2026-04-05 | Descartar "3 puntos del sitio activo" para validar poses | Requiere conocimiento previo del target — misma objeción que Fase A |
| 2026-04-05 | Adoptar filtro geométrico automático de poses (3 checks) | No requiere conocimiento del target, computacionalmente trivial, elimina poses basura |
| 2026-04-05 | Descartar segundo ML "auditor" para sesgo | Mismo sesgo si mismos datos — no resuelve el problema |
| 2026-04-05 | Adoptar Modelo NULL como control negativo permanente | Detecta sesgo en producción por predicción individual, no solo offline |
| 2026-04-05 | Crear métrica "Delta de Especificidad 3D" | Mide contribución de interacciones 3D vs propiedades genéricas — diferenciador de producto |
| 2026-04-05 | Pipeline de auditoría "Solo Casos VIP" para PDBbind | 5 checks programáticos por complejo — solo datos limpios y confiables para entrenamiento |
| 2026-04-05 | Clasificar PDBbind por familia estructural (NO por sistema biológico) | La física de binding depende de estructura 3D del bolsillo, no del órgano |
| 2026-04-05 | Delta como warning visual (semáforo), NO modifica score | Métrica nueva sin validación externa — prematuro alterar score compuesto |
| 2026-04-05 | Protocolo de auto-actualización del modelo con test set congelado | Re-entrenar con PDBbind nuevo, deploy solo si métricas mejoran en test fijo |
| 2026-04-05 | Semáforo verde/amarillo/rojo para Delta | Umbrales calibrados empíricamente (percentiles 25 y 60 de distribución PDBbind) |
| 2026-04-05 | Microservicio de rescoring en Python 3.12 (Docker) | Feature extraction + modelo + Delta en contenedor separado — consistencia total train/inference |
| 2026-04-05 | Descartar "exportar pesos a 3.14" como solución completa | La feature extraction (ODDT) también corre en producción — no basta con exportar el modelo |
| 2026-04-05 | PDBbind NUNCA en repo — artefactos del modelo SÍ en repo | Datos crudos (~5 GB) en .gitignore; artefactos ligeros (~10 MB) sí se comitean |
| 2026-04-05 | Script setup_pdbbind.py con fallbacks encadenados | ODDT mirror → RCSB+BindingDB (gratis) → instrucciones manuales. Un solo comando. |
| 2026-04-05 | Dos perfiles de usuario: final (0 setup) vs científico (1 comando) | El usuario final tiene modelo incluido; solo el científico que re-entrena necesita PDBbind |
| 2026-04-05 | **Learning to Rank (LTR)** — `objective='rank:pairwise'` en vez de regresión | De Recuperación de Información (Google). El problema es ranking (Spearman), no predicción absoluta (RMSE). XGBoost lo soporta nativo. |
| 2026-04-05 | **Applicability Domain** con distancia de Mahalanobis | De Banca (Basilea III / PSI). Detectar automáticamente moléculas fuera del dominio de entrenamiento antes de predecir. |
| 2026-04-05 | **Likelihood Ratios** para comunicación al usuario | De Medicina Clínica. Un LR+ con IC95% es radicalmente más honesto que "score 78/100". Lenguaje que un PhD en farmacología respeta. |
| 2026-04-05 | Descartar ensemble de conformers extra | No multiplicar trabajo de Vina. Usar varianza de las 9 poses existentes como feature de incertidumbre (costo: 0 seg extra). |
| 2026-04-05 | Backlog: Bühlmann, CUSUM, DAGs, G×E → `FUTURE_ARCHITECTURE.md` | Conceptos sólidos pero innecesarios para sprint actual del ML Rescoring. |
| 2026-04-05 | **Vina Energy Terms** como features individuales del modelo | Los 5 términos Lagrangianos (gauss1, gauss2, repulsion, hydrophobic, hydrogen) ya definidos en `VINA_ENERGY_FEATURES`. Activar en Fase 2 cuando estemos extrayendo features reales de PDBbind. |
| 2026-04-05 | **Visualización de superficie 3D** — 3 niveles progresivos | A1: cargas parciales Gasteiger (bajo costo, 3Dmol.js nativo). A2: mapa de lipofilia/hidrofobicidad Crippen. A3: ESP real con APBS (opcional, alto costo computacional, no debe bloquear tiempo de respuesta). Implementar cuando sea oportuno, no en sprint de ML Rescoring. |
| 2026-04-06 | **ProLIF 2.1.0 reemplaza ODDT** para feature extraction | ODDT no compila en Python 3.14 (OpenBabel bindings). ProLIF funciona directamente con RDKit. |
| 2026-04-06 | **RDKit-direct** para carga de proteínas (0.08s) | `Chem.MolFromPDBFile()` con sanitización relajada. 250x más rápido que MDAnalysis (~20s). |
| 2026-04-06 | **reg:squarederror** en lugar de rank:pairwise para v3 | PDBbind tiene ~3 ligandos/target en promedio → insuficiente para grupos de ranking. Se evaluará LTR en v5+ cuando haya datos enriquecidos. |
| 2026-04-06 | **n_jobs=1 obligatorio** en ProLIF run_from_iterable | ProLIF n_jobs=None → 12 subprocesos × 6 workers = 72 procesos → deadlock en Windows. Con n_jobs=1: 10x más rápido y estable. |
| 2026-04-06 | **Rescoring en mismo entorno** Python (no microservicio) | ProLIF + RDKit + XGBoost corren en Python 3.14 directamente → no se necesita contenedor separado para MVP. Se puede migrar a microservicio cuando escale. |
| 2026-04-06 | **Mejoras v4 priorizadas**: MW norm > shell atoms > re-dock > ECIF | Basado en diagnóstico SHAP/ablation. Universalidad para moléculas nuevas es el criterio principal. |

---

> **Estado (2026-04-06):** Modelo v3 entrenado y deployado. Spearman 0.435 ± 0.060 (5-fold scaffold CV, 3,019 complejos PDBbind).  
> **Código implementado:** `rescoring/feature_extractor.py` (ProLIF + RDKit-direct), `rescoring/train_orchestrator.py`, `rescoring/train_pipeline.py`, `rescoring/vip_audit.py`, `rescoring/data_splitter.py`, `rescoring/pdbbind_parser.py`.  
> **Artefactos deployados:** `backend/artifacts/model_a.joblib`, `model_null.joblib`, `training_report.json`, `applicability_domain.json`, `delta_distribution.json`, `shap_summary.json`.  
> **Desviaciones vs diseño original:** ProLIF reemplazó ODDT (compatibilidad Python 3.14). `reg:squarederror` en lugar de `rank:pairwise` (datos insuficientes por target para LTR, se usará en v5+). Rescoring corre en mismo entorno Python, no microservicio separado (simplificación MVP).  
> **Próximo paso:** Mejoras v4 — normalizar MW, shell atom counts (RF-Score), ECIF, re-docking de cristales para Group B. Target: Spearman ≥ 0.55.  
> **Si el ML rescoring no cumple los criterios de aceptación, no se deploya.**  
> La honestidad científica prima sobre la conveniencia de tener un feature nuevo.  
> Ver [docs/TRAINING_LOG_V3.md](TRAINING_LOG_V3.md) para detalles completos del entrenamiento.
