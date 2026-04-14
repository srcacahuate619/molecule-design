# Arquitectura Futura — Propuestas en Backlog

> **Fecha:** 2026-04-05  
> **Origen:** Análisis interdisciplinario (`docs/INTERDISCIPLINARY_IMPROVEMENTS.md`)  
> **Estado:** BACKLOG — ninguna de estas propuestas se implementa en el sprint actual  
> **Regla:** No escribir código sobre estas propuestas hasta que el ML Rescoring base esté entrenado, validado y en producción.

---

## Propósito de este documento

Este archivo documenta 4 propuestas interdisciplinarias que son científicamente sólidas pero **prematuras** para el sprint actual. Se preservan aquí para que no se pierdan y para que futuras sesiones de trabajo puedan evaluarlas con contexto.

Cada propuesta tiene **prerrequisitos claros** que deben cumplirse antes de considerarla.

---

## P3: Teoría de Credibilidad de Bühlmann (de Ciencias Actuariales)

### Concepto

En seguros, cuando hay poca data para un grupo específico (e.g., conductores zurdos en Islandia), la tarifa se calcula como promedio ponderado entre la **experiencia particular del grupo** y la **experiencia de la población general**:

```
Tarifa = Z × experiencia_grupo + (1 - Z) × experiencia_global
```

Donde Z ∈ [0, 1] es el **factor de credibilidad** que depende del tamaño de muestra del grupo.

### Aplicación a MolDesign

Para familias de proteínas sub-representadas en PDBbind (e.g., GPCRs con ~50-100 complejos vs ~5,000 totales):

```
predicción_GPCR = Z_GPCR × modelo_GPCR + (1 - Z_GPCR) × modelo_general
```

Con Z_GPCR bajo (pocos datos) → predicción se ancla al modelo general.
Con Z_GPCR alto (muchos datos) → predicción confía más en el sub-modelo.

### Prerrequisitos

1. **Modelo base entrenado y validado** — primero necesitamos saber qué performance tiene el modelo general por familia
2. **Métricas por familia** — el training report debe desglosar NDCG/Spearman por familia de proteínas
3. **Al menos 3-5 familias** con >20 complejos para que el cálculo de Z sea significativo
4. **Definir umbral de credibilidad:** ¿a partir de qué n el sub-modelo es más útil que el general?

### Estimación de esfuerzo

- Complejidad: MEDIA (implementación simple, validación compleja)
- Riesgo: BAJO (método bien establecido en actuaría, >100 años de uso)
- Impacto: MEDIO (mejora predicción para GPCRs y familias raras)

### Referencia

- Bühlmann H. "Experience Rating and Credibility." ASTIN Bulletin. 1967;4(3):199-207.
- Klugman SA, Panjer HH, Willmot GE. "Loss Models: From Data to Decisions." Wiley, 2012.

---

## P4: Control Estadístico de Procesos / CUSUM (de Manufactura / Six Sigma)

### Concepto

En manufactura (Toyota, Six Sigma), la calidad se monitorea con **control charts** que detectan automáticamente cuándo un proceso se sale de control:

- **Gráfico X-bar / R:** monitorea media y rango de mediciones
- **CUSUM (Cumulative Sum):** detecta shifts pequeños y sostenidos que un gráfico de Shewhart perdería
- **Alarma automática** cuando una métrica cruza un umbral estadístico (no heurístico)

### Aplicación a MolDesign

Monitorear la calidad del modelo ML en producción:

```
Para cada batch de N moléculas evaluadas:
  - Calcular score medio, varianza, % fuera del Applicability Domain
  - Comparar contra distribución esperada del training set
  - Si CUSUM cruza h (decision interval): WARNING → el modelo podría estar degradado
```

**Trigger automático:** Si las moléculas que están evaluando los usuarios cambian significativamente (más grandes, más polares, scaffolds nuevos), el modelo ya no es válido para esa población.

### Prerrequisitos

1. **Modelo en producción** — necesitamos datos reales de moléculas evaluadas por usuarios
2. **Al menos 100-500 evaluaciones** para establecer una baseline de producción
3. **Applicability Domain implementado** — el % de moléculas fuera de dominio es una de las señales a monitorear
4. **Pipeline de logging** — las predicciones y sus features deben persistirse para análisis retrospectivo

### Estimación de esfuerzo

- Complejidad: MEDIA (CUSUM es simple de implementar, definir parámetros requiere datos)
- Riesgo: BAJO (método estándar de ingeniería industrial)
- Impacto: ALTO (detectar degradación temprano evita resultados inválidos en producción)

### Referencia

- Page ES. "Continuous Inspection Schemes." Biometrika. 1954;41(1/2):100-115.
- Montgomery DC. "Introduction to Statistical Quality Control." Wiley, 8th ed., 2019.
- Hawkins DM, Olwell DH. "Cumulative Sum Charts and Charting for Quality Improvement." Springer, 1998.

---

## P6: DAGs Causales / Grafos Acíclicos Dirigidos (de Epidemiología)

### Concepto

En epidemiología, antes de modelar "¿fumar causa cáncer?", se dibuja un **DAG** (Directed Acyclic Graph) que explicita las relaciones causales entre todas las variables. Esto permite identificar:

- **Confounders** que deben ser controlados
- **Mediators** que no deben ser controlados
- **Colliders** que introducen sesgo si se controlan incorrectamente

```
     MW ←── SMILES ──→ LogP
      ↓         ↓        ↓
    Pose  ←── Docking ──→ Vina_Score
      ↓                      ↓
  Contact_Map ──→ ML_Score ←─┘
                     ↓
                Delta = ML - NULL
```

### Aplicación a MolDesign

Formalizar la relación entre features del modelo para verificar que:
1. **El Modelo NULL controla correctamente** por propiedades intrínsecas del ligando
2. **No hay un confounding** inesperado (e.g., MW afecta tanto al score como al número de contactos, inflando la correlación)
3. **Delta tiene interpretación causal** correcta (diferencia de predicciones, no de raws)

### Prerrequisitos

1. **Feature list finalizada** — necesitamos saber exactamente qué features tiene el modelo
2. **Modelo entrenado con SHAP values** — las importancias de features informan el DAG
3. **Conocimiento de dominio** para dibujar relaciones causales (no es puramente data-driven)

### Estimación de esfuerzo

- Complejidad: BAJA (es un diagrama + análisis, no código nuevo)
- Riesgo: NULO (es documentación analítica, no modifica el pipeline)
- Impacto: MEDIO (previene errores de interpretación del modelo)

### Referencia

- Pearl J. "Causality: Models, Reasoning, and Inference." Cambridge University Press, 2000.
- Hernán MA, Robins JM. "Causal Inference: What If." Chapman & Hall/CRC, 2020.
- Greenland S, Pearl J, Robins JM. "Causal Diagrams for Epidemiologic Research." Epidemiology. 1999;10:37-48.

---

## P8: Modelos de Interacción G×E / AMMI (de Agronomía)

### Concepto

En mejoramiento de cultivos, el rendimiento de una variedad depende de su interacción con el ambiente (suelo, clima). El modelo **AMMI** descompone:

```
Y_ij = μ + G_i + E_j + Σ(λ_k × α_ik × γ_jk) + ε_ij
```

- G_i = efecto del genotipo (variedad)
- E_j = efecto del ambiente (ubicación)  
- Interacción = lo que le pasa a ESA variedad en ESE ambiente

### Aplicación a MolDesign (Post-MVP Multi-Target)

Cuando MolDesign soporte múltiples targets, modelar:

```
pKd_ij = μ + L_i + P_j + Interacción(L_i, P_j) + ε_ij
```

- L_i = efecto intrínseco del ligando (≈ Modelo NULL)
- P_j = efecto de druggability del target
- **Interacción = Delta de Especificidad 3D generalizado a multi-target**

Un biplot AMMI permitiría visualizar qué ligandos son "estables" (buenos para muchos targets) vs "específicos" (buenos solo para un target particular).

### Prerrequisitos

1. **Multi-target operativo** — actualmente MolDesign solo soporta 7E2Y/5-HT1A
2. **Al menos 3-5 targets** con datos de evaluación
3. **Datos cruzados** — las mismas moléculas evaluadas contra múltiples targets
4. **Frontend capaz de mostrar biplots** o gráficos de interacción

### Estimación de esfuerzo

- Complejidad: ALTA (requiere refactorizar el pipeline para multi-target)
- Riesgo: BAJO (método con >40 años de validación en genética cuantitativa)
- Impacto: ALTO (pero solo cuando hay multi-target)

### Referencia

- Gauch HG. "Statistical Analysis of Regional Yield Trials: AMMI Analysis of Factorial Designs." Elsevier, 1992.
- Yan W. "GGE Biplot Analysis." CRC Press, 2014.
- Finlay KW, Wilkinson GN. "The Analysis of Adaptation in a Plant-Breeding Programme." Australian J Agric Res. 1963;14:742-754.

---

## Orden sugerido de implementación futura

Una vez que el ML Rescoring base esté en producción:

| Prioridad | Propuesta | Trigger para iniciar |
|---|---|---|
| 1 | P6: DAGs Causales | Modelo entrenado + SHAP disponibles |
| 2 | P3: Bühlmann | Training report con métricas por familia |
| 3 | P4: CUSUM/SPC | >100 evaluaciones reales en producción |
| 4 | P8: G×E / AMMI | Multi-target implementado |

---

## Visualización 3D de Superficie — 3 niveles progresivos

> **Fecha:** 2026-04-05  
> **Origen:** Discusión sobre "Paisaje de Potencial" en frontend  
> **Decisión:** Documentar para implementación futura, no en sprint de ML Rescoring  

### Contexto

El visor 3D actual (`MoleculeViewer3D.tsx`) muestra proteína (cartoon + VDW gris) y ligando (stick + sphere). La superficie no transmite información electrostática ni de hidrofobicidad. Una visualización más rica ayudaría al usuario a entender *por qué* Vina colocó la molécula en ese lugar exacto.

### 3 niveles (implementar en orden)

#### Nivel A1: Cargas Parciales Gasteiger

- **Qué hace:** Colorear la superficie del receptor por carga parcial (rojo = negativa, azul = positiva)
- **Costo:** Bajo — 3Dmol.js soporta `colorfunc` y `voldata` nativamente
- **Honestidad:** Etiquetar como "Cargas parciales Gasteiger" — NO como "Potencial Electrostático"
- **Implementación:** Frontend puro, sin cálculos backend extra
- **Valor:** Alto impacto visual, el usuario ve la complementariedad de cargas en el binding pocket

#### Nivel A2: Mapa de Lipofilia / Hidrofobicidad

- **Qué hace:** Colorear por hidrofobicidad (escala Crippen: LogP atómico)
- **Costo:** Bajo-medio — requiere asignar contribuciones de LogP por átomo (RDKit o tabla precalculada)
- **Honestidad:** Etiquetar como "Contribución hidrofóbica atómica (Crippen)"
- **Valor:** Muy útil para entender contactos hidrofóbicos (la feature más predictiva en muchos bolsillos)

#### Nivel A3: ESP Real con APBS (Opcional)

- **Qué hace:** Resolver la ecuación de Poisson-Boltzmann con APBS para generar un grid .dx de potencial electrostático real
- **Costo:** Alto — cálculo de minutos por proteína, nuevo servicio/contenedor Docker
- **Honestidad:** 100% honesto — es ESP de verdad
- **Restricción:** DEBE ser opcional / on-demand. No puede bloquear el tiempo de respuesta del flujo principal. El usuario lo activa si quiere, y espera el cálculo ~1-3 min
- **Prerrequisitos:** 
  1. Niveles A1 y A2 implementados y validados
  2. Infraestructura Docker estable
  3. Decisión de si cachear ESP por proteína (mismo target = mismo ESP para todas las moléculas)

### Principios de diseño (aplican a los 3 niveles)

1. **Transparencia radical:** Cada visualización debe indicar qué método la generó
2. **Disclaimer:** "Visualización computacional aproximada — no equivale a datos experimentales"
3. **Toggle claro:** El usuario elige qué capa ver (cargas / lipofilia / ESP / ninguna)
4. **No engañar:** Nunca llamar "ESP" a cargas Gasteiger

### Trigger para implementar

- A1 y A2: Cuando el MVP científico esté funcional end-to-end y haya tiempo para mejorar UX
- A3: Solo cuando haya demanda de usuarios y la infraestructura lo soporte sin degradar latencia

---

> **Recordatorio:** Estas propuestas son científicamente sólidas pero **no bloquean** el sprint actual. El foco es entrenar, validar y deployar el ML Rescoring con LTR, Applicability Domain y Likelihood Ratios.
