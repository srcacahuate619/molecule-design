import io
from datetime import datetime
from rdkit import Chem
from rdkit.Chem import Draw
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from core.models import MoleculeORM, EvaluationResultORM

def get_2d_image(smiles: str, width=2.5*inch, height=2.5*inch):
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None
    img = Draw.MolToImage(mol, size=(400, 400))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return Image(buf, width=width, height=height)

def generate_certificate_pdf(mol: MoleculeORM, eval_result: EvaluationResultORM, target_name: str) -> io.BytesIO:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, 
        pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Styles
    brand_color = colors.HexColor('#3b82f6')
    
    title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=brand_color,
        alignment=1, # Center
        spaceAfter=10
    )
    
    subtitle_style = ParagraphStyle(
        'SubTitle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#64748b'),
        alignment=1,
        spaceAfter=20
    )
    
    section_title_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=15,
        spaceAfter=10,
        borderPadding=(0,0,2,0),
        borderColor=brand_color,
        borderWidth=1
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 10
    normal_style.leading = 14
    
    mono_style = ParagraphStyle(
        'Mono',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=9,
        textColor=colors.HexColor('#475569')
    )

    story = []

    # HEADER
    story.append(Paragraph("REPORTE CIENTÍFICO Y EVIDENCIA DIGITAL", title_style))
    cert_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    story.append(Paragraph(f"Registrado inmutablemente en Solana (Devnet) • {cert_date}", subtitle_style))
    
    # TARGET SECTION
    story.append(Paragraph("Receptor Biológico (Target)", section_title_style))
    story.append(Paragraph(f"<b>PDB ID:</b> {mol.target.pdb_id.upper() if mol.target else 'N/A'} | <b>Nombre:</b> {target_name}", normal_style))
    story.append(Spacer(1, 10))
    target_desc = mol.target.description if mol.target and mol.target.description else "Descripción fisiológica no disponible."
    story.append(Paragraph(f"<b>Contexto Fisiológico:</b> {target_desc}", normal_style))
    story.append(Spacer(1, 15))

    # MOLECULE SECTION
    story.append(Paragraph("Detalles de la Molécula", section_title_style))
    
    mol_info_data = [
        [Paragraph("<b>Nombre Asignado:</b>", normal_style), Paragraph(mol.name or f"Ligando {mol.smiles_hash[:8]}", normal_style)],
        [Paragraph("<b>ID de Sistema:</b>", normal_style), Paragraph(str(mol.id), mono_style)],
        [Paragraph("<b>SMILES Hash:</b>", normal_style), Paragraph(mol.smiles_hash, mono_style)],
        [Paragraph("<b>Estructura SMILES:</b>", normal_style), Paragraph(mol.smiles, mono_style)]
    ]
    
    mol_table = Table(mol_info_data, colWidths=[130, 360])
    mol_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    
    img = get_2d_image(mol.smiles)
    if img:
        # Create a layout with text on left, image on right
        layout_table = Table([[mol_table, img]], colWidths=[350, 140])
        layout_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
        story.append(layout_table)
    else:
        story.append(mol_table)

    story.append(Spacer(1, 15))

    # DOCKING & INTERACTION SECTION
    story.append(Paragraph("Interacción Molecular y Docking (AutoDock Vina)", section_title_style))
    
    dock_data = [
        ["Afinidad (Energía de Unión)", f"{eval_result.affinity_kcal:.2f} kcal/mol"],
        ["Score de Especificidad", f"{eval_result.specificity_score:.2f} / 100" if eval_result.specificity_score is not None else "N/A"],
        ["Eficiencia de Ligando (LE)", f"{eval_result.ligand_efficiency:.3f}" if eval_result.ligand_efficiency else "N/A"],
        ["Eficiencia Lipofílica (LLE)", f"{eval_result.ligand_lipophilicity_efficiency:.3f}" if hasattr(eval_result, 'ligand_lipophilicity_efficiency') and eval_result.ligand_lipophilicity_efficiency else "N/A"]
    ]
    
    dock_table = Table(dock_data, colWidths=[200, 290])
    dock_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f8fafc')),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 6)
    ]))
    story.append(dock_table)
    
    story.append(Spacer(1, 10))
    if eval_result.hotspots_hit:
        hotspots_str = ", ".join(eval_result.hotspots_hit)
        story.append(Paragraph(f"<b>Residuos Hotspots Impactados:</b> {hotspots_str}", normal_style))
    
    story.append(Spacer(1, 15))

    # ADME & PHYSICOCHEMICAL
    story.append(Paragraph("Perfil Fisicoquímico (ADME)", section_title_style))
    adme_data = [
        ["Propiedad", "Valor", "Propiedad", "Valor"],
        ["Peso Molecular (MW)", f"{eval_result.molecular_weight:.2f} Da" if eval_result.molecular_weight else "N/A", 
         "Coef. Partición (LogP)", f"{eval_result.log_p:.2f}" if eval_result.log_p else "N/A"],
        ["Área Sup. Polar (TPSA)", f"{eval_result.tpsa:.2f} Å²" if eval_result.tpsa else "N/A",
         "Átomos Pesados", f"{eval_result.heavy_atom_count}" if eval_result.heavy_atom_count else "N/A"],
        ["Donadores H-Bond (HBD)", f"{eval_result.hbd}" if eval_result.hbd is not None else "N/A",
         "Aceptores H-Bond (HBA)", f"{eval_result.hba}" if eval_result.hba is not None else "N/A"],
        ["Enlaces Rotables", f"{eval_result.rotatable_bonds}" if eval_result.rotatable_bonds is not None else "N/A",
         "Anillos", f"{eval_result.ring_count}" if eval_result.ring_count is not None else "N/A"]
    ]
    
    adme_table = Table(adme_data, colWidths=[145, 100, 145, 100])
    adme_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (0,1), (0,-1), colors.HexColor('#f8fafc')),
        ('BACKGROUND', (2,1), (2,-1), colors.HexColor('#f8fafc')),
        ('FONTNAME', (0,1), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,1), (2,-1), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 6)
    ]))
    story.append(adme_table)
    
    story.append(Spacer(1, 15))

    # DRUG-LIKENESS
    story.append(Paragraph("Drug-likeness y Viabilidad Sintética", section_title_style))
    dl_data = [
        ["Regla de Lipinski", "PASA" if eval_result.lipinski_pass else "FALLA", 
         "Score QED", f"{eval_result.qed:.3f}" if eval_result.qed else "N/A"],
        ["Regla de Veber", "PASA" if eval_result.veber_pass else "FALLA",
         "SA Score (Accesibilidad)", f"{eval_result.sa_score:.2f} / 10" if eval_result.sa_score else "N/A"]
    ]
    
    dl_table = Table(dl_data, colWidths=[145, 100, 145, 100])
    dl_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f8fafc')),
        ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#f8fafc')),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 6)
    ]))
    story.append(dl_table)
    
    if eval_result.sa_reasons:
        story.append(Spacer(1, 5))
        reasons = ", ".join(eval_result.sa_reasons)
        story.append(Paragraph(f"<b>Penalizaciones Sintéticas:</b> {reasons}", normal_style))
        
    story.append(Spacer(1, 15))

    # GLOBAL SCORE
    story.append(Paragraph("Puntuación Global (MolDesign Scoring)", section_title_style))
    scores_str = (
        f"<b>Score Total:</b> {eval_result.total_score:.2f} / 100<br/>"
        f"• Score Afinidad: {eval_result.affinity_score:.2f} / 100<br/>"
        f"• Score ADME: {eval_result.adme_score:.2f} / 100<br/>"
        f"• Score Drug-likeness: {eval_result.druglikeness_score:.2f} / 100"
    )
    story.append(Paragraph(scores_str, normal_style))

    story.append(Spacer(1, 15))

    # BLOCKCHAIN
    story.append(Paragraph("Auditoría y Proof of Discovery (Blockchain Solana)", section_title_style))
    tx_id = eval_result.blockchain_tx_id or "Pendiente de Certificación"
    
    bc_data = [
        [Paragraph("<b>Firma de Transacción:</b>", normal_style), Paragraph(tx_id, mono_style)]
    ]
    if eval_result.blockchain_tx_id:
        link = f"https://explorer.solana.com/tx/{tx_id}?cluster=devnet"
        bc_data.append([
            Paragraph("<b>Enlace de Verificación:</b>", normal_style),
            Paragraph(f'<a href="{link}" color="blue">{link}</a>', mono_style)
        ])
        
    bc_table = Table(bc_data, colWidths=[130, 360])
    bc_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(bc_table)

    # FOOTER
    story.append(Spacer(1, 30))
    footer_text = "<font color='#94a3b8' size='8'><i>Generado de forma autónoma por MolDesign AI bajo licencia abierta CC0.<br/>Código y Plataforma: https://github.com/srcacahuate619/molecule-design</i></font>"
    story.append(Paragraph(footer_text, ParagraphStyle('Footer', alignment=1)))

    doc.build(story)
    buf.seek(0)
    return buf
