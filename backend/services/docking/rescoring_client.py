import httpx
from typing import Any, List
from pydantic import BaseModel, Field
from core.config import get_settings
from utils.logger import get_logger

settings = get_settings()
log = get_logger(__name__)

class PoseData(BaseModel):
    pdbqt_block: str
    vina_score: float
    rmsd_lb: float = 0.0
    rmsd_ub: float = 0.0

class RescoreRequest(BaseModel):
    smiles: str
    target_pdb_path: str
    poses: List[PoseData]
    molecular_weight: float
    logp: float
    tpsa: float
    hbd: int
    hba: int
    rotatable_bonds: int
    qed: float
    grid_center: List[float] | None = None
    grid_size: List[float] | None = None
    run_gnn: bool = False  # Activa RTMScore GNN (Nivel 2) cuando True

async def get_ml_rescore(
    smiles: str,
    target_pdb_path: str,
    poses: List[Any],
    properties: Any,
    grid_center: List[float] | None = None,
    grid_size: List[float] | None = None,
    run_gnn: bool = True,  # Por defecto activo — el microservicio lo maneja con fallback si no hay pesos
) -> dict:
    """
    Llama al microservicio de rescoring ML para obtener la afinidad corregida.

    Args:
        run_gnn: Si True, el microservicio también ejecuta RTMScore GNN (Nivel 2)
                 y devuelve `gnn_score`. Si el modelo no está disponible, el
                 microservicio lo ignora sin error.
    """
    url = f"{settings.rescoring_url}/rescore"
    
    # Mapear poses al formato esperado por el microservicio (vina_score)
    payload_poses = []
    for p in poses:
        # p puede ser un dict o un objeto con model_dump (DockingPose)
        p_dict = p.model_dump() if hasattr(p, "model_dump") else p
        payload_poses.append(PoseData(
            pdbqt_block=p_dict.get("pdbqt_block") or "",
            vina_score=p_dict.get("affinity", 0.0), # affinity -> vina_score
            rmsd_lb=p_dict.get("rmsd_lb", 0.0),
            rmsd_ub=p_dict.get("rmsd_ub", 0.0)
        ))
    
    request_data = RescoreRequest(
        smiles=smiles,
        target_pdb_path=target_pdb_path,
        poses=payload_poses,
        molecular_weight=properties.molecular_weight,
        logp=properties.log_p,
        tpsa=properties.tpsa,
        hbd=properties.hbd,
        hba=properties.hba,
        rotatable_bonds=properties.rotatable_bonds,
        qed=properties.qed,
        grid_center=grid_center,
        grid_size=grid_size,
        run_gnn=run_gnn,
    )
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:  # timeout aumentado por GNN en CPU
            response = await client.post(
                url, 
                json=request_data.model_dump(),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        log.error("rescoring_service_error", error=str(e), url=url)
        return {"error": str(e), "fallback": True}
