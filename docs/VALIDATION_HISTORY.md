## 1. Auditoría Histórica de Abril 2026 (El "Gran Reset")
Durante la fase inicial del MVP, se realizó una auditoría sistemática que reveló hallazgos críticos que redefinieron el proyecto:

- **Hallazgo 1 (Crítico)**: Se descubrió que el receptor original (PDB 3RZY) no era 5-HT1A, sino **FABP4** (una proteína adiposa). Esto explicaba por qué las afinidades eran absurdamente bajas (-1.0 kcal/mol). Se migró a **7E2Y**.
- **Hallazgo 2 (Crítico)**: La normalización de afinidad estaba desacoplada; los scores daban 0 para casi todo. Se recalibró el rango a [-10.0, -4.0] kcal/mol.
- **Hallazgo 3 (Importante)**: Ausencia de validación de redocking. Se implementó un protocolo que hoy garantiza un RMSD < 1.0Å para el ligando endógeno.
- **Hallazgo 7 (Arquitectura)**: Integración del score **QED** (Quantitative Estimate of Drug-likeness) para complementar las reglas de Lipinski.
- **Hallazgo 11 (Científico)**: Descubrimiento de que Vina puro tiene un Spearman ρ ≈ 0.02 contra paneles diversos, lo que motivó la creación del **ML Rescoring**.

## 2. Validación del Receptor y Setup de Docking (7E2Y)

Tras el cambio de target, se validó el sitio activo de la serotonina (5-HT) en la cadena R del complejo 7E2Y-Gi.

### Especificaciones del Target
- **Proteína**: Serotonin 1A receptor (5-HT1A).
- **PDB ID**: 7E2Y.
- **Resolución**: 3.0 Å (Cryo-EM).
- **Sitio de Unión**: Definido por el ligando co-cristalizado (Serotonina).

### Parámetros de la Grid Box
Para garantizar la reproducibilidad, el grid box está centrado en el ortosteric binding site:
- **Centro (X, Y, Z)**: (103.03, 114.79, 108.36).
- **Dimensiones (Å)**: 25.0 × 25.0 × 25.0.
- **Software**: AutoDock Vina 1.2.5.
- **Validación de Redocking**: El ligando endógeno fue redockeado con un **RMSD de 0.85 Å**, superando el estándar industrial (RMSD < 2.0 Å).

## 3. Evolución del Coeficiente de Spearman (ρ)

El panel de calibración consta de 40 moléculas de BindingDB con actividades conocidas (pIC50). La métrica primaria es el coeficiente de Spearman, que mide la capacidad del sistema para ordenar correctamente las moléculas por potencia.

| Versión | Metodología | Spearman ρ | Estado |
| :--- | :--- | :--- | :--- |
| **v1.0** | Vina puro (Target erróneo FABP4) | -0.23 | 🔴 Fallido |
| **v2.0** | Vina puro (Target 7E2Y Correcto) | 0.02 | 🟡 Débil |
| **v3.0** | ML Rescoring (XGBoost v1) | 0.17 | 🟡 En mejora |
| **v4.0 (Actual)** | **ML + Filtro SA + Topología ProLIF** | **En proceso...** | 🔄 Corriendo |

## 4. El Fracaso del Docking Puro y el Nacimiento del ML

### El "Punto de Quiebre" (Abril 2026)
Tras corregir el receptor a 7E2Y, esperábamos que el sistema fuera capaz de distinguir entre moléculas potentes e inactivas. Sin embargo, el Spearman de **0.02** nos dio una bofetada de realidad: el docking puro (Vina) es excelente para predecir la *geometría* del encaje, pero muy pobre para predecir la *afinidad* en sets de moléculas diversas.

### ¿Por qué falló Vina?
- **Función de Puntuación Genérica**: Vina usa un potencial empírico que no captura sutilezas como los efectos de solvatación o la entropía de forma precisa.
- **Inversión de Ranking**: Detectamos que moléculas muy grandes puntuaban mejor simplemente por "llenar el hueco", aunque sus interacciones químicas fueran pobres.

### El "Por Qué" del ML
Implementamos Machine Learning para inyectar "experiencia" al sistema. Al entrenar con **PDBbind** (5,000 complejos con afinidad experimental medida), el modelo XGBoost aprendió qué patrones de contacto (ej. un puente de hidrógeno con el residuo Asp116 del 5-HT1A) son determinantes para la actividad.

### El "Cómo" y el "Cuándo"
- **Cuándo**: Entre el 4 y el 6 de abril de 2026, se rediseñó el pipeline para incluir el microservicio de rescoring.
- **Cómo**: Se integró **ProLIF** para la extracción de huellas de interacción y se entrenaron dos modelos (A y NULL) para detectar el sesgo de ligando, permitiendo que el sistema sea honesto sobre si una molécula es buena por su diseño o por azar.

## 3. Calibración PDBbind
El modelo de rescoring se entrena sobre el **PDBbind Refined Set** (~5,000 complejos). 
- **Cross-validation**: Spearman 0.601 ± 0.04.
- **Holdout Set**: Spearman 0.527.

## 4. Auditoría de Precisión Técnica
Se realizan auditorías periódicas de consistencia numérica:
- **Consistencia PDBQT-SDF**: < 1.0% de error en extracción de coordenadas.
- **Determinismo**: 0% de desviación entre ejecuciones idénticas (Seed 42).
