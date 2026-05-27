# MolDesign IA 🧪 (con Módulo Moldex)

**Plataforma de Descubrimiento Farmacológico In Silico con Auditoría Científica Profunda, Rescoring por ML y Certificación Blockchain.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)]()
[![Next.js: 14](https://img.shields.io/badge/Next.js-14-black.svg)]()
[![Solana: Devnet](https://img.shields.io/badge/Blockchain-Solana_Devnet-purple.svg)]()
[![Spearman ρ: 0.512](https://img.shields.io/badge/Spearman_%CF%81_blind-0.512-brightgreen.svg)]()
[![Redocking RMSD: 0.85Å](https://img.shields.io/badge/Redocking_RMSD-0.85_Å-brightgreen.svg)]()

> *"Democratizando la creación de fármacos mediante el rigor de la ciencia computacional y la transparencia de datos."*

**MolDesign IA** es una plataforma *Open Science* evolucionada que permite a investigadores y estudiantes diseñar moléculas contra blancos biológicos críticos. No solo calcula afinidades; realiza una **auditoría científica profunda** (LE, LLE, Hotspot Analysis) para validar cada diseño, integrando el módulo **Moldex** como su interfaz de registro e inmutabilidad histórica. Cada hallazgo queda certificado de forma inmutable en la blockchain de Solana.


### Novedades v6.1: Calibración de Rigor Biofísico y Suelo de Potencia Suave
La plataforma ha escalado su motor científico con la actualización **v6.1**, corrigiendo sesgos termodinámicos tradicionales en el cribado virtual:
- **Size-Adaptive LE:** Punto medio de Eficiencia de Ligando dinámico ($LE_{mid}$) entre $-0.38$ y $-0.20$ kcal/mol/at. Evita la penalización injusta de fármacos de alto peso molecular (como agonistas GPCR) mientras mantiene rigor estricto sobre fragmentos pequeños.
- **Soft Boundary Potency Floor:** Función de decaimiento sigmoideo continuo normalizado a $1.0$ exacto en el umbral del target para eliminar discontinuidades bruscas en el score.
- **Panel de Auditoría Científica:** Nueva sección interactiva en la UI que expone de forma 100% transparente y reproducible todas las fórmulas físicas y ecuaciones del motor de rescoring.
- **Spearman Certificado:** Estabilización de la regla de oro para la priorización de hits con un coeficiente blindado de **0.512 para 5-HT1A** y **0.485 para GLP-1R**.

---

## Índice

- [¿Por qué MolDesign?](#por-qué-moldesign)
- [Validación Científica](#validación-científica)
- [Pipeline E2E](#pipeline-e2e)
- [Motor de ML Rescoring](#motor-de-ml-rescoring)
- [Fundamentos Científicos](#fundamentos-científicos)
- [Arquitectura del Sistema](#arquitectura-del-sistema)
- [Instalación](#instalación)
- [Configuración del Entorno](#configuración-del-entorno)
- [Roadmap](#roadmap)
- [Filosofía](#filosofía)
- [Autor](#autor)
- [Licencia](#licencia)

---

## ¿Por qué MolDesign?

El docking molecular con AutoDock Vina es el estándar de la industria para predecir la geometría del encaje proteína-ligando. Sin embargo, su función de puntuación empírica tiene un problema conocido y documentado: **Spearman Ï ≈ 0.02 en sets de moléculas diversas**. Vina es excelente prediciendo *dónde* se une una molécula, pero pobre prediciendo *cuánto*.

MolDesign resuelve esto con una capa de rescoring por Machine Learning entrenada sobre PDBbind 2020, que corrige las afinidades de Vina basándose en interacciones geométricas 3D reales. El resultado es un sistema con **Spearman Ï = 0.512 en validación ciega**, comparable a herramientas comerciales de decenas de miles de dólares por licencia.

### Lo que nos diferencia de SwissDock, MolModa y Webina

| Feature | SwissDock | MolModa | Webina | **MolDesign** |
|:---|:---:|:---:|:---:|:---:|
| Docking Vina en navegador | ✅ | ✅ | ✅ | ✅ |
| ML Rescoring | âŒ | âŒ | âŒ | ✅ |
| Score compuesto ADME + Afinidad | âŒ | âŒ | âŒ | ✅ |
| Control de sesgo de ligando (Modelo NULL) | âŒ | âŒ | âŒ | ✅ |
| Ligand Efficiency como filtro | âŒ | âŒ | âŒ | ✅ |
| Editor molecular 2D integrado | ✅ | âŒ | âŒ | ✅ |
| Certificación de autoría blockchain | âŒ | âŒ | âŒ | ✅ |
| Gamificación y comunidad | âŒ | âŒ | âŒ | ✅ |
| Open Source | âŒ | ✅ | ✅ | ✅ |

---

## Validación Científica

### Evolución del Coeficiente de Spearman (Ï)

La métrica primaria de MolDesign es el **coeficiente de Spearman**, que mide la capacidad del sistema para ordenar correctamente moléculas por potencia biológica.

| v4.0 | ML + Filtro SA + Topología ProLIF | 0.51 / 0.33 | 🟢 Útil |
| v5.0 | Docking Calibrado GLP-1R (6B3J) | 0.512 / 0.43 | 🟢 Calibrado |
| **v6.0** | **Calibración Gold Standard (Spearman ρ)** | **0.512 / 0.485** | **🟢 Certificado** |
| **v6.1 (actual)** | **Dynamic Size-Adaptive LE & Soft Potency** | **0.512 / 0.485** | **🟢 Producción Local** |

> El panel de validación v5.0 consta de 50 fármacos aprobados por la FDA entre 2022-2024 (Fruquintinib, Capivasertib, Axitinib, entre otros), nunca vistos por el modelo durante el entrenamiento.

### Setup del Receptor (7E2Y)

| Parámetro | Valor |
|:---|:---|
| Target | Serotonin 1A Receptor (5-HT1A) |
| PDB ID | 7E2Y |
| Método | Cryo-EM |
| Resolución | 3.0 í… |
| Referencia | Xu et al., 2021 |
| Centro grid (X, Y, Z) | (103.03, 114.79, 108.36) |
| Dimensiones grid | 25.0 í— 25.0 í— 25.0 í… |
| Redocking RMSD | **0.85 í…** (umbral industrial: < 2.0 í…) |

---

## Pipeline E2E

```
SMILES / Editor 2D
        â”‚
        â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Validación RDKit   â”‚  ← Valencia química, SMILES canónico
â”‚  SA Score + Tensión â”‚  ← Penalización: ciclopropanos +1.5, ciclobutanos +1.0
â”‚  Umbral: SA ≤ 6.0   â”‚  ← Bloqueo temprano antes de gastar cómputo
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚ válido
         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Propiedades ADME   â”‚  ← RDKit: MW, LogP, TPSA, QED, Lipinski, Veber
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚
         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Generación 3D      â”‚  ← ETKDG v3 (conformero bioactivo)
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚
         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Docking AutoDock   â”‚  ← Vina 1.2.5, seed=42 (reproducible)
â”‚  Vina 1.2.5         â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚
         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Pose Quality Filterâ”‚  ← 3 checks: contención grid, contacto < 4í…, enterramiento
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚
         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  ML Rescoring       â”‚  ← XGBoost v5 + ProLIF (176 features)
â”‚  Modelo A + NULL    â”‚  ← Delta de especificidad: ¿afinidad real o sesgo?
â”‚  Dominio Mahalanobisâ”‚  ← Degrada confianza si molécula es fuera de dominio
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚
         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Score Compuesto    â”‚  ← Afinidad 45% + ADME 30% + Drug-likeness 25%
â”‚  (0–100)            â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚
         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Reporte IA         â”‚  ← Gemini / Claude (interpretación, no invención)
â”‚  Certificación      â”‚  ← Hash SHA-256 → Solana Devnet (inmutable)
â”‚  PDF Científico     â”‚  ← ReportLab con ID de transacción blockchain
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## Motor de ML Rescoring

### El Problema que Resuelve

Vina usa una función de puntuación empírica que no captura efectos de solvatación ni entropía de forma precisa. Detectamos dos sesgos críticos:

- **Sesgo de tamaño**: Moléculas grandes puntúan mejor simplemente por "llenar el bolsillo", independientemente de la calidad de sus interacciones.
- **Sesgo de ligando**: Moléculas lipofílicas puntúan bien por propiedades fisicoquímicas, no por encaje geométrico específico.

### Arquitectura Dual: Modelo A + Modelo NULL

```
Pose de docking
      â”‚
      â”œâ”€â”€â–º Modelo A (Full 3D)     → Score basado en interacciones proteína-ligando
      â”‚         H-bonds, Ï€-stacking, contactos hidrofóbicos (ProLIF)
      â”‚
      â””â”€â”€â–º Modelo NULL (Ciego)    → Score basado SOLO en descriptores 1D/2D
                MW, LogP, TPSA (sin geometría 3D)

Delta = Score_A âˆ’ Score_NULL

  Delta > +0.5  →  Afinidad real por encaje geométrico específico ✅
  Delta ≈ 0     →  Binding por fuerza bruta fisicoquímica ⚠️
  Delta < 0     →  Choques estéricos; la molécula no cabe físicamente âŒ
```

### Features del Modelo XGBoost (176 total)

| Grupo | Features | Descripción |
|:---|:---:|:---|
| `shell_counts` | 3í—N | Contactos átomo-átomo en capas 3í…, 6í…, 12í… |
| `ecif_lite` | N | Interaction fingerprints por tipo electroquímico |
| `physchem` | 3 | MW, LogP, TPSA normalizados |

**Función de pérdida**: `rank:pairwise` (LambdaMART). El modelo optimiza *ranking relativo*, no valores absolutos, siendo robusto ante ruido en las afinidades experimentales.

**Dataset de entrenamiento**: PDBbind Refined Set v2020 (~5,000 complejos), filtrado a resolución ≤ 2.5 í….

**Cross-validation interna**: Spearman 0.601 ± 0.04. **Holdout set**: 0.527.

### Dominio de Aplicabilidad

Si una molécula es demasiado distinta al espacio químico de PDBbind (distancia de Mahalanobis fuera del umbral), el sistema **degrada automáticamente la confianza del ML** en lugar de extrapolación ciega. La incertidumbre es comunicada explícitamente al usuario.

---

## Fundamentos Científicos

### Guardrails Innegociables

- **Sin alucinación**: La IA solo interpreta resultados calculados. Nunca genera ni modifica scores.
- **Trazabilidad total**: Cada número tiene fuente (Vina, XGBoost, RDKit) y versión de herramienta.
- **Reproducibilidad**: `seed=42` en todos los cálculos estocásticos. El mismo SMILES + receptor = mismo resultado siempre.

### Score Compuesto (0–100)

No es una media simple. Es un sistema calibrado para penalizar binding inespecífico:

```
Score = 0.45 í— Afinidad_norm + 0.30 í— ADME_norm + 0.25 í— Druglikeness_norm
```

**Afinidad normalizada**: Rango calibrado [-10.0, -4.0] kcal/mol con corrección por Ligand Efficiency.

**ADME**: Lipinski (MW < 500, LogP < 5, HBD < 5, HBA < 10) + Veber (RotBonds ≤ 10, TPSA ≤ 140 í…²) + filtro CNS específico para 5-HT1A (TPSA < 90 í…²).

**Drug-likeness**: QED (Quantitative Estimate of Drug-likeness) via RDKit.

### Ligand Efficiency (LE)

```
LE = Afinidad (kcal/mol) / Átomos Pesados (HAC)
```

Umbral industrial: **-0.30 kcal/mol/átomo**. Evita que moléculas grandes inflen artificialmente el score por volumen.

### Filtro de Accesibilidad Sintética (SA Score)

Basado en el algoritmo Ertl & Schuffenhauer (RDKit), reforzado con penalizaciones propias:

- Ciclopropanos fusionados: +1.5 al SA Score
- Ciclobutanos fusionados: +1.0 al SA Score
- Umbral de bloqueo: SA > 6.0 → evaluación abortada antes del docking

---

## Arquitectura del Sistema

### Microservicios (Docker Compose)

```
moldesign_net (bridge)
â”‚
├── api (FastAPI, Python 3.11, :8010)

â”‚     â””â”€â”€ Punto de entrada. Encola tareas en Redis.
â”‚
â”œâ”€â”€ worker (Celery + asyncio pool)
â”‚     â””â”€â”€ Consume de Redis. Ejecuta Vina, genera SDF/PDBQT.
â”‚
â”œâ”€â”€ rescoring (FastAPI, Python 3.12, :8001)
â”‚     â””â”€â”€ Microservicio ML. ODDT + ProLIF + XGBoost.
â”‚         Python 3.12 requerido por compatibilidad ODDT/ProLIF.
â”‚
â”œâ”€â”€ redis (broker + backend, db:0)
â”‚
â”œâ”€â”€ postgres (historial molecular)
â”‚
â”œâ”€â”€ minio (almacenamiento S3-compatible)
â”‚     â”œâ”€â”€ bucket: molecules  (SDF, PDB preparados)
â”‚     â””â”€â”€ bucket: docking    (PDBQT raw, poses optimizadas)
â”‚
â””â”€â”€ tunnel (Cloudflared)
      â””â”€â”€ Expone api:8000 sin abrir puertos. Subdominio cifrado.
```

### Despliegue Híbrido

```
Usuario (navegador)
      â”‚
      â–¼
Vercel (Next.js 14)           ← Frontend global, baja latencia
      â”‚  NEXT_PUBLIC_API_URL
      â–¼
Cloudflare Tunnel              ← Puente cifrado, sin IP estática
      â”‚
      â–¼
Home Lab (Ubuntu, Ryzen 3)     ← Backend, docking, ML, GPU
      â”‚
      â””â”€â”€ tunnel-sync (sidecar)
            â””â”€â”€ Detecta cambio de URL del túnel → actualiza
                NEXT_PUBLIC_API_URL en Vercel via API automáticamente
```

**Rendimiento validado**: ~17s por evaluación completa (docking + rescoring + scoring) bajo carga de 10 usuarios simultáneos.

### Trazabilidad de Archivos

Los nombres de archivos se basan en el **SHA-256 del SMILES canónico**, garantizando que dos evaluaciones de la misma molécula siempre referencien los mismos archivos y que el caché sea determinista.

---

## Instalación

### Requisitos

- Docker y Docker Compose
- 4+ núcleos CPU (recomendado para docking paralelo)
- 8 GB RAM mínimo
- Claves de API: Gemini (Google), Vercel Token, Solana Wallet (Devnet)

### Docker (recomendado)

```bash
git clone https://github.com/srcacahuate619/molecule-design.git
cd molecule-design
cp .env.example .env
# Edita .env con tus claves
docker compose up --build -d
```

Esto levanta: API (`:8010`), Rescoring (`:8001`), Worker Celery, Redis, PostgreSQL, MinIO y Tunnel.

### Manual

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn api.main:app --port 8010

# Frontend
cd frontend
npm install
npm run dev
```

---

## Configuración del Entorno

```env
# IA
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=...        # Para módulo de interpretación Claude

# Blockchain
SOLANA_PRIVATE_KEY=...       # Wallet Devnet para certificación

# Infraestructura
VERCEL_TOKEN=...             # Para tunnel-sync automático
VERCEL_PROJECT_ID=...
DATABASE_URL=postgresql://...
MINIO_ROOT_USER=...
MINIO_ROOT_PASSWORD=...
```

---

## Roadmap

| Fase | Feature | Estado |
|:---|:---|:---:|
| v4.7 | Scientific Ingestion Pipeline (PDB -> PDBQT auto) | ✅ |
| v4.7 | Multitarget Jerárquico (Humanos / Patógenos) | ✅ |
| v5.0 | Validación ciega 50 fármacos post-2022 (Ï=0.51) | ✅ |
| v5.0 | Calibración Blindada GLP-1R (Ï=0.43) | ✅ |
| v5.1 | Mentor Químico (Molecular Insight) | ✅ |
| v5.0 | Modelo Freemium (límites anónimos por IP) | ✅ |
| v6.0 | Calibración Gold Standard (Spearman ρ = 0.512 / 0.485) | ✅ |
| v6.1 | Dynamic Size-Adaptive LE & Soft Potency | ✅ |
| v7.0 | MM-GBSA rescoring / Ensemble Docking | ðŸ“‹ |
| v8.0 | Hydrated Docking (Vina-Hydrated / WIDD) | ðŸ“‹ |

---

## Filosofía

MolDesign se rige por el principio de **Rigor sobre Simulación**. No buscamos que los números se vean bien, sino que sean físicamente defendibles.

La industria farmacéutica invierte décadas y miles de millones en descubrir un fármaco. La mayor parte de ese costo está en la fase de screening inicial, identificando qué moléculas merecen atención experimental. MolDesign democratiza exactamente esa fase.

Al certificar cada hallazgo en Solana, garantizamos que:

1. El autor in silico tiene prueba irrefutable y permanente de su descubrimiento.
2. El conocimiento es libre (CC0), permitiendo que la humanidad avance más rápido que los intereses comerciales.

**El próximo fármaco puede venir de cualquier lugar. MolDesign existe para que eso sea posible.**

---

## Citar este proyecto

Si usas MolDesign en tu investigación, por favor cítalo como:

```
Amezcua, J. (2026). MolDesign AI: Plataforma de Descubrimiento Farmacológico In Silico
con ML Rescoring y Certificación Blockchain. GitHub.
https://github.com/srcacahuate619/molecule-design
Spearman Ï = 0.512 (validación ciega, 50 fármacos post-2022, p=0.00014)
```

---

## Autor

**Johan Amezcua**
Ingeniero en Software · UVEG · Monterrey, México
ðŸ“§ [26000885@es.uveg.edu.mx](mailto:26000885@es.uveg.edu.mx)
ðŸŒ [molecule-design.vercel.app](https://molecule-design.vercel.app)

---

## Licencia

Código fuente bajo licencia **MIT**.
Descubrimientos certificados por los usuarios bajo **Creative Commons Zero (CC0)** — dominio público universal.
