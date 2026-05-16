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
        # 1. Target Base (7E2Y)
        target_7e2y = await self.get_target_by_pdb_id("7E2Y")
        if not target_7e2y:
            target_7e2y = TargetORM(
                pdb_id="7E2Y",
                name="5-HT1A serotonin receptor",
                chain="R",
                description="Target base del MVP científico de MolDesign.",
                grid_center_x=103.03, grid_center_y=114.79, grid_center_z=108.36,
                grid_size_x=25.0, grid_size_y=25.0, grid_size_z=25.0,
                requires_cns=True,
                structural_family="gpcr",
                organism="Homo sapiens",
                resolution=2.8,
                is_prepared=True,
                spearman_rho=0.512,
                hotspots=[
                    {"name": "MET97", "importance": 0.8},
                    {"name": "ASP116", "importance": 1.0},
                    {"name": "VAL117", "importance": 0.7},
                    {"name": "SER190", "importance": 0.6},
                    {"name": "PHE361", "importance": 0.9}
                ]
            )
            self.db.add(target_7e2y)
            log.info("target 7E2Y creado con hotspots")

        # 2. Hot Target (6B3J) - GLP-1R
        target_6b3j = await self.get_target_by_pdb_id("6B3J")
        if not target_6b3j:
            target_6b3j = TargetORM(
                pdb_id="6B3J",
                name="GLP-1 receptor (GLP-1R)",
                chain="R",
                description="Target prioritario para enfermedades metabólicas.",
                grid_center_x=120.5, grid_center_y=110.2, grid_center_z=95.8,
                grid_size_x=25.0, grid_size_y=25.0, grid_size_z=25.0,
                requires_cns=False,
                structural_family="gpcr",
                organism="Homo sapiens",
                resolution=3.3,
                is_prepared=True,
                is_hot=True,
                spearman_rho=0.485,
                hotspots=[
                    {"name": "TYR152", "importance": 0.9},
                    {"name": "ARG190", "importance": 1.0},
                    {"name": "LYS197", "importance": 0.8},
                    {"name": "ASP198", "importance": 1.0},
                    {"name": "GLN210", "importance": 0.7}
                ]
            )
            self.db.add(target_6b3j)
            log.info("target 6B3J (HOT) creado con hotspots")

        # 3. PCSK9 Target (2P4E)
        target_2p4e = await self.get_target_by_pdb_id("2P4E")
        if not target_2p4e:
            target_2p4e = TargetORM(
                pdb_id="2P4E",
                name="PCSK9 (Proprotein Convertase)",
                chain="A",
                description="Inhibición de la interacción PCSK9-LDLR para hipercolesterolemia.",
                grid_center_x=-14.6, grid_center_y=24.5, grid_center_z=-45.7,
                grid_size_x=22.0, grid_size_y=22.0, grid_size_z=22.0,
                requires_cns=False,
                structural_family="hydrolase",
                organism="Homo sapiens",
                resolution=1.97,
                is_prepared=True,
                spearman_rho=0.0, # Pendiente de validación sistemática
                hotspots=[
                    {"name": "GLY292", "importance": 1.0},
                    {"name": "TYR293", "importance": 1.0},
                    {"name": "SER294", "importance": 1.0}
                ]
            )
            self.db.add(target_2p4e)
            log.info("target 2P4E (PCSK9) creado con hotspots")

        await self.db.flush()
        return target_6b3j or target_7e2y

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

    async def get_moldex_molecules(
        self,
        user_id: uuid.UUID,
        target_pdb_id: str | None = None,
    ) -> list[EvaluationResultORM]:
        """Obtiene todas las moléculas evaluadas exitosamente para la Pokedex."""
        stmt = (
            select(EvaluationResultORM)
            .join(MoleculeORM, EvaluationResultORM.molecule_id == MoleculeORM.id)
            .join(TargetORM, MoleculeORM.target_id == TargetORM.id)
            .where(MoleculeORM.user_id == user_id)
            .where(MoleculeORM.status == MoleculeStatus.EVALUATED)
            .options(
                joinedload(EvaluationResultORM.molecule).joinedload(MoleculeORM.target)
            )
            .order_by(EvaluationResultORM.evaluated_at.desc())
        )
        
        if target_pdb_id:
            stmt = stmt.where(TargetORM.pdb_id == target_pdb_id.upper())
            
        result = await self.db.execute(stmt)
        return list(result.unique().scalars().all())

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
            result.affinity_multiplier = safe_float(scores.get("affinity_multiplier"))
            result.specificity_multiplier = safe_float(scores.get("specificity_multiplier"))

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

    async def delete_molecule(self, molecule_id: uuid.UUID) -> bool:
        """Elimina una molécula y sus resultados asociados (vía CASCADE)."""
        molecule = await self.db.get(MoleculeORM, molecule_id)
        if molecule:
            await self.db.delete(molecule)
            await self.db.flush()
            log.info("molécula eliminada por limpieza automática", molecule_id=str(molecule_id))
            return True
        return False


def get_repository(db: AsyncSession) -> Repository:
    return Repository(db)