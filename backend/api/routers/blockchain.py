"""
Blockchain certification router.

Provides endpoints for certifying molecular discoveries on Solana devnet.
"""

import uuid
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi.responses import StreamingResponse

from core.config import get_settings, Settings
from core.database import get_db
from core.exceptions import TransactionFailedError
from core.models import BlockchainRecord, MoleculeORM, EvaluationResultORM, UserORM
from api.dependencies import get_current_user
from services.blockchain.certifier import certify_molecule_async
from services.blockchain.pdf_generator import generate_certificate_pdf
from services.blockchain.target_info import fetch_and_translate_target_info


router = APIRouter(prefix="/blockchain", tags=["blockchain"])


class CertificationRequest(BaseModel):
    molecule_id: uuid.UUID
    user_wallet: Optional[str] = None


class CertificationResponse(BaseModel):
    signature: str
    message: str


@router.post("/certify", response_model=CertificationResponse)
async def certify_molecule(
    request: CertificationRequest,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings)
):
    """
    Certify a molecular discovery on Solana devnet.

    This creates an immutable record of the scientific contribution
    with CC0 license on the Solana blockchain.
    """
    try:
        stmt = select(MoleculeORM).options(selectinload(MoleculeORM.target)).where(MoleculeORM.id == request.molecule_id)
        result = await db.execute(stmt)
        mol = result.scalar_one_or_none()
        if not mol:
            raise HTTPException(status_code=404, detail="Molécula no encontrada en la base de datos")
        
        if mol.user_id and mol.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="No tienes permiso para certificar esta molécula")
            
        evaluation = await db.scalar(
            select(EvaluationResultORM).where(EvaluationResultORM.molecule_id == request.molecule_id)
        )
        if not evaluation:
            raise HTTPException(status_code=400, detail="La molécula no ha sido evaluada aún")

        if evaluation.blockchain_tx_id:
            return CertificationResponse(
                signature=evaluation.blockchain_tx_id,
                message="Esta molécula ya cuenta con una certificación activa"
            )

        # 1. Check globally if any other user has already certified this SMILES + Target
        stmt_existing = (
            select(EvaluationResultORM.blockchain_tx_id)
            .join(MoleculeORM, MoleculeORM.id == EvaluationResultORM.molecule_id)
            .where(MoleculeORM.smiles_hash == mol.smiles_hash)
            .where(MoleculeORM.target_id == mol.target_id)
            .where(EvaluationResultORM.blockchain_tx_id.isnot(None))
            .limit(1)
        )
        existing_tx = await db.scalar(stmt_existing)

        if existing_tx:
            # Another user already certified it! Just link it.
            signature = existing_tx
            message = "Esta molécula ya había sido certificada previamente por otro investigador. Hemos enlazado la evidencia global."
        else:
            # Create new blockchain record
            record = BlockchainRecord(
                smiles_hash=mol.smiles_hash,
                total_score=evaluation.total_score or 0.0,
                target_pdb_id=mol.target.pdb_id if mol.target else "7E2Y",
                user_wallet=request.user_wallet or current_user.email,
                timestamp=datetime.utcnow()
            )

            # Certify on blockchain
            signature = await certify_molecule_async(record, record.user_wallet)
            message = "Molécula certificada y guardada exitosamente en tu historial"

        # 2. Sync signature to ALL evaluations of this SMILES + Target globally
        stmt_subquery = (
            select(MoleculeORM.id)
            .where(MoleculeORM.smiles_hash == mol.smiles_hash)
            .where(MoleculeORM.target_id == mol.target_id)
        )
        stmt_update = (
            update(EvaluationResultORM)
            .where(EvaluationResultORM.molecule_id.in_(stmt_subquery))
            .values(blockchain_tx_id=signature)
        )
        await db.execute(stmt_update)
        # Ensure current molecule is marked as saved and owned by the user
        mol.is_saved = True
        if mol.user_id is None:
            mol.user_id = current_user.id
        
        await db.commit()

        return CertificationResponse(
            signature=signature,
            message=message
        )

    except TransactionFailedError as e:
        raise HTTPException(status_code=502, detail=e.message)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@router.get("/verify/{signature}")
async def verify_certification(signature: str):
    """
    Verify a certification transaction on the blockchain.

    Returns the certified record if found and valid.
    """
    from services.blockchain.certifier import certifier
    
    record = await certifier.verify_certification(signature)
    
    if record is None:
        raise HTTPException(status_code=404, detail="Certification not found or invalid")
    
    return {
        "signature": signature,
        "record": record.dict(),
        "status": "verified",
        "message": "Certification verified on Solana blockchain"
    }

@router.get("/certificate/{molecule_id}")
async def get_certificate(molecule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Generates and downloads a PDF certificate for the certified molecule.
    """
    stmt = select(MoleculeORM).options(selectinload(MoleculeORM.target)).where(MoleculeORM.id == molecule_id)
    result = await db.execute(stmt)
    mol = result.scalar_one_or_none()
    
    if not mol:
        raise HTTPException(status_code=404, detail="Molécula no encontrada")
        
    evaluation = await db.scalar(
        select(EvaluationResultORM).where(EvaluationResultORM.molecule_id == molecule_id)
    )
    if not evaluation:
        raise HTTPException(status_code=400, detail="La molécula no ha sido evaluada")
        
    if mol.target and not mol.target.description:
        description = await fetch_and_translate_target_info(mol.target.pdb_id)
        mol.target.description = description
        await db.commit()
        # Refresh mol to ensure it has the description
        await db.refresh(mol)
        
    target_name = mol.target.name if mol.target else "7E2Y (5-HT1A)"
    pdf_buf = generate_certificate_pdf(mol, evaluation, target_name)
    
    return StreamingResponse(
        pdf_buf, 
        media_type="application/pdf", 
        headers={"Content-Disposition": f"attachment; filename=MolDesign_Certificate.pdf"}
    )