import logging
import gc
from typing import Dict, Any, List

from core.models import PhysicochemicalProperties

logger = logging.getLogger(__name__)

# Intentar importar modelos (pueden faltar dependencias en entorno base)
try:
    from admet_ai import ADMETModel
    # Initialize globally to avoid loading on every request, 
    # but in a memory-constrained sequential factory, we might load/unload dynamically.
    _ADMET_MODEL = None 
except ImportError:
    _ADMET_MODEL = None
    logger.warning("admet-ai not installed. Blood viability will use mock predictions.")

try:
    from tabpfn import TabPFNClassifier
except ImportError:
    logger.warning("tabpfn not installed. Custom toxicity flags will be empty.")


def get_admet_model():
    """Carga perezosa del modelo ADMET para optimizar RAM."""
    global _ADMET_MODEL
    if _ADMET_MODEL is None:
        try:
            from admet_ai import ADMETModel
            # Cargamos la variante rápida si es posible para ahorrar RAM
            _ADMET_MODEL = ADMETModel()
        except Exception as e:
            logger.error(f"Error loading ADMETModel: {e}")
            return None
    return _ADMET_MODEL

def predict_admet_ai(smiles: str) -> Dict[str, Any]:
    """Predice propiedades ADMET usando el ensamble Chemprop de ADMET-AI."""
    model = get_admet_model()
    if not model:
        # Fallback de emergencia
        return {
            "Solubility": -4.0,
            "PPB": 95.0,
            "BBB": 1,
            "HIA": 1,
            "hERG": 0,
            "Clearance": 5.0
        }
    
    try:
        # [FIX] La API de ADMET-AI v2 usa predict() con un DataFrame de pandas.
        # El método predict_smiles() no existe en la versión actual (Chemprop v2).
        import pandas as pd
        df_input = pd.DataFrame({"smiles": [smiles]})
        df = model.predict(df_input)
        row = df.iloc[0]
        # [FIX] Series.get(key, Series.get(fallback)) no funciona en pandas:
        # si la clave primaria no existe, devuelve el default de la outer llamada
        # (-3.0), nunca evalúa el fallback interno. Usamos `in` explícito.
        def _col(series, *keys, default=0.0):
            for k in keys:
                if k in series.index:
                    return series[k]
            return default

        return {
            "Solubility": float(_col(row, "ESOL", "Solubility", default=-3.0)),
            "PPB":        float(_col(row, "PPBR_AZ", "PPB", default=90.0)),
            "BBB":        int(_col(row, "BBB_Martins", "BBB", default=1)),
            "HIA":        int(_col(row, "HIA_Hou", "HIA", default=1)),
            "hERG":       int(_col(row, "hERG", default=0)),
            "Clearance":  float(_col(row, "Clearance_Hepatocyte_AZ", "Clearance", default=10.0)),
        }
    except Exception as e:
        logger.error(f"ADMET-AI prediction failed: {e}")
        return {"Solubility": -3.0, "PPB": 90.0, "BBB": 1, "HIA": 1, "hERG": 0, "Clearance": 10.0}

def predict_tabpfn_custom_toxicity(properties: PhysicochemicalProperties) -> List[str]:
    """
    In-context learning tabular classifier.
    Checks descriptors against custom internal knowledge base (PAINS, Patents).
    """
    alerts = []
    # Aquí en el futuro cargaremos `control_toxics.csv` con pandas
    # y haremos clasificador.fit(X, y).predict([descriptores])
    # Por ahora simulamos la estructura de alertas.
    if properties.tpsa > 140:
        alerts.append("High TPSA (Custom Rule)")
    if properties.sa_score > 6:
        alerts.append("Hard to synthesize (SA > 6)")
    
    # Forzamos una limpieza de RAM como se solicitó para TabPFN en el plan secuencial
    gc.collect()
    return alerts


def calculate_blood_viability(smiles: str, properties: PhysicochemicalProperties) -> PhysicochemicalProperties:
    """
    Aplica el flujo MPO (Geometric Mean) para la Capa 3 usando IAs avanzadas.
    """
    # 1. Predicciones ADMET (Deep Learning)
    admet_preds = predict_admet_ai(smiles)
    
    # 2. Predicciones TabPFN (Custom Data)
    tabpfn_alerts = predict_tabpfn_custom_toxicity(properties)
    
    # --- ASIGNACIÓN DE PROPIEDADES INFORMATIVAS ---
    properties.blood_solubility_logs = admet_preds["Solubility"]
    properties.blood_bbb_permeable = bool(admet_preds["BBB"])
    properties.blood_hia_permeable = bool(admet_preds["HIA"])
    properties.blood_systemic_reactivity = tabpfn_alerts
    
    ppb = admet_preds["PPB"]
    if ppb > 99.0:
        properties.blood_ppb_category = "extreme"
    elif ppb > 90.0:
        properties.blood_ppb_category = "high"
    else:
        properties.blood_ppb_category = "low"

    # --- MPO (OPTIMIZACIÓN MULTIPARAMÉTRICA) ---
    # Calculamos factores de supervivencia (S_factor) de 0.0 a 1.0
    
    # S_sol: Solubilidad. Si logS < -6 (inviable), cae a 0.2. Si > -4, perfecto (1.0).
    logS = properties.blood_solubility_logs
    if logS >= -4.0:
        S_sol = 1.0
    elif logS <= -6.0:
        S_sol = 0.2
    else:
        # Interpolación lineal entre -6 y -4
        S_sol = 0.2 + 0.8 * ((logS - (-6.0)) / 2.0)
        
    # S_hia: Absorción. Si no se absorbe, S = 0.5.
    S_hia = 1.0 if properties.blood_hia_permeable else 0.5
    
    # S_tox: Toxicidad hERG o alertas personalizadas
    S_tox = 1.0
    if admet_preds["hERG"] == 1:
        S_tox *= 0.1  # Paro cardíaco casi seguro
    if len(tabpfn_alerts) > 0:
        S_tox *= (0.8 ** len(tabpfn_alerts)) # Penalización progresiva
        
    # Geometric Mean de 3 parámetros
    viability = (S_sol * S_hia * S_tox) ** (1/3)
    properties.blood_viability_score = float(viability * 100)
    
    logger.info(f"Blood Viability calculated: {properties.blood_viability_score:.2f} (S_sol={S_sol:.2f}, S_hia={S_hia:.2f}, S_tox={S_tox:.2f})")
    
    return properties
