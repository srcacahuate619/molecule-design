# Sistema de Hotspots Moleculares 🎯🧬

Este documento detalla el funcionamiento del sistema de "Hotspots" (puntos calientes) biológicos implementado en MolDesign v4.2 para garantizar la especificidad en el diseño de fármacos.

## 1. ¿Qué es un Hotspot?

En el contexto de MolDesign, un hotspot es un residuo de aminoácido del receptor que ha sido identificado (vía cristalografía, mutagénesis o literatura) como crucial para la actividad biológica. No basta con que una molécula se una al bolsillo; debe interactuar con estos residuos para ser considerada un "hit" de alta calidad.

## 2. Jerarquía Visual y Lógica (3 Niveles)

El visor 3D y el motor de scoring utilizan una jerarquía de tres niveles para comunicar el éxito del diseño:

### 🟢 Impacto Crítico (Verde Neón Brillante)
- **Criterio**: El ligando se encuentra a < 5.0 Å del hotspot **Y** existe una interacción polar directa (puente de hidrógeno o contacto salino) a < 3.5 Å.
- **Representación**: Esfera verde neón grande (#00ff00) con brillo.
- **Significado**: El diseño ha logrado un anclaje físico fuerte con un punto clave.

### 🟢 Contacto de Proximidad (Verde Esmeralda Pálido)
- **Criterio**: El ligando se encuentra a < 5.0 Å del hotspot, pero no hay un puente de hidrógeno directo.
- **Representación**: Esfera verde translúcida (#10b981, 45% opacidad).
- **Significado**: Existe una interacción hidrofóbica o de apilamiento (stacking). Es biológicamente relevante pero menos estable que un enlace polar.

### 🔴 Sin Interacción (Magenta)
- **Criterio**: El ligando se encuentra a > 5.0 Å del hotspot.
- **Representación**: Esfera magenta estándar (#ff00ff).
- **Significado**: El ligando está ignorando este punto crítico.

## 3. Calibración del Threshold (5.0 Å)

Originalmente el sistema usaba 4.0 Å, pero fue ampliado a **5.0 Å** tras validar el target **CTLA-4 (3OSK)**.
- **Justificación**: Muchos hotspots críticos (como Prolinas o Tirosinas) ejercen su influencia mediante contactos de van der Waals o apilamiento aromático, cuyos radios de influencia son mayores a los de un puente de hidrógeno convencional. 5.0 Å permite capturar estos "hits" biológicos sin generar falsos positivos excesivos.

## 4. Integración en el Scoring (Specificity Score)

La especificidad no es solo visual; afecta el score final (0-100):
- **Cálculo del Score de Especificidad**: Se calcula como el porcentaje de importancia de los hotspots impactados respecto al total de importancia de todos los hotspots configurados para el receptor:
  $$specificity\_score = \frac{\sum Hits\_Importance}{\sum Total\_Importance} \times 100$$
- **Cálculo del Multiplicador de Especificidad**: El score total se modula mediante un multiplicador que escala el score base:
  $$specificity\_multiplier = specificity\_floor + \left((1.0 - specificity\_floor) \times \frac{specificity\_score}{100.0}\right)$$
- **Suelo de Especificidad Configurable (`specificity_floor`)**: Cada target define su propio suelo de penalización (por defecto **0.5x**, limitando el castigo al 50%). Para targets con hotspots muy conocidos y críticos, el valor se puede configurar dinámicamente en el rango de `[0.1, 0.9]` (con un clamp defensivo). Si `specificity_floor` se establece en `0.1`, una molécula con 0 hits de especificidad verá su score base reducido a solo el 10% (penalización del 90%).
- **Impacto**: Una molécula con excelente afinidad pero 0 hits de especificidad para un receptor estándar verá su score final reducido a la mitad, penalizando severamente el "binding inespecífico".

## 5. Alerta de Fragmento (Fragment Warning)

Para evitar el exceso de optimismo en moléculas pequeñas (como la Serotonina), el sistema dispara una alerta si:
- **Heavy Atom Count < 15**.
- **Resultado**: El sistema advierte que se trata de un "Potencial de Fragmento". Aunque el score sea alto, se requiere crecimiento estructural para lograr un bloqueo competitivo del target.

---
*Versión: 2.0 (v6.2 Active)*
*Targets de Referencia: CTLA-4 (3OSK) & ER-alpha (3ERT) / CDK6 (5L2I)*
