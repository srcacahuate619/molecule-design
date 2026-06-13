# Fundamentos Científicos y Guardrails 🧬🛡️

MolDesign se rige por el principio de **Rigor sobre Simulación**. No buscamos que los números "se vean bien", sino que sean físicamente defendibles.

## 1. Guardrails Innegociables

- **No a la Alucinación**: La IA solo interpreta datos calculados; nunca genera scores ni modifica afinidades.
- **Trazabilidad Total**: Cada score tiene una fuente (Vina, XGBoost, RDKit) y una versión de herramienta asociada.
- **Reproducibilidad**: Usamos semillas fijas (`seed=42`) para garantizar que el mismo SMILES contra el mismo receptor dé siempre el mismo resultado.

## 2. Validación Química y Estabilidad

Cada molécula pasa por un riguroso proceso de validación antes de ser procesada:
- **Verificación de Valencia**: RDKit audita la química básica.
- **SA Score (Accesibilidad Sintética)**: Estimación de qué tan difícil es fabricar la molécula (1 = fácil, 10 = imposible).
- **Penalización por Tensión de Anillo**: Anillos de 3 y 4 carbonos fusionados (como en el Cubano) disparan el SA Score para reflejar la inestabilidad geométrica.

## 3. Calibración del Scoring y Eficiencia de Ligando (v6.2)

El score final de MolDesign (0-100) no es una simple media, sino un sistema calibrado para penalizar el binding inespecífico y equilibrar la biofísica de la unión.

### Eficiencia de Ligando Adaptativa al Tamaño (Size-Adaptive LE) [v6.2]
La afinidad cruda de Vina tiende a favorecer moléculas grandes simplemente por tener más átomos (efecto de superficie). Para corregir esto, usamos la **Eficiencia de Ligando (LE)** ($LE = \frac{\Delta G}{N_H}$). Sin embargo, un umbral estático de $-0.30$ castiga de forma injusta a ligandos más grandes porque la densidad de unión biofísica decae fisiológicamente con el tamaño debido a limitaciones estéricas de empaquetamiento.

En la versión **v6.2**, consolidamos el **punto medio de LE dinámico y adaptativo ($LE_{mid}$)**:
- **Moléculas pequeñas ($N_H < 15$ átomos pesados)**: $LE_{mid} = -0.38$ kcal/mol/átomo (los fragmentos deben ser altamente eficientes).
- **Moléculas grandes ($N_H > 45$ átomos pesados)**: $LE_{mid} = -0.20$ kcal/mol/átomo (compuestos maduros toleran menor densidad por acoples hidrofóbicos extendidos).
- **Moléculas medianas ($15 \le N_H \le 45$)**: Interpolación lineal continua entre $-0.38$ y $-0.20$:
  $$LE_{mid} = -0.38 + (N_H - 15) \times \frac{0.18}{30}$$

Esto estabiliza el score físico y previene que moléculas nanomolares de alto peso molecular (ej. agonistas peptídicos de GPCRs como GLP-1R) sufran penalizaciones injustas.

### Suelo de Afinidad Absoluta Suave (Soft Boundary Potency Floor) [NUEVO v6.1]
Para evitar que moléculas pequeñas pero ultra-eficientes (como fragmentos de bajo peso molecular) inflen artificialmente su score sin tener la afinidad total necesaria, aplicamos un **Potency Floor**:
- **Umbral del Target**: Cada receptor tiene un `affinity_threshold` biológico en base de datos (ej: $-7.5$ kcal/mol para GLP-1R).
- **Frontera Continua**: Si la afinidad cumple o supera el threshold ($\Delta G \le \text{Threshold}$), **no hay penalización** (factor = $1.0$).
- **Decaimiento Suave**: Si es más débil ($\Delta G > \text{Threshold}$), se aplica un decaimiento sigmoideo suave normalizado a $1.0$ en la frontera exacta del umbral para evitar saltos y caídas abruptas en la curva de puntuación:
  $$\text{Potency Factor} = \min\left(1.0, \frac{2.0}{1 + e^{2.0 \times (\Delta G - \text{Threshold})}}\right)$$
- **Filosofía**: La eficiencia (LE) es necesaria para evitar compuestos gigantes inespecíficos, pero la potencia absoluta es obligatoria para garantizar actividad farmacológica.

### Reglas Fisicoquímicas Detalladas
MolDesign evalúa el "Drug-likeness" basándose en tres estándares de la industria:
1.  **Regla de Lipinski (Oralidad)**: MW < 500 Da, LogP < 5, H-Bond Donors < 5, H-Bond Acceptors < 10.
2.  **Regla de Veber (Biodisponibilidad)**: Rotatable Bonds ≤ 10, TPSA ≤ 140 Å².
3.  **Filtro CNS (Cerebral)**: Para el receptor 5-HT1A, penalizamos TPSA > 90 Å², ya que dificulta el cruce de la barrera hematoencefálica.
4.  **Biological Specificity (Hotspots)**: Penalización por falta de contacto con residuos clave definidos experimentalmente.

### Diferenciación de Scores ADME y Drug-likeness [v6.5]
Los dos componentes del score fisicoquímico miden cosas distintas y complementarias:
- **Score ADME (peso 0.30):** Evalúa el perfil de absorción/distribución explícitamente mediante 3 factores físicos independientes: TPSA (permeabilidad oral y BBB), logP (lipofilia, distribución en tejido) y SA Score (accesibilidad sintética). Penaliza directamente los factores que afectan la viabilidad clínica.
- **Score Drug-likeness (peso 0.25):** Basado en el **QED** (Bickerton et al., *Nat. Chem.* 2012), que combina 8 propiedades moleculares ponderadas (MW, logP, HBD, HBA, PSA, RotBonds, Aromáticos, Alertas estructurales) en un único índice de 0 a 1 calibrado contra el juicio de expertos en química medicinal sobre ~1,500 moléculas aprobadas.

## 4. Especificidad Biológica y Hotspots (5.0 Å)

MolDesign v4.2 introduce el concepto de **Puntos de Interacción Críticos (Hotspots)** para diferenciar entre "unir cualquier bolsillo" y "bloquear el sitio funcional".

### Calibración del Umbral de Interacción
Tras pruebas de validación con el target CTLA-4 (3OSK), hemos ajustado el umbral de detección:
- **Umbral Antiguo (4.0 Å)**: Demasiado estricto para interacciones hidrofóbicas y de apilamiento aromático (pi-stacking).
- **Nuevo Umbral (5.0 Å)**: Optimizado para capturar el radio de influencia biológica de residuos como Metionina y Tirosina.
- **Especificidad de Cadena (v4.2)**: Para proteínas multiméricas (como el dímero de CTLA-4), los hotspots se definen con prefijo de cadena (ej: `A:MET99`). Esto evita falsos positivos visuales en la cadena opuesta del receptor.
- **Lógica de Scoring**: Cada hotspot tiene un peso relativo. Si una molécula no "toca" al menos un hotspot crítico, el score final es penalizado mediante un multiplicador de especificidad (rango 0.5x a 1.0x).

### Ingestión de Targets Oncológicos y Soporte Dual GPCR (v6.2)
En la versión **v6.2**, se amplió el catálogo de targets biológicos integrando 8 receptores críticos para la oncología del cáncer de mama (ER-alpha, CDK4, CDK6, PIK3CA, AKT1, HER2, PARP1 y Timidilato Sintasa). Sus cavidades de unión y hotspots se alinearon individualmente a partir de estructuras cristalográficas co-complejadas con ligandos clínicos.

Asimismo, se resolvió la especificidad de unión para el receptor **GLP-1R** mediante un modelado de bolsillo dual:
1. **GLP-1R ECD (6B3J)**: Centrado en el dominio extracelular. Valida la complementariedad y afinidad para análogos peptídicos y peptidomiméticos voluminosos.
2. **GLP-1R TMD (6X1A)**: Centrado en la cavidad transmembranal helicoidal profunda. Calibrado específicamente para cribar agonistas orales no peptídicos (como Danuglipron), donde el residuo **TRP33** actúa como hotspot crítico de especificidad biológica.

## 5. El "Filtro de Honestidad" y ML v4.2 (Spearman ρ=0.512)

Para evitar el **sesgo de ligando** (atribuir éxito a una molécula solo por su lipofilia), MolDesign utiliza un sistema de dos modelos:

- **Modelo A (Full)**: Entrenado con interacciones proteína-ligando (H-bonds, π-stacking, contactos hidrofóbicos).
- **Modelo NULL (Ciego)**: Entrenado SOLO con descriptores 1D/2D (MW, LogP, etc.).
- **Métrica de Desempeño**: El modelo actual v4.2 ha sido calibrado para un **Spearman ρ=0.512**, mejorando significativamente la capacidad de ranking frente a la v4.0 (ρ=0.33).
- **Interpretación del Delta**:
    - `Delta < 0`: Hay choques estéricos; la molécula "quiere" unirse por sus propiedades pero "no cabe" físicamente.

### 5.1 Calibración de Baseline por Target (Ej: GLP-1R)
Para asegurar que el motor de docking no solo corre, sino que predice, realizamos calibraciones de baseline (Vina puro) contra receptores específicos. En el caso de **GLP-1R (6B3J)**, se obtuvo un **Spearman ρ=0.43**, lo que valida que el sitio activo y los parámetros de grid box capturan la física esencial del receptor antes incluso de aplicar el rescoring de IA.

### 5.2 Framework Masivo de Validación Global Spearman (v7.0)

Para blindar la validez científica y auditable del software antes de su publicación en el preprint, implementamos el **Framework de Validación Global Spearman (v7.0)**. Este evalúa de forma ciega 250 complejos proteína-ligando post-2022.

#### Formulación Matemática del Ranking de Potencia

El motor evalúa el orden relativo de predicción contra la afinidad experimental del compuesto utilizando la correlación de rangos de Spearman ($\rho$):

$$\rho = 1 - \frac{6 \sum_{i=1}^n d_i^2}{n(n^2 - 1)}$$

Donde:
*   $d_i = \text{rg}(X_i) - \text{rg}(Y_i)$ es la diferencia entre los rangos de la afinidad molecular estimada por la IA ($X_i$) y el valor experimental de pValue ($Y_i$).
*   $n = 50$ compuestos evaluados por cada diana farmacológica.
*   El $p$-value se calcula mediante una distribución $t$ de Student de dos colas con $n-2$ grados de libertad para certificar significancia estadística ($p < 0.05$).

#### Error Absoluto Medio (MAE)

Para medir la desviación absoluta en unidades de afinidad logarítmica (pValue), calculamos el MAE:

$$\text{MAE} = \frac{1}{n} \sum_{i=1}^n \left| pK_i^{\text{exp}} - pK_i^{\text{pred}} \right|$$

Donde $pK_i = -\log_{10}(\text{Afinidad en Molar})$. Un MAE $< 1.5$ unidades logarítmicas se define como el umbral de éxito biofísico.

#### Protocolo de Reproducibilidad Estricta

Para garantizar la reproducibilidad matemática e industrial de cada pose y docking:
1.  **Semilla Determinista**: Semilla aleatoria estricta `--seed 42` para AutoDock Vina en cada corrida.
2.  **Exhaustividad Constante**: `--exhaustiveness 8` y `--num_modes 9` fijados en la API para asegurar exploración exhaustiva del espacio conformacional tridimensional.
3.  **Aislamiento Térmico**: Concurrencia restringida a 1 hilo de Celery worker, asegurando la reproducibilidad libre de ruidos por fluctuaciones de CPU.


### 5.3 Prevención de Fuga de Datos (Data Leakage) en Rescoring
Para garantizar que el modelo aprenda auténtica física estructural y no tome "atajos matemáticos", la arquitectura de XGBoost en MolDesign aísla estrictamente sus descriptores:
- **Exclusión de Puntuación Vina**: La afinidad termodinámica calculada por Vina (`FEATURE_GROUP_B`) está estrictamente censurada de los inputs del modelo XGBoost.
- **Razón Científica**: Si se incluye, el modelo sufre de *Data Leakage*. Al ver un score de Vina de `0.0` (debido a colisiones severas o penalizaciones por tensión de anillo), el modelo de ML simplemente aprenderá a predecir `0.0` ignorando las características 3D (contactos H-bond, pi-stacking) que debe analizar.
- **Física Pura**: Al censurar a Vina, obligamos al árbol de decisión a comprender por sí mismo la topología del bolsillo mediante los vectores de ProLIF y RDKit.

## 5. Física de la Tensión de Anillo y SA Score

El **SA Score (Synthetic Accessibility)** se calcula mediante un algoritmo de fragmentación de RDKit (Ertl & Schuffenhauer), pero en MolDesign v4 lo hemos endurecido:

### Penalización de Scaffolds Tensionados
La química computacional a veces acepta estructuras que son imposibles de sintetizar debido a la tensión angular. 
- **Ciclopropanos/Ciclobutanos**: Añadimos una penalización aditiva al SA Score (+1.5 y +1.0 respectivamente).
- **Por qué importa**: En el caso del **Cubano**, la tensión de los ángulos de 90° hace que la molécula sea un "resorte" químico. Aunque Vina le dé buen score, su inestabilidad la hace inviable como fármaco. MolDesign bloquea cualquier molécula con SA > 6.0 antes de gastar recursos en docking.

## 6. Rigor en la Comunicación Visual (3D Viewer)

La ciencia no solo se calcula, se comunica. El visor 3D de MolDesign integra capas de datos críticos para la validación visual:
- **Mapas de Carga Electrostática**: Coloreado automático de residuos (Rojo: Ácidos, Azul: Básicos) para validar la complementariedad de carga con el ligando.
- **Interacciones en Tiempo Real**: Visualización de puentes de hidrógeno (H-bonds) mediante cilindros dinámicos basados en un umbrales de distancia física (<3.5Å).
- **Detección Automática de Bolsillo**: Resaltado de residuos a <5Å de la pose de docking para facilitar el análisis del sitio activo sin necesidad de selección manual.

## 7. El Dilema del Agua (Solvente Implícito vs Explícito)

En el pipeline actual de MolDesign v4, el agua se trata mediante un modelo de **Solvente Implícito**:

### Estado Actual
- **Eliminación de Aguas**: Durante la preparación del receptor (`preparer.py`), eliminamos todos los registros `HOH`, `WAT` y `DOD`. Esto es una práctica estándar en docking rápido para evitar que aguas desordenadas en el cristal bloqueen artificialmente el sitio de unión.
- **Aproximación de Born Continua**: AutoDock Vina compensa la falta de agua explícita mediante términos de desolvatación en su función de puntuación, asumiendo que el agua es un medio continuo.

### Limitaciones y Roadmap
Somos conscientes de que el agua "atrapada" en el sitio activo puede ser clave para la afinidad (puentes de hidrógeno mediados por agua).
- **Fase 5/6 (Planned)**: Integración de **Hydrated Docking** (usando Vina-Hydrated o WIDD), permitiendo que ciertas moléculas de agua "cruciales" permanezcan en el receptor o sean desplazadas por el ligando, calculando el costo entrópico asociado.

## 8. Nivel 2: Redes Neuronales de Grafos (GNN - RTMScore) [v6.3]

En la actualización **v6.3**, MolDesign AI integra oficialmente el **Nivel 2 de la Cascada de Rescoring** basado en la arquitectura GNN **RTMScore** (Residue-Atom Graph Transformer Module). Este nivel supera las limitaciones estadísticas de la puntuación empírica discreta y tabular de Vina/XGBoost, permitiendo evaluar la complementariedad geométrica y el campo de fuerzas en una dimensión continua espacial.

### 8.1 Representación de Grafos Bipartitos
El complejo proteína-ligando se modela de forma determinista como un par de grafos complementarios:
1.  **Grafo del Receptor ($G_p$):** Representado a nivel de residuos para eficiencia computacional. Cada nodo es un residuo (con características físicas como tipo, volumen estérico, y ángulos diedros $\phi$, $\psi$, $\omega$, $\chi_1$).
2.  **Grafo del Ligando ($G_l$):** Representado a nivel atómico para capturar la precisión química completa. Los nodos representan átomos (tipo, carga formal, hibridación, aromaticidad) y las aristas representan enlaces covalentes (tipo de enlace, conjugación, pertenencia a anillos).

### 8.2 Mecanismo de Graph Transformer
La red utiliza capas de **Graph Transformer con Auto-Atención Multicabezal** para actualizar las representaciones de los nodos basándose en su entorno 3D espacial y las distancias físicas entre el bolsillo de unión y los átomos del ligando:
- La información geométrica del ligando se propaga hacia el bolsillo.
- La auto-atención aprende qué interacciones no covalentes (ej. puentes de hidrógeno específicos, apilamientos aromáticos, contactos hidrofóbicos) tienen la mayor relevancia termodinámica.

### 8.3 Predicción de Densidad de Distancias por GMM
A diferencia de otros modelos clásicos de predicción directa de energía (que sufren de alta variabilidad y sobrefajado), RTMScore calcula la probabilidad de ajuste prediciendo los parámetros de un **Modelo de Mezclas Gaussianas (GMM)**:
- **Salida del Modelo:** Para cada par átomo-residuo en el espacio tridimensional, la red predice la mezcla de gaussianas ($\pi, \sigma, \mu$) que describe las distancias óptimas de contacto.
- **Función de Probabilidad:** Se evalúa la densidad de probabilidad de la distancia euclidiana real observada en la pose de docking contra el perfil predicho:
  $$\text{Score}_{\text{GNN}} = \sum_{i \in \text{lig}} \sum_{j \in \text{prot}} \text{GMM}(d_{ij} \mid \pi_{ij}, \sigma_{ij}, \mu_{ij})$$
- **Rigor de Forma:** Si la pose contiene choques estéricos o se encuentra desplazada de la zona óptima de unión, la densidad de probabilidad cae a valores infinitesimales (cercanos a $0.0$), penalizando radicalmente los falsos positivos conformacionales.

### 8.4 Resolución del Mismatch de Coordenadas (MDAnalysis Merge)
Para garantizar la integridad y exactitud de la selección tridimensional en el backend, se implementó una estrategia robusta basada en **`MDAnalysis.Merge`**:
- Las búsquedas de selección de átomos inter-universo (ej. buscar átomos en el universo del receptor cercanos al universo del ligando) tienden a fallar en MDAnalysis debido a confusiones con los índices locales de átomos.
- MolDesign AI combina dinámicamente ambos grupos de átomos en un único universo virtual unificado mediante `mda.Merge(u_prot.atoms, u_lig.atoms)`.
- Se aplica el operador de distancia de bolsillo `byres (around 10.0 group mylig)` sobre el universo combinado y luego se extrae la subselección exclusivamente del receptor. Esto elimina falsas lecturas y garantiza que la GNN trabaje con los residuos correctos en contacto real.
- El parser cuenta adicionalmente con un flujo de carga tolerante a formatos mixtos (PDB/PDBQT) que extrae las coordenadas 3D limpias incluso si el ligando posee problemas de valencia o formalización de cargas.

---

## 9. Nivel 3: Motores Peptídicos (DiffPepDock / ColabFold) [v6.4]

En la actualización **v6.4**, se integra la capacidad de predecir el acoplamiento y plegado de macromoléculas lineales y cíclicas (péptidos). Cuando una molécula supera los límites estándar de docking para moléculas pequeñas (peso molecular $> 1000$ Da, enlaces rotables $> 32$, o $\ge 3$ enlaces amida consecutivos), el pipeline la desvía automáticamente a la cascada de Nivel 3 en lugar de utilizar AutoDock Vina, debido a que el espacio conformacional de un péptido flexible es demasiado grande para los algoritmos estocásticos clásicos.

### 9.1 Motores de Docking Peptídico
1.  **DiffPepDock (Inferencia Rápida por Difusión):** Un modelo de aprendizaje profundo generativo que trata el docking como un proceso de difusión inversa en el grupo SE(3) (rotaciones y traslaciones) y en el espacio de de ángulos torsionales del péptido. Permite obtener resultados en menos de 60 segundos.
2.  **ColabFold (Co-plegado por Co-evolución):** Utiliza la arquitectura de AlphaFold-Multimer optimizada para predecir la estructura tridimensional del complejo receptor-péptido completo de forma asíncrona (con un tiempo de cómputo de 5 a 15 minutos).

### 9.2 Sesgo del Sitio Activo (Active-Site Guided Soft Prior)
DiffPepDock por defecto realiza una búsqueda ciega (*blind docking*). Para enfocar la búsqueda conformacional en la cavidad terapéutica activa (ej: en GPCRs como 5-HT1A o GLP-1R):
- El backend inyecta los parámetros de `grid_center` y `grid_size` como un prior bayesiano gaussiano de traslación en el paso inicial de difusión ($t=1$).
- El sesgo se calibra mediante la variable `diffpepdock_prior_weight` (por defecto $0.7$). Un valor $< 1.0$ actúa como una restricción suave (*soft constraint*), concentrando la probabilidad de búsqueda en el bolsillo pero permitiendo que el péptido explore conformaciones alostéricas adyacentes si hay fuerzas electrostáticas favorables.

### 9.3 Capa de Refinamiento Estructural con Restricciones (Amber/OpenMM & Fallback UFF)
Los modelos difusivos como DiffPepDock son excelentes localizando el sitio de unión global, pero suelen generar poses con colisiones atómicas locales (*steric clashes*). Para solventar esto, implementamos una capa de minimización energética con restricciones:
- **Amber/OpenMM:** Utiliza el campo de fuerzas **AMBER14SB** con solvente implícito GB/SA (OBC2) para optimizar la geometría termodinámica. Para evitar que la proteína se desnaturalice o deforme artificialmente, se aplican **restricciones posicionales armónicas** (constante de fuerza $k = 50.0\text{ kcal/mol/\AA}^2$) en los átomos del esqueleto (*backbone*: `N`, `CA`, `C`, `O`) del receptor, permitiendo flexibilidad total solo en las cadenas laterales del bolsillo y en el péptido.
- **RDKit UFF Fallback:** Si OpenMM no está instalado en el entorno, el sistema activa automáticamente un fallback de optimización local mediante el campo de fuerzas universal (**UFF**) en RDKit, fijando rígidamente todos los átomos del receptor (`AddFixedPoint`) para aliviar colisiones estéricas de forma segura y veloz.

---

## 10. Nivel 4: Docking Cuántico de Metales (xtb + AD4) [v6.4]

La mayoría de los motores de docking (incluyendo AutoDock Vina) carecen de parámetros físicos para metales de transición (como `Fe`, `Zn`, `Cu`, `Mn`, etc.), provocando fallos al evaluar metaloenzimas o compuestos de coordinación.

### 10.1 Cálculo de Cargas Semiempírico (xtb)
Cuando se detecta un metal en el ligando o en el bolsillo del receptor:
- El pipeline ejecuta un cálculo de estructura electrónica rápido mediante la herramienta cuántica semiempírica de enlace fuerte **xtb** (GFN2-xTB).
- Esto genera un mapa preciso de cargas parciales y polarización electrónica en la vecindad del centro de coordinación metálico.

### 10.2 Docking en AutoDock 4 (AD4)
- El receptor y el ligando parametrizados con las cargas cuánticas de `xtb` se enrutan automáticamente a **AutoDock 4** en lugar de Vina.
- AD4 cuenta con soporte explícito y calibración para geometrías de coordinación de metales de transición, garantizando precisión biofísica en metaloproteínas.
