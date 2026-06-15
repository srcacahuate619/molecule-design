# Changelog v7.1: Lista Blanca Dinámica de Cofactores

## Novedades Principales

### 1. Ingesta Dinámica de Cofactores via API RCSB
En versiones anteriores, el motor de preparación (`preparer.py`) purgaba de forma sistemática y ruda todos los registros atómicos no correspondientes a aminoácidos (HETATM), con la excepción de una pequeña lista de metales duros (Zn, Mg, Ca, Fe). 

Con v7.1, hemos introducido la **Lista Blanca Dinámica**:
- Al ingerir un nuevo Target (`services/targets/ingestion_manager.py`), el sistema consulta directamente la API GraphQL del **RCSB PDB**.
- Se analiza cada molécula cristalográfica presente en el archivo (Entidades No Poliméricas) y se descartan automáticamente artefactos como disolventes genéricos, cristalizantes y carbohidratos irrelevantes.
- Los compuestos biológicos verdaderamente funcionales del receptor (ej. el grupo `HEM` en la Ciclooxigenasa-2) son añadidos a una lista blanca inyectada en la base de datos de PostgreSQL bajo la nueva columna `cofactors_whitelist (JSONB)`.

### 2. Mayor Rigidez Biológica en el Docking
- El motor Meeko ahora lee esta base de datos antes de generar el `.pdbqt`. 
- **Impacto Biológico:** Los receptores ahora conservan de manera inteligente la forma biológica natural de su bolsillo de unión. Esto mejora fuertemente la calidad de la correlación de puntuación (Spearman) al prevenir que la IA simule acoples estéricamente irrazonables, y permitiendo interacciones termodinámicas lícitas con los cofactores circundantes.

### 3. Escalabilidad Total
Esta mejora elimina la necesidad de ajustar manualmente los scripts backend para evitar borrar cofactores exóticos cuando se integran nuevas familias enzimáticas. El proceso está al 100% automatizado, haciendo que el pipeline de escalamiento de la plataforma (ej. preparación en masa de 100 targets oncológicos) sea considerablemente más robusto y biológicamente honesto.
