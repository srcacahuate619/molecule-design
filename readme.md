# MolDesign AI ðŸ§¬

**Plataforma de Descubrimiento FarmacolÃ³gico In Silico con Rescoring por ML, Rigor Industrial y CertificaciÃ³n Blockchain.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)]()
[![Next.js: 14](https://img.shields.io/badge/Next.js-14-black.svg)]()
[![Solana: Devnet](https://img.shields.io/badge/Blockchain-Solana_Devnet-purple.svg)]()
[![Spearman Ï: 0.512](https://img.shields.io/badge/Spearman_%CF%81_blind-0.512-brightgreen.svg)]()
[![Redocking RMSD: 0.85Ã…](https://img.shields.io/badge/Redocking_RMSD-0.85_Ã…-brightgreen.svg)]()

> *"Democratizando la creaciÃ³n de fÃ¡rmacos mediante el rigor de la ciencia computacional."*

MolDesign es una plataforma *Open Science* que permite a cualquier persona â€” desde un estudiante de quÃ­mica hasta un investigador independiente â€” diseÃ±ar y evaluar molÃ©culas contra blancos biolÃ³gicos reales, utilizando los mismos estÃ¡ndares que la industria farmacÃ©utica. Cada hallazgo queda certificado de forma inmutable en la blockchain de Solana, otorgando reconocimiento permanente al **creador in silico**.

### Novedades v4.7.2: Ã‰xito en CalibraciÃ³n GLP-1R
La plataforma ha alcanzado un nuevo hito de precisiÃ³n cientÃ­fica. Mediante una prueba de Spearman blindada contra el receptor **GLP-1R (6B3J)**, el motor de docking demostrÃ³ una correlaciÃ³n de **0.43**, validando la arquitectura de descubrimiento automÃ¡tico de pockets y hotspots.

**Highlights Recientes:**
- **CalibraciÃ³n Blindada:** Ã‰xito en el receptor GLP-1R con Spearman Ï = 0.43 (baseline Vina-only).
- **SincronizaciÃ³n de Grid:** CorrecciÃ³n y validaciÃ³n de coordenadas crÃ­ticas (`93.2, 148.1, 103.3`) para targets GPCR.
- **Scientific Ingestion:** Descubrimiento automÃ¡tico de pockets basado en ligandos co-cristalizados.
- **Remote Scaling:** EjecuciÃ³n distribuida en servidor Ryzen 3 (Ubuntu) con soporte para dockings de alta exhaustividad (timeout 600s).

---

## Ãndice

- [Â¿Por quÃ© MolDesign?](#por-quÃ©-moldesign)
- [ValidaciÃ³n CientÃ­fica](#validaciÃ³n-cientÃ­fica)
- [Pipeline E2E](#pipeline-e2e)
- [Motor de ML Rescoring](#motor-de-ml-rescoring)
- [Fundamentos CientÃ­ficos](#fundamentos-cientÃ­ficos)
- [Arquitectura del Sistema](#arquitectura-del-sistema)
- [InstalaciÃ³n](#instalaciÃ³n)
- [ConfiguraciÃ³n del Entorno](#configuraciÃ³n-del-entorno)
- [Roadmap](#roadmap)
- [FilosofÃ­a](#filosofÃ­a)
- [Autor](#autor)
- [Licencia](#licencia)

---

## Â¿Por quÃ© MolDesign?

El docking molecular con AutoDock Vina es el estÃ¡ndar de la industria para predecir la geometrÃ­a del encaje proteÃ­na-ligando. Sin embargo, su funciÃ³n de puntuaciÃ³n empÃ­rica tiene un problema conocido y documentado: **Spearman Ï â‰ˆ 0.02 en sets de molÃ©culas diversas**. Vina es excelente prediciendo *dÃ³nde* se une una molÃ©cula, pero pobre prediciendo *cuÃ¡nto*.

MolDesign resuelve esto con una capa de rescoring por Machine Learning entrenada sobre PDBbind 2020, que corrige las afinidades de Vina basÃ¡ndose en interacciones geomÃ©tricas 3D reales. El resultado es un sistema con **Spearman Ï = 0.512 en validaciÃ³n ciega**, comparable a herramientas comerciales de decenas de miles de dÃ³lares por licencia.

### Lo que nos diferencia de SwissDock, MolModa y Webina

| Feature | SwissDock | MolModa | Webina | **MolDesign** |
|:---|:---:|:---:|:---:|:---:|
| Docking Vina en navegador | âœ… | âœ… | âœ… | âœ… |
| ML Rescoring | âŒ | âŒ | âŒ | âœ… |
| Score compuesto ADME + Afinidad | âŒ | âŒ | âŒ | âœ… |
| Control de sesgo de ligando (Modelo NULL) | âŒ | âŒ | âŒ | âœ… |
| Ligand Efficiency como filtro | âŒ | âŒ | âŒ | âœ… |
| Editor molecular 2D integrado | âœ… | âŒ | âŒ | âœ… |
| CertificaciÃ³n de autorÃ­a blockchain | âŒ | âŒ | âŒ | âœ… |
| GamificaciÃ³n y comunidad | âŒ | âŒ | âŒ | âœ… |
| Open Source | âŒ | âœ… | âœ… | âœ… |

---

## ValidaciÃ³n CientÃ­fica

### EvoluciÃ³n del Coeficiente de Spearman (Ï)

La mÃ©trica primaria de MolDesign es el **coeficiente de Spearman**, que mide la capacidad del sistema para ordenar correctamente molÃ©culas por potencia biolÃ³gica.

| v4.0 | ML + Filtro SA + TopologÃ­a ProLIF | 0.33 | ðŸŸ¢ Ãštil |
| v5.0 | **ML Rescoring** (50 fÃ¡rmacos post-2022) | **0.51** | **ðŸŸ¢ ProducciÃ³n** |
| **v5.1 (actual)** | **Docking Baseline GLP-1R (6B3J)** | **0.43** | **ðŸŸ¢ Calibrado** |

> El panel de validaciÃ³n v5.0 consta de 50 fÃ¡rmacos aprobados por la FDA entre 2022-2024 (Fruquintinib, Capivasertib, Axitinib, entre otros), nunca vistos por el modelo durante el entrenamiento.

### Setup del Receptor (7E2Y)

| ParÃ¡metro | Valor |
|:---|:---|
| Target | Serotonin 1A Receptor (5-HT1A) |
| PDB ID | 7E2Y |
| MÃ©todo | Cryo-EM |
| ResoluciÃ³n | 3.0 Ã… |
| Referencia | Xu et al., 2021 |
| Centro grid (X, Y, Z) | (103.03, 114.79, 108.36) |
| Dimensiones grid | 25.0 Ã— 25.0 Ã— 25.0 Ã… |
| Redocking RMSD | **0.85 Ã…** (umbral industrial: < 2.0 Ã…) |

---

## Pipeline E2E

```
SMILES / Editor 2D
        â”‚
        â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  ValidaciÃ³n RDKit   â”‚  â† Valencia quÃ­mica, SMILES canÃ³nico
â”‚  SA Score + TensiÃ³n â”‚  â† PenalizaciÃ³n: ciclopropanos +1.5, ciclobutanos +1.0
â”‚  Umbral: SA â‰¤ 6.0   â”‚  â† Bloqueo temprano antes de gastar cÃ³mputo
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚ vÃ¡lido
         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Propiedades ADME   â”‚  â† RDKit: MW, LogP, TPSA, QED, Lipinski, Veber
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚
         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  GeneraciÃ³n 3D      â”‚  â† ETKDG v3 (conformero bioactivo)
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚
         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Docking AutoDock   â”‚  â† Vina 1.2.5, seed=42 (reproducible)
â”‚  Vina 1.2.5         â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚
         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Pose Quality Filterâ”‚  â† 3 checks: contenciÃ³n grid, contacto < 4Ã…, enterramiento
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚
         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  ML Rescoring       â”‚  â† XGBoost v5 + ProLIF (176 features)
â”‚  Modelo A + NULL    â”‚  â† Delta de especificidad: Â¿afinidad real o sesgo?
â”‚  Dominio Mahalanobisâ”‚  â† Degrada confianza si molÃ©cula es fuera de dominio
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚
         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Score Compuesto    â”‚  â† Afinidad 45% + ADME 30% + Drug-likeness 25%
â”‚  (0â€“100)            â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
         â”‚
         â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  Reporte IA         â”‚  â† Gemini / Claude (interpretaciÃ³n, no invenciÃ³n)
â”‚  CertificaciÃ³n      â”‚  â† Hash SHA-256 â†’ Solana Devnet (inmutable)
â”‚  PDF CientÃ­fico     â”‚  â† ReportLab con ID de transacciÃ³n blockchain
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## Motor de ML Rescoring

### El Problema que Resuelve

Vina usa una funciÃ³n de puntuaciÃ³n empÃ­rica que no captura efectos de solvataciÃ³n ni entropÃ­a de forma precisa. Detectamos dos sesgos crÃ­ticos:

- **Sesgo de tamaÃ±o**: MolÃ©culas grandes puntÃºan mejor simplemente por "llenar el bolsillo", independientemente de la calidad de sus interacciones.
- **Sesgo de ligando**: MolÃ©culas lipofÃ­licas puntÃºan bien por propiedades fisicoquÃ­micas, no por encaje geomÃ©trico especÃ­fico.

### Arquitectura Dual: Modelo A + Modelo NULL

```
Pose de docking
      â”‚
      â”œâ”€â”€â–º Modelo A (Full 3D)     â†’ Score basado en interacciones proteÃ­na-ligando
      â”‚         H-bonds, Ï€-stacking, contactos hidrofÃ³bicos (ProLIF)
      â”‚
      â””â”€â”€â–º Modelo NULL (Ciego)    â†’ Score basado SOLO en descriptores 1D/2D
                MW, LogP, TPSA (sin geometrÃ­a 3D)

Delta = Score_A âˆ’ Score_NULL

  Delta > +0.5  â†’  Afinidad real por encaje geomÃ©trico especÃ­fico âœ…
  Delta â‰ˆ 0     â†’  Binding por fuerza bruta fisicoquÃ­mica âš ï¸
  Delta < 0     â†’  Choques estÃ©ricos; la molÃ©cula no cabe fÃ­sicamente âŒ
```

### Features del Modelo XGBoost (176 total)

| Grupo | Features | DescripciÃ³n |
|:---|:---:|:---|
| `shell_counts` | 3Ã—N | Contactos Ã¡tomo-Ã¡tomo en capas 3Ã…, 6Ã…, 12Ã… |
| `ecif_lite` | N | Interaction fingerprints por tipo electroquÃ­mico |
| `physchem` | 3 | MW, LogP, TPSA normalizados |

**FunciÃ³n de pÃ©rdida**: `rank:pairwise` (LambdaMART). El modelo optimiza *ranking relativo*, no valores absolutos, siendo robusto ante ruido en las afinidades experimentales.

**Dataset de entrenamiento**: PDBbind Refined Set v2020 (~5,000 complejos), filtrado a resoluciÃ³n â‰¤ 2.5 Ã….

**Cross-validation interna**: Spearman 0.601 Â± 0.04. **Holdout set**: 0.527.

### Dominio de Aplicabilidad

Si una molÃ©cula es demasiado distinta al espacio quÃ­mico de PDBbind (distancia de Mahalanobis fuera del umbral), el sistema **degrada automÃ¡ticamente la confianza del ML** en lugar de extrapolaciÃ³n ciega. La incertidumbre es comunicada explÃ­citamente al usuario.

---

## Fundamentos CientÃ­ficos

### Guardrails Innegociables

- **Sin alucinaciÃ³n**: La IA solo interpreta resultados calculados. Nunca genera ni modifica scores.
- **Trazabilidad total**: Cada nÃºmero tiene fuente (Vina, XGBoost, RDKit) y versiÃ³n de herramienta.
- **Reproducibilidad**: `seed=42` en todos los cÃ¡lculos estocÃ¡sticos. El mismo SMILES + receptor = mismo resultado siempre.

### Score Compuesto (0â€“100)

No es una media simple. Es un sistema calibrado para penalizar binding inespecÃ­fico:

```
Score = 0.45 Ã— Afinidad_norm + 0.30 Ã— ADME_norm + 0.25 Ã— Druglikeness_norm
```

**Afinidad normalizada**: Rango calibrado [-10.0, -4.0] kcal/mol con correcciÃ³n por Ligand Efficiency.

**ADME**: Lipinski (MW < 500, LogP < 5, HBD < 5, HBA < 10) + Veber (RotBonds â‰¤ 10, TPSA â‰¤ 140 Ã…Â²) + filtro CNS especÃ­fico para 5-HT1A (TPSA < 90 Ã…Â²).

**Drug-likeness**: QED (Quantitative Estimate of Drug-likeness) via RDKit.

### Ligand Efficiency (LE)

```
LE = Afinidad (kcal/mol) / Ãtomos Pesados (HAC)
```

Umbral industrial: **-0.30 kcal/mol/Ã¡tomo**. Evita que molÃ©culas grandes inflen artificialmente el score por volumen.

### Filtro de Accesibilidad SintÃ©tica (SA Score)

Basado en el algoritmo Ertl & Schuffenhauer (RDKit), reforzado con penalizaciones propias:

- Ciclopropanos fusionados: +1.5 al SA Score
- Ciclobutanos fusionados: +1.0 al SA Score
- Umbral de bloqueo: SA > 6.0 â†’ evaluaciÃ³n abortada antes del docking

---

## Arquitectura del Sistema

### Microservicios (Docker Compose)

```
moldesign_net (bridge)
â”‚
â”œâ”€â”€ api (FastAPI, Python 3.14, :8010)
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

### Despliegue HÃ­brido

```
Usuario (navegador)
      â”‚
      â–¼
Vercel (Next.js 14)           â† Frontend global, baja latencia
      â”‚  NEXT_PUBLIC_API_URL
      â–¼
Cloudflare Tunnel              â† Puente cifrado, sin IP estÃ¡tica
      â”‚
      â–¼
Home Lab (Ubuntu, Ryzen 3)     â† Backend, docking, ML, GPU
      â”‚
      â””â”€â”€ tunnel-sync (sidecar)
            â””â”€â”€ Detecta cambio de URL del tÃºnel â†’ actualiza
                NEXT_PUBLIC_API_URL en Vercel via API automÃ¡ticamente
```

**Rendimiento validado**: ~17s por evaluaciÃ³n completa (docking + rescoring + scoring) bajo carga de 10 usuarios simultÃ¡neos.

### Trazabilidad de Archivos

Los nombres de archivos se basan en el **SHA-256 del SMILES canÃ³nico**, garantizando que dos evaluaciones de la misma molÃ©cula siempre referencien los mismos archivos y que el cachÃ© sea determinista.

---

## InstalaciÃ³n

### Requisitos

- Docker y Docker Compose
- 4+ nÃºcleos CPU (recomendado para docking paralelo)
- 8 GB RAM mÃ­nimo
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

## ConfiguraciÃ³n del Entorno

```env
# IA
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=...        # Para mÃ³dulo de interpretaciÃ³n Claude

# Blockchain
SOLANA_PRIVATE_KEY=...       # Wallet Devnet para certificaciÃ³n

# Infraestructura
VERCEL_TOKEN=...             # Para tunnel-sync automÃ¡tico
VERCEL_PROJECT_ID=...
DATABASE_URL=postgresql://...
MINIO_ROOT_USER=...
MINIO_ROOT_PASSWORD=...
```

---

## Roadmap

| Fase | Feature | Estado |
|:---|:---|:---:|
| v4.7 | Scientific Ingestion Pipeline (PDB -> PDBQT auto) | âœ… |
| v4.7 | Multitarget JerÃ¡rquico (Humanos / PatÃ³genos) | âœ… |
| v5.0 | ValidaciÃ³n ciega 50 fÃ¡rmacos post-2022 (Ï=0.51) | âœ… |
| v5.0 | CalibraciÃ³n Blindada GLP-1R (Ï=0.43) | âœ… |
| v5.1 | Mentor QuÃ­mico (Molecular Insight) | âœ… |
| v5.0 | Modelo Freemium (lÃ­mites anÃ³nimos por IP) | âœ… |
| v5.1 | Feature Asp114 como interacciÃ³n obligatoria 5-HT1A | ðŸ”„ |
| v5.2 | MM-GBSA rescoring con AmberTools | ðŸ“‹ |
| v6.0 | GNN / Point Cloud rescoring | ðŸ“‹ |
| v6.0 | Ensemble docking (receptor flexible) | ðŸ“‹ |
| v7.0 | Hydrated Docking (Vina-Hydrated / WIDD) | ðŸ“‹ |

---

## FilosofÃ­a

MolDesign se rige por el principio de **Rigor sobre SimulaciÃ³n**. No buscamos que los nÃºmeros se vean bien, sino que sean fÃ­sicamente defendibles.

La industria farmacÃ©utica invierte dÃ©cadas y miles de millones en descubrir un fÃ¡rmaco. La mayor parte de ese costo estÃ¡ en la fase de screening inicial, identificando quÃ© molÃ©culas merecen atenciÃ³n experimental. MolDesign democratiza exactamente esa fase.

Al certificar cada hallazgo en Solana, garantizamos que:

1. El autor in silico tiene prueba irrefutable y permanente de su descubrimiento.
2. El conocimiento es libre (CC0), permitiendo que la humanidad avance mÃ¡s rÃ¡pido que los intereses comerciales.

**El prÃ³ximo fÃ¡rmaco puede venir de cualquier lugar. MolDesign existe para que eso sea posible.**

---

## Citar este proyecto

Si usas MolDesign en tu investigaciÃ³n, por favor cÃ­talo como:

```
Amezcua, J. (2026). MolDesign AI: Plataforma de Descubrimiento FarmacolÃ³gico In Silico
con ML Rescoring y CertificaciÃ³n Blockchain. GitHub.
https://github.com/srcacahuate619/molecule-design
Spearman Ï = 0.512 (validaciÃ³n ciega, 50 fÃ¡rmacos post-2022, p=0.00014)
```

---

## Autor

**Johan Amezcua**
Ingeniero en Software Â· UVEG Â· Monterrey, MÃ©xico
ðŸ“§ [26000885@es.uveg.edu.mx](mailto:26000885@es.uveg.edu.mx)
ðŸŒ [molecule-design.vercel.app](https://molecule-design.vercel.app)

---

## Licencia

CÃ³digo fuente bajo licencia **MIT**.
Descubrimientos certificados por los usuarios bajo **Creative Commons Zero (CC0)** â€” dominio pÃºblico universal.
