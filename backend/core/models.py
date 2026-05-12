"""
core/models.py

Contrato de datos de todo el sistema. Hay dos capas aquí:

1. ORM Models (SQLAlchemy): representan las tablas de PostgreSQL.
   Se usan para leer/escribir en la DB. Solo viven en db/repository.py.

2. Pydantic Schemas: representan los datos que viajan entre servicios
   y que se exponen en la API. Se usan en routers, servicios y workers.

Por qué separarlos:
- Los ORM models tienen relaciones lazy-loaded que explotan fuera de
  una sesión de DB activa. Los Pydantic schemas son simples dataclasses
  serializables que funcionan en cualquier contexto.
- Los endpoints nunca deben exponer ORM objects directamente —
  siempre se convierten a Pydantic schemas antes de salir.
"""

import enum
import uuid
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


# ── Base ORM ──────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Base declarativa para todos los ORM models."""
    pass


# ── Enums ─────────────────────────────────────────────────────────────────────

class MoleculeStatus(str, enum.Enum):
    """
    Ciclo de vida de una molécula en el sistema.

    PENDING   → recién creada, esperando validación química
    VALIDATED → SMILES válido, propiedades calculadas
    DOCKING   → job de docking en cola o corriendo
    EVALUATED → docking completo, score calculado
    FAILED    → algún paso falló (ver error_message en EvaluationResult)
    """
    PENDING   = "pending"
    VALIDATED = "validated"
    DOCKING   = "docking"
    EVALUATED = "evaluated"
    FAILED    = "failed"


class MutationType(str, enum.Enum):
    """
    Tipo de transformación química que el usuario aplicó.
    Se guarda para poder reconstruir el árbol de modificaciones.
    """
    SUBSTITUTION    = "substitution"     # sustitución de grupo funcional
    BIOISOSTERE     = "bioisostere"      # reemplazo bioisostérico
    RING_CLOSURE    = "ring_closure"     # ciclación
    RING_OPENING    = "ring_opening"     # apertura de anillo
    ADDITION        = "addition"         # adición de grupo
    DELETION        = "deletion"         # eliminación de grupo
    STEREOCHEMISTRY = "stereochemistry"  # cambio estereoquímico
    SCAFFOLD        = "scaffold"         # cambio de scaffold completo


# ═════════════════════════════════════════════════════════════════════════════
# ORM MODELS — tablas de PostgreSQL
# ═════════════════════════════════════════════════════════════════════════════

class TargetORM(Base):
    """
    Target biológico (proteína) contra el que se hace el docking.
    En el MVP solo existe un target (5-HT1A, PDB: 7E2Y, cadena R).
    Xu et al., Nature 592:469-473 (2021).
    La tabla permite añadir más targets sin cambiar el schema.
    """
    __tablename__ = "targets"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pdb_id      = Column(String(10), unique=True, nullable=False, index=True)
    name        = Column(String(200), nullable=False)
    chain       = Column(String(5), nullable=False, default="A")
    description = Column(Text, nullable=True)

    # Coordenadas del grid box para Vina (Angstroms)
    # Se determinan del ligando co-cristalizado en el PDB
    grid_center_x = Column(Float, nullable=False)
    grid_center_y = Column(Float, nullable=False)
    grid_center_z = Column(Float, nullable=False)
    grid_size_x   = Column(Float, nullable=False, default=20.0)
    grid_size_y   = Column(Float, nullable=False, default=20.0)
    grid_size_z   = Column(Float, nullable=False, default=20.0)

    # Ruta en MinIO al archivo .pdbqt preparado (listo para Vina)
    prepared_file_path = Column(String(500), nullable=True)
    is_prepared        = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    molecules = relationship("MoleculeORM", back_populates="target")


class UserORM(Base):
    """Usuario del sistema. Mínimo para el MVP."""
    __tablename__ = "users"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email        = Column(String(320), unique=True, nullable=False, index=True)
    username     = Column(String(50), unique=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    is_active    = Column(Boolean, default=True, nullable=False)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    molecules = relationship("MoleculeORM", back_populates="user")


class MoleculeORM(Base):
    """
    Molécula diseñada por el usuario.

    parent_id permite reconstruir el árbol de modificaciones:
    lead_inicial → modificación_1 → modificación_2 → ...
    Esto es la base del sistema de "árbol evolutivo" del juego.
    """
    __tablename__ = "molecules"

    id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    smiles    = Column(Text, nullable=False)
    name      = Column(String(200), nullable=True)   # nombre opcional del usuario
    status    = Column(
        Enum(
            MoleculeStatus,
            values_callable=lambda e: [x.value for x in e],
            create_type=False,
        ),
        default=MoleculeStatus.PENDING,
        nullable=False,
        index=True,
    )
    mutation_type = Column(
        Enum(
            MutationType,
            values_callable=lambda e: [x.value for x in e],
            create_type=False,
        ),
        nullable=True,
    )

    # Árbol de modificaciones
    parent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("molecules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Foreign keys
    user_id   = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(UUID(as_uuid=True), ForeignKey("targets.id"), nullable=False)

    # Hash SHA-256 del SMILES canonicalizado.
    # Permite detectar moléculas duplicadas y usar cache de docking.
    smiles_hash = Column(String(64), nullable=False, index=True)
    is_saved    = Column(Boolean, default=False, server_default='false', nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relaciones
    user             = relationship("UserORM", back_populates="molecules")
    target           = relationship("TargetORM", back_populates="molecules")
    parent           = relationship("MoleculeORM", remote_side="MoleculeORM.id")
    evaluation_result = relationship(
        "EvaluationResultORM",
        back_populates="molecule",
        uselist=False,   # one-to-one
    )


class EvaluationResultORM(Base):
    """
    Resultado completo de la evaluación de una molécula.
    One-to-one con MoleculeORM — cada molécula tiene como máximo un resultado.
    """
    __tablename__ = "evaluation_results"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    molecule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("molecules.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # ── Docking (AutoDock Vina) ──────────────────────────────────────────────
    affinity_kcal    = Column(Float, nullable=True)   # kcal/mol, negativo = mejor
    affinity_score   = Column(Float, nullable=True)   # normalizado 0-100
    docking_poses    = Column(JSONB, nullable=True)   # lista de poses [{affinity, rmsd_lb, rmsd_ub}]
    poses_file_path  = Column(String(500), nullable=True)  # ruta .sdf en MinIO
    parsing_source   = Column(String(50), nullable=True)
    vina_version     = Column(String(50), nullable=True)
    vina_random_seed = Column(Integer, nullable=True)
    scientific_warnings = Column(JSONB, nullable=True)
    celery_task_id   = Column(String(200), nullable=True)  # para polling del frontend

    # ── Propiedades fisicoquímicas (RDKit) ───────────────────────────────────
    molecular_weight = Column(Float, nullable=True)
    log_p            = Column(Float, nullable=True)
    tpsa             = Column(Float, nullable=True)   # Topological Polar Surface Area
    hbd              = Column(Integer, nullable=True) # H-bond donors
    hba              = Column(Integer, nullable=True) # H-bond acceptors
    rotatable_bonds  = Column(Integer, nullable=True)
    heavy_atom_count = Column(Integer, nullable=True)
    ring_count       = Column(Integer, nullable=True)

    # ── Drug-likeness ────────────────────────────────────────────────────────
    lipinski_pass    = Column(Boolean, nullable=True)
    veber_pass       = Column(Boolean, nullable=True)
    qed              = Column(Float, nullable=True)  # QED: Bickerton et al., Nat Chem 2012

    # ── Scores normalizados (0–100 cada uno) ────────────────────────────────
    adme_score       = Column(Float, nullable=True)
    druglikeness_score = Column(Float, nullable=True)
    total_score      = Column(Float, nullable=True, index=True)  # score final del juego
    is_control       = Column(Boolean, default=False)           # si es True, se ignoran penalizaciones ADME

    # ── Reporte IA ───────────────────────────────────────────────────────────
    ai_report        = Column(Text, nullable=True)   # reporte narrativo de Claude

    # ── Blockchain ───────────────────────────────────────────────────────────
    blockchain_tx_id  = Column(String(200), nullable=True)
    blockchain_hash   = Column(String(64), nullable=True)

    # ── Metadatos ────────────────────────────────────────────────────────────
    error_message    = Column(Text, nullable=True)   # si status == FAILED
    evaluated_at     = Column(DateTime(timezone=True), server_default=func.now())

    molecule = relationship("MoleculeORM", back_populates="evaluation_result")


# ═════════════════════════════════════════════════════════════════════════════
# PYDANTIC SCHEMAS — contratos de datos entre servicios y API
# ═════════════════════════════════════════════════════════════════════════════

class PhysicochemicalProperties(BaseModel):
    """
    Propiedades fisicoquímicas calculadas por RDKit.
    Viajan desde chem/properties.py hacia scoring/engine.py y la API.
    """
    molecular_weight: float = Field(..., ge=0, description="Peso molecular en Da")
    log_p:            float = Field(..., description="Coeficiente de partición octanol/agua")
    tpsa:             float = Field(..., ge=0, description="Área polar topológica superficial en Å²")
    hbd:              int   = Field(..., ge=0, description="Número de dadores de H-bond")
    hba:              int   = Field(..., ge=0, description="Número de aceptores de H-bond")
    rotatable_bonds:  int   = Field(..., ge=0)
    heavy_atom_count: int   = Field(..., ge=1)
    ring_count:       int   = Field(..., ge=0)
    qed:              float = Field(..., ge=0, le=1, description="QED (Bickerton et al., Nat Chem 2012). 0-1, mayor = más drug-like.")
    lipinski_pass:    bool
    veber_pass:       bool

    @model_validator(mode="after")
    def validate_lipinski_consistency(self) -> "PhysicochemicalProperties":
        """
        Verifica que lipinski_pass sea coherente con los valores calculados.
        Lipinski: MW ≤ 500, logP ≤ 5, HBD ≤ 5, HBA ≤ 10.
        Si hay inconsistencia, es un bug en chem/properties.py.
        """
        expected = (
            self.molecular_weight <= 500
            and self.log_p <= 5
            and self.hbd <= 5
            and self.hba <= 10
        )
        if self.lipinski_pass != expected:
            raise ValueError(
                f"lipinski_pass={self.lipinski_pass} es inconsistente con "
                f"MW={self.molecular_weight}, logP={self.log_p}, "
                f"HBD={self.hbd}, HBA={self.hba}. "
                f"Valor esperado: {expected}"
            )
        return self


class DockingPose(BaseModel):
    """Una sola pose de docking retornada por AutoDock Vina."""
    rank:     int   = Field(..., ge=1)
    affinity: float = Field(..., description="Energía de unión en kcal/mol. Más negativo = mejor.")
    rmsd_lb:  float = Field(..., ge=0, description="RMSD lower bound vs pose 1")
    rmsd_ub:  float = Field(..., ge=0, description="RMSD upper bound vs pose 1")


class DockingResult(BaseModel):
    """Resultado completo del docking de una molécula contra un target."""
    best_affinity: float              = Field(..., description="Mejor afinidad (pose 1) en kcal/mol")
    poses:         list[DockingPose]  = Field(..., min_length=1)
    poses_file_path: str | None       = None   # ruta .sdf en MinIO
    parsing_source: Literal["sdf", "pdbqt", "vina_stdout"] = "sdf"
    vina_version: str | None = None
    vina_random_seed: int | None = None
    scientific_warnings: list[str] = Field(default_factory=list)

    @field_validator("best_affinity")
    @classmethod
    def affinity_must_be_negative(cls, v: float) -> float:
        """
        Las afinidades de Vina son siempre estrictamente negativas.
        Un valor >= 0 indica un error en el parsing del output de Vina
        o una ejecución inválida (una afinidad de 0.0 kcal/mol significa
        ausencia total de interacción, que no es un resultado válido).
        """
        if v >= 0:
            raise ValueError(
                f"La afinidad de docking debe ser estrictamente negativa (got {v}). "
                "Un valor >= 0 indica un error en el parsing de Vina o ausencia de interacción."
            )
        return v


class MoleculeCreate(BaseModel):
    """Schema para crear una molécula nueva. Input del endpoint POST /molecules."""
    smiles:        str              = Field(..., min_length=1, max_length=2000)
    name:          str | None       = Field(None, max_length=200)
    target_pdb_id: str              = Field(..., min_length=4, max_length=10)
    parent_id:     uuid.UUID | None = None
    mutation_type: MutationType | None = None

    @field_validator("smiles")
    @classmethod
    def smiles_must_not_be_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("SMILES no puede ser un string vacío o solo espacios")
        return stripped


class MoleculeRead(BaseModel):
    """Schema de respuesta al leer una molécula. Output de la API."""
    id:            uuid.UUID
    smiles:        str
    name:          str | None
    status:        MoleculeStatus
    mutation_type: MutationType | None
    parent_id:     uuid.UUID | None
    user_id:       uuid.UUID
    target_id:     uuid.UUID
    smiles_hash:   str
    is_saved:      bool
    created_at:    datetime
    updated_at:    datetime | None

    model_config = {"from_attributes": True}  # permite crear desde ORM object


class EvaluationResultRead(BaseModel):
    """Schema de respuesta completa de evaluación. Output principal de la API."""
    id:            uuid.UUID
    molecule_id:   uuid.UUID

    # Docking
    affinity_kcal:   float | None
    affinity_score:  float | None
    docking_poses:   list[DockingPose] | None
    poses_file_path: str | None        # ruta en MinIO al .sdf de poses
    parsing_source:  str | None
    vina_version:    str | None
    vina_random_seed: int | None
    scientific_warnings: list[str] | None
    celery_task_id:  str | None

    # Propiedades
    molecular_weight: float | None
    log_p:            float | None
    tpsa:             float | None
    hbd:              int | None
    hba:              int | None
    rotatable_bonds:  int | None
    heavy_atom_count: int | None
    ring_count:       int | None
    lipinski_pass:    bool | None
    veber_pass:       bool | None
    qed:              float | None

    # Scores
    adme_score:         float | None
    druglikeness_score: float | None
    total_score:        float | None   # 0–100, el score del juego

    @computed_field
    @property
    def ligand_efficiency(self) -> float | None:
        if self.affinity_kcal is not None and self.heavy_atom_count and self.heavy_atom_count > 0:
            return round(self.affinity_kcal / self.heavy_atom_count, 3)
        return None

    is_control:        bool = False

    # Reporte
    ai_report:         str | None
    poseData:          str | None = None  # Raw SDF content for 3D viewer


    # Blockchain
    blockchain_tx_id:  str | None

    error_message: str | None
    evaluated_at:  datetime

    model_config = {"from_attributes": True}


class ScoreBreakdown(BaseModel):
    """
    Desglose del score para mostrar al usuario en la UI del juego.
    Le permite entender por qué su molécula tiene ese puntaje
    y qué dimensión mejorar en el siguiente intento.
    """
    affinity_score:     float = Field(..., ge=0, le=100)
    adme_score:         float = Field(..., ge=0, le=100)
    druglikeness_score: float = Field(..., ge=0, le=100)
    total_score:        float = Field(..., ge=0, le=100)
    ligand_efficiency:  float | None = None

    # Pesos usados en el cálculo (para transparencia)
    weight_affinity:     float
    weight_adme:         float
    weight_druglikeness: float

    # Feedback textual para la UI
    strongest_dimension:  str   # ej. "afinidad"
    weakest_dimension:    str   # ej. "ADME"
    improvement_hint:     str   # ej. "Reduce el logP por debajo de 3.5"


class Target(BaseModel):
    """Schema de target biológico para la UI."""
    id:          uuid.UUID
    pdb_id:      str
    name:        str
    chain:       str
    description: str | None
    is_prepared: bool

    model_config = {"from_attributes": True}


class ValidationResult(BaseModel):
    """
    Resultado de la validación química de un SMILES.
    Retornado por el endpoint POST /chem/validate.
    """
    is_valid:         bool
    canonical_smiles: str | None   # SMILES canonicalizado por RDKit
    smiles_hash:      str | None   # SHA-256 del canonical SMILES
    errors:           list[str]    # vacío si is_valid == True
    warnings:         list[str]    # problemas no fatales (ej. valencia inusual pero válida)
    heavy_atom_count: int | None
    molecular_formula: str | None  # ej. "C9H8O4" (aspirina)


class JobStatus(BaseModel):
    """
    Estado de un job asíncrono de docking.
    El frontend hace polling a GET /docking/status/{task_id}.
    """
    task_id:    str
    status:     str   # "PENDING" | "STARTED" | "SUCCESS" | "FAILURE" | "RETRY"
    progress:   int   = Field(default=0, ge=0, le=100)   # 0-100
    result:     EvaluationResultRead | None = None
    error:      str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AIReportRequest(BaseModel):
    """
    Input del servicio de IA (services/ai/interpreter.py).
    Datos estructurados que Claude convierte en reporte narrativo.
    """
    molecule_smiles:  str
    target_name:      str
    affinity_kcal:    float
    affinity_score:   float
    properties:       PhysicochemicalProperties
    score_breakdown:  ScoreBreakdown
    parent_smiles:    str | None = None   # para comparar con la versión anterior
    mutation_type:    MutationType | None = None
    is_control:       bool = False

    model_config = {"from_attributes": True}


class BlockchainRecord(BaseModel):
    """Registro que se envía a Solana al certificar una molécula."""
    smiles_hash:  str   = Field(..., min_length=64, max_length=64)
    total_score:  float = Field(..., ge=0, le=100)
    target_pdb_id: str
    user_wallet:  str
    timestamp:    datetime

    @field_validator("smiles_hash")
    @classmethod
    def hash_must_be_hex(cls, v: str) -> str:
        try:
            int(v, 16)
        except ValueError:
            raise ValueError(f"smiles_hash debe ser un string hexadecimal válido, got: {v[:10]}...")
        return v
