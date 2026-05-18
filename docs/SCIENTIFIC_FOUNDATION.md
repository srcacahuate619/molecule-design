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

## 3. Calibración del Scoring y Eficiencia de Ligando (v6.1)

El score final de MolDesign (0-100) no es una simple media, sino un sistema calibrado para penalizar el binding inespecífico y equilibrar la biofísica de la unión.

### Eficiencia de Ligando Adaptativa al Tamaño (Size-Adaptive LE) [NUEVO v6.1]
La afinidad cruda de Vina tiende a favorecer moléculas grandes simplemente por tener más átomos (efecto de superficie). Para corregir esto, usamos la **Eficiencia de Ligando (LE)** ($LE = \frac{\Delta G}{N_H}$). Sin embargo, un umbral estático de $-0.30$ castiga de forma injusta a ligandos más grandes porque la densidad de unión biofísica decae fisiológicamente con el tamaño debido a limitaciones estéricas de empaquetamiento.

En la versión **v6.1**, implementamos un **punto medio de LE dinámico y adaptativo ($LE_{mid}$)**:
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

## 4. Especificidad Biológica y Hotspots (5.0 Å)

MolDesign v4.2 introduce el concepto de **Puntos de Interacción Críticos (Hotspots)** para diferenciar entre "unir cualquier bolsillo" y "bloquear el sitio funcional".

### Calibración del Umbral de Interacción
Tras pruebas de validación con el target CTLA-4 (3OSK), hemos ajustado el umbral de detección:
- **Umbral Antiguo (4.0 Å)**: Demasiado estricto para interacciones hidrofóbicas y de apilamiento aromático (pi-stacking).
- **Nuevo Umbral (5.0 Å)**: Optimizado para capturar el radio de influencia biológica de residuos como Metionina y Tirosina.
- **Especificidad de Cadena (v4.2)**: Para proteínas multiméricas (como el dímero de CTLA-4), los hotspots se definen con prefijo de cadena (ej: `A:MET99`). Esto evita falsos positivos visuales en la cadena opuesta del receptor.
- **Lógica de Scoring**: Cada hotspot tiene un peso relativo. Si una molécula no "toca" al menos un hotspot crítico, el score final es penalizado mediante un multiplicador de especificidad (rango 0.5x a 1.0x).

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
