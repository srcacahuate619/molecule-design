# Changelog v6.10: Alineación de Multiplicadores Físicos y Desglose Tecnológico MPO (ADMET-AI & TabPFN)

## Novedades Principales

### 1. Sincronización Matemática entre Frontend y Backend
Anteriormente, el panel de auditoría de Rigor Científico del frontend recalculaba los multiplicadores del motor compuesto localmente, lo cual generaba discrepancias con el backend:
* **Penalización GNN ($M_g$):** El frontend utilizaba una fórmula sigmoide con centro en `20.0`, mientras que el backend utilizaba una formulación dinámica adaptada a la escala y diana del receptor.
* **Penalización de Accesibilidad Sintética ($M_{sa}$):** El frontend aplicaba una función de paso abrupta que anulaba la puntuación a `0.00` si la molécula superaba un SA de `7.0`, ignorando el piso dinámico del backend de `0.35` derivado de la dificultad de síntesis en 6 niveles.
* **Penalización de Viabilidad Sanguínea ($M_v$):** Se recalculaba sobre el score de sangre crudo en lugar de acoplarse al factor del motor.

En **v6.10**, se eliminaron por completo las recalculaciones de UI. El backend ahora transmite los factores exactos (`gnn_factor`, `sa_factor` y `blood_factor`) calculados directamente en `ScoreBreakdown` dentro de `backend/scoring/engine.py`. El componente `ScoreCard.tsx` del frontend renderiza directamente los coeficientes del servidor.

### 2. Panel Detallado de Farmacocinética MPO y Reconocimiento de Motores
Se rediseñó la pestaña **"Parámetros"** de la vista de inspección 3D PRO en `ProEvaluation.tsx` para incorporar el desglose detallado de farmacocinética y toxicología multiparamétrica (MPO), atribuyendo explícitamente el trabajo predictivo a los motores científicos del pipeline:
* **LogS (Solubilidad Acuosa):** Métrica termodinámica predictiva provista por **ADMET-AI**.
* **PPB (Fijación a Proteínas Plasmáticas):** Métrica de afinidad a albúmina sérica provista por **ADMET-AI**.
* **HIA (Absorción Intestinal):** Permeabilidad de membrana provista por **ADMET-AI**.
* **BBB (Barrera Hematoencefálica):** Capacidad de penetración al Sistema Nervioso Central provista por **ADMET-AI**.
* **Alertas Toxicológicas e Inmunogenicidad:** Evaluado mediante un clasificador de Machine Learning Tabular **TabPFN** ejecutado in-context en el backend para predecir reactividad sistémica y toxicología de grupos funcionales exóticos.

### 3. Resolución de Tipos y Limpieza de Código Muerto
* **Next.js & React 18 Compilación:** Corregido el tipado estricto del WalletProvider de Solana (`ConnectionProvider` y `SolanaWalletProvider`) mediante un casting a `any` para evitar fallos de renderizado en el prerendering estático de Next.js.
* **Remoción de Legacy Components:** Se eliminaron las vistas obsoletas duplicadas en la raíz del frontend (`page.tsx`, `api.ts`, `ScoreCard.tsx` y `MoldexCard.tsx`) y el módulo `/app/pokedex` para asegurar un empaquetado Webpack limpio y sin warnings de importación.
