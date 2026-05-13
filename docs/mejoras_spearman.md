# Estrategia de Optimización: Asalto al Spearman 0.50 📈🔬

Este documento detalla las líneas de investigación científica para elevar la correlación de Spearman ($\rho$) del actual **0.33** al objetivo de **0.50+** (State-of-the-Art).

---

## 1. Refinamiento por Mecánica Molecular (MM-GBSA) 🧪🌊
**Problema**: Vina estima la afinidad mediante funciones de puntuación empíricas, pero ignora los efectos de solvatación (el agua).
**Propuesta**: Implementar un paso de re-scoring usando **AmberTools (MM-PBSA/GBSA)**.
- **Mecánica**: Calcular la energía libre de unión considerando el solvente implícito.
- **Impacto esperado**: Incremento significativo en la precisión al modelar el efecto hidrofóbico, crítico en GPCRs.
- **Estado**: AmberTools ya está instalado en el contenedor `rescoring`.

## 2. Lógica de Interacción Crítica (Asp114) 🎯🔑
**Problema**: El modelo actual trata todos los contactos ProLIF con pesos similares. En el 5-HT1A, ciertas interacciones son obligatorias para la actividad.
**Propuesta**: Inyectar "Conocimiento de Dominio" en el modelo ML.
- **Mecánica**: Crear una feature binaria `has_asp114_interaction`. Penalizar severamente a las moléculas que no formen el puente salino/H-bond con el residuo Asp114 (3.32).
- **Impacto esperado**: Eliminación de falsos positivos que ocupan el bolsillo pero carecen de eficacia biológica.

## 3. Análisis de Sitios de Hidratación (WaterMap Logic) 💧📦
**Problema**: El agua en el bolsillo del receptor puede ser un puente (ayuda) o un obstáculo (estorba).
**Propuesta**: Pre-calcular mapas de densidad de agua (usando **3D-RISM**).
- **Mecánica**: Identificar aguas "infelices" (alta energía) que el ligando debería desplazar para ganar afinidad.
- **Impacto esperado**: Mayor realismo en el diseño de grupos químicos que reemplazan moléculas de agua estratégicas.

## 4. Ensemble Docking (Receptor Flexible) 🕺🧬
**Problema**: Usar una sola estructura (7E2Y) ignora que la proteína es dinámica.
**Propuesta**: Dockear contra un "Ensemble" de conformaciones.
- **Mecánica**: Usar 3-5 estructuras (Criomicroscopía + Dinámica Molecular + AlphaFold).
- **Impacto esperado**: Capturar "binders" que hoy fallan por choques estéricos menores con cadenas laterales que en realidad son flexibles.

## 5. Modelos de Grafos (v5 - Deep Learning) 🤖🕸️
**Problema**: XGBoost solo ve conteos. No ve la topología 3D del complejo.
**Propuesta**: Migrar a una **Graph Neural Network (GNN)** o un modelo basado en **Point Clouds** (ej. Gnina).
- **Mecánica**: Representar el bolsillo y el ligando como un grafo de interacciones.
- **Impacto esperado**: Captura de patrones espaciales complejos no lineales.

---
*Documento de trabajo para la Fase 4.1 de MolDesign.*
