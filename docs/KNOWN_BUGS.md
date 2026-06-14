# Known Bugs

This document tracks known issues that require future resolution.

## [v6.6] Desglose Farmacóforos "No disponible"
- **Descripción:** El gráfico de radar interactivo para el desglose de farmacóforos GNN aparece como "No disponible" en algunas moléculas que se evalúan correctamente (ej. Paracetamol).
- **Causa Raíz:** Vina despoja hidrógenos no-polares, y Meeko exporta la molécula PDBQT con cargas formales basadas en protonaciones específicas (ej. aminas secundarias). Al intentar mapear de forma topológica estricta (`GetSubstructMatch`) los átomos pesados del modelo 3D con la representación ideal 2D proveniente del SMILES canónico, RDKit rechaza el empalme debido a diferencias subyacentes en estados de protonación de red o valencias implícitas residuales en los fenoles (como el paracetamol). Al fallar el empalme, el fallback descarta los enlaces dobles y el conteo de SMARTS cae a cero.
- **Workaround:** Por el momento, la atención atómica SVG general (Heatmap) se dibuja siempre, pero el radar se oculta si la validación falla.
- **Próximos Pasos:** Implementar un mapeo basado en subestructuras MCS (Maximum Common Substructure) en lugar de un isomorfismo total estricto, o limpiar las valencias implícitas del ligando exportado por Meeko antes del match.
