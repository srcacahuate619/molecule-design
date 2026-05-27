# MolDesign AI 🧬

**Plataforma de Descubrimiento Farmacológico In Silico — Docking Físico · ML Rescoring · Certificación Blockchain**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)]()
[![Next.js: 14](https://img.shields.io/badge/Next.js-14-black.svg)]()
[![Solana: Devnet](https://img.shields.io/badge/Blockchain-Solana_Devnet-purple.svg)]()
[![Spearman ρ: 0.33](https://img.shields.io/badge/Spearman_%CF%81_blind-0.33-brightgreen.svg)]()
[![ML Features: 176](https://img.shields.io/badge/XGBoost_features-176-orange.svg)]()

> *"Democratizando el diseño de fármacos mediante rigor científico, transparencia total y registro inmutable de autoría."*

**MolDesign AI** es una plataforma *Open Science* para el cribado virtual de moléculas contra blancos biológicos de relevancia terapéutica. Combina un pipeline de **docking físico real** (AutoDock Vina), **rescoring por Machine Learning** (XGBoost, 176 features 3D), **auditoría científica profunda** (LE, LLE, Hotspot Analysis) y **certificación inmutable de autoría** en la blockchain de Solana. Los resultados completos se exportan como **Reporte Científico PDF** generado automáticamente.

El módulo **Moldex** sirve como la interfaz principal de evaluación y registro histórico de moléculas.

---

## Índice

- [¿Por qué MolDesign?](#por-qué-moldesign)
- [Receptores Disponibles](#receptores-disponibles)
- [Pipeline Completo](#pipeline-completo)
- [Motor de ML Rescoring](#motor-de-ml-rescoring)
- [Validación Científica](#validación-científica)
- [Reporte Científico PDF](#reporte-científico-pdf)
- [Arquitectura del Sistema](#arquitectura-del-sistema)
- [Instalación](#instalación)
- [Variables de Entorno](#variables-de-entorno)
- [Roadmap Técnico](#roadmap-técnico)
- [Filosofía](#filosofía)
- [Autor](#autor)
- [Licencia](#licencia)

---

## ¿Por qué MolDesign?

AutoDock Vina es el estándar industrial para predecir *dónde* se une una molécula a un receptor. Su limitación conocida: **Spearman ρ ≈ 0.02** en sets de moléculas diversas al predecir *cuánto* se une. Es excelente en geometría, pobre en termodinámica.

MolDesign resuelve esto con:

1. **ML Rescoring sobre PDBbind 2020**: XGBoost entrenado con 3,019 complejos proteína-ligando, 176 features que capturan interacciones geométricas 3D reales (shell counts, ECIF-lite, ProLIF).
2. **Control dual Modelo A + NULL**: Detecta si la afinidad proviene de encaje geométrico específico o de propiedades fisicoquímicas brutas.
3. **Score compuesto auditable**: Ponderación documentada Afinidad 45% + ADME 30% + Drug-likeness 25%.
4. **Dominio de aplicabilidad**: Distancia de Mahalanobis — degrada la confianza si la molécula está fuera del espacio químico de entrenamiento, en lugar de extrapolar ciegamente.

### Comparativa con herramientas públicas

| Feature | SwissDock | MolModa | Webina | **MolDesign** |
|:---|:---:|:---:|:---:|:---:|
| Docking Vina real | ✅ | ✅ | ✅ | ✅ |
| ML Rescoring 3D | ❌ | ❌ | ❌ | ✅ |
| Score compuesto ADME + Afinidad | ❌ | ❌ | ❌ | ✅ |
| Control sesgo (Modelo NULL) | ❌ | ❌ | ❌ | ✅ |
| Ligand Efficiency + LLE | ❌ | ❌ | ❌ | ✅ |
| Análisis de Hotspots (residuos clave) | ❌ | ❌ | ❌ | ✅ |
| Reporte PDF científico automático | ❌ | ❌ | ❌ | ✅ |
| Certificación de autoría blockchain | ❌ | ❌ | ❌ | ✅ |
| Visor 3D interactivo (mapa de cargas, H-bonds) | ❌ | ✅ | ❌ | ✅ |
| Multi-target (varios receptores) | ❌ | ❌ | ❌ | ✅ |
| Open Source | ❌ | ✅ | ✅ | ✅ |

---

## Receptores Disponibles

La plataforma soporta múltiples targets, cada uno con su grid box calibrado individualmente y hotspots definidos desde estructuras cristalográficas del PDB:

| Receptor | PDB ID | Relevancia Terapéutica | Método Cristalográfico |
|:---|:---:|:---|:---:|
| **5-HT1A Serotonin Receptor** | 7E2Y | Ansiedad, depresión, esquizofrenia | Cryo-EM, 3.0 Å |
| **GLP-1 Receptor** | 6B3J | Diabetes tipo 2, obesidad | Cryo-EM |
| **PCSK9** | 2P4E | Hipercolesterolemia, ECV | X-ray |
| **PCSK9 (Alostérico)** | 6U26 | Sitio alostérico alternativo | X-ray |
| **CTLA-4** | 3OSK | Inmuno-oncología, checkpoint | X-ray |

Nuevos receptores se integran mediante el pipeline de ingestión automática: `insert_target_{pdb_id}.py` + PDBQT preparado.

---

## Pipeline Completo

```
SMILES / Editor Molecular 2D (Ketcher)
        │
        ▼
┌─────────────────────────────────┐
│  Validación Química (RDKit)     │  ← Valencias, SMILES canónico, quiralidad
│  SA Score + Tensión de Anillo   │  ← Ciclopropanos +1.5, ciclobutanos +1.0
│  Filtros: Lipinski + Veber      │  ← Bloqueo antes de gastar cómputo
│  Umbral de bloqueo: SA > 6.0    │
└────────────┬────────────────────┘
             │ válido
             ▼
┌─────────────────────────────────┐
│  Propiedades ADME (RDKit)       │  ← MW, LogP, TPSA, QED, HBD, HBA,
│                                 │     RotBonds, RingCount, HeavyAtomCount
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  Generación Conformero 3D       │  ← ETKDG v3 (geometría bioactiva de baja energía)
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  Docking AutoDock Vina 1.2.5    │  ← seed=42 (reproducible), grid box por receptor
│  (Celery Worker, asíncrono)     │  ← ~15-20s de cómputo real en servidor
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  Filtro de Calidad de Pose      │  ← Contención en grid, contacto < 4Å,
│                                 │     factor de enterramiento
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  ML Rescoring (XGBoost v4)      │  ← 176 features: shell counts (3D) +
│  Modelo A (3D) + NULL (1D/2D)   │     ECIF-lite + ProLIF fingerprints
│  Dominio de Applicabilidad      │  ← Mahalanobis p99 = 7.2365
│  Delta de Especificidad         │  ← A − NULL: ¿binding real o bruto?
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  Auditoría Científica           │  ← Ligand Efficiency (LE), LLE
│  Análisis de Hotspots           │  ← Residuos activos < 4Å hit/miss
│  Score Compuesto (0–100)        │  ← 45% Afinidad + 30% ADME + 25% QED
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  Interpretación IA (Gemini)     │  ← Solo interpreta; nunca inventa números
│  Certificación Blockchain       │  ← SHA-256 → Solana Devnet (tx permanente)
│  Reporte Científico PDF         │  ← Descripción del receptor (PDB+UniProt+ES),
│                                 │     todas las métricas calculadas, firma blockchain
└─────────────────────────────────┘
```

> **Nota de latencia**: El System Monitor muestra ~48ms de respuesta de API (tiempo de lectura de PostgreSQL/Redis). El tiempo de cómputo real del docking es 15–20s en el worker de Celery. Los parámetros del grid box para cada receptor están en `docs/HOTSPOTS_SYSTEM.md`.

---

## Motor de ML Rescoring

### Arquitectura Dual: Modelo A + Modelo NULL

```
Pose de docking
      │
      ├──► Modelo A (Full 3D)    → Score basado en interacciones P-L reales
      │         H-bonds, π-stacking, contactos hidrofóbicos (ProLIF)
      │         Shell counts átomo-átomo en capas 3Å / 6Å / 12Å
      │         ECIF-lite: fingerprints de pares electroquímicos
      │
      └──► Modelo NULL (Ciego)   → Score basado SOLO en descriptores 1D/2D
                MW, LogP, TPSA (sin geometría 3D)

Delta = Score_A − Score_NULL

  Delta > +0.5  →  Binding real por encaje geométrico específico ✅
  Delta ≈ 0     →  Binding por propiedades fisicoquímicas brutas  ⚠️
  Delta < 0     →  Choques estéricos; la molécula no cabe          ❌
```

### Features (176 total)

| Grupo | Cantidad | Descripción |
|:---|:---:|:---|
| `shell_counts` (RF-Score) | 96 | Contactos C-C, C-N, C-O, etc. en capas de 3/6/12 Å |
| `ecif_lite` | 56 | Interaction fingerprints por tipo electroquímico a 6Å |
| `physchem` | 3 | MW, LogP, TPSA normalizados |
| `vina_raw` | 21 | Componentes internos de la función de score de Vina |

**Función de pérdida**: `rank:pairwise` (LambdaMART). Optimiza ranking relativo, robusto ante ruido en afinidades experimentales.

**Dataset**: PDBbind Refined Set v2020 · 3,019 complejos · resolución ≤ 2.5 Å · scaffold-split reproducible (seed=42).

### Métricas del Modelo Entrenado

| Métrica | Valor |
|:---|:---|
| Spearman CV (interno) | **0.601 ± 0.040** |
| Spearman Holdout (scaffold-split) | **0.527** |
| Spearman Validación Ciega (panel externo 40 moléculas) | **0.33** (p < 0.05) |
| Vina solo (mismo panel) | -0.14 |
| NDCG@10 CV | **0.609 ± 0.065** |
| RMSE CV | **2.031 ± 0.098** kcal/mol |
| Top SHAP features | shell_C_C_8_12, mw, ecif_O_acc_C, ecif_C_aro_O |

---

## Validación Científica

### Receptor 5-HT1A (7E2Y)

| Parámetro | Valor |
|:---|:---|
| Target | Serotonin 1A Receptor (5-HT1A) |
| PDB ID | 7E2Y |
| Método | Cryo-EM · 3.0 Å |
| Referencia | Xu et al., 2021 |
| Centro grid (X, Y, Z) | (103.03, 114.79, 108.36) |
| Dimensiones grid | 25.0 × 25.0 × 25.0 Å |
| Hotspots definidos | ASP116, VAL117, SER190, PHE361 |
| Redocking RMSD | **0.85 Å** (umbral industrial: < 2.0 Å ✅) |

### Evolución del Spearman ρ

| Versión | Descripción | ρ (interno/externo) |
|:---|:---|:---:|
| v1 baseline | Solo MW | 0.275 / — |
| v3 ProLIF | ProLIF 2.1.0, RDKit-direct | 0.435 / — |
| v4 (actual) | +RF-Score shells + ECIF + MW norm | 0.601 / **0.33** |
| v5 (Fase 6.1) | +GNINA CNN rescoring 3D | *target: 0.50–0.65* |

El coeficiente de validación ciega (**ρ = 0.33**, p < 0.05) fue calculado sobre un panel de 40 moléculas con actividad experimental medida en 5-HT1A, **nunca vistas por el modelo durante el entrenamiento**. Vina sola en el mismo panel: ρ = −0.14.

---

## Reporte Científico PDF

Al completar una evaluación, el usuario puede descargar un reporte PDF que incluye:

- **Descripción del receptor**: Generada automáticamente desde PDB → UniProt → traducida al español con `deep-translator`. Sin tokens de pago ni modelos de lenguaje externos. Funciona para cualquier receptor del PDB.
- **Todas las métricas calculadas**: Afinidad Vina, ML score, LE, LLE, QED, SA, ADME completo, hotspots hit/miss, especificidad, score compuesto con breakdown por componente.
- **Firma blockchain**: Hash SHA-256 + ID de transacción en Solana Devnet.
- **Aviso de limitaciones metodológicas**: Proteína rígida, dominio de aplicabilidad, incertidumbre del modelo.

---

## Arquitectura del Sistema

### Microservicios (Docker Compose)

```
├── moldesign_api      (FastAPI, Python 3.11, :8010)
│     └── Punto de entrada. Autenticación JWT. Encola tareas en Redis (Celery).
│
├── moldesign_worker   (Celery + asyncio, mismo código que API)
│     └── Consume de Redis. Ejecuta Vina, ProLIF, XGBoost, Blockchain, PDF.
│
├── moldesign_rescoring (FastAPI, Python 3.12, :8001)
│     └── Microservicio ML independiente (Python 3.12 requerido por ProLIF).
│
├── moldesign_frontend (Node 20 Alpine, Next.js 14, :3001)
│     └── UI React. Modo dev con hot-reload en contenedor Docker.
│
├── redis              Broker Celery + caché de resultados
├── postgres           Historial molecular, usuarios, targets, evaluaciones
├── minio              Almacenamiento S3-compatible (SDF, PDBQT, poses)
└── ngrok              Túnel seguro para exponer la API al frontend en Vercel
```

### Despliegue Actual

```
Usuario (navegador)
      │
      ▼
Vercel (Next.js 14)          ← Frontend global
      │  NEXT_PUBLIC_API_URL  
      ▼
ngrok tunnel                 ← Túnel cifrado sin IP estática
      │
      ▼
Ubuntu Server (Ryzen 3)      ← Backend + Celery + ML + Blockchain + PDF
      │
      └── Docker Compose (API + Worker + Rescoring + Redis + PostgreSQL + MinIO)
```

**Rendimiento**: ~17s por evaluación completa bajo carga de 10 usuarios simultáneos.

### Nombrado de Moléculas (Target-Based)

```
MDX-{PDB_ID}-{SMILES_HASH[:4]}
Ejemplo: MDX-7E2Y-a3f1
```

### Trazabilidad

- Cada número tiene fuente explícita: `Vina 1.2.5`, `XGBoost v4`, `RDKit 2024`.
- `seed=42` en todos los cálculos estocásticos → mismo SMILES + receptor = mismo resultado siempre.
- Archivos nombrados por SHA-256 del SMILES canónico → caché determinista.
- Cada evaluación certificada tiene `blockchain_tx_id` permanente en Solana Devnet.

---

## Instalación

### Requisitos

- Docker y Docker Compose
- 4+ núcleos CPU (recomendado para docking)
- 8 GB RAM mínimo
- AutoDock Vina 1.2.5 (incluido en el Dockerfile del backend)

### Docker (recomendado)

```bash
git clone https://github.com/srcacahuate619/molecule-design.git
cd molecule-design
cp .env.example .env
# Editar .env con tus claves
docker compose --profile dev up --build -d
```

Levanta: API (`:8010`) · Rescoring (`:8001`) · Worker Celery · Frontend (`:3001`) · Redis · PostgreSQL · MinIO · ngrok.

### Manual (desarrollo local)

```bash
# Backend
cd backend
pip install micromamba  # o conda
micromamba env create -f environment.yml
uvicorn api.main:app --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

---

## Variables de Entorno

```env
# Base de datos
DATABASE_URL=postgresql://user:password@host/moldesign

# Redis (broker Celery)
REDIS_URL=redis://localhost:6379/0

# MinIO (almacenamiento de archivos moleculares)
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=...
MINIO_SECRET_KEY=...

# IA (interpretación de resultados)
GEMINI_API_KEY=...           # Gemini para reportes narrativos
ANTHROPIC_API_KEY=...        # Claude (alternativo)

# Blockchain (certificación de autoría)
SOLANA_PRIVATE_KEY=...       # Wallet Devnet en formato base58

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8010
```

---

## Roadmap Técnico

| Fase | Feature | Estado |
|:---|:---|:---:|
| v4.0 | Pipeline E2E: Vina + XGBoost + ADME + Blockchain | ✅ |
| v4.7 | Multi-target + pipeline de ingestión automática de PDB | ✅ |
| v5.0 | Validación ciega 40 moléculas · ρ=0.33 vs Vina ρ=−0.14 | ✅ |
| v5.1 | Mentor Químico (MolecularInsight) · Árbol evolutivo | ✅ |
| v5.2 | Rebranding Moldex · Auditoría científica profunda (LE, LLE) | ✅ |
| v6.0 | PDF Científico automático · Descripción dinámica UniProt/PDB | ✅ |
| v6.1 | Integración GNINA (rescoring 3D CNN) | 📋 |
| v6.2 | 3D-RISM desolvatación (AmberTools) | 📋 |
| v6.3 | Flexibilidad proteica (ensemble docking, requiere GPU) | 🔬 |

Ver detalles técnicos en [`docs/MVP_ROADMAP.md`](docs/MVP_ROADMAP.md) — Sección 16 (Fase 6.0).

---

## Filosofía

MolDesign se rige por el principio de **Rigor sobre Simulación**. No buscamos que los números se vean impresionantes; buscamos que sean físicamente defendibles y científicamente honestos.

- **Sin alucinación**: La IA solo interpreta los números que el pipeline calculó. Nunca los genera ni modifica.
- **Limitaciones visibles**: El sistema muestra explícitamente advertencias sobre proteína rígida, dominio de aplicabilidad y naturaleza in silico de los resultados.
- **Open Science**: Todos los hallazgos certificados quedan bajo licencia CC0 (dominio público). El conocimiento es libre; la autoría es inmutable.

> *El próximo fármaco puede venir de cualquier lugar. MolDesign existe para que eso sea posible.*

---

## Citar este proyecto

```
Amezcua, J. (2026). MolDesign AI: Plataforma de Descubrimiento Farmacológico In Silico
con ML Rescoring y Certificación Blockchain.
https://github.com/srcacahuate619/molecule-design
Spearman ρ = 0.33 (validación ciega, 40 moléculas 5-HT1A, p < 0.05)
```

---

## Autor

**Johan Amezcua**  
Ingeniero en Software · UVEG · Monterrey, México  
📧 [26000885@es.uveg.edu.mx](mailto:26000885@es.uveg.edu.mx)  
🌐 [molecule-design.vercel.app](https://molecule-design.vercel.app)

---

## Licencia

Código fuente bajo licencia **MIT**.  
Descubrimientos certificados por los usuarios bajo **Creative Commons Zero (CC0)** — dominio público universal.
