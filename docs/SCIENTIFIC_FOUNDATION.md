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

## 3. Calibración del Scoring y Eficiencia de Ligando

El score final de MolDesign (0-100) no es una simple media, sino un sistema calibrado para penalizar el binding inespecífico.

### Ligand Efficiency (LE)
La afinidad cruda de Vina tiende a favorecer moléculas grandes simplemente por tener más átomos (efecto de superficie). Para corregir esto, usamos la **Eficiencia de Ligando (LE)**:
- **Fórmula**: `LE = Afinidad (kcal/mol) / Número de Átomos Pesados (HAC)`
- **Umbral Industrial**: -0.30 kcal/mol/at.
- **Lógica**: Una molécula con -10 kcal/mol y 50 átomos (LE = -0.20) es menos prometedora que una con -8 kcal/mol y 20 átomos (LE = -0.40). La segunda aprovecha mejor cada interacción atómica.

### Reglas Fisicoquímicas Detalladas
MolDesign evalúa el "Drug-likeness" basándose en tres estándares de la industria:
1.  **Regla de Lipinski (Oralidad)**: MW < 500 Da, LogP < 5, H-Bond Donors < 5, H-Bond Acceptors < 10.
2.  **Regla de Veber (Biodisponibilidad)**: Rotatable Bonds ≤ 10, TPSA ≤ 140 Å².
3.  **Filtro CNS (Cerebral)**: Para el receptor 5-HT1A, penalizamos TPSA > 90 Å², ya que dificulta el cruce de la barrera hematoencefálica.

## 4. El "Filtro de Honestidad" (Delta 3D y Control NULL)

Para evitar el **sesgo de ligando** (atribuir éxito a una molécula solo por su lipofilia), MolDesign utiliza un sistema de dos modelos:

- **Modelo A (Full)**: Entrenado con interacciones proteína-ligando (H-bonds, π-stacking, contactos hidrofóbicos).
- **Modelo NULL (Ciego)**: Entrenado SOLO con descriptores 1D/2D (MW, LogP, etc.).
- **Interpretación del Delta**:
    - `Delta (A - NULL) > 0.5`: La geometría 3D aporta afinidad real.
    - `Delta ≈ 0`: La molécula se une por "fuerza bruta" fisicoquímica, no por diseño.
    - `Delta < 0`: Hay choques estéricos; la molécula "quiere" unirse por sus propiedades pero "no cabe" físicamente.

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
