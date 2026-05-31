# Parámetros de Grid Box y Hotspots Moleculares 🎯🧬

Este documento recopila las coordenadas exactas de la **Grid Box** (caja de docking) y los residuos clave de **especificidad (Hotspots)** para las 14 dianas terapéuticas integradas en el motor biofísico de **MolDesign v6.2**.

---

## 📊 Tabla de Parámetros del Grid Box (Cribado Virtual)

Los centros ($X, Y, Z$) y dimensiones ($X, Y, Z$, en Angstroms $\text{Å}$) han sido calibrados basándose en los ligandos co-cristalizados para asegurar que el docking se concentre estrictamente en el sitio biológicamente activo del receptor:

| Receptor / Target | PDB ID | Chain | Centroide ($X, Y, Z$) | Dimensiones ($X, Y, Z$ en $\text{Å}$) | Resolución ($\text{Å}$) | Familia Estructural |
|:---|:---:|:---:|:---:|:---:|:---:|:---|
| **5-HT1A Serotonin Receptor** | `7E2Y` | R | $(103.03, 114.79, 108.36)$ | $25.0 \times 25.0 \times 25.0$ | $3.00$ | GPCR |
| **GLP-1R (ECD / Peptide Pocket)** | `6B3J` | R | $(93.23, 148.16, 103.33)$ | $30.0 \times 30.0 \times 30.0$ | $3.30$ | GPCR |
| **GLP-1R (TMD / Oral Agonist)** | `6X1A` | R | $(131.35, 116.78, 155.04)$ | $30.0 \times 30.0 \times 30.0$ | $2.50$ | GPCR |
| **PCSK9 (Proprotein Convertase)** | `2P4E` | A | $(28.82, 31.75, 40.92)$ | $22.0 \times 22.0 \times 22.0$ | $1.97$ | Hydrolase |
| **PCSK9 (Allosteric)** | `6U26` | A | $(40.87, 30.19, 29.78)$ | $20.0 \times 20.0 \times 20.0$ | $1.60$ | Serine Protease |
| **CTLA-4 Immune Checkpoint** | `3OSK` | A | $(-2.13, -19.59, 22.15)$ | $25.0 \times 25.0 \times 25.0$ | $2.50$ | Checkpoint |
| **ER-alpha LBD (Tamoxifen)** | `3ERT` | A | $(31.57, -1.59, 25.60)$ | $25.0 \times 25.0 \times 25.0$ | $1.90$ | Nuclear Receptor |
| **CDK6 (Palbociclib)** | `5L2I` | A | $(13.98, 28.18, 9.65)$ | $25.0 \times 25.0 \times 25.0$ | $2.75$ | Kinase |
| **CDK4 (Apo/Cyclin D1)** | `2W96` | B | $(7.41, 2.10, 81.55)$ | $25.0 \times 25.0 \times 25.0$ | $2.30$ | Kinase |
| **PIK3CA WT (Alpelisib)** | `4JPS` | A | $(-1.32, -9.51, 16.95)$ | $25.0 \times 25.0 \times 25.0$ | $2.20$ | Kinase |
| **AKT1 (Allosteric Inhibitor VIII)** | `3O96` | A | $(8.37, -6.83, 12.62)$ | $25.0 \times 25.0 \times 25.0$ | $2.70$ | Kinase |
| **HER2 Kinase Domain (SYR-475)** | `3PP0` | A | $(17.10, 16.55, 26.60)$ | $25.0 \times 25.0 \times 25.0$ | $2.25$ | Kinase |
| **PARP1 LBD (NMS-P118)** | `4ZZZ` | A | $(63.41, 6.48, 9.59)$ | $25.0 \times 25.0 \times 25.0$ | $1.90$ | Polymerase |
| **Thymidylate Synthase (Raltitrexed)** | `1HVY` | A | $(0.40, 12.39, 17.77)$ | $25.0 \times 25.0 \times 25.0$ | $1.90$ | Transferase |

---

## 🎯 Residuos Hotspots Asignados (Especificidad de Binding)

Para que el multiplicador de especificidad de MolDesign se mantenga en $1.0\text{x}$, el compuesto debe interaccionar físicamente a menos de $5.0 \text{ Å}$ de los siguientes residuos, ordenados por su nivel de importancia relativa:

### Neuropsiquiatría y Metabolismo
*   **7E2Y (5-HT1A):** ASP116 (1.0) · PHE361 (0.9) · MET97 (0.8) · VAL117 (0.7) · SER190 (0.6)
*   **6B3J (GLP-1R ECD):** ARG121 (1.0) · GLU138 (1.0) · ARG299 (0.9) · TRP306 (0.8) · TYR69 (0.8)
*   **6X1A (GLP-1R TMD):** LYS197 (1.0) · TRP203 (1.0) · ARG380 (0.9) · TRP33 (0.9) · THR298 (0.8) · LEU141 (0.7)

### Cardiovascular e Inmunología
*   **2P4E (PCSK9):** GLY292 (1.0) · TYR293 (1.0) · SER294 (1.0)
*   **6U26 (PCSK9 Alostérico):** ASP186 (1.0) · PHE187 (1.0) · ASP367 (0.9)
*   **3OSK (CTLA-4):** MET99 (1.0) · TYR100 (1.0) · PRO101 (1.0) · PRO102 (1.0) · PRO103 (1.0) · TYR104 (1.0)

### Oncología (Cáncer de Mama)
*   **3ERT (ER-alpha):** GLU353 (1.0) · ARG394 (0.85) · ASP351 (0.8) · ALA350 (0.78) · MET421 (0.72)
*   **5L2I (CDK6):** VAL101 (1.0) · GLU99 (0.9) · VAL27 (0.88) · GLN149 (0.86) · LEU152 (0.85)
*   **2W96 (CDK4):** LYS35 (1.0) · VAL96 (0.91) · ASP158 (0.91) · ILE12 (0.84) · GLU144 (0.79)
*   **4JPS (PIK3CA):** SER854 (1.0) · GLN859 (0.96) · VAL851 (0.93) · LYS802 (0.87) · ILE800 (0.85)
*   **3O96 (AKT1):** SER205 (1.0) · ASP292 (0.94) · TYR272 (0.92) · CYS296 (0.91) · LYS268 (0.87)
*   **3PP0 (HER2):** MET801 (1.0) · ASP863 (0.96) · ASN850 (0.93) · ALA751 (0.93) · LEU796 (0.90)
*   **4ZZZ (PARP1):** SER904 (1.0) · GLY863 (0.99) · HIS862 (0.84) · TYR907 (0.80) · PHE897 (0.76)
*   **1HVY (TS):** ASP218 (1.0) · GLY222 (0.89) · GLU87 (0.78) · MET311 (0.78) · TRP109 (0.77)

---

## ⚙️ Modificación de Parámetros en el Código

Si deseas agregar nuevos targets o recalibrar las coordenadas de una Grid Box existente:
1.  Edita el archivo [seed_targets.py](file:///d:/molecular-design/backend/scripts/seed_targets.py).
2.  Actualiza el diccionario en la función `main` y corre el script dentro del contenedor Docker para sembrar la base de datos:
    ```bash
    docker exec -t moldesign_api micromamba run -n base python scripts/seed_targets.py
    ```
3.  Si deseas que las simulaciones previas se re-preparen automáticamente a las nuevas coordenadas en tu almacenamiento MinIO, ejecuta:
    ```bash
    docker exec -t moldesign_api micromamba run -n base python scripts/prepare_new_targets.py
    ```
