import asyncio
import sys
import os

# Añadir el path del backend para importar módulos internos
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.database import get_db
from db.repository import Repository
from core.models import TargetORM
from services.blockchain.target_info import fetch_and_translate_target_info

async def main():
    print("🚀 Sembrando/actualizando targets biológicos en la base de datos...")
    
    # Parámetros biológicos calibrados
    targets_data = [
        {
            "pdb_id": "7E2Y",
            "name": "5-HT1A serotonin receptor",
            "chain": "R",
            "description": "Target base del MVP científico de MolDesign.",
            "grid_center_x": 103.03, "grid_center_y": 114.79, "grid_center_z": 108.36,
            "grid_size_x": 25.0, "grid_size_y": 25.0, "grid_size_z": 25.0,
            "requires_cns": True, "structural_family": "GPCR", "organism": "Homo sapiens",
            "resolution": 3.0, "spearman_rho": 0.512, "affinity_threshold": -7.5,
            "is_hot": False,
            "hotspots": [
                {"name": "MET97", "importance": 0.8},
                {"name": "ASP116", "importance": 1.0},
                {"name": "VAL117", "importance": 0.7},
                {"name": "SER190", "importance": 0.6},
                {"name": "PHE361", "importance": 0.9}
            ]
        },
        {
            "pdb_id": "6B3J",
            "name": "GLP-1R (ECD; Co-cristalizado con Exendin-P5)",
            "chain": "R",
            "description": "Receptor GLP-1 acoplado a proteína Gs en estado activo con agonista peptídico Exendin-P5 (Cadena P). Resolución 3.3 Å Cryo-EM (Liang et al. 2018, Nature). Bolsillo del Dominio Extracelular (ECD): indica complementariedad para análogos peptídicos, peptidomiméticos y moléculas con anclaje N-terminal. Para agonistas orales small-molecule, usar el target GLP-1R TMD (6X1A).",
            "grid_center_x": 93.23, "grid_center_y": 148.16, "grid_center_z": 103.33,
            "grid_size_x": 30.0, "grid_size_y": 30.0, "grid_size_z": 30.0,
            "requires_cns": False, "structural_family": "GPCR", "organism": "Homo sapiens",
            "resolution": 3.3, "spearman_rho": 0.485, "affinity_threshold": -8.0,
            "is_hot": True,
            "hotspots": [
                {"name": "ARG121", "importance": 1.0},
                {"name": "GLU138", "importance": 1.0},
                {"name": "ARG299", "importance": 0.9},
                {"name": "TRP306", "importance": 0.8},
                {"name": "TYR69",  "importance": 0.8}
            ]
        },
        {
            "pdb_id": "6X1A",
            "name": "GLP-1R (TMD; Co-cristalizado con Danuglipron)",
            "chain": "R",
            "description": "Receptor GLP-1 en estado activo unido al agonista oral no peptídico Danuglipron (PF-06882961, Pfizer; ligando UK4, Cadena R). Resolución 2.5 Å Cryo-EM (Song et al. 2020, Cell). Bolsillo del Dominio Transmembranal (TMD): TM1/TM2/TM3/TM7. Target primario para virtual screening de fármacos orales. TRP33 es primate-específico y crítico para selectividad de especie.",
            "grid_center_x": 131.35, "grid_center_y": 116.78, "grid_center_z": 155.04,
            "grid_size_x": 30.0, "grid_size_y": 30.0, "grid_size_z": 30.0,
            "requires_cns": False, "structural_family": "GPCR", "organism": "Homo sapiens",
            "resolution": 2.5, "spearman_rho": -0.267, "affinity_threshold": -7.5,
            "is_hot": True,
            "hotspots": [
                {"name": "LYS197", "importance": 1.0},
                {"name": "TRP203", "importance": 1.0},
                {"name": "ARG380", "importance": 0.9},
                {"name": "TRP33",  "importance": 0.9},
                {"name": "THR298", "importance": 0.8},
                {"name": "LEU141", "importance": 0.7}
            ]
        },
        {
            "pdb_id": "2P4E",
            "name": "PCSK9 (Proprotein Convertase)",
            "chain": "A",
            "description": "Inhibición de la interacción PCSK9-LDLR para hipercolesterolemia.",
            "grid_center_x": 28.82, "grid_center_y": 31.75, "grid_center_z": 40.92,
            "grid_size_x": 22.0, "grid_size_y": 22.0, "grid_size_z": 22.0,
            "requires_cns": False, "structural_family": "hydrolase", "organism": "Homo sapiens",
            "resolution": 1.97, "spearman_rho": 0.0, "affinity_threshold": -7.5,
            "is_hot": False,
            "hotspots": [
                {"name": "GLY292", "importance": 1.0},
                {"name": "TYR293", "importance": 1.0},
                {"name": "SER294", "importance": 1.0}
            ]
        },
        {
            "pdb_id": "6U26",
            "name": "PCSK9 (Allosteric)",
            "chain": "A",
            "description": "Bolsillo de unión alostérico para inhibidores de pequeña molécula.",
            "grid_center_x": 40.87, "grid_center_y": 30.19, "grid_center_z": 29.78,
            "grid_size_x": 20.0, "grid_size_y": 20.0, "grid_size_z": 20.0,
            "requires_cns": False, "structural_family": "Serine Protease", "organism": "Homo sapiens",
            "resolution": 1.6, "spearman_rho": 0.0, "affinity_threshold": -7.5,
            "is_hot": False,
            "hotspots": [
                {"name": "ASP186", "importance": 1.0},
                {"name": "PHE187", "importance": 1.0},
                {"name": "ASP367", "importance": 0.9}
            ]
        },
        {
            "pdb_id": "3OSK",
            "name": "CTLA-4 Immune Checkpoint",
            "chain": "A",
            "description": "Receptor inmunitario (Checkpoint). Sitio de unión B7 (Loop MYPPPY).",
            "grid_center_x": -2.132, "grid_center_y": -19.592, "grid_center_z": 22.149,
            "grid_size_x": 25.0, "grid_size_y": 25.0, "grid_size_z": 25.0,
            "requires_cns": False, "structural_family": "checkpoint", "organism": "Homo sapiens",
            "resolution": 2.5, "spearman_rho": 0.0, "affinity_threshold": -7.0,
            "is_hot": False,
            "hotspots": [
                {"name": "MET99", "importance": 1.0},
                {"name": "TYR100", "importance": 1.0},
                {"name": "PRO101", "importance": 1.0},
                {"name": "PRO102", "importance": 1.0},
                {"name": "PRO103", "importance": 1.0},
                {"name": "TYR104", "importance": 1.0}
            ]
        },
        {
            "pdb_id": "3ERT",
            "name": "ER-alpha LBD (Co-cristalizado con 4-Hidroxitamoxifeno)",
            "chain": "A",
            "description": "Receptor de estrogeno alfa humano (LBD) co-cristalizado con el modulador selectivo 4-Hidroxitamoxifeno (OHT). Diana principal en terapia endocrina de cancer de mama ER+.",
            "grid_center_x": 31.57, "grid_center_y": -1.59, "grid_center_z": 25.60,
            "grid_size_x": 25.0, "grid_size_y": 25.0, "grid_size_z": 25.0,
            "requires_cns": False, "structural_family": "Nuclear Receptor", "organism": "Homo sapiens",
            "resolution": 1.9, "spearman_rho": -0.583, "affinity_threshold": -7.5,
            "is_hot": False,
            "hotspots": [
                {"name": "GLU353", "importance": 1.0},
                {"name": "ARG394", "importance": 0.85},
                {"name": "ASP351", "importance": 0.8},
                {"name": "ALA350", "importance": 0.78},
                {"name": "MET421", "importance": 0.72}
            ]
        },
        {
            "pdb_id": "5L2I",
            "name": "CDK6 (Co-cristalizado con Palbociclib)",
            "chain": "A",
            "description": "Ciclina dependiente de quinasa 6 (CDK6) humana unida al inhibidor selectivo de quinasa Palbociclib (Ibrance). Control del ciclo celular G1/S en tumores ER+.",
            "grid_center_x": 13.98, "grid_center_y": 28.18, "grid_center_z": 9.65,
            "grid_size_x": 25.0, "grid_size_y": 25.0, "grid_size_z": 25.0,
            "requires_cns": False, "structural_family": "Kinase", "organism": "Homo sapiens",
            "resolution": 2.75, "spearman_rho": -0.483, "affinity_threshold": -7.5,
            "is_hot": False,
            "hotspots": [
                {"name": "VAL101", "importance": 1.0},
                {"name": "GLU99", "importance": 0.9},
                {"name": "VAL27", "importance": 0.88},
                {"name": "GLN149", "importance": 0.86},
                {"name": "LEU152", "importance": 0.85}
            ]
        },
        {
            "pdb_id": "2W96",
            "name": "CDK4 (Complejo con Ciclina D1; sitio por homología estructural con CDK6)",
            "chain": "B",
            "description": "Ciclina dependiente de quinasa 4 (CDK4) humana en complejo activo con Ciclina D1. Bolsillo ATP alineado estructuralmente con Palbociclib para cribado selectivo.",
            "grid_center_x": 7.41, "grid_center_y": 2.10, "grid_center_z": 81.55,
            "grid_size_x": 25.0, "grid_size_y": 25.0, "grid_size_z": 25.0,
            "requires_cns": False, "structural_family": "Kinase", "organism": "Homo sapiens",
            "resolution": 2.3, "spearman_rho": -0.550, "affinity_threshold": -7.5,
            "is_hot": False,
            "hotspots": [
                {"name": "LYS35", "importance": 1.0},
                {"name": "VAL96", "importance": 0.91},
                {"name": "ASP158", "importance": 0.91},
                {"name": "ILE12", "importance": 0.84},
                {"name": "GLU144", "importance": 0.79}
            ]
        },
        {
            "pdb_id": "4JPS",
            "name": "PIK3CA WT (Co-cristalizado con Alpelisib)",
            "chain": "A",
            "description": "Subunidad catalitica p110alfa de fosfatidilinositol 3-quinasa (PI3K) salvaje en complejo con el inhibidor BYL719 (Alpelisib) indicado para resistencia endocrina.",
            "grid_center_x": -1.32, "grid_center_y": -9.51, "grid_center_z": 16.95,
            "grid_size_x": 25.0, "grid_size_y": 25.0, "grid_size_z": 25.0,
            "requires_cns": False, "structural_family": "Kinase", "organism": "Homo sapiens",
            "resolution": 2.2, "spearman_rho": 0.610, "affinity_threshold": -7.5,
            "is_hot": False,
            "hotspots": [
                {"name": "SER854", "importance": 1.0},
                {"name": "GLN859", "importance": 0.96},
                {"name": "VAL851", "importance": 0.93},
                {"name": "LYS802", "importance": 0.87},
                {"name": "ILE800", "importance": 0.85}
            ]
        },
        {
            "pdb_id": "3O96",
            "name": "AKT1 (Co-cristalizado con Inhibidor Alostérico VIII)",
            "chain": "A",
            "description": "RAC-alfa serina/treonina-proteina quinasa 1 (AKT1) en estado inactivo con inhibidor alosterico VIII. Bloqueo de la señalizacion aguas abajo de PI3K.",
            "grid_center_x": 8.37, "grid_center_y": -6.83, "grid_center_z": 12.62,
            "grid_size_x": 25.0, "grid_size_y": 25.0, "grid_size_z": 25.0,
            "requires_cns": False, "structural_family": "Kinase", "organism": "Homo sapiens",
            "resolution": 2.7, "spearman_rho": -0.333, "affinity_threshold": -7.5,
            "is_hot": False,
            "hotspots": [
                {"name": "SER205", "importance": 1.0},
                {"name": "ASP292", "importance": 0.94},
                {"name": "TYR272", "importance": 0.92},
                {"name": "CYS296", "importance": 0.91},
                {"name": "LYS268", "importance": 0.87}
            ]
        },
        {
            "pdb_id": "3PP0",
            "name": "HER2 Kinase Domain (Co-cristalizado con SYR-475)",
            "chain": "A",
            "description": "Dominio quinasa de la tirosina-proteina quinasa erbB-2 (HER2/Neu) en complejo con el inhibidor pirrolopirimidinico selectivo SYR-475.",
            "grid_center_x": 17.10, "grid_center_y": 16.55, "grid_center_z": 26.60,
            "grid_size_x": 25.0, "grid_size_y": 25.0, "grid_size_z": 25.0,
            "requires_cns": False, "structural_family": "Kinase", "organism": "Homo sapiens",
            # spearman_rho=None: Benchmark anterior (ρ=+0.167) fue calculado con grid box
            # centrada en coordenadas incorrectas (centroide del multímero completo vs Cadena A).
            # Pendiente de recálculo con la geometría corregida. Auditado: 2026-05-31.
            "resolution": 2.25, "spearman_rho": None, "affinity_threshold": -7.5,
            "is_hot": False,
            "hotspots": [
                {"name": "MET801", "importance": 1.0},
                {"name": "ASP863", "importance": 0.96},
                {"name": "ASN850", "importance": 0.93},
                {"name": "ALA751", "importance": 0.93},
                {"name": "LEU796", "importance": 0.90}
            ]
        },
        {
            "pdb_id": "4ZZZ",
            "name": "PARP1 LBD (Co-cristalizado con NMS-P118)",
            "chain": "A",
            "description": "Dominio catalitico de Poli(ADP-ribosa) polimerasa 1 (PARP1) unida al inhibidor de isoindolinona NMS-P118. Letalidad sintetica en tumores con mutacion BRCA.",
            "grid_center_x": 63.41, "grid_center_y": 6.48, "grid_center_z": 9.59,
            "grid_size_x": 25.0, "grid_size_y": 25.0, "grid_size_z": 25.0,
            "requires_cns": False, "structural_family": "Polymerase", "organism": "Homo sapiens",
            # spearman_rho=None: Benchmark anterior (ρ=-0.407) fue calculado con grid box
            # centrada en coordenadas incorrectas (centroide del dímero completo vs Cadena A).
            # Pendiente de recálculo con la geometría corregida. Auditado: 2026-05-31.
            "resolution": 1.9, "spearman_rho": None, "affinity_threshold": -7.5,
            "is_hot": False,
            "hotspots": [
                {"name": "SER904", "importance": 1.0},
                {"name": "GLY863", "importance": 0.99},
                {"name": "HIS862", "importance": 0.84},
                {"name": "TYR907", "importance": 0.80},
                {"name": "PHE897", "importance": 0.76}
            ]
        },
        {
            "pdb_id": "1HVY",
            "name": "Thymidylate Synthase (Co-cristalizado con Raltitrexed)",
            "chain": "A",
            "description": "Timidilato sintasa humana (dímero catalítico, Cadena A) en complejo cerrado con el analogo de folato Raltitrexed (D16) y dUMP. Blanco quimioterapeutico clasico.",
            "grid_center_x": 0.40, "grid_center_y": 12.39, "grid_center_z": 17.77,
            "grid_size_x": 25.0, "grid_size_y": 25.0, "grid_size_z": 25.0,
            "requires_cns": False, "structural_family": "Transferase", "organism": "Homo sapiens",
            # spearman_rho=None: Benchmark anterior (ρ=-0.335) fue calculado con grid box
            # centrada en coordenadas incorrectas (centroide del homodímero completo vs Cadena A).
            # Pendiente de recálculo con la geometría corregida. Auditado: 2026-05-31.
            "resolution": 1.9, "spearman_rho": None, "affinity_threshold": -7.5,
            "is_hot": False,
            "hotspots": [
                {"name": "ASP218", "importance": 1.0},
                {"name": "GLY222", "importance": 0.89},
                {"name": "GLU87", "importance": 0.78},
                {"name": "MET311", "importance": 0.78},
                {"name": "TRP109", "importance": 0.77}
            ]
        },
        {
            "pdb_id": "4I5I",
            "name": "SIRT1 (Conformación Activa - Longevidad)",
            "chain": "A",
            "description": "Sirtuina 1 humana (gen de la longevidad) en estado catalítico activo unido a NAD+ y análogo de activador alostérico (EX-527). Blanco principal para polifenoles y fitonutrientes antienvejecimiento.",
            "grid_center_x": 42.96, "grid_center_y": -21.41, "grid_center_z": 18.53,
            "grid_size_x": 25.0, "grid_size_y": 25.0, "grid_size_z": 25.0,
            "requires_cns": False, "structural_family": "Deacetylase", "organism": "Homo sapiens",
            "resolution": 2.5, "spearman_rho": 0.0, "affinity_threshold": -7.5,
            "is_hot": False,
            "hotspots": [
                {"name": "PHE273", "importance": 1.0},
                {"name": "PHE297", "importance": 0.9},
                {"name": "ILE347", "importance": 0.8}
            ]
        },
        {
            "pdb_id": "6D8X",
            "name": "PPAR-gamma (Conformación Activa - Metabolismo)",
            "chain": "A",
            "description": "Receptor activado por proliferadores de peroxisomas gamma (PPAR-γ) unido a agonista completo GW1929. Regulador clave del metabolismo de lípidos, glucosa y sensibilidad a insulina.",
            "grid_center_x": 1.39, "grid_center_y": -4.32, "grid_center_z": -19.36,
            "grid_size_x": 25.0, "grid_size_y": 25.0, "grid_size_z": 25.0,
            "requires_cns": False, "structural_family": "Nuclear Receptor", "organism": "Homo sapiens",
            "resolution": 1.9, "spearman_rho": 0.0, "affinity_threshold": -7.5,
            "is_hot": False,
            "hotspots": [
                {"name": "HIS323", "importance": 1.0},
                {"name": "HIS449", "importance": 1.0},
                {"name": "TYR473", "importance": 1.0}
            ]
        },
        {
            "pdb_id": "5IKR",
            "name": "COX-2 (Conformación Inhibida - Antiinflamatorio)",
            "chain": "A",
            "description": "Ciclooxigenasa-2 humana (COX-2) en complejo con el inhibidor Ácido Mefenámico. Blanco molecular para fitoquímicos con actividad antiinflamatoria y analgésica.",
            "grid_center_x": 38.96, "grid_center_y": 2.35, "grid_center_z": 61.50,
            "grid_size_x": 25.0, "grid_size_y": 25.0, "grid_size_z": 25.0,
            "requires_cns": False, "structural_family": "Enzyme", "organism": "Homo sapiens",
            "resolution": 2.34, "spearman_rho": 0.0, "affinity_threshold": -7.5,
            "is_hot": False,
            "hotspots": [
                {"name": "ARG120", "importance": 1.0},
                {"name": "TYR355", "importance": 0.9},
                {"name": "SER530", "importance": 0.8}
            ]
        },
        {
            "pdb_id": "4RER",
            "name": "AMPK (Conformación Activa - Energética Celular)",
            "chain": "A",
            "description": "Proteína quinasa activada por AMP (AMPK) humana unida al activador alostérico A-769662. Sensor energético celular crítico regulador del metabolismo de carbohidratos.",
            "grid_center_x": 45.94, "grid_center_y": -30.22, "grid_center_z": 5.12,
            "grid_size_x": 25.0, "grid_size_y": 25.0, "grid_size_z": 25.0,
            "requires_cns": False, "structural_family": "Kinase", "organism": "Homo sapiens",
            "resolution": 2.9, "spearman_rho": 0.0, "affinity_threshold": -7.5,
            "is_hot": False,
            "hotspots": [
                {"name": "ASP139", "importance": 1.0},
                {"name": "PHE223", "importance": 0.8}
            ]
        },
        {
            "pdb_id": "5VEW",
            "name": "GLP-1R TMD (Conformación Inactiva - Bloqueado)",
            "chain": "A",
            "description": "Receptor GLP-1 (Dominio Transmembranal) en estado inactivo estabilizado por el modulador alostérico negativo PF-06305591. Útil para cribado comparativo de especificidad funcional.",
            "grid_center_x": 20.56, "grid_center_y": 30.93, "grid_center_z": 27.96,
            "grid_size_x": 30.0, "grid_size_y": 30.0, "grid_size_z": 30.0,
            "requires_cns": False, "structural_family": "GPCR", "organism": "Homo sapiens",
            "resolution": 3.0, "spearman_rho": 0.0, "affinity_threshold": -7.5,
            "is_hot": False,
            "hotspots": [
                {"name": "PHE367", "importance": 1.0},
                {"name": "LEU360", "importance": 0.9}
            ]
        },
        {
            "pdb_id": "1ERE",
            "name": "ER-alpha LBD (Conformación Activa - Estimulado)",
            "chain": "A",
            "description": "Receptor de estrógeno alfa humano (LBD) en estado activo unido a la hormona natural Estradiol. Modelo clásico para el estudio de fitoestrógenos nutricionales.",
            "grid_center_x": 9.27, "grid_center_y": 46.29, "grid_center_z": 131.21,
            "grid_size_x": 25.0, "grid_size_y": 25.0, "grid_size_z": 25.0,
            "requires_cns": False, "structural_family": "Nuclear Receptor", "organism": "Homo sapiens",
            "resolution": 2.3, "spearman_rho": 0.0, "affinity_threshold": -7.5,
            "is_hot": False,
            "hotspots": [
                {"name": "GLU353", "importance": 1.0},
                {"name": "ARG394", "importance": 1.0}
            ]
        },
        {
            "pdb_id": "4EKL",
            "name": "AKT1 (Conformación Activa - Fosforilado)",
            "chain": "A",
            "description": "Quinasa AKT1 humana fosforilada y activa unida a inhibidor competitivo de ATP. Permite evaluar la modulación directa de la supervivencia celular por nutracéuticos.",
            "grid_center_x": 28.03, "grid_center_y": 5.22, "grid_center_z": 10.89,
            "grid_size_x": 25.0, "grid_size_y": 25.0, "grid_size_z": 25.0,
            "requires_cns": False, "structural_family": "Kinase", "organism": "Homo sapiens",
            "resolution": 2.0, "spearman_rho": 0.0, "affinity_threshold": -7.5,
            "is_hot": False,
            "hotspots": [
                {"name": "ALA230", "importance": 1.0},
                {"name": "GLU234", "importance": 0.8}
            ]
        }
    ]

    async for db in get_db():
        repo = Repository(db)
        for t_data in targets_data:
            print(f"Obteniendo descripción UniProt detallada para {t_data['pdb_id']}...")
            try:
                desc = await fetch_and_translate_target_info(t_data["pdb_id"])
                if desc and not desc.startswith("Receptor Biológico PDB") and not desc.startswith("Descripción del receptor"):
                    t_data["description"] = desc
            except Exception as e:
                print(f"⚠️ Error al descargar info para {t_data['pdb_id']}: {e}")
            existing = await repo.get_target_by_pdb_id(t_data["pdb_id"])
            if not existing:
                t = TargetORM(
                    pdb_id=t_data["pdb_id"],
                    name=t_data["name"],
                    chain=t_data["chain"],
                    description=t_data["description"],
                    grid_center_x=t_data["grid_center_x"],
                    grid_center_y=t_data["grid_center_y"],
                    grid_center_z=t_data["grid_center_z"],
                    grid_size_x=t_data["grid_size_x"],
                    grid_size_y=t_data["grid_size_y"],
                    grid_size_z=t_data["grid_size_z"],
                    requires_cns=t_data["requires_cns"],
                    structural_family=t_data["structural_family"],
                    organism=t_data["organism"],
                    resolution=t_data["resolution"],
                    is_prepared=True,  # Se marcará is_prepared=True tras correr la preparación estructural
                    spearman_rho=t_data["spearman_rho"],
                    affinity_threshold=t_data["affinity_threshold"],
                    hotspots=t_data["hotspots"],
                    is_hot=t_data["is_hot"]
                )
                db.add(t)
                print(f"➕ Target {t_data['pdb_id']} insertado en la base de datos.")
            else:
                # Actualizar campos para asegurar calibración exacta
                existing.name = t_data["name"]
                existing.chain = t_data["chain"]
                existing.description = t_data["description"]
                existing.grid_center_x = t_data["grid_center_x"]
                existing.grid_center_y = t_data["grid_center_y"]
                existing.grid_center_z = t_data["grid_center_z"]
                existing.grid_size_x = t_data["grid_size_x"]
                existing.grid_size_y = t_data["grid_size_y"]
                existing.grid_size_z = t_data["grid_size_z"]
                existing.requires_cns = t_data["requires_cns"]
                existing.structural_family = t_data["structural_family"]
                existing.organism = t_data["organism"]
                existing.resolution = t_data["resolution"]
                existing.spearman_rho = t_data["spearman_rho"]
                existing.affinity_threshold = t_data["affinity_threshold"]
                existing.hotspots = t_data["hotspots"]
                existing.is_hot = t_data["is_hot"]
                print(f"🔄 Target {t_data['pdb_id']} actualizado en la base de datos.")
        
        await db.commit()
        print("✅ Siembra y sincronización de todos los 14 targets completada con éxito.")
        break

if __name__ == "__main__":
    asyncio.run(main())
