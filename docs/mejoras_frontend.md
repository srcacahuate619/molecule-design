# Mejoras del Frontend v4.0 — Transparencia y Dinamismo Científico

Este documento detalla las mejoras implementadas para elevar la calidad científica, la interactividad y la lógica de negocio del frontend de MolDesign.

## 1. Módulo de Insight Molecular (Mentor Químico) 🧠 [IMPLEMENTADO]
Se ha integrado un componente reactivo (`MolecularInsight.tsx`) que analiza los resultados en tiempo real y ofrece consejos específicos.

### Lógica de Análisis:
- **Riesgo de 'Grease Ball'**: Detecta alta afinidad pero lipofilicidad excesiva (`logP > 5`). Sugiere añadir grupos polares.
- **Dificultad Sintética (SA Score)**: Alerta si el score es superior a 6.0, desglosando los motivos estructurales (e.g., anillos tensionados, puentes).
- **Validación Científica v4.0**: Solo se otorga si la molécula tiene un `total_score > 35`, confirmando la señal biológica mediante descriptores de interacción (ProLIF).
- **Aprovechamiento de Fragmento/LE**: Analiza la Eficiencia de Ligando. Si el score es bajo pero la eficiencia es alta, lo marca como un punto de partida para optimización (Fragment-based design).
- **Alerta de Tamaño (Fragment Warning)**: Si la molécula tiene <15 átomos pesados, el sistema advierte que, a pesar de scores altos (como en Serotonina), se requiere crecimiento estructural para ser un inhibidor competitivo.
- **Reporte de Hotspots**: Desglose dinámico de los residuos críticos impactados exitosamente por el ligando.

## 2. Refuerzo de Transparencia (Línea de Vida v4.0) 📉 [IMPLEMENTADO]
Se han actualizado los módulos de metadatos para reflejar el estado actual del proyecto:
- **ML Model Version**: Identificación explícita de `v4.2 (Spearman ρ=0.512)`.
- **Reproducibilidad**: Inyección de la versión del modelo en el panel de metadatos para auditoría científica.
- **Jerarquía Visual de Hotspots**: Nueva leyenda 3D que clasifica los impactos en: Crítico (Verde Neón), Proximidad (Verde Pálido) y Miss (Magenta).

## 3. Pipeline End-to-End con Solana ⛓️🛡️ [IMPLEMENTADO]
El flujo visual del pipeline ahora refleja la realidad del sistema completo:
`validación (RDKit) → propiedades (SA) → conformer 3D → docking (Vina) → rescoring (ML v4.2) → hotspots → interpretación IA → certificación On-Chain (Solana)`

## 4. Modelo Freemium (Límites Anónimos) 🌐🛑 [IMPLEMENTADO]
Para proteger los recursos computacionales y fomentar el registro, se ha implementado un sistema de límites basado en IP:
- **Usuarios Anónimos**: Límite de 2 evaluaciones moleculares por IP.
- **Bloqueo Inteligente**: Al alcanzar la 3ra solicitud, el sistema devuelve un error 403 y el frontend muestra una invitación clara al registro.

## 5. Infraestructura de IA Local (Local MedGemma) 🧬🤖 [FUTURO]
Se ha verificado la operatividad de `medgemma1.5` en el servidor local (Ryzen 3). 
- **Estado**: Operativo en contenedor `ollama-engine`.
- **Plan**: Integrar como fallback local para la generación de reportes científicos (Modo Soberano/Offline).

---
*Fecha de actualización: 2026-05-13*
*Versión: v4.0 (Spearman Active)*
*Estado: Producción / Sincronizado*
