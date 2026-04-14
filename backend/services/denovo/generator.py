"""
services/denovo/generator.py

Generador de sugerencias moleculares usando RDKit.

Fase 1: Usa transformaciones de química medicinal basadas en reglas
(bioisosteric replacements, scaffold hopping hints, functional group
modifications) para sugerir variantes de una molécula evaluada.

Fase 2 (futura): Integración con REINVENT4 o MolGPT para generación
guiada por scoring function.

Transparencia científica:
- Cada sugerencia tiene un tipo (bioisostere, substitution, etc.)
- Cada sugerencia tiene un razonamiento explícito
- Ninguna sugerencia se presenta como "mejora garantizada"
- El usuario decide si evalúa la sugerencia

Referencia:
  Meanwell (2011) "Synopsis of Some Recent Tactical Application of
  Bioisosteres in Drug Design" J Med Chem 54(8):2529-2591
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class MolecularSuggestion:
    """Una sugerencia de modificación molecular."""
    smiles: str
    name: str
    description: str
    rationale: str
    modification_type: str  # bioisostere, substitution, addition, deletion, scaffold
    expected_effect: str  # "may_improve_affinity", "may_improve_adme", "may_improve_druglikeness"
    confidence: str  # "high", "medium", "low"
    source: str = "rule_based"  # "rule_based", "reinvent", "molgpt"
    warnings: list[str] = field(default_factory=list)


@dataclass
class GenerationResult:
    """Resultado del generador de sugerencias."""
    success: bool
    suggestions: list[MolecularSuggestion] = field(default_factory=list)
    method: str = "rule_based"
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


# ── Transformaciones de química medicinal ─────────────────────────────────────

# Bioisosteric replacements comunes
# Ref: Meanwell (2011), Patani & LaVoie (1996)
BIOISOSTERIC_PAIRS = [
    # (SMARTS pattern to find, replacement SMARTS, name, rationale)
    ("C(=O)O", "C(=O)N", "Ácido → Amida",
     "Reemplazo bioisostérico clásico. La amida es más estable metabólicamente "
     "y puede mantener interacciones similares de H-bond."),
    ("c1ccccc1", "c1ccncc1", "Fenilo → Piridina",
     "Introducir un nitrógeno en el anillo aromático puede mejorar la solubilidad "
     "acuosa y crear un nuevo punto de interacción H-bond con el target."),
    ("C(F)(F)F", "C(=O)C", "Trifluorometil → Acetil",
     "Puede mejorar propiedades metabólicas en ciertos contextos, "
     "aunque cambia las propiedades electrónicas significativamente."),
    ("S(=O)(=O)N", "C(=O)N", "Sulfonamida → Amida",
     "Simplifica la molécula manteniendo la capacidad de H-bond. "
     "Puede mejorar la permeabilidad de membrana."),
    ("OC", "NC", "O-metil → N-metil",
     "La N-metilación puede mejorar la permeabilidad de membrana "
     "y la estabilidad metabólica en algunos scaffolds."),
]


def _try_rdkit_available() -> bool:
    """Verifica que RDKit esté disponible."""
    try:
        from rdkit import Chem
        return True
    except ImportError:
        return False


def generate_suggestions(
    smiles: str,
    properties: dict[str, Any] | None = None,
    scores: dict[str, Any] | None = None,
    max_suggestions: int = 5,
) -> GenerationResult:
    """
    Genera sugerencias de modificación molecular basadas en reglas.

    Args:
        smiles: SMILES canónico de la molécula a optimizar
        properties: Propiedades fisicoquímicas calculadas (opcional)
        scores: Scores de evaluación (opcional, para guiar sugerencias)
        max_suggestions: Máximo de sugerencias a generar

    Returns:
        GenerationResult con lista de sugerencias.

    Las sugerencias son HIPÓTESIS computacionales que deben evaluarse.
    No se garantiza que ninguna modificación mejore las propiedades.
    """
    if not _try_rdkit_available():
        return GenerationResult(
            success=False,
            error="RDKit no disponible para generación de sugerencias",
        )

    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return GenerationResult(
                success=False,
                error=f"SMILES inválido: {smiles}",
            )

        suggestions = []

        # 1. Sugerencias basadas en propiedades problemáticas
        if properties:
            mw = properties.get("molecular_weight", 0)
            logp = properties.get("log_p", 0)
            tpsa = properties.get("tpsa", 0)
            hbd = properties.get("hbd", 0)

            if logp and logp > 5:
                suggestions.append(MolecularSuggestion(
                    smiles="",  # Se llenaría con generación concreta
                    name="Reducir lipofilia",
                    description="LogP > 5 puede indicar pobre solubilidad acuosa",
                    rationale=(
                        f"LogP actual = {logp:.2f}. Valores > 5 violan la regla de Lipinski "
                        "y se asocian con pobre absorción oral y solubilidad. "
                        "Considerar: agregar grupos polares (OH, NH2), "
                        "reemplazar C-H por N (heteroaromáticos), "
                        "o reducir cadenas alifáticas."
                    ),
                    modification_type="property_optimization",
                    expected_effect="may_improve_adme",
                    confidence="high",
                    warnings=["Reducir LogP puede afectar la afinidad por el target"],
                ))

            if tpsa and tpsa < 20:
                suggestions.append(MolecularSuggestion(
                    smiles="",
                    name="Aumentar área polar",
                    description="TPSA < 20 Å² puede indicar baja solubilidad",
                    rationale=(
                        f"TPSA actual = {tpsa:.1f} Å². Valor muy bajo asociado con "
                        "pobre solubilidad. Considerar agregar grupos polares como "
                        "amida, sulfonamida, o heteroátomos en anillos."
                    ),
                    modification_type="property_optimization",
                    expected_effect="may_improve_adme",
                    confidence="medium",
                    warnings=["Aumentar TPSA > 140 Å² perjudicaría permeabilidad"],
                ))

            if tpsa and tpsa > 140:
                suggestions.append(MolecularSuggestion(
                    smiles="",
                    name="Reducir área polar",
                    description="TPSA > 140 Å² compromete permeabilidad de membrana",
                    rationale=(
                        f"TPSA actual = {tpsa:.1f} Å². Supera el umbral de Veber "
                        "para absorción oral. Considerar: N-metilación de amidas, "
                        "convertir OH a éter, o reducir grupos polares expuestos."
                    ),
                    modification_type="property_optimization",
                    expected_effect="may_improve_adme",
                    confidence="high",
                    warnings=["Reducir polaridad puede disminuir solubilidad"],
                ))

            if mw and mw > 500:
                suggestions.append(MolecularSuggestion(
                    smiles="",
                    name="Reducir peso molecular",
                    description="MW > 500 Da viola la regla de Lipinski",
                    rationale=(
                        f"MW actual = {mw:.1f} Da. Considerar eliminar grupos "
                        "periféricos no esenciales para la interacción con el target. "
                        "Fragmentos más pequeños suelen tener mejor farmacocinética."
                    ),
                    modification_type="deletion",
                    expected_effect="may_improve_druglikeness",
                    confidence="medium",
                    warnings=["Eliminar fragmentos puede reducir afinidad"],
                ))

        # 2. Sugerencias bioisostéricas basadas en estructura
        smiles_str = smiles
        for pattern, replacement, name, rationale in BIOISOSTERIC_PAIRS:
            if len(suggestions) >= max_suggestions:
                break
            if pattern in smiles_str:
                new_smiles = smiles_str.replace(pattern, replacement, 1)
                # Validar que el resultado sea una molécula válida
                new_mol = Chem.MolFromSmiles(new_smiles)
                if new_mol is not None:
                    canonical = Chem.MolToSmiles(new_mol)
                    if canonical != Chem.MolToSmiles(mol):  # No sugerir la misma molécula
                        suggestions.append(MolecularSuggestion(
                            smiles=canonical,
                            name=name,
                            description=f"Reemplazo bioisostérico: {pattern} → {replacement}",
                            rationale=rationale,
                            modification_type="bioisostere",
                            expected_effect="may_improve_adme",
                            confidence="medium",
                            warnings=[
                                "Los reemplazos bioisostéricos pueden alterar la afinidad. "
                                "Se recomienda evaluar la sugerencia para verificar."
                            ],
                        ))

        # 3. Sugerencia general de fragmento si el score de afinidad es bajo
        if scores and scores.get("affinity_score", 100) < 40:
            suggestions.append(MolecularSuggestion(
                smiles="",
                name="Mejorar interacciones con el target",
                description="El score de afinidad es bajo — considerar modificaciones del farmacóforo",
                rationale=(
                    "Un score de afinidad bajo sugiere interacciones débiles con el sitio activo. "
                    "Considerar: (1) agregar grupos aromáticos para interacciones π-π, "
                    "(2) agregar H-bond donors/acceptors para interacciones polares, "
                    "(3) modificar la geometría para mejor complementariedad estérica."
                ),
                modification_type="scaffold",
                expected_effect="may_improve_affinity",
                confidence="low",
                warnings=[
                    "Esta es una sugerencia general de química medicinal. "
                    "Se necesita análisis visual de la pose de docking para "
                    "guiar modificaciones específicas."
                ],
            ))

        # Limitar a max_suggestions
        suggestions = suggestions[:max_suggestions]

        result_warnings = [
            "Las sugerencias son hipótesis computacionales basadas en reglas de química medicinal.",
            "Ninguna sugerencia garantiza mejora en actividad biológica real.",
            "Se recomienda evaluar cada sugerencia con el pipeline completo antes de aceptarla.",
        ]

        if not suggestions:
            result_warnings.append(
                "No se encontraron sugerencias automáticas para esta molécula. "
                "Considerar análisis manual de la pose de docking."
            )

        log.info(
            "sugerencias generadas",
            smiles=smiles[:50],
            num_suggestions=len(suggestions),
            method="rule_based",
        )

        return GenerationResult(
            success=True,
            suggestions=suggestions,
            method="rule_based",
            warnings=result_warnings,
        )

    except Exception as e:
        log.error("error generando sugerencias", error=str(e))
        return GenerationResult(
            success=False,
            error=str(e),
            warnings=["El generador de sugerencias falló. Esto no afecta la evaluación principal."],
        )
