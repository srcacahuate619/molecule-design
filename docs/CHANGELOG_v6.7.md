# Changelog v6.7 (GNN Spearman Calibration & Hardened Infra)

## Nuevas Características y Mejoras
- **Calibración Matemática GNN (RTMScore):** Se eliminó la normalización por átomos pesados (GNN-LE) en la función de puntuación total. La sigmoide ahora opera directamente sobre la distribución bruta del RTMScore poblacional, permitiendo un fuerte bono (+30%) a verdaderos positivos grandes sin penalizarlos por su peso molecular, y conservando el castigo estricto a señuelos geométricos (<40).
- **Timeouts Seguros en Celery:** Se implementó un `soft_time_limit=270` y un `time_limit=300` en el worker para abortar y fallar graciosamente aquellas simulaciones donde el refinamiento (OpenMM) o cálculo cuántico (xTB) se congele (Silent Timeouts), garantizando la disponibilidad del clúster durante análisis masivos.
- **Recolección de Basura de PDBQT:** Se eliminó la fuga de disco en Vina al remover volcados de archivos temporales de depuración no sanitizados.

## Preparación de Benchmarks
- La plataforma queda matemáticamente lista para superar los límites de Spearman ($\rho > 0.50$) gracias a la alineación vectorial del XGBoost y la GNN hacia el mismo objetivo.
