"""
rescoring/structural_family.py

Clasificación de complejos de PDBbind por familia estructural de proteínas.

Según ML_RESCORING_ARCHITECTURE.md (Problema 6), la clasificación debe ser:
  - Por ESTRUCTURA del binding site (fold, tipo de bolsillo)
  - NO por sistema biológico/órgano

Familias definidas:
  - GPCRs Clase A: 7-TM, bolsillo transmembranal
  - Kinasas: ATP-binding, hinge region
  - Proteasas: surco catalítico
  - Receptores nucleares: bolsillo lipofílico cerrado
  - Enzimas solubles: variable
  - Otros: no clasificados

Estrategia de clasificación:
  1. Primero: lookup por PDB ID en tabla conocida (PDBbind curated list)
  2. Segundo: keywords en header del PDB file
  3. Tercero: SIFTS/UniProt mapping (offline, si disponible)
  4. Default: "other"

Limitación documentada: La clasificación heurística tiene ~80% de accuracy.
Para un pipeline científico completo, se usarían ECOD/PFAM annotations.
Este módulo es suficiente para el propósito de evaluar performance por familia
y detectar sub-representación de GPCRs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from logger import get_logger

log = get_logger(__name__)


# Familias estructurales de proteínas
FAMILIES = [
    "gpcr",
    "kinase",
    "protease",
    "nuclear_receptor",
    "soluble_enzyme",
    "other",
]


# ─── Keywords para clasificación heurística desde PDB headers ───
# Cada familia tiene una lista de regex patterns que se buscan en:
# - HEADER line del PDB
# - TITLE line del PDB
# - COMPND line del PDB
# Los patterns están ordenados del más específico al más genérico.

FAMILY_PATTERNS: dict[str, list[re.Pattern]] = {
    "gpcr": [
        re.compile(r"\b(gpcr|g.protein.coupled)\b", re.I),
        re.compile(r"\b(serotonin|5-ht|5ht)\b.*receptor", re.I),
        re.compile(r"\b(dopamine|d[1-5])\b.*receptor", re.I),
        re.compile(r"\b(adrenergic|adrenoceptor)\b", re.I),
        re.compile(r"\b(muscarinic|cholinergic)\b.*receptor", re.I),
        re.compile(r"\b(opioid|opiate)\b.*receptor", re.I),
        re.compile(r"\b(cannabinoid|cb[12])\b.*receptor", re.I),
        re.compile(r"\b(histamine|h[1-4])\b.*receptor", re.I),
        re.compile(r"\b(angiotensin|at[12])\b.*receptor", re.I),
        re.compile(r"\b(endothelin|et[ab])\b.*receptor", re.I),
        re.compile(r"\b(chemokine|cxc|ccr)\b.*receptor", re.I),
        re.compile(r"\b(adenosine|a[123])\b.*receptor", re.I),
        re.compile(r"\b(rhodopsin)\b", re.I),
        re.compile(r"\b(melatonin|mt[12])\b.*receptor", re.I),
        re.compile(r"\btransmembrane.*receptor\b", re.I),
        re.compile(r"\b7.?tm\b", re.I),
    ],
    "kinase": [
        re.compile(r"\bkinase\b", re.I),
        re.compile(r"\b(cdk\d|cyclin.dependent)\b", re.I),
        re.compile(r"\b(egfr|her2|erbb)\b", re.I),
        re.compile(r"\b(abl|bcr.abl)\b", re.I),
        re.compile(r"\b(braf|raf)\b", re.I),
        re.compile(r"\b(mapk|mek|erk)\b", re.I),
        re.compile(r"\b(jak|janus)\b", re.I),
        re.compile(r"\b(aurora|plk|polo)\b", re.I),
        re.compile(r"\b(pi3k|akt|mtor)\b", re.I),
        re.compile(r"\b(vegfr|fgfr|pdgfr)\b", re.I),
        re.compile(r"\b(src|lyn|fyn)\b", re.I),
        re.compile(r"\b(phosphotransferase)\b", re.I),
    ],
    "protease": [
        re.compile(r"\b(protease|proteinase|peptidase)\b", re.I),
        re.compile(r"\b(hiv.*(protease|pr))\b", re.I),
        re.compile(r"\b(caspase|apoptosis.*protease)\b", re.I),
        re.compile(r"\b(thrombin|trypsin|chymotrypsin)\b", re.I),
        re.compile(r"\b(cathepsin|calpain)\b", re.I),
        re.compile(r"\b(matrix metalloproteinase|mmp)\b", re.I),
        re.compile(r"\b(renin|pepsin|aspartyl)\b", re.I),
        re.compile(r"\b(elastase|subtilisin)\b", re.I),
        re.compile(r"\b(secretase|adam|bace)\b", re.I),
        re.compile(r"\b(hepatitis.*protease|ns3)\b", re.I),
        re.compile(r"\b(coronavirus.*protease|mpro|3cl)\b", re.I),
    ],
    "nuclear_receptor": [
        re.compile(r"\b(nuclear.*receptor)\b", re.I),
        re.compile(r"\b(estrogen.*receptor|er.alpha|er.beta)\b", re.I),
        re.compile(r"\b(androgen.*receptor)\b", re.I),
        re.compile(r"\b(progesterone.*receptor)\b", re.I),
        re.compile(r"\b(glucocorticoid.*receptor)\b", re.I),
        re.compile(r"\b(mineralocorticoid)\b", re.I),
        re.compile(r"\b(thyroid.*receptor)\b", re.I),
        re.compile(r"\b(retinoic.*receptor|rar|rxr)\b", re.I),
        re.compile(r"\b(ppar|peroxisome.*proliferator)\b", re.I),
        re.compile(r"\b(vitamin.*d.*receptor|vdr)\b", re.I),
        re.compile(r"\b(liver.*x.*receptor|lxr)\b", re.I),
        re.compile(r"\b(farnesoid.*x|fxr)\b", re.I),
    ],
    "soluble_enzyme": [
        re.compile(r"\b(cyclooxygenase|cox.?[12])\b", re.I),
        re.compile(r"\b(acetylcholinesterase|ache)\b", re.I),
        re.compile(r"\b(phosphodiesterase|pde\d)\b", re.I),
        re.compile(r"\b(carbonic.*anhydrase)\b", re.I),
        re.compile(r"\b(dihydrofolate.*reductase|dhfr)\b", re.I),
        re.compile(r"\b(thymidylate.*synthase)\b", re.I),
        re.compile(r"\b(neuraminidase)\b", re.I),
        re.compile(r"\b(reverse.*transcriptase)\b", re.I),
        re.compile(r"\b(topoisomerase)\b", re.I),
        re.compile(r"\b(dehydrogenase)\b", re.I),
        re.compile(r"\b(transferase)\b", re.I),  # Catch-all for transferases
        re.compile(r"\b(hydrolase)\b", re.I),
        re.compile(r"\b(oxidoreductase)\b", re.I),
        re.compile(r"\b(lyase)\b", re.I),
        re.compile(r"\b(isomerase)\b", re.I),
        re.compile(r"\b(ligase)\b", re.I),
        re.compile(r"\b(synthase|synthetase)\b", re.I),
        re.compile(r"\b(reductase)\b", re.I),
    ],
}


# ─── PDB IDs conocidos para familias curadas manualmente ───
# Casos donde la clasificación heurística falla o donde queremos certeza.
# Fuentes: PDBbind documentation, RCSB annotations.
# Solo incluimos los más comunes/importantes. Se extiende según necesidad.

CURATED_FAMILIES: dict[str, str] = {
    # GPCRs (comunes en PDBbind)
    "7e2y": "gpcr",  # 5-HT1A (nuestro target principal)
    "6g79": "gpcr",  # 5-HT2A
    "3rze": "gpcr",  # β2-adrenérgico
    "3pbl": "gpcr",  # D3 dopamine
    "6cm4": "gpcr",  # D2 dopamine
    "4dkl": "gpcr",  # μ-opioid
    "4rws": "gpcr",  # δ-opioid
    "5v54": "gpcr",  # κ-opioid
    "5rgs": "gpcr",  # A2A adenosine
    "2ydv": "gpcr",  # A2A adenosine
    # Kinasas emblemáticas
    "1oiu": "kinase",  # CDK2
    "2hyy": "kinase",  # ABL
    "1m17": "kinase",  # EGFR
    "3poz": "kinase",  # BRAF
    "4yne": "kinase",  # JAK2
    # Proteasas emblemáticas
    "1hpv": "protease",  # HIV-1 protease
    "1hxw": "protease",  # Caspase-3
    "3own": "protease",  # β-secretase/BACE
    # Receptores nucleares
    "1err": "nuclear_receptor",  # Estrogen receptor
    "2am9": "nuclear_receptor",  # Androgen receptor
    "1fm6": "nuclear_receptor",  # PPARγ
}


@dataclass
class FamilyClassification:
    """Resultado de la clasificación de un complejo."""
    pdb_id: str
    family: str
    confidence: str  # "curated", "high", "low", "unclassified"
    matched_pattern: str = ""  # Pattern que matcheó (para debug)
    source: str = ""  # "curated_lookup", "pdb_header", "default"


class StructuralFamilyClassifier:
    """
    Clasifica proteínas de PDBbind en familias estructurales.

    Estrategia (en orden de prioridad):
    1. Lookup en tabla curada (confianza: curated)
    2. PDB header keywords (confianza: high o low)
    3. Default → "other" (confianza: unclassified)

    Limitación documentada: clasificación heurística ~80% accuracy.
    Para pipeline completo, usar ECOD o PFAM annotations.
    """

    def __init__(
        self,
        additional_curated: dict[str, str] | None = None,
    ):
        """
        Args:
            additional_curated: mapeo extra PDB ID → familia
        """
        self._curated = dict(CURATED_FAMILIES)
        if additional_curated:
            self._curated.update(additional_curated)

    def classify(
        self,
        pdb_id: str,
        pdb_header: str = "",
    ) -> FamilyClassification:
        """
        Clasificar un complejo en una familia estructural.

        Args:
            pdb_id: PDB ID (4-char)
            pdb_header: contenido de HEADER + TITLE + COMPND del PDB file

        Returns:
            FamilyClassification
        """
        pdb_id = pdb_id.lower()

        # 1. Lookup en tabla curada
        if pdb_id in self._curated:
            return FamilyClassification(
                pdb_id=pdb_id,
                family=self._curated[pdb_id],
                confidence="curated",
                source="curated_lookup",
            )

        # 2. Keywords en PDB header
        if pdb_header:
            for family, patterns in FAMILY_PATTERNS.items():
                for pattern in patterns:
                    match = pattern.search(pdb_header)
                    if match:
                        return FamilyClassification(
                            pdb_id=pdb_id,
                            family=family,
                            confidence="high" if family != "soluble_enzyme" else "low",
                            matched_pattern=match.group(0),
                            source="pdb_header",
                        )

        # 3. Default
        return FamilyClassification(
            pdb_id=pdb_id,
            family="other",
            confidence="unclassified",
            source="default",
        )

    def classify_from_pdb_file(
        self,
        pdb_id: str,
        pdb_path: str | Path | None = None,
    ) -> FamilyClassification:
        """
        Clasificar leyendo el header del archivo PDB.

        Args:
            pdb_id: PDB ID
            pdb_path: path al archivo PDB de la proteína
        """
        header = ""
        if pdb_path:
            header = self._extract_pdb_header(Path(pdb_path))
        return self.classify(pdb_id, header)

    def classify_all(
        self,
        complexes: list[Any],
    ) -> dict[str, FamilyClassification]:
        """
        Clasificar todos los complejos.

        Args:
            complexes: lista de PDBBindComplex

        Returns:
            dict {pdb_id: FamilyClassification}
        """
        results = {}
        for cpx in complexes:
            classification = self.classify_from_pdb_file(
                pdb_id=cpx.pdb_id,
                pdb_path=cpx.protein_pdb_path,
            )
            results[cpx.pdb_id] = classification

        # Log summary
        family_counts = {}
        confidence_counts = {}
        for cls in results.values():
            family_counts[cls.family] = family_counts.get(cls.family, 0) + 1
            confidence_counts[cls.confidence] = confidence_counts.get(cls.confidence, 0) + 1

        log.info(
            "family_classification_complete",
            total=len(results),
            families=family_counts,
            confidence=confidence_counts,
        )

        return results

    @staticmethod
    def _extract_pdb_header(pdb_path: Path) -> str:
        """
        Extraer HEADER, TITLE, COMPND de un archivo PDB.

        Solo lee las primeras ~100 líneas (el header metadata).
        """
        if not pdb_path.exists():
            return ""

        lines = []
        try:
            with open(pdb_path) as f:
                for i, line in enumerate(f):
                    if i > 200:  # Solo leer header
                        break
                    if line.startswith(("HEADER", "TITLE", "COMPND", "KEYWDS")):
                        lines.append(line[10:].strip())
                    elif line.startswith("ATOM"):
                        break  # Pasamos el header
        except Exception:
            return ""

        return " ".join(lines)

    def get_family_summary(
        self,
        classifications: dict[str, FamilyClassification],
    ) -> dict[str, Any]:
        """
        Generar resumen estadístico de la clasificación.

        Útil para evaluar representación de cada familia en el dataset.
        """
        summary: dict[str, Any] = {
            "total": len(classifications),
            "by_family": {},
            "by_confidence": {},
        }

        for cls in classifications.values():
            # Por familia
            if cls.family not in summary["by_family"]:
                summary["by_family"][cls.family] = {
                    "count": 0, "pdb_ids_sample": [], "confidence_breakdown": {}
                }
            fam = summary["by_family"][cls.family]
            fam["count"] += 1
            if len(fam["pdb_ids_sample"]) < 10:
                fam["pdb_ids_sample"].append(cls.pdb_id)
            fam["confidence_breakdown"][cls.confidence] = (
                fam["confidence_breakdown"].get(cls.confidence, 0) + 1
            )

            # Por confianza
            summary["by_confidence"][cls.confidence] = (
                summary["by_confidence"].get(cls.confidence, 0) + 1
            )

        # Calcular porcentajes
        total = max(len(classifications), 1)
        for family_data in summary["by_family"].values():
            family_data["pct"] = round(family_data["count"] / total * 100, 1)

        return summary
