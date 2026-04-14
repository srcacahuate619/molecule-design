# Contributing to MolDesign

## Principio rector

MolDesign existe para construir una **plataforma de diseño molecular científicamente honesta, reproducible y útil para la humanidad**.

Cualquier contribución debe respetar esta prioridad absoluta:

> **Si hay conflicto entre velocidad, UX, estética, hype, gamificación o conveniencia vs. validez científica, gana la validez científica.**

---

## Qué tipo de proyecto es este

Esto **no** es:
- una demo cosmética de IA,
- un generador de números plausibles,
- un juego desconectado de la química real,
- una app cripto con barniz científico.

Esto **sí** es:
- una herramienta computacional de exploración molecular,
- basada en RDKit, AutoDock Vina y scoring auditable,
- con IA subordinada a la evidencia,
- y con trazabilidad suficiente para que los resultados tengan valor científico real.

---

## Reglas no negociables

### 1. No inventar ciencia
No introducir:
- afinidades inventadas,
- scores arbitrarios sin documentación,
- ADME inventado por IA,
- placeholders que parezcan cálculo real,
- mocks no etiquetados como mocks.

### 2. La IA no calcula
La IA solo puede:
- explicar,
- comparar,
- contextualizar,
- proponer hipótesis,
- resumir resultados ya calculados.

La IA no puede:
- generar números científicos,
- alterar cifras,
- corregir docking “porque parece raro”,
- presentar hipótesis como hechos.

### 3. Reproducibilidad obligatoria
Todo cambio debe favorecer trazabilidad de:
- SMILES de entrada,
- SMILES canónico,
- smiles_hash,
- target,
- parámetros de cálculo,
- versiones de software,
- timestamps,
- artefactos relevantes.

### 4. Transparencia radical
No ocultar:
- warnings científicos,
- errores de convergencia,
- limitaciones del docking,
- fallas del sistema,
- incertidumbre del método.

### 5. Separación estricta de responsabilidades
- `chem/`: química básica y validación
- `services/docking/`: preparación y docking
- `scoring/`: normalización y score
- `services/ai/`: interpretación narrativa
- `services/blockchain/`: certificación opt-in
- `api/`: orquestación HTTP
- `db/`: persistencia
- `frontend/`: presentación

---

## Cómo decidir entre dos implementaciones

Elegir siempre la opción que:
1. sea más científicamente defendible,
2. haga más visibles las limitaciones,
3. preserve mejor la reproducibilidad,
4. reduzca el riesgo de engaño involuntario,
5. sea más fácil de testear,
6. y solo después sea más rápida o cómoda.

---

## Claims permitidos y prohibidos

### Permitidos
- “sugiere”
- “es consistente con”
- “podría indicar”
- “merece evaluación adicional”
- “hipótesis de trabajo”
- “resultado computacional”

### Prohibidos
- “demuestra eficacia”
- “confirma actividad biológica”
- “garantiza valor terapéutico”
- “equivale a evidencia experimental”
- “es un candidato clínico” sin contexto ni limitaciones

---

## Qué debe incluir una contribución científica correcta

Cuando un cambio toca lógica científica, debe dejar claro:
- qué calcula,
- con qué método,
- qué supuestos usa,
- qué limitaciones tiene,
- cómo se interpreta correctamente,
- y cómo se prueba.

---

## Checklist antes de aprobar una contribución

- [ ] No introduce fake science.
- [ ] No delega a IA lo que debe calcular RDKit/Vina.
- [ ] Mantiene trazabilidad y reproducibilidad.
- [ ] Expone warnings y limitaciones relevantes.
- [ ] Respeta la arquitectura modular.
- [ ] Incluye tests o justificación clara si aún no es posible.
- [ ] No sobrevende hallazgos computacionales.
- [ ] No convierte blockchain en fuente de verdad científica.

---

## Definition of Done mínima

Un cambio está realmente terminado solo si:
- funciona técnicamente,
- es científicamente defendible,
- no oculta incertidumbre,
- tiene límites explícitos,
- y no induce a interpretar resultados computacionales como validación experimental.

---

## Recordatorio final

**MolDesign solo tiene valor si se mantiene radicalmente honesto con la ciencia.**

Si una funcionalidad hace el producto más vistoso pero menos verdadero, no debe entrar.
