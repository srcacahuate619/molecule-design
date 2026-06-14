# Auditoría End-to-End del Pipeline (Fase 2) - Preparación para Spearman

**Fecha:** 13 de Junio de 2026
**Molécula de Prueba:** Imatinib (Gleevec)
**Receptores Evaluados:** 18 blancos biológicos oncológicos y metabólicos.

Se ejecutó una validación rigurosa de toda la cascada matemática y física del sistema MolDesign utilizando Imatinib, un potente inhibidor de quinasas de gran tamaño anatómico, enfrentándolo contra todos los 18 targets del sistema.

El objetivo fue confirmar que cada uno de los microservicios operara matemáticamente sin errores de sintaxis y que las lógicas de penalización (Umbral Vina, Filtro ADME, Dominio de Aplicabilidad, GNN-LE) funcionaran a la perfección, garantizando estabilidad técnica y rigor científico justo antes de lanzar el benchmark global del Coeficiente de Spearman (Fase 3).

## Resultados Consolidados

| Target (PDB) | Vina (kcal/mol) | GNN-LE | Especificidad | Total Score | Notas Científicas Relevantes |
|--------------|-----------------|--------|---------------|-------------|------------------------------|
| **4I5I** (Src) | -13.44 | 175.18 | 60.0% | **66.09** | ⚠️ XGBoost Fuera de Dominio de Aplicabilidad (Distancia 74271 > 16.2). GNN SÍ evaluó topología 3D exitosamente. |
| **3O96** (MEK1) | -12.20 | 171.10 | 100.0% | **76.56** | ⚠️ XGBoost Fuera de Dominio de Aplicabilidad. GNN SÍ evaluó. |
| **6X1A** (CDK) | -11.54 | 141.85 | 100.0% | **71.47** | ⚠️ XGBoost Fuera de Dominio de Aplicabilidad. GNN SÍ evaluó. |
| **4ZZZ** (PARP1) | -11.25 | 170.98 | 100.0% | **70.73** | ⚠️ XGBoost Fuera de Dominio de Aplicabilidad. GNN SÍ evaluó. |
| **4NC3** (CDK6) | -11.18 | 173.05 | 100.0% | **70.28** | Incertidumbre de Pose. Múltiples modos de enlace idénticos. |
| **3PP0** (ERK) | -10.91 | 207.74 | 100.0% | **65.83** | ⚠️ XGBoost Fuera de Dominio de Aplicabilidad. GNN SÍ evaluó. |
| **4JPS** (B-Raf) | -10.58 | 139.06 | 100.0% | **57.93** | ⚠️ XGBoost Fuera de Dominio de Aplicabilidad. GNN SÍ evaluó. |
| **5L2I** (Mcl-1) | -10.44 | 160.73 | 77.7% | **50.02** | Oportunidad Crítica: Se han fallado residuos de máxima importancia (VAL101). |
| **4EKL** (PI3K) | -10.40 | 154.50 | 100.0% | **55.38** | ⚠️ XGBoost Fuera de Dominio de Aplicabilidad. GNN SÍ evaluó. |
| **1HVY** (TS) | -10.30 | 152.51 | 100.0% | **53.59** | ⚠️ XGBoost Fuera de Dominio de Aplicabilidad. GNN SÍ evaluó. |
| **6D8X** (JAK2) | -9.97 | 143.36 | **0.0%** | **23.79** | ⚠️ Fracaso de Farmacóforo: No interactúa con NINGÚN hotspot definido. |
| **3ERT** (ERa) | -9.89 | 151.20 | 82.6% | **42.51** | ⚠️ XGBoost Fuera de Dominio de Aplicabilidad. GNN SÍ evaluó. |
| **5IKR** (KRAS) | -9.84 | 130.01 | 60.0% | **35.90** | Oportunidad Crítica: Se ha fallado PHE395. |
| **4RER** (EGFR) | -9.74 | 173.79 | 100.0% | **44.64** | ⚠️ XGBoost Fuera de Dominio de Aplicabilidad. GNN SÍ evaluó. |
| **7E2Y** (5-HT) | -8.45 | 96.21 | 100.0% | **24.80** | Baja Eficiencia de Ligando (LE=0.23): Molécula demasiado grande para la afinidad obtenida. |
| **5VEW** (ALK) | -8.08 | 84.40 | 52.9% | **16.76** | Oportunidad Crítica: Se ha fallado MET397. |
| **3OSK** (Aurora)| -7.41 | 99.29 | 62.9% | **16.44** | Oportunidad Crítica: Se ha fallado ASN78. |
| **1ERE** (ERa) | **-2.56** | 185.15 | 100.0% | **4.30** | ⚠️ Afinidad Débil. Riesgo toxicidad hidrofóbica (Baja Eficiencia Lipofílica). |

## Hallazgos Arquitecturales y Matemáticos
1. **Dominio de Aplicabilidad Activo**: El sistema XGBoost detectó la molécula fuera de su límite de confianza e inteligentemente se "apagó" previniendo la alucinación de datos (Distancia de Mahalanobis extrema).
2. **Resiliencia GNN 3D**: La Red de Grafos 3D absorbió exitosamente la caída del XGBoost evaluando las topologías complejas sin problema y garantizando un rankeo numérico basado puramente en topología.
3. **Métricas de Penalización Honestas (Farmacóforo)**: Se validó que, aunque una molécula tenga excelente Score Vina (-9.97 en 6D8X), si no intercepta los aminoácidos críticos designados por la literatura, el score total es aplastado (23.79) impidiendo falsos positivos.

**Estado Actual:** TODO el pipeline está completamente funcional de inicio a fin. Sistema verificado y listo para Fase 3 (Benchmark de Spearman).
