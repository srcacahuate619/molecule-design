# Gestión de Datos y Calidad Molecular 🧹🧬

MolDesign implementa un sistema estricto de gestión de datos para asegurar que la base de datos se mantenga limpia, eficiente y enfocada en resultados de alta relevancia científica.

## 1. El Umbral de Calidad (Score >= 60)

El sistema clasifica automáticamente cada evaluación exitosa basándose en su **Score Compuesto (0-100)**. 

| Rango de Score | Clasificación | Acción del Sistema |
| :--- | :--- | :--- |
| **60.0 - 100.0** | **Prometedora (Hit)** | Se conserva permanentemente en la base de datos (Pokedex). |
| **0.0 - 59.9** | **Descartable** | Se programa para eliminación automática tras **1 hora**. |
| **N/A (FAILED)** | **Inválida** | Se programa para eliminación automática tras **1 hora**. |

### Racional Científico
En el descubrimiento de fármacos, la gran mayoría de las moléculas evaluadas son "ruido" o falsos positivos con afinidades pobres. Mantener miles de registros de baja calidad dificulta la identificación de verdaderos *leads*. Un score de **60.0** representa un punto de corte donde la molécula muestra una combinación equilibrada de afinidad, ADME y propiedades químicas.

### 3. Capa de Calidad: Scientific Auditor Engine
A partir de la v5.2, Moldex integra un motor de auditoría post-procesamiento que garantiza la validez de los datos persistidos:
- **Validación de Eficiencia**: Cálculo dinámico de Ligand Efficiency (LE) y Lipophilic Efficiency (LLE).
- **Hotspot Audit**: Verificación de contactos con residuos críticos para asegurar especificidad biológica.
- **Detección de Incertidumbre**: Marcaje de resultados con alta varianza en poses de unión (Binding Uncertainty).
- **Interpretación Dinámica**: Los resultados no son solo números; se acompañan de advertencias científicas que contextualizan la potencia absoluta frente al target.

## 2. Proceso de Limpieza Automática (Auto-Purge)

Para evitar la acumulación de "datos inútiles", el pipeline de evaluación (`queue_handler.py`) utiliza tareas diferidas de Celery:

1.  **Detección**: Al finalizar una evaluación, si el score es `< 60` o el estado es `FAILED`, se dispara una tarea `cleanup_unsaved_molecule` con un retraso (`countdown`) de 3600 segundos.
2.  **Periodo de Gracia**: Durante esa hora, el usuario puede visualizar los resultados en el frontend y decidir si la molécula tiene algún valor subjetivo.
3.  **Verificación de Salvaguarda**: Antes de borrar, el sistema verifica el campo `is_saved`. Si el usuario hizo clic en **"Guardar Molécula"**, la limpieza se cancela inmediatamente.
4.  **Ejecución**: Si tras una hora `is_saved` sigue siendo `False`, el registro y todos sus archivos asociados se eliminan de forma permanente.

## 3. Usuarios Anónimos y Persistencia

La plataforma sigue una política de **"Registro para Conservar"**:

- **Acceso Anónimo**: Los usuarios no registrados comparten la cuenta técnica `demo`. 
- **Restricción de Guardado**: Los anónimos no pueden marcar moléculas como `is_saved`. Esto previene que la cuenta demo se sature con miles de moléculas de diferentes usuarios.
- **Consecuencia**: Todas las evaluaciones de usuarios anónimos con score `< 60` desaparecerán tras 1 hora. Solo los "Hits" excepcionales (> 60) permanecerán visibles en el Moldex global.

## 4. Integridad Referencial
El sistema utiliza borrado en cascada (`ON DELETE CASCADE`) a nivel de base de datos. Al eliminar una molécula, se eliminan automáticamente:
- El registro de resultados de evaluación (`evaluation_results`).
- El historial de tareas de Celery asociado.
- (Próximamente) Los archivos temporales en MinIO asociados al ID de la molécula.

---
*Última actualización: Mayo 2026 - Implementado en v5.0*
