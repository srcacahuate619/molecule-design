"""
db/repository.py

Repositorio async mínimo para el MVP.

Responsabilidades:
- CRUD básico de targets, moléculas y evaluation_results
- deduplicación por smiles_hash + target
- siembra controlada del target fijo del MVP
- persistencia explícita de estados del pipeline
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from chem.validator import smiles_to_hash
from core.config import get_settings
from core.exceptions import DatabaseQueryError, TargetNotFound
from core.models import (
    AnonymousLimitORM,
    DockingResult,
    EvaluationResultORM,
    MoleculeCreate,
    MoleculeORM,
    MoleculeStatus,
    MutationType,
    PhysicochemicalProperties,
    TargetORM,
    UserORM,
)
from utils.logger import get_logger

settings = get_settings()
log = get_logger(__name__)


class Repository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_target_by_pdb_id(self, pdb_id: str) -> TargetORM | None:
        stmt = select(TargetORM).where(TargetORM.pdb_id == pdb_id.upper())
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_targets(self) -> list[TargetORM]:
        stmt = select(TargetORM).order_by(TargetORM.created_at.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def ensure_default_target(self) -> TargetORM:
        target = await self.get_target_by_pdb_id(settings.default_target_pdb_id)
        if target is not None:
            return target

        target = TargetORM(
            pdb_id=settings.default_target_pdb_id,
            name="5-HT1A serotonin receptor",
            chain=settings.default_target_chain,
            description="Target fijo del MVP científico de MolDesign.",
            grid_center_x=settings.vina_center_x,
            grid_center_y=settings.vina_center_y,
            grid_center_z=settings.vina_center_z,
            grid_size_x=settings.vina_size_x,
            grid_size_y=settings.vina_size_y,
            grid_size_z=settings.vina_size_z,
            requires_cns=True,
            structural_family="gpcr",
            organism="Homo sapiens",
            resolution=2.8,
            is_prepared=False,
        )
        self.db.add(target)
        await self.db.flush()
        log.info("target fijo del MVP creado en DB", pdb_id=target.pdb_id)
        return target

    async def get_or_create_test_user(self) -> UserORM:
        stmt = select(UserORM).where(UserORM.email == "demo@moldesign.local")
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        user = UserORM(
            email="demo@moldesign.local",
            username="demo",
            hashed_password="mvp-bootstrap-user",
            is_active=True,
        )
        self.db.add(user)
        await self.db.flush()
        log.info("usuario demo creado para flujo MVP", user_id=str(user.id))
        return user

    async def create_molecule(
        self,
        data: MoleculeCreate,
        user_id: uuid.UUID,
    ) -> MoleculeORM:
        target = await self.get_target_by_pdb_id(data.target_pdb_id)
        if target is None:
            raise TargetNotFound(data.target_pdb_id)

        molecule = MoleculeORM(
            smiles=data.smiles,
            name=data.name,
            status=MoleculeStatus.PENDING,
            mutation_type=data.mutation_type,
            parent_id=data.parent_id,
            user_id=user_id,
            target_id=target.id,
            smiles_hash=smiles_to_hash(data.smiles),
        )
        self.db.add(molecule)
        await self.db.flush()
        log.info("molécula creada", molecule_id=str(molecule.id), target=target.pdb_id)
        return molecule

    async def get_molecule(self, molecule_id: uuid.UUID) -> MoleculeORM | None:
        stmt = (
            select(MoleculeORM)
            .options(
                selectinload(MoleculeORM.target),
                selectinload(MoleculeORM.evaluation_result),
            )
            .where(MoleculeORM.id == molecule_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_molecule_by_hash(
        self,
        smiles_hash: str,
        target_id: uuid.UUID | None = None,
    ) -> MoleculeORM | None:
        stmt = select(MoleculeORM).where(MoleculeORM.smiles_hash == smiles_hash)
        if target_id is not None:
            stmt = stmt.where(MoleculeORM.target_id == target_id)

        stmt = stmt.order_by(MoleculeORM.created_at.desc())
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create_or_get_molecule(
        self,
        smiles: str,
        target_pdb_id: str | None = None,
        name: str | None = None,
        user_id: uuid.UUID | None = None,
        parent_id: uuid.UUID | None = None,
        mutation_type: MutationType | None = None,
    ) -> MoleculeORM:
        target = await self.get_target_by_pdb_id(target_pdb_id or settings.default_target_pdb_id)
        if target is None:
            target = await self.ensure_default_target()

        smiles_hash = smiles_to_hash(smiles)
        existing = await self.get_molecule_by_hash(smiles_hash, target.id)
        
        # Si ya existe, verificamos si podemos "reclamarla"
        if existing is not None:
            # Si la molécula existe pero pertenece al usuario demo y ahora tenemos un usuario real,
            # actualizamos el dueño para que aparezca en su historial y no le de 403.
            if user_id is not None:
                demo_user = await self.get_or_create_test_user()
                if existing.user_id == demo_user.id and user_id != demo_user.id:
                    existing.user_id = user_id
                    existing.updated_at = datetime.now(UTC)
                    await self.db.flush()
                    log.info("molécula existente reclamada por usuario", molecule_id=str(existing.id), user_id=str(user_id))
            return existing

        if user_id is None:
            user = await self.get_or_create_test_user()
            user_id = user.id

        molecule = MoleculeORM(
            smiles=smiles,
            name=name,
            status=MoleculeStatus.PENDING,
            mutation_type=mutation_type,
            parent_id=parent_id,
            user_id=user_id,
            target_id=target.id,
            smiles_hash=smiles_hash,
        )
        self.db.add(molecule)
        await self.db.flush()
        return molecule

    async def set_molecule_status(
        self,
        molecule_id: uuid.UUID,
        status_value: MoleculeStatus,
    ) -> MoleculeORM:
        molecule = await self.get_molecule(molecule_id)
        if molecule is None:
            raise DatabaseQueryError(f"Molecule '{molecule_id}' no encontrada")

        molecule.status = status_value
        molecule.updated_at = datetime.now(UTC)
        await self.db.flush()
        return molecule

    async def get_evaluation_result(
        self,
        molecule_id: uuid.UUID,
    ) -> EvaluationResultORM | None:
        stmt = (
            select(EvaluationResultORM)
            .join(MoleculeORM, EvaluationResultORM.molecule_id == MoleculeORM.id)
            .join(TargetORM, MoleculeORM.target_id == TargetORM.id)
            .where(EvaluationResultORM.molecule_id == molecule_id)
            .options(joinedload(EvaluationResultORM.molecule).joinedload(MoleculeORM.target))
        )
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def upsert_evaluation_result(
        self,
        molecule_id: uuid.UUID,
        properties: PhysicochemicalProperties | None = None,
        docking: DockingResult | None = None,
        scores: dict[str, Any] | None = None,
        ai_report: str | None = None,
        is_control: bool = False,
        error_message: str | None = None,
        celery_task_id: str | None = None,
    ) -> EvaluationResultORM:
        result = await self.get_evaluation_result(molecule_id)
        if result is None:
            result = EvaluationResultORM(molecule_id=molecule_id)
            self.db.add(result)
        
        result.is_control = is_control

        if properties is not None:
            # Cast all numerics to native Python types
            result.molecular_weight = float(properties.molecular_weight)
            result.log_p = float(properties.log_p)
            result.tpsa = float(properties.tpsa)
            result.hbd = int(properties.hbd)
            result.hba = int(properties.hba)
            result.rotatable_bonds = int(properties.rotatable_bonds)
            result.heavy_atom_count = int(properties.heavy_atom_count)
            result.ring_count = int(properties.ring_count)
            result.lipinski_pass = bool(properties.lipinski_pass)
            result.veber_pass = bool(properties.veber_pass)
            result.qed = float(properties.qed)
            result.sa_score = float(properties.sa_score)
            result.sa_reasons = list(properties.sa_reasons)

        if docking is not None:
            # Ensure all numerics in DockingResult are native types
            result.affinity_kcal = float(docking.best_affinity)
            # For poses, cast all numerics in each pose
            def cast_pose(p):
                return {
                    "rank": int(p.rank),
                    "affinity": float(p.affinity),
                    "rmsd_lb": float(p.rmsd_lb),
                    "rmsd_ub": float(p.rmsd_ub),
                }
            result.docking_poses = [cast_pose(pose) for pose in docking.poses]
            # Only allow output SDF from docking as poses_file_path
            if hasattr(docking, 'poses_file_path') and docking.poses_file_path and docking.poses_file_path.endswith('.sdf'):
                result.poses_file_path = str(docking.poses_file_path)
            else:
                result.poses_file_path = None
            result.parsing_source = str(docking.parsing_source) if docking.parsing_source is not None else None
            result.vina_version = str(docking.vina_version) if docking.vina_version is not None else None
            result.vina_random_seed = int(docking.vina_random_seed) if docking.vina_random_seed is not None else None
            result.scientific_warnings = list(docking.scientific_warnings) if docking.scientific_warnings is not None else []
            result.hotspots_hit = list(docking.hotspots_hit) if hasattr(docking, "hotspots_hit") and docking.hotspots_hit is not None else []

        if scores is not None:
            # Cast all scores to native float
            def safe_float(val):
                try:
                    return float(val) if val is not None else None
                except Exception:
                    return None
            result.affinity_score = safe_float(scores.get("affinity_score"))
            result.adme_score = safe_float(scores.get("adme_score"))
            result.druglikeness_score = safe_float(scores.get("druglikeness_score"))
            result.total_score = safe_float(scores.get("total_score"))
            result.specificity_score = safe_float(scores.get("specificity_score"))
            result.ligand_efficiency = safe_float(scores.get("ligand_efficiency"))
            result.ligand_lipophilicity_efficiency = safe_float(scores.get("lipophilic_efficiency"))
            result.affinity_threshold = safe_float(scores.get("affinity_threshold"))

        if ai_report is not None:
            result.ai_report = ai_report

        if error_message is not None:
            result.error_message = error_message
            # Si hay error, limpiar scores y docking previos para evitar datos stale
            result.total_score = None
            result.affinity_score = None
            result.adme_score = None
            result.druglikeness_score = None
            result.affinity_kcal = None
            result.docking_poses = None
            result.poses_file_path = None
            result.scientific_warnings = []
            result.ai_report = None

        if celery_task_id is not None:
            result.celery_task_id = celery_task_id

        result.evaluated_at = datetime.now(UTC)
        await self.db.flush()
        return result

    async def list_user_molecules(
        self,
        user_id: uuid.UUID,
        limit: int = 50,
    ) -> list[MoleculeORM]:
        stmt = (
            select(MoleculeORM)
            .options(
                selectinload(MoleculeORM.target),
                selectinload(MoleculeORM.evaluation_result),
            )
            .where(MoleculeORM.user_id == user_id)
            .order_by(MoleculeORM.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_anonymous_limit(self, ip_address: str) -> AnonymousLimitORM | None:
        stmt = select(AnonymousLimitORM).where(AnonymousLimitORM.ip_address == ip_address)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def increment_anonymous_count(self, ip_address: str) -> int:
        limit = await self.get_anonymous_limit(ip_address)
        if limit is None:
            limit = AnonymousLimitORM(ip_address=ip_address, request_count=1)
            self.db.add(limit)
        else:
            limit.request_count += 1
        
        await self.db.flush()
        return limit.request_count


def get_repository(db: AsyncSession) -> Repository:
    return Repository(db)