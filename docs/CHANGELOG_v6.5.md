# MolDesign AI v6.5 - Interfaz Dual e Interactividad Profunda

**Fecha de Liberación:** Junio 2026

## Resumen de la Actualización
La versión 6.5 de MolDesign da un salto generacional en la capa de presentación (Frontend) introduciendo una separación profunda en la experiencia de usuario (UX/UI) mediante la creación de dos modos distintos y altamente personalizados: **Modo Pro** y **Modo Academy**. Esta división permite satisfacer tanto las necesidades de investigadores avanzados que requieren herramientas analíticas densas, como las de estudiantes y académicos que necesitan un entorno más pedagógico y amigable.

## ¿Qué hicimos y por qué?

### 1. Interfaz Dual: Pro vs Academy
Antes, la información científica se presentaba de manera genérica para todos los usuarios. Con esta versión, la interfaz se adapta al contexto del usuario:
- **Modo Pro:** Utiliza descripciones precisas, técnicas y directas, enfocadas en la eficiencia para el investigador de laboratorio o ingeniero de quimioinformática. 
- **Modo Academy (Edu):** Reemplaza la jerga altamente condensada con párrafos explicativos completos, lenguaje accesible ("Ciencia para todos") y descripciones pedagógicas sobre cómo funciona cada capa de la plataforma (desde RDKit hasta las redes neuronales GNN).

**¿Por qué?** Para democratizar el conocimiento sin sacrificar la eficiencia del usuario experto. El diseño inmersivo fomenta el aprendizaje en el entorno universitario, mientras que el diseño técnico mantiene el rigor industrial.

### 2. Modales Interactivos en Cascada
Se transformó gran parte del texto estático y sobrecargado (especialmente en los diagramas de flujo y pilares arquitectónicos) en tarjetas y botones dinámicos.
- **Cerebro Orquestador:** Las ramas de ejecución (Fragmentos, Drug-Like, Péptidos, Metales) ya no son simples textos diminutos. Ahora son botones que despliegan ventanas emergentes enfocadas que explican en detalle el *Engine* seleccionado.
- **Flujo de Ejecución (Pipeline):** Los 9 pasos del pipeline (tanto en el *Home* como en la vista del *Simulador de Evaluación*) se han vuelto componentes interactivos. En el *Modo Pro*, muestran resúmenes técnicos; en el *Modo Academy*, despliegan ventanas de lectura inmersiva con explicaciones didácticas.
- **Stack Tecnológico y Pilares Científicos:** Todo el stack (AutoDock Vina, XGBoost, OpenMM, etc.) se puede inspeccionar individualmente para comprender su rol específico dentro del rescoring en cascada de MolDesign (Nivel 1 al 4).

**¿Por qué?** Las interfaces científicas suelen sufrir de sobrecarga cognitiva. Al esconder los detalles detrás de elementos interactivos (ventanas modales emergentes desenfocadas), mantenemos una interfaz ultra-limpia (estética minimalista) que permite profundizar ("Drill-Down") únicamente cuando el investigador o estudiante lo desea, mejorando radicalmente la legibilidad.

### 3. Ajuste Estético y Eliminación del Efecto "Gamer"
Se depuró el exceso de brillos, "efectos neón" e iluminaciones excesivas en botones y modales que hacían parecer a la plataforma un videojuego (introducidos en v6.2.1).
- **¿Por qué?** Para proyectar mayor seriedad, elegancia y un tono verdaderamente científico o académico, adoptando colores más sobrios (índigos profundos, superficies oscuras) y reservando el "glow" exclusivamente para elementos de marca (como el logo principal).

---
*Con esta actualización v6.5, MolDesign no solo potencia su motor de orquestación (completado en v6.4), sino que lo vuelve accesible y auditable visualmente para toda la comunidad científica e investigativa.*
