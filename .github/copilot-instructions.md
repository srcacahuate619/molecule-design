# Copilot Instructions — MolDesign

## Propósito innegociable del proyecto

MolDesign es una **plataforma de diseño molecular asistido por IA con validez científica real**.

Este proyecto **NO** debe comportarse como un juguete, demo cosmética o generador de resultados plausibles pero falsos.
El objetivo es construir un **producto científico útil para la humanidad**, lo más cercano posible a la realidad experimental/computacional disponible dentro de las limitaciones del software open source y del cómputo accesible.

La regla principal es:

> **Si hay conflicto entre velocidad de entrega, estética, comodidad de implementación o narrativa de marketing vs. validez científica, siempre gana la validez científica.**

---

## Filosofía científica obligatoria

### 1. La química no se inventa
Todo valor químico, fisicoquímico o farmacológico debe provenir de herramientas o métodos científicos explícitos y reproducibles.

Esto significa:
- La validación estructural sale de **RDKit**.
- Las propiedades fisicoquímicas salen de **RDKit**.
- La afinidad primaria sale de **AutoDock Vina**.
- El score compuesto sale de funciones de normalización explícitas y auditables.
- La IA solo **explica**, **resume** o **contextualiza** resultados ya calculados.

### 2. La IA nunca debe inventar números
La IA **no puede**:
- inventar afinidades,
- inventar propiedades ADME,
- inventar scores,
- corregir resultados numéricos porque “parecen raros”,
- reemplazar cálculos científicos con texto plausible.

La IA solo puede:
- interpretar resultados estructurados,
- explicar implicaciones farmacológicas,
- sugerir hipótesis o siguientes pasos,
- traducir datos a lenguaje accesible,
- comparar resultados ya calculados sin alterar cifras.

### 3. Reproducibilidad por encima de magia
Cada output relevante debe poder rastrearse a:
- input SMILES,
- SMILES canónico,
- hash SHA-256,
- target biológico,
- parámetros de cálculo,
- versiones de software,
- fecha/hora,
- y archivos de soporte cuando aplique.

Toda decisión importante debe favorecer que un científico externo pueda reproducir el resultado.

### 4. Transparencia radical
Nunca ocultar:
- limitaciones del docking,
- limitaciones de RDKit,
- fallos de convergencia,
- warnings por átomos problemáticos,
- incertidumbre del método,
- degradación del sistema,
- ausencia de datos.

Si algo es una aproximación, debe decirse claramente.
Si algo falla, debe reportarse claramente.
Si algo no puede saberse, no debe fingirse certeza.

---

## North Star del producto

MolDesign debe convertirse en una plataforma donde un usuario pueda:
1. diseñar o editar una molécula,
2. validarla químicamente en tiempo real,
3. calcular propiedades reales relevantes para drug discovery,
4. generar una estructura 3D razonable,
5. ejecutar docking real contra un target,
6. obtener un score compuesto científicamente justificable,
7. leer una interpretación útil y honesta,
8. opcionalmente certificar su contribución científica en blockchain,
9. todo ello sin sacrificar rigor científico por gamificación.

La gamificación, comunidad, leaderboard, blockchain y UX son **capas secundarias**.
El núcleo del sistema es el **pipeline científico**.

---

## Prioridades absolutas de implementación

Cuando haya que decidir qué hacer primero, seguir este orden:

1. **Integridad científica**
2. **Correctitud de datos y modelos**
3. **Reproducibilidad y trazabilidad**
4. **Estabilidad del backend**
5. **Persistencia y observabilidad**
6. **Experiencia de usuario**
7. **Velocidad de desarrollo**
8. **Gamificación**
9. **Blockchain**

Nunca invertir este orden.

---

## Reglas obligatorias para cualquier cambio de código

### 1. No romper la separación de responsabilidades
El proyecto debe respetar estrictamente estas fronteras:

- `chem/` valida y calcula química básica.
- `services/docking/` prepara proteínas y ejecuta Vina.
- `scoring/` normaliza y calcula scores.
- `services/ai/` interpreta resultados ya calculados.
- `services/blockchain/` registra certificados, pero no altera el pipeline científico.
- `api/` expone endpoints, middleware y orquestación HTTP.
- `db/` persiste y consulta datos.
- `frontend/` presenta el flujo al usuario, no reemplaza lógica científica.

No mezclar responsabilidades innecesariamente.

### 2. No introducir “fake science”
Está prohibido implementar:
- scores inventados sin base documentada,
- atajos que simulen docking sin avisarlo,
- respuestas de IA presentadas como cálculo real,
- heurísticas de juguete vendidas como evidencia científica,
- placeholders silenciosos que parezcan funcionalidad real.

Si se necesita un mock temporal, debe ser explícito, aislado y etiquetado como mock.

### 3. Toda lógica científica debe quedar documentada
Cuando se implemente o modifique:
- normalización de afinidad,
- scoring ADME,
- penalización por Lipinski/Veber,
- reglas de selección de fragmento,
- preparación de proteína,
- interpretación IA,

entonces debe explicarse:
- qué hace,
- por qué se hace así,
- qué fuente o criterio la respalda,
- y cuáles son sus limitaciones.

### 4. No esconder warnings científicos
Warnings como:
- macrociclos,
- elementos no soportados por Vina,
- mezcla de fragmentos,
- peso molecular extremo,
- falta de convergencia,
- fallas de preparación,

no deben suprimirse por razones visuales o comerciales.

### 5. Preferir errores honestos sobre resultados dudosos
Si el sistema no puede producir un resultado científicamente defendible:
- debe fallar,
- o degradarse explícitamente,
- pero nunca simular precisión inexistente.

---

## Reglas para IA y reportes narrativos

### La IA debe comportarse como intérprete científico, no como oráculo
Siempre asumir:
- los cálculos vienen de módulos científicos,
- la IA recibe estructuras ya calculadas,
- la IA explica, no sustituye evidencia.

### Todo prompt o capa de interpretación debe respetar esto
Instrucciones mínimas para el servicio de IA:
- no alterar ningún valor numérico,
- no inventar propiedades no calculadas,
- no afirmar actividad biológica real más allá del docking computacional,
- no presentar hipótesis como hechos,
- diferenciar claramente entre observación, interpretación e hipótesis,
- usar lenguaje honesto sobre incertidumbre.

### Lenguaje permitido para la IA
Sí:
- “sugiere”
- “es consistente con”
- “podría indicar”
- “merece evaluación adicional”
- “hipótesis de trabajo”

No:
- “demuestra”
- “confirma eficacia”
- “garantiza actividad biológica”
- “es un fármaco prometedor” sin contexto de limitaciones

---

## Reglas para scoring

El score total debe ser:
- explícito,
- auditable,
- reproducible,
- desglosable por dimensión,
- científicamente justificable.

El score **no** debe presentarse como verdad biológica absoluta.
Debe presentarse como una **heurística compuesta para priorización** basada en:
- afinidad de docking,
- perfil ADME/fisicoquímico,
- drug-likeness.

Siempre que sea posible:
- mostrar breakdown del score,
- mostrar pesos usados,
- mostrar hints de mejora,
- mostrar limitaciones del método.

Nunca usar funciones arbitrarias sin explicación.

---

## Reglas para docking

### Docking es costoso y limitado
Siempre recordar:
- Docking no equivale a validación experimental.
- Un buen score de Vina no demuestra eficacia.
- Un mal score no elimina completamente el valor de una molécula.
- El docking depende críticamente de preparación de proteína, grid box y protonación.

### Requisitos de implementación
- cachear resultados cuando sea correcto hacerlo,
- persistir poses y logs relevantes,
- publicar progreso del job,
- reportar errores de preparación o ejecución,
- evitar repetir docking idéntico innecesariamente,
- registrar parámetros clave usados por Vina.

### Nunca presentar docking como certeza clínica
La interfaz y los reportes deben evitar implicar que el resultado equivale a evidencia experimental humana, animal o in vitro.

---

## Reglas para frontend y UX

El frontend debe ser bonito y claro, pero nunca engañoso.

### UX obligatoria
La UI debe ayudar al usuario a entender:
- qué se calculó realmente,
- qué es estimación,
- qué es warning,
- qué parte viene de IA,
- qué parte viene de RDKit/Vina,
- qué puede hacerse después.

### UX prohibida
No diseñar pantallas que:
- oculten incertidumbre,
- sobrevendan hallazgos,
- conviertan el score en una “verdad final”,
- premien únicamente números altos sin contexto,
- hagan parecer que blockchain valida ciencia.

### Gamificación con límites
La gamificación solo es válida si:
- no distorsiona la interpretación científica,
- no incentiva trampas o inputs absurdos,
- no premia moléculas irreales solo por score numérico,
- mantiene alineación con química medicinal razonable.

---

## Reglas para blockchain / DeSci

La blockchain en MolDesign es una capa de **certificación de contribución científica**, no una fuente de verdad química.

### La blockchain no debe:
- calcular ciencia,
- alterar scores,
- modificar resultados,
- definir validez química,
- contaminar el pipeline principal.

### La blockchain sí debe:
- registrar evidencia reproducible,
- preservar autoría y timestamp,
- usar hashes de resultados trazables,
- ser completamente opt-in,
- mantenerse desacoplada del pipeline científico.

Si hay conflicto entre blockchain y simplicidad del MVP científico, se pospone blockchain.

---

## Reglas de calidad técnica

### 1. Tipado y contratos claros
Preferir:
- Pydantic para contratos,
- SQLAlchemy para persistencia,
- modelos explícitos,
- errores específicos,
- nombres claros y científicos.

### 2. Tests en lo crítico
Prioridad de tests:
1. validación SMILES,
2. propiedades fisicoquímicas,
3. normalización y scoring,
4. integración del pipeline,
5. endpoints críticos,
6. degradación de IA y cache.

### 3. Health checks reales
Los health checks deben reflejar estado real de:
- PostgreSQL,
- Redis,
- MinIO,
- Vina,
- y servicios críticos.

No usar health checks falsos o triviales si no prueban funcionalidad real.

### 4. Observabilidad
Toda operación crítica debe dejar trazabilidad suficiente para depuración:
- request_id,
- molecule_id o smiles_hash,
- task_id,
- target,
- estado del job,
- errores claros.

---

## Reglas para toma de decisiones futuras

Cuando Copilot tenga que decidir entre varias implementaciones, debe preferir la que:

1. sea más científicamente defendible,
2. haga más explícitas las limitaciones,
3. preserve mejor la arquitectura modular,
4. sea más reproducible,
5. reduzca riesgo de resultados engañosos,
6. sea más fácil de testear,
7. y solo después considere conveniencia o rapidez.

---

## Lo que jamás debe olvidarse

### Recordatorio permanente
MolDesign debe ayudar a la humanidad **solo si dice la verdad científica lo mejor posible**.

No estamos construyendo:
- una app bonita con números inventados,
- un chatbot que “parece saber química”,
- una plataforma cripto con barniz científico,
- un juego que sacrifica rigor por engagement.

Estamos construyendo:
- una herramienta computacional seria,
- científicamente honesta,
- útil para exploración molecular,
- abierta a la humanidad,
- con IA subordinada a la evidencia,
- y con trazabilidad suficiente para que el conocimiento generado tenga valor real.

---

## Instrucción final para cualquier sesión futura

Antes de proponer código, arquitectura o UX, asumir siempre:

> **La misión de MolDesign es maximizar utilidad científica real, reproducibilidad, honestidad metodológica y beneficio humano; nunca sacrificar estos principios por rapidez, apariencia o hype.**

---

## Checklist obligatorio antes de escribir código

Antes de implementar cualquier cambio, verificar siempre:

1. ¿Este cambio acerca el producto a una herramienta científica real o solo a una demo más vistosa?
2. ¿Los números seguirán viniendo de módulos científicos explícitos y no de IA?
3. ¿La implementación conserva trazabilidad, límites y reproducibilidad?
4. ¿El usuario podrá distinguir claramente cálculo real, interpretación y warning?
5. ¿Si algo falla, el sistema lo reportará honestamente en vez de simular precisión?

Si cualquiera de estas respuestas es "no", la implementación debe replantearse.

---

## Definition of Done obligatoria

Un cambio solo puede considerarse terminado si cumple simultáneamente lo siguiente:

- funciona técnicamente,
- mantiene coherencia con la arquitectura modular del proyecto,
- es científicamente defendible,
- deja explícitas sus limitaciones,
- no inventa ni altera evidencia,
- no oculta warnings relevantes,
- y no induce a conclusiones biológicas más fuertes que los datos disponibles.

Si algo "funciona" pero viola uno de esos puntos, entonces **no está terminado**.

---

## Instrucciones especiales para futuras decisiones de producto

Si en el futuro aparece una tensión entre dos caminos, decidir así:

### Elegir siempre el camino que:
- preserve la verdad científica,
- muestre incertidumbre con claridad,
- haga el sistema más reproducible,
- y reduzca el riesgo de engañar al usuario.

### Evitar siempre el camino que:
- haga la interfaz más impresionante pero menos honesta,
- use texto para cubrir cálculos faltantes,
- convierta heurísticas en aparentes certezas,
- o sacrifique validez por velocidad de entrega.

---

## Regla de memoria permanente

Si alguna vez hay duda sobre qué hacer, recordar esto primero:

> **MolDesign no existe para parecer ciencia. Existe para hacer ciencia computacional lo más honestamente posible y convertirla en una herramienta útil para la humanidad.**

---

## Roadmap obligatorio del MVP

Para futuras sesiones, seguir como fuente operativa principal:

- `docs/MVP_ROADMAP.md`

Reglas de uso:
- No desviarse a features secundarios si el roadmap del MVP sigue incompleto.
- Mapear cada cambio propuesto a una fase concreta del roadmap.
- Si una idea no ayuda a terminar el MVP científico, posponerla.
- No reordenar prioridades salvo que exista una dependencia técnica real.
