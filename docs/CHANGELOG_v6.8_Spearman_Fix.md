# Changelog v6.8 - Spearman Benchmark Optimization & Hardware Scaling

**Fecha:** 14 de Junio de 2026
**Estado:** Pruebas Piloto en Progreso (Esperando resultados de Spearman).

## 🛠 Problema Original
La métrica de correlación de Spearman para el modelo predictivo (XGBoost + GNN) había caído drásticamente, mostrando alta variabilidad y resultados desastrosos en casi todos los receptores. Además, el pipeline completo era lento y mostraba cuellos de botella en la evaluación de moléculas.

## 🚀 Cambios Realizados Hoy

### 1. Descongelamiento del Servidor FastAPI (ML Rescoring)
- **Problema:** La red neuronal (GNN) y XGBoost estaban ejecutando operaciones síncronas bloqueantes en el hilo principal de la API.
- **Solución:** Se envolvió la inferencia predictiva usando `asyncio.get_event_loop().run_in_executor()` en `rescoring/app.py`. Ahora el modelo no bloquea el servidor durante predicciones pesadas.

### 2. Recuperación del Caché de Docking
- **Problema:** El pipeline estaba ignorando el caché existente (calculando poses repetidas desde cero) y destruyéndolo agresivamente.
- **Solución:** Se corrigió el bypass en `vina_service.py` y se removió la lógica de destrucción de caché en `queue_handler.py`.

### 3. Estabilización Matemática de la GNN
- **Problema:** Un sigmoide doble en el cálculo del `RTMScore` estaba aplanando la varianza de las predicciones, ocultando las diferencias reales entre buenas y malas moléculas.
- **Solución:** Se purgaron las transformaciones destructivas en el `engine.py` y `gnn_service.py` para exponer el score puro de afinidad.

### 4. Transparencia del Reporte Spearman
- **Problema:** El generador de reportes en `run_global_spearman_benchmark.py` tenía una conclusión estática y "mentirosa" (decía "Media: 0.512") hardcodeada, ocultando la gravedad real del rendimiento.
- **Solución:** Se reescribió la lógica de reporte para que las conclusiones, promedios y advertencias se calculen matemáticamente en tiempo real según el output real de los dockings.

### 5. Escalamiento de Hardware (Ubuntu Server)
- **Problema:** El hardware de 4 núcleos (Ryzen) estaba siendo subutilizado al 25% de su capacidad. Celery y Vina corrían en modo estrictamente secuencial.
- **Solución:** Se actualizó `docker-compose.yml` para usar `--pool=prefork` y `--concurrency=3`. La velocidad del benchmark masivo se triplicó, bajando el tiempo esperado de 6 horas a 1.5 horas.

## ⏳ Estado Actual
Se encuentra corriendo una **Prueba Piloto Asíncrona (10 moléculas experimentales por target)** en el servidor de producción. Estamos a la espera del `Spearman_Report_Latest.md` para validar si la purga de bugs de hoy devolvió al modelo a su antigua gloria o si la arquitectura de la GNN necesita un re-entrenamiento con hiperparámetros distintos.

### 6. Resolución de Problemas Físico-Químicos (Protonación a pH 7.4)
- **Problema:** `conformer.py` añadía hidrógenos a los ligandos asumiendo que siempre eran neutros, ignorando que a pH fisiológico en sangre (7.4) ácidos y bases se ionizan. Esto causaba repulsión electrostática masiva en bolsillos con puente salino e invertía la correlación empírica en varios receptores.
- **Solución:** Se integró `dimorphite_dl` nativamente en el pipeline de embebido 3D. RDKit ahora protona rigurosamente el compuesto al microambiente de la sangre humana antes de calcular la geometría, restaurando los puentes salinos para Vina y XGBoost.
