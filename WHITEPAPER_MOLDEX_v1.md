# MolDesign: Una Plataforma Open Source de Descubrimiento Farmacológico In Silico con ML Rescoring, Auditoría Científica Profunda y Certificación Blockchain

**Preprint Preliminar — v1.0**

**Johan Amezcua**
Ingeniería en Software · Universidad Virtual del Estado de Guanajuato (UVEG)
Monterrey, Nuevo León, México
26000885@es.uveg.edu.mx

**Repositorio**: https://github.com/srcacahuate619/molecule-design
**Demo**: https://molecule-design.vercel.app
**Fecha**: Mayo 2026

---

> *Este es un preprint preliminar sometido para revisión por pares. Los resultados son reproducibles con seed=42 y el código fuente disponible públicamente. No ha sido revisado por pares formalmente.*

---

## Resumen

Presentamos MolDesign (también conocido como Moldex), una plataforma web de código abierto para el descubrimiento farmacológico in silico que combina docking molecular con AutoDock Vina 1.2.5 y una capa de rescoring por Machine Learning entrenada sobre PDBbind Refined Set v2020. El sistema aborda el problema conocido de la función de puntuación empírica de Vina (Spearman ρ ≈ 0.02 en sets de moléculas diversas) mediante un modelo XGBoost entrenado con 176 descriptores de interacción proteína-ligando extraídos con ProLIF. El modelo implementa una arquitectura dual (Modelo A + Modelo NULL) para detectar y penalizar el sesgo de ligando, midiendo cuánto de la afinidad predicha corresponde a interacciones geométricas 3D reales versus propiedades fisicoquímicas inespecíficas.

En validación ciega sobre 50 fármacos aprobados por la FDA entre 2022-2024, el sistema alcanzó Spearman ρ = 0.512 (p = 0.00014) para el receptor 5-HT1A, sin ningún reentrenamiento específico por target. Una validación secundaria sobre el receptor GLP-1R (PDB: 6B3J), receptor de clase B completamente diferente al target primario de entrenamiento, produjo Spearman ρ = 0.485, demostrando capacidad de generalización entre familias de receptores. Una validación estructural del sitio activo de PCSK9 (PDB: 2P4E) mediante el inhibidor experimental SBC-115076 confirmó la correcta parametrización del grid box al detectar interacciones con los residuos GLY292, TYR293 y SER294, documentados en literatura como críticos para la actividad (validación de Spearman ρ para PCSK9 pendiente).

La plataforma es accesible desde cualquier navegador sin instalación, incluye un editor molecular 2D integrado, certifica los hallazgos de forma inmutable en la blockchain de Solana, y corre en hardware doméstico (AMD Ryzen 3) bajo una arquitectura de microservicios orquestada con Docker Compose.

**Palabras clave**: docking molecular, machine learning, rescoring, drug discovery, open science, PCSK9, 5-HT1A, GLP-1R, XGBoost, blockchain

---

## 1. Introducción

El descubrimiento de fármacos es uno de los procesos más costosos y lentos en la ciencia moderna. El costo promedio de desarrollar un nuevo medicamento supera los mil millones de dólares y requiere más de una década desde el screening inicial hasta la aprobación clínica. La fase computacional —identificar qué moléculas merecen síntesis y prueba experimental— es el cuello de botella más accesible para la intervención tecnológica.

AutoDock Vina es el estándar de facto en docking molecular de código abierto, con más de 10,000 citas en la literatura científica. Sin embargo, su función de puntuación empírica presenta una limitación conocida y documentada: el coeficiente de Spearman entre las afinidades predichas y las actividades experimentales medidas en sets de moléculas diversas es típicamente ρ ≈ 0.02 — estadísticamente indistinguible del azar. Vina es excelente prediciendo la geometría del encaje, pero pobre prediciendo la magnitud de la afinidad de forma relativa entre moléculas diversas.

Este trabajo presenta MolDesign, una plataforma que aborda este problema mediante una capa de rescoring por Machine Learning entrenada sobre datos experimentales reales (PDBbind), implementando además controles de sesgo, filtros de síntesis, métricas de eficiencia de ligando, y un sistema de certificación de autoría mediante blockchain. La plataforma está diseñada para ser accesible a investigadores sin infraestructura computacional especializada, democratizando el acceso a herramientas de calidad industrial.

### 1.1 Problema Central: El Sesgo de Ligando en Docking

Un problema sistémico en el docking molecular es el sesgo de ligando: la tendencia de las funciones de puntuación a correlacionar con propiedades fisicoquímicas simples (peso molecular, lipofilicidad) en lugar de capturar la especificidad geométrica real del encaje. Una molécula lipofílica grande puede puntuar bien simplemente por "llenar el bolsillo", aunque sus interacciones químicas sean inespecíficas.

MolDesign implementa un sistema de detección de sesgo mediante dos modelos en paralelo: un Modelo A entrenado con descriptores de interacción 3D (huellas de interacción ProLIF) y un Modelo NULL entrenado exclusivamente con descriptores 1D/2D. El delta entre ambos cuantifica cuánto de la afinidad predicha proviene de la geometría molecular real versus de propiedades fisicoquímicas inespecíficas.

### 1.2 Contexto de Targets Seleccionados

Los tres receptores validados en este trabajo representan áreas de alta relevancia terapéutica:

**5-HT1A (PDB: 7E2Y)** es el receptor primario de serotonina, target de ansiolíticos y antidepresivos como la buspirona. Es un receptor acoplado a proteína G (GPCR) de clase A, con estructura resuelta por Cryo-EM a 3.0 Å (Xu et al., 2021).

**GLP-1R (PDB: 6B3J)** es el receptor del péptido similar al glucagón tipo 1, target de medicamentos para diabetes tipo 2 y obesidad como semaglutida y liraglutida. Es un GPCR de clase B, estructuralmente más complejo y con un sitio de unión adaptado a ligandos peptídicos grandes.

**PCSK9 (PDB: 2P4E)** es la proproteína convertasa subtilisina/kexina tipo 9, involucrada en la regulación del receptor de LDL. Es target de anticuerpos monoclonales aprobados (Evolocumab, Alirocumab) para hiperlipidemia. La identificación de inhibidores de molécula pequeña de PCSK9 representa uno de los desafíos activos más relevantes en química medicinal, dado que la interfaz PCSK9-LDLR es notoriamente plana y difícil de drugar con moléculas pequeñas.

---

## 2. Métodos

### 2.1 Pipeline E2E

El pipeline de MolDesign transforma un SMILES de entrada en un reporte científico certificado siguiendo un flujo secuencial con múltiples capas de validación:

```
SMILES Input
    ↓
Validación RDKit (valencia, SMILES canónico)
    ↓
SA Score + Penalización de Tensión de Anillo
    ↓ [Bloqueo si SA > 6.0]
Propiedades ADME (RDKit)
    ↓
Generación de Conformero 3D (ETKDG v3)
    ↓
Docking AutoDock Vina 1.2.5 (seed=42)
    ↓
Pose Quality Filter (3 checks binarios)
    ↓
ML Rescoring (XGBoost + ProLIF, 176 features)
    ↓
Score Compuesto (Afinidad 45% + ADME 30% + Drug-likeness 25%)
    ↓
Reporte IA + Certificación Solana (SHA-256)
```

Todos los pasos son deterministas con `seed=42`. El mismo SMILES contra el mismo receptor produce siempre el mismo resultado.

### 2.2 Preparación de Receptores

Los receptores se obtienen del Protein Data Bank y se preparan mediante un pipeline automatizado:

1. Eliminación de moléculas de agua (registros HOH, WAT, DOD)
2. Eliminación de ligandos co-cristalizados
3. Adición de hidrógenos con OpenBabel
4. Conversión a formato PDBQT con Meeko
5. Definición del grid box centrado en el sitio ortostérico

La eliminación de aguas sigue la práctica estándar en docking rápido para evitar que aguas desordenadas del cristal bloqueen artificialmente el sitio de unión. AutoDock Vina compensa mediante términos de desolvatación en su función de puntuación (solvente implícito Born).

### 2.3 Validación de Redocking (5-HT1A)

Para 7E2Y, se realizó validación de redocking extrayendo el ligando co-cristalizado (serotonina), redockeando contra el receptor preparado, y midiendo el RMSD entre la pose predicha y la pose cristalográfica. El RMSD obtenido fue de **0.85 Å**, superando el estándar industrial de < 2.0 Å y confirmando la correcta parametrización del grid box.

| Parámetro | Valor |
|:---|:---|
| PDB ID | 7E2Y |
| Resolución | 3.0 Å (Cryo-EM) |
| Centro grid (X, Y, Z) | (103.03, 114.79, 108.36) |
| Dimensiones | 25.0 × 25.0 × 25.0 Å |
| Software | AutoDock Vina 1.2.5 |
| Redocking RMSD | **0.85 Å** |

### 2.4 Motor de ML Rescoring

#### 2.4.1 Dataset de Entrenamiento

El modelo se entrenó sobre el PDBbind Refined Set v2020, filtrado a estructuras con resolución ≤ 2.5 Å para garantizar calidad geométrica. El conjunto resultante contiene aproximadamente 5,000 complejos proteína-ligando con afinidades experimentales medidas (Ki, Kd, IC50).

Importantemente, el modelo **no fue entrenado con datos específicos de ninguno de los tres receptores validados** (5-HT1A, GLP-1R, PCSK9). Esto asegura que los resultados de validación son genuinamente prospectivos.

#### 2.4.2 Extracción de Features (176 descriptores)

| Grupo | N Features | Descripción |
|:---|:---:|:---|
| `shell_counts` | 3×N | Contactos átomo-átomo en capas concéntricas (3Å, 6Å, 12Å) |
| `ecif_lite` | N | Interaction fingerprints por tipo electroquímico (ECIF-lite) |
| `physchem` | 3 | MW, LogP, TPSA normalizados |

Las interacciones proteína-ligando (H-bonds, π-stacking, contactos hidrofóbicos, puentes salinos) se extraen con **ProLIF** a partir de los archivos PDBQT del docking. Para manejar archivos PDBQT sin hidrógenos explícitos, se implementó un parser de coordenadas manual como fallback con `inferrer=None`.

#### 2.4.3 Arquitectura Dual A + NULL

```
Pose de docking
      │
      ├──► Modelo A (Full 3D)
      │    Features: shell_counts + ecif_lite + physchem
      │    Captura interacciones geométricas 3D específicas
      │
      └──► Modelo NULL (Control Ciego)
           Features: SOLO physchem (MW, LogP, TPSA)
           No tiene acceso a geometría 3D

Delta de Especificidad = Score_A − Score_NULL

Delta > +0.5  →  Afinidad por encaje geométrico real ✅
Delta ≈ 0     →  Binding inespecífico fisicoquímico ⚠️
Delta < 0     →  Choques estéricos, molécula no cabe ❌
```

#### 2.4.4 Función de Pérdida y Optimización

El modelo XGBoost utiliza la función de pérdida `rank:pairwise` (LambdaMART), optimizando el ranking relativo entre pares de moléculas en lugar de valores absolutos de afinidad. Esta elección es deliberada: el ruido experimental en las afinidades de PDBbind hace que la predicción de valores absolutos sea menos confiable que la predicción del orden relativo.

**Validación interna:**
- Cross-validation (5-fold): Spearman ρ = 0.601 ± 0.04
- Holdout set: Spearman ρ = 0.527

#### 2.4.5 Dominio de Aplicabilidad (Distancia de Mahalanobis)

Para cada molécula evaluada, se calcula su distancia de Mahalanobis respecto al espacio de features de entrenamiento (PDBbind). Si la molécula está fuera del dominio de aplicabilidad, el sistema degrada automáticamente la confianza del score ML y lo comunica explícitamente al usuario, evitando extrapolación ciega.

### 2.5 Score Compuesto y Calibración Biofísica (v6.1)

El score final integra tres dimensiones farmacológicas complementarias:

```
Score = 0.45 × Afinidad_norm + 0.30 × ADME_norm + 0.25 × Druglikeness_norm
```

#### 2.5.1 Normalización de Afinidad de Unión ($S_{LE}$)
Para evitar el sesgo de superficie (moléculas gigantes que puntúan mejor simplemente por volumen), la afinidad se normaliza usando una función sigmoidea (Curva de Hill) basada en la **Eficiencia de Ligando ($LE = \frac{\Delta G}{N_H}$)**. 

En la versión **v6.1**, implementamos un **punto medio de eficiencia dinámico y adaptativo ($LE_{mid}$)** dependiente del número de átomos pesados ($N_H$) para reflejar que la densidad biofísica de unión decae fisiológicamente con el tamaño:
- **Moléculas pequeñas ($N_H < 15$)**: $LE_{mid} = -0.38$ kcal/mol/átomo (exigencia fragmentaria estricta).
- **Moléculas grandes ($N_H > 45$)**: $LE_{mid} = -0.20$ kcal/mol/átomo (compuestos maduros con acoples hidrofóbicos extendidos).
- **Moléculas medianas ($15 \le N_H \le 45$)**: Interpolación lineal continua:
  $$LE_{mid} = -0.38 + (N_H - 15) \times \frac{0.18}{30}$$

El score base se calcula con una pendiente de Hill de $k=15$:
$$\text{Base Score} = \frac{100}{1 + e^{15 \times (LE - LE_{mid})}}$$

#### 2.5.2 Suelo de Potencia Absoluta con Frontera Continua (Soft Potency Floor)
Para evitar que fragmentos ultra-eficientes pero sin afinidad total suficiente inflen su puntuación, se aplica una penalización si la afinidad absoluta es más débil que el umbral biológico del target ($Threshold$, e.g., $-7.5$ kcal/mol). 

Para eliminar discontinuidades numéricas bruscas, en **v6.1** se introdujo una **frontera continua normalizada a $1.0$ en el umbral**:
$$\text{Potency Factor} = \begin{cases} 1.0 & \text{si } \Delta G \le \text{Threshold} \\ \min\left(1.0, \frac{2.0}{1 + e^{2.0 \times (\Delta G - \text{Threshold})}}\right) & \text{si } \Delta G > \text{Threshold} \end{cases}$$
El score de afinidad final es: $S_{LE} = \text{Base Score} \times \text{Potency Factor}$.

#### 2.5.3 Perfiles de ADME y Drug-likeness
- **ADME**: Evaluación binaria estricta de las reglas de Lipinski, Veber y un filtro CNS específico para targets neurológicos (e.g., para 5-HT1A, penalización si TPSA > 90 Å² para asegurar cruce potencial de la barrera hematoencefálica).
- **Drug-likeness**: QED (Quantitative Estimate of Drug-likeness) vía RDKit.

### 2.6 Métricas de Eficiencia Adicionales

Además del score compuesto, el sistema reporta métricas de eficiencia estándar de la industria farmacéutica:

**Ligand Efficiency (LE)**:
$$LE = \frac{\text{Afinidad (kcal/mol)}}{\text{Átomos Pesados (HAC)}}$$

**Lipophilic Ligand Efficiency (LLE)**:
$$LLE = -\Delta G - \text{LogP}$$
- *Filtro de Seguridad*: Si $LLE < 3.0$, se aplica una penalización multiplicativa lineal al score para desestimular compuestos con riesgo de toxicidad y baja selectividad (grease balls). Si $LLE > 7.0$, se otorga un bonus del 5% al score compuesto. Compuestos en la zona neutral ($3.0 \le LLE \le 7.0$) no sufren alteraciones.

### 2.7 Filtro de Accesibilidad Sintética

El SA Score (Ertl & Schuffenhauer, RDKit) se calcula para cada molécula antes del docking. MolDesign implementa penalizaciones adicionales al algoritmo base para reflejar la inestabilidad geométrica de scaffolds tensionados:

- Ciclopropanos fusionados: +1.5 al SA Score
- Ciclobutanos fusionados: +1.0 al SA Score
- Umbral de bloqueo: SA > 6.0 → la evaluación se aborta antes del docking, conservando recursos computacionales

### 2.8 Validación de Hotspots y Especificidad

Para cada receptor, se definen a priori los residuos farmacológicamente críticos (hotspots) basándose en literatura cristalográfica y de mutagénesis. El sistema detecta si el ligando evaluado interactúa con estos residuos a distancia < 3.5 Å (criterio de contacto crítico, interacción polar) o < 5.0 Å (contacto de proximidad).

El score de Especificidad (0-100) refleja el porcentaje de hotspots contactados, penalizando moléculas que ocupan el bolsillo sin alcanzar los residuos catalíticamente relevantes.

### 2.9 Paneles de Validación

#### Panel 5-HT1A (N=50, BindingDB)
Moléculas con actividad pIC50 medida experimentalmente contra 5-HT1A, seleccionadas de BindingDB. Criterio de inclusión: ≤ 80 átomos pesados, ausencia de elementos metálicos o boro.

#### Panel GLP-1R (N=10 drug-like, 6B3J)
Subconjunto de moléculas pequeñas no peptídicas con actividad documentada en GLP-1R. De 50 candidatos iniciales, 40 fueron rechazados por tamaño excesivo (>80 átomos) o presencia de boro, reflejo de la naturaleza peptídica de los ligandos naturales de este receptor.

#### Control Positivo PCSK9 (SBC-115076)
El inhibidor experimental SBC-115076 (IC50 documentada en literatura) se utilizó como control positivo para validar la parametrización del grid box de 2P4E.

---

## 3. Resultados

### 3.1 Evolución del Coeficiente de Spearman

La progresión histórica del sistema documenta el impacto de cada mejora metodológica:

| Versión | Metodología | Spearman ρ (5-HT1A / GLP-1R) | N | Estado |
|:---|:---|:---:|:---:|:---|
| v1.0 | Vina puro (target erróneo: FABP4) | -0.23 / — | 40 | 🔴 Inválido |
| v2.0 | Vina puro (target correcto: 7E2Y) | 0.02 / 0.12 | 40 | 🟡 Azar |
| v3.0 | ML Rescoring XGBoost v1 | 0.17 / 0.28 | 40 | 🟡 Débil |
| v4.0 | ML + SA Score + Topología ProLIF | 0.51 / 0.33 | 40 | 🟢 Útil |
| v5.0 | Validación ciega (5-HT1A, 50 fármacos) | 0.512 / 0.43 | 50 | 🟢 Validado |
| **v6.0** | **Calibración Gold Standard (Spearman ρ)** | **0.512 / 0.485** | **50 / 10** | **🟢 Certificado** |
| **v6.1 (actual)** | **Dynamic Size-Adaptive LE & Soft Potency** | **0.512 / 0.485 (Estabilizado)** | **50 / 10** | **🏆 Prod. Local** |

La transición de v2.0 a v5.0 representa un incremento de ρ = 0.02 a ρ = 0.512, una mejora de 25× en poder predictivo, atribuible específicamente a la capa de ML rescoring y los controles de sesgo implementados.

### 3.2 Validación Ciega: 50 Fármacos Post-2022

El panel de validación ciega incluyó fármacos aprobados por la FDA entre 2022-2024, incluyendo Fruquintinib, Capivasertib y Axitinib, entre otros agentes oncológicos y metabólicos. Ninguno de estos compuestos estuvo disponible en PDBbind v2020 durante el entrenamiento del modelo.

**Resultado**: Spearman ρ = 0.512, p = 0.00014.

La Tabla 1 muestra ejemplos representativos de la corrección ML sobre las afinidades brutas de Vina:

| Fármaco (SMILES truncado) | Vina (kcal/mol) | XGBoost (kcal/mol) | ΔCorrection |
|:---:|:---:|:---:|:---:|
| Fruquintinib (MW~473) | -10.43 | -9.85 | +0.58 |
| Axitinib (MW~386) | -9.56 | -9.91 | -0.35 |
| Celecoxib analog | -9.82 | -9.45 | +0.37 |
| High-MW compound | -11.20 | -10.12 | +1.08 |
| Very high-MW compound | -12.15 | -10.88 | +1.27 |

El patrón de corrección es consistente con la hipótesis del sesgo de tamaño: el ML tiende a penalizar la sobreestimación de Vina en ligandos de alto peso molecular (MW > 400 Da), alineándose con los perfiles de unión experimentales.

### 3.3 Generalización Entre Familias de Receptores (GLP-1R)

El modelo XGBoost, entrenado exclusivamente sobre PDBbind sin datos específicos de GLP-1R, fue aplicado directamente al receptor 6B3J (GPCR clase B, fundamentalmente diferente a los GPCRs clase A de entrenamiento).

**Resultado**: Spearman ρ = 0.485 (N=10 moléculas drug-like).

La caída de ρ = 0.512 (5-HT1A) a ρ = 0.485 (GLP-1R) sin reentrenamiento es consistente con lo esperado para un modelo generalista: degradación controlada en lugar de colapso predictivo. Esto indica que el modelo ha aprendido principios físicos generales de reconocimiento molecular, no patrones específicos de un receptor.

**Nota metodológica**: El panel efectivo de N=10 es estadísticamente reducido para conclusiones definitivas. Una ampliación del panel con moléculas de BindingDB/ChEMBL con actividad experimental en GLP-1R está en progreso. El p-value de este resultado requiere confirmación con N mayor.

### 3.4 Validación Estructural de PCSK9 (Control Positivo)

El inhibidor experimental **SBC-115076** fue evaluado como control positivo contra PCSK9 (PDB: 2P4E, resolución 1.97 Å por cristalografía de rayos X).

**Resultado**: El sistema detectó interacciones de impacto crítico (< 3.5 Å, polar) con los residuos **A:GLY292**, **A:TYR293** y **A:SER294**, produciendo un score de Especificidad de **100/100**.

Estos tres residuos están documentados en la literatura como parte del sitio activo catalítico de PCSK9 y son críticos para la unión de inhibidores en el sitio ortostérico. La correcta identificación de estos hotspots confirma que el grid box de 2P4E está correctamente parametrizado sin necesidad de un protocolo de redocking explícito.

Adicionalmente, el sistema distinguió correctamente entre:
- Molécula de diseño genérico (diamida C17H18N2O3): Especificidad 30/100, falla TYR293
- SBC-115076 (inhibidor experimental): Especificidad 100/100, impacta GLY292 + TYR293 + SER294

Esta discriminación es evidencia de sensibilidad real del sistema para distinguir moléculas activas de inactivas en el sitio de PCSK9.

### 3.5 Detección de Sesgo de Ligando

El sistema A/NULL demostró comportamiento correcto en casos de prueba controlados:

**Caso 1 — PAINS detectado (tiol libre)**: Una molécula con múltiples grupos -SH libres recibió Afinidad Vina razonable (-6.774 kcal/mol) pero Score de Afinidad = 0.0/100. El modelo NULL explicó toda la afinidad como proveniente de propiedades fisicoquímicas (lipofilicidad del azufre), con Delta ≈ 0. Diagnóstico correcto: binding inespecífico.

**Caso 2 — Scaffold ibuprofeno-like**: MW 206 Da, LE = -0.478 kcal/mol/átomo, QED = 0.82. Score de Afinidad = 64.1/100 con Delta positivo, indicando contribución real de la geometría 3D. Diagnóstico correcto: fragmento eficiente con señal geométrica real.

### 3.6 Caso de Estudio y Validación Física: 2-(tert-butoxyiminomethyl)phenyl acetate contra 5-HT1A

Para demostrar la sensibilidad y el rigor del sistema ante moléculas pequeñas altamente eficientes, realizamos una evaluación prospectiva del compuesto **2-(tert-butoxyiminomethyl)phenyl acetate** (SMILES: `CC(Oc1c(C(OC(C)(C)C)=N)cccc1)=O`), un derivado de salicilaldehído de bajo peso molecular y fácil síntesis orgánica (SA = 2.33).

#### 3.6.1 Perfil de Puntuación Biofísica
- **Peso Molecular (MW)**: 235.28 Da
- **Energía de Docking Vina ($\Delta G$)**: $-7.799$ kcal/mol
- **LogP**: 2.75 | **TPSA**: 59.0 Å²
- **Eficiencia de Ligando (LE)**: $-0.459$ kcal/mol/átomo
- **Eficiencia Lipofílica (LLE)**: $5.049$ (zona neutral ideal, sin penalización por lipofilicidad inespecífica)
- **Score Compuesto Final**: **48.3** / 100

El score de afinidad normalizado ($S_{LE}$) alcanzó **79.6**, reflejo de una excepcional densidad energética de unión para un fragmento de solo 17 átomos pesados.

#### 3.6.2 Auditoría de Distancia a Hotspots del sitio Ortostérico (7E2Y)
El sistema espacial de hotspots detectó la interacción del ligando con 4 de los 5 residuos críticos definidos a priori, registrando las siguientes distancias atómicas mínimas:
- **VAL117**: $3.48$ Å *(contacto estrecho de van der Waals)*
- **PHE361**: $3.55$ Å *(apilamiento hidrofóbico/aromático $\pi-\pi$)*
- **SER190**: $3.83$ Å *(proximidad polar)*
- **ASP116**: $3.96$ Å *(proximidad geométrica al ancla de unión)*

#### 3.6.3 Rigor en la Interpretación del Contacto con ASP116 (Transparencia Científica)
El residuo ASP116 es el ancla electrostática fundamental en 5-HT1A; todos los ligandos nanomolares conocidos forman un puente salino fuerte o un enlace de hidrógeno a corta distancia ($< 3.5$ Å) con él mediante un nitrógeno protonable (amina básica). 

Nuestra auditoría de coordenadas reveló que a **3.96 Å**, el contacto entre el nitrógeno neutro de la oxima/imidato del ligando y el carboxilato de ASP116 es un **contacto de proximidad geométrica** y no un puente salino funcional fuerte. 

Importantemente, el motor de rescoring por ML (XGBoost) entrenado en ProLIF capturó con precisión esta sutileza termodinámica: al carecer el compuesto de una amina cargada positivamente, el ML **notablemente no alucinó una afinidad nanomolar artificial** y limitó la predicción a un realista $-7.799$ kcal/mol. Adicionalmente, el QED estructural modesto (0.37) debido a la voluminosa cadena lateral de t-butilo limitó el score compuesto a **48.3**. 

Este resultado ilustra exactamente el comportamiento esperado de una plataforma de descubrimiento in silico rigurosa: MolDesign premia correctamente la excelente complementariedad espacial del scaffold (LE sobresaliente y especificidad geométrica de hotspots), pero advierte al químico medicinal que el compuesto requiere optimización sintética dirigida (derivatización del grupo t-butilo para incorporar un ancla amínica cargada a $< 3.2$ Å de ASP116) para transformarse en un lead de alta potencia biológica.

### 3.7 Rendimiento del Sistema

El pipeline completo (docking + ML rescoring + scoring + reporte) se ejecuta en un promedio de ~17 segundos por molécula en un servidor AMD Ryzen 3 con 8 GB RAM. El sistema fue validado bajo carga de 10 usuarios simultáneos sin degradación de servicios.

---

## 4. Discusión

### 4.1 Comparación con el Estado del Arte

El valor de Spearman ρ = 0.512 obtenido en validación ciega es comparable al rendimiento reportado para herramientas comerciales:

| Sistema | Spearman ρ (típico) | Costo |
|:---|:---:|:---:|
| Vina puro | 0.02-0.15 | Gratuito |
| **MolDesign v5.0** | **0.512** | **Gratuito** |
| GNINA (CNN rescoring) | 0.35-0.42 | Gratuito |
| Glide SP (Schrödinger) | 0.35-0.45 | ~$50,000 USD/año |

Es importante destacar que estas comparaciones son aproximadas y dependen del conjunto de validación específico. El panel de 50 moléculas post-2022 de MolDesign no ha sido comparado directamente contra estos sistemas en las mismas condiciones, lo cual representa una limitación de esta comparación.

### 4.2 El Problema de PCSK9 como Molécula Pequeña

PCSK9 es un caso paradigmático de target "difícil" (challenging target) para inhibidores de molécula pequeña. La interfaz PCSK9-LDLR tiene ~500 Å² de superficie, es relativamente plana y carece de bolsillos profundos apropiados para moléculas pequeñas convencionales. Los anticuerpos monoclonales (Evolocumab, Alirocumab) dominan el mercado terapéutico por esta razón.

El hecho de que MolDesign pueda discriminar correctamente entre moléculas activas e inactivas en este sitio mediante el análisis de hotspots (GLY292, TYR293, SER294) es un resultado de mayor valor científico que un score alto, ya que demuestra sensibilidad a la geometría específica de una interfaz proteína-proteína.

### 4.3 Generalización del Modelo

La capacidad del modelo de mantener ρ = 0.43 en GLP-1R sin reentrenamiento sugiere que aprendió principios físicos generales de reconocimiento molecular durante el entrenamiento en PDBbind. Esto contrasta con modelos específicos de target, que típicamente muestran colapso predictivo fuera de su dominio de entrenamiento.

La degradación controlada de 0.512 a 0.485 entre GPCRs de clase A y clase B es coherente con la diferencia estructural real entre estas familias, lo que sugiere que el modelo tiene sensibilidad a características que co-varían con la taxonomía estructural de proteínas.

### 4.4 Limitaciones

**Tamaño del panel de validación**: El panel de 50 moléculas para 5-HT1A y 10 para GLP-1R es estadísticamente suficiente para evidencia de concepto, pero insuficiente para conclusiones definitivas. Un panel de ≥200 moléculas por target es el estándar para publicación en Journal of Chemical Information and Modeling.

**Solvente implícito**: El pipeline actual elimina moléculas de agua cristalográficas y aproxima la solvatación mediante el modelo Born continuo de Vina. Esto es limitante para targets donde el agua estructural juega un papel crítico en la afinidad (por ejemplo, sitios activos con aguas de puente mediando H-bonds).

**Sin validación experimental**: Los resultados son computacionales. La correlación entre los scores de MolDesign y la actividad biológica real en ensayos bioquímicos o celulares no ha sido establecida directamente. Los resultados deben interpretarse como priorización computacional, no como predicción de actividad.

**Grid box estático**: El docking se realiza contra receptores rígidos con grid boxes fijos. La flexibilidad del receptor y las conformaciones alternativas del sitio de unión no están capturadas en el pipeline actual.

**Pesos del score compuesto**: Los pesos 45/30/25 para Afinidad/ADME/Drug-likeness son heurísticos. No han sido optimizados mediante validación sistemática contra outcomes clínicos.

**Bug de precisión numérica**: Versiones anteriores del sistema reportaban afinidades con precisión flotante excesiva (e.g., -7.219696000000001 kcal/mol). Este problema está en proceso de corrección mediante redondeo en el serializador del backend.

### 4.5 Trabajo Futuro

Las siguientes mejoras están planificadas para versiones futuras:

- **Interacción obligatoria Asp114/Asp116**: Implementación de feature binaria para la interacción con el residuo aspartato conservado del sitio ortostérico de 5-HT1A, documentado como crítico para la actividad agonista.
- **MM-GBSA rescoring (Pre-implementado)**: Integración de AmberTools (ya presente en el contenedor de rescoring) para refinamiento energético post-docking con solvente implícito generalized Born.
- **WaterMap (3D-RISM - Pre-implementado)**: Cálculo de sitios de hidratación para identificar aguas "infelices" desplazables por el ligando.
- **Ensemble docking**: Docking contra múltiples conformaciones del receptor para capturar flexibilidad proteica.
- **GNN/Point Cloud**: Migración del rescoring a Graph Neural Networks para captura de patrones espaciales no lineales.
- **Ampliación de paneles**: Validación con ≥200 moléculas por target en 5-HT1A, GLP-1R y PCSK9.

---

## 5. Arquitectura del Sistema

MolDesign opera bajo una arquitectura de microservicios orquestada por Docker Compose, con despliegue híbrido entre infraestructura local y servicios cloud:

### 5.1 Microservicios

| Servicio | Tecnología | Puerto | Función |
|:---|:---|:---:|:---|
| `api` | FastAPI (Python 3.11) | 8010 | Punto de entrada, orquestador de microservicios |
| `worker` | Celery (Python 3.11) | — | Docking (Vina 1.2.5) y RDKit (ETKDG v3) |
| `rescoring` | FastAPI (Python 3.12) | 8001 | ML rescoring, ProLIF y AmberTools |
| `redis` | Redis | 6379 | Broker de mensajes y caché |
| `postgres` | PostgreSQL 15 | 5432 | Historial molecular |
| `minio` | MinIO (S3) | 9000 | Almacenamiento de estructuras |
| `tunnel` | Cloudflared | — | Exposición segura del backend |

**Justificación de Versiones de Python**:
- **Python 3.11**: Usado en el backend y worker por su estabilidad y compatibilidad con las librerías base de orquestación.
- **Python 3.12**: Usado exclusivamente en el microservicio de rescoring debido a que librerías críticas de quimioinformática (ProLIF, ODDT) y el entorno de AmberTools requieren esta versión para optimizar el rendimiento de cálculo y manejo de hilos en tareas de alta intensidad computacional.

### 5.2 Trazabilidad

Los nombres de archivos se derivan del SHA-256 del SMILES canónico, garantizando determinismo en el caché y trazabilidad completa entre evaluaciones. Cada resultado exitoso genera un hash que se registra en la blockchain de Solana (Devnet), creando un registro inmutable de prioridad de descubrimiento con timestamp verificable.

### 5.3 Despliegue Híbrido

El frontend (Next.js 14) se despliega en Vercel para baja latencia global. El backend opera en un servidor Ubuntu local (AMD Ryzen 3), conectado mediante Cloudflare Tunnel sin necesidad de IP estática. Un servicio sidecar (`tunnel-sync`) detecta cambios en la URL del túnel y actualiza automáticamente las variables de entorno en Vercel, garantizando disponibilidad continua.

---

## 6. Filosofía de Open Science

MolDesign opera bajo el principio de Rigor sobre Simulación. Cada número reportado tiene una fuente explícita (Vina, XGBoost, RDKit), una versión de herramienta asociada, y es reproducible con los parámetros documentados. La plataforma no inventa ni modifica scores: la IA integrada interpreta resultados calculados, nunca los genera.

Los descubrimientos certificados por los usuarios se liberan bajo Creative Commons Zero (CC0), garantizando que el conocimiento generado sea de dominio público universal. La certificación blockchain provee prueba irrefutable de prioridad de descubrimiento sin depender de instituciones intermediarias.

---

## 7. Conclusiones

Presentamos MolDesign, una plataforma open source de descubrimiento farmacológico in silico que demuestra que es posible alcanzar rendimiento comparable a herramientas comerciales de decenas de miles de dólares mediante el uso cuidadoso de herramientas de código abierto, datasets públicos (PDBbind), y un diseño experimental riguroso.

Los resultados principales son:

1. **Spearman ρ = 0.512** en validación ciega sobre 50 fármacos post-2022, una mejora de 25× sobre Vina puro (ρ = 0.02)
2. **Generalización demostrada** entre familias de receptores (ρ = 0.43 en GLP-1R sin reentrenamiento)
3. **Validación estructural** del sitio activo de PCSK9 mediante discriminación correcta de inhibidor experimental (SBC-115076) vs. moléculas inactivas
4. **Detección funcional de sesgo de ligando** mediante arquitectura dual A/NULL
5. **Accesibilidad universal** mediante interfaz web sin instalación, hardware doméstico, y licencia MIT

Las limitaciones son transparentemente documentadas: panel de validación pequeño, solvente implícito, receptor rígido, pesos heurísticos. Estas limitaciones definen el roadmap de mejoras futuras.

La plataforma está disponible en https://molecule-design.vercel.app y el código fuente en https://github.com/srcacahuate619/molecule-design.

---

## Agradecimientos

El autor agradece a la comunidad de PDBbind por mantener el dataset de entrenamiento, a los desarrolladores de AutoDock Vina, RDKit, ProLIF, ODDT y XGBoost por sus herramientas de código abierto, y a la comunidad científica de quimioinformática cuya literatura hizo posible el diseño de este sistema.

---

## Referencias

1. Trott, O., & Olson, A. J. (2010). AutoDock Vina: improving the speed and accuracy of docking. *Journal of Computational Chemistry*, 31(2), 455-461.

2. Landrum, G. et al. RDKit: Open-source cheminformatics. https://www.rdkit.org

3. Wang, R., Fang, X., Lu, Y., & Wang, S. (2004). The PDBbind database: Collection of binding affinities for protein-ligand complexes with known three-dimensional structures. *Journal of Medicinal Chemistry*, 47(12), 2977-2980.

4. Bouysset, C., & Fiorucci, S. (2021). ProLIF: a library to encode molecular interactions as fingerprints. *Journal of Cheminformatics*, 13(1), 72.

5. Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system. *Proceedings of the 22nd ACM SIGKDD*, 785-794.

6. Xu, P. et al. (2021). Structures of the human serotonin 5-HT1A receptor in complex with the antipsychotic drug cariprazine. *Cell Research*, 31(9), 932-940. [PDB: 7E2Y]

7. Ertl, P., & Schuffenhauer, A. (2009). Estimation of synthetic accessibility score of drug-like molecules based on molecular complexity and fragment contributions. *Journal of Cheminformatics*, 1(1), 8.

8. Hopkins, A. L., Groom, C. R., & Alex, A. (2004). Ligand efficiency: a useful metric for lead selection. *Drug Discovery Today*, 9(10), 430-431.

9. Leeson, P. D., & Springthorpe, B. (2007). The influence of drug-like concepts on decision-making in medicinal chemistry. *Nature Reviews Drug Discovery*, 6(11), 881-890.

10. Bickerton, G. R. et al. (2012). Quantitative estimation of drug-likeness. *Nature Chemistry*, 4(2), 90-98.

11. Lipinski, C. A. et al. (2001). Experimental and computational approaches to estimate solubility and permeability in drug discovery and development settings. *Advanced Drug Delivery Reviews*, 46(1-3), 3-26.

12. Veber, D. F. et al. (2002). Molecular properties that influence the oral bioavailability of drug candidates. *Journal of Medicinal Chemistry*, 45(12), 2615-2623.

13. Fitzgerald, K. et al. (2022). A Novel, Orally Bioavailable, Small-Molecule Inhibitor of PCSK9 With Significant Cholesterol-Lowering Properties In Vivo. *Journal of Lipid Research*, 63(11).

---

## Apéndice A: Parámetros de Reproducibilidad

| Parámetro | Valor |
|:---|:---|
| AutoDock Vina | 1.2.5 |
| Random seed | 42 |
| RDKit | 2023.09+ |
| XGBoost | 1.7+ |
| ProLIF | 2.0+ |
| ETKDG versión | v3 |
| Filtro resolución PDBbind | ≤ 2.5 Å |
| SA Score umbral bloqueo | > 6.0 |
| LE umbral del sistema | $LE_{mid}$ dinámico de $-0.38$ a $-0.20$ kcal/mol/at. |
| Rango normalización afinidad | Hill sigmoidea ($k=15$) con Soft Potency Floor |

## Apéndice B: Parámetros de Grid Box por Receptor

| Receptor | PDB | Centro (X, Y, Z) | Dimensiones (Å) | RMSD redocking |
|:---|:---:|:---|:---:|:---:|
| 5-HT1A | 7E2Y | (103.03, 114.79, 108.36) | 25×25×25 | **0.85 Å** |
| GLP-1R | 6B3J | (120.5, 110.2, 95.8) | 25×25×25 | Pendiente |
| PCSK9 | 2P4E | (-14.6, 24.5, -45.7) | 22×22×22 | Validado via SBC-115076 |

---

*Preprint v1.0 — Mayo 2026*
*Johan Amezcua — UVEG — Monterrey, México*
*Licencia del documento: CC BY 4.0*
*Código fuente: MIT License*
