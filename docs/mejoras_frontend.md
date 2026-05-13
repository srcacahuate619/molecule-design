# Mejoras del Frontend v4.0 — Transparencia y Dinamismo Científico

Este documento detalla las mejoras planificadas e implementadas para elevar la calidad científica y la interactividad del frontend de MolDesign.

## 1. Módulo de Insight Molecular (Dinámico) 🧠
En lugar de mostrar solo números, el sistema proporcionará consejos químicos basados en los resultados específicos de la molécula.

### Lógica Reactiva:
- **Alerta "Grease Ball"**: Si `logP > 5` y `afinidad` es alta.
  - *Mensaje*: "Afinidad prometedora pero lipofilicidad excesiva. Riesgo de baja solubilidad y toxicidad inespecífica."
- **Alerta de Tensión de Anillo**: Si `SA Score > 6.0`.
  - *Mensaje*: "Dificultad sintética crítica detectada. Los anillos tensionados pueden comprometer la viabilidad del scaffold."
- **Insight de Consistencia**: Comparación Vina vs ML v4.0.
  - *Mensaje*: "Señal biológica validada por modelo ML (ρ=0.33)."

## 2. Refuerzo de Reproducibilidad (Transparencia) 📉
Actualización del panel de parámetros técnicos para incluir el linaje del modelo de re-scoring.

### Elementos:
- **ML Model Version**: Identificación clara de `v4.0 (Spearman 0.33)`.
- **Target Context**: Confirmación del receptor (5-HT1A) y el PDB de referencia (7E2Y).

## 3. Disclaimer de Método v4.0 ℹ️
Evolución de las advertencias estáticas a un formato que refleje las capacidades actuales.

- Eliminación de placeholders "en construcción".
- Clarificación sobre la IA como herramienta de interpretación y no de generación de datos primarios.

## 4. Visualización de "Señal Científica" 🚦
Implementación de un indicador visual de confianza basado en la convergencia de los scores de Vina y el re-scoring ML.
- **Verde**: Vina y ML coinciden en alta afinidad.
- **Amarillo**: ML rescata una molécula que Vina subestima.
- **Rojo**: Desajuste significativo o propiedades ADME críticas.

---
*Fecha de inicio: 2026-05-13*
*Estado: En implementación*
