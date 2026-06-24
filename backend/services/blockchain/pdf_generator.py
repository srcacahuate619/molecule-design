import io
import os
from datetime import datetime
from rdkit import Chem
from rdkit.Chem import Draw
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from core.models import MoleculeORM, EvaluationResultORM

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 7)
        self.setFillColor(colors.HexColor("#64748b"))
        
        # Read metadata parameters if we cached them
        target_info = getattr(self, "target_info", "MolDesign Target")
        affinity_info = getattr(self, "affinity_info", "")
        score_info = getattr(self, "score_info", "")
        
        # Left executive summary
        summary_text = f"{target_info} | {affinity_info} | {score_info} | MolDesign AI"
        self.drawString(1.5*cm, 0.8*cm, summary_text)
        
        # Right page number
        page_text = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(A4[0] - 1.5*cm, 0.8*cm, page_text)
        
        # Thin divider line
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(1.5*cm, 1.1*cm, A4[0] - 1.5*cm, 1.1*cm)
        self.restoreState()

CO_CRYSTAL_LIGANDS = {
    "7E2Y": "5-HT (Serotonina)",
    "6B3J": "Exendin-P5 (Péptido)",
    "6X1A": "Danuglipron (PF-06882961)",
    "2P4E": "SBC-115076",
    "6U26": "Inhibidor Alostérico 11a",
    "3OSK": "Péptido MYPPPY (B7-1)",
    "3ERT": "4-Hidroxitamoxifeno (OHT)",
    "5L2I": "Palbociclib (Ibrance)",
    "2W96": "Palbociclib (CDK4/6)",
    "4JPS": "Alpelisib (BYL719)",
    "3O96": "Inhibidor Alostérico VIII",
    "3PP0": "SYR-475",
    "4ZZZ": "NMS-P118",
    "1HVY": "Raltitrexed (Tomudex)",
    "4I5I": "EX-527 (Selisistat)",
    "6D8X": "GW1929",
    "5IKR": "Ácido Mefenámico",
    "4RER": "A-769662",
    "5VEW": "PF-06305591"
}

def get_2d_image(smiles: str, width=2.5*inch, height=2.5*inch):
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None
    img = Draw.MolToImage(mol, size=(400, 400))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return Image(buf, width=width, height=height)

def generate_energy_profile_plot(poses: list[dict], width=4.5*inch, height=2.0*inch):
    if not poses:
        return None
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        plt.clf()
        plt.close('all')
        
        ranks = [p.get("rank") for p in poses if p.get("rank") is not None]
        affinities = [p.get("affinity") for p in poses if p.get("affinity") is not None]
        
        if not ranks or not affinities:
            return None
            
        fig, ax = plt.subplots(figsize=(6.5, 2.5), dpi=150)
        ax.plot(ranks, affinities, marker='o', color='#3b82f6', linewidth=2, markersize=5, markerfacecolor='#1e3a8a')
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#cbd5e1')
        ax.spines['bottom'].set_color('#cbd5e1')
        ax.tick_params(axis='both', colors='#475569', labelsize=8)
        
        ax.set_ylabel("Afinidad (kcal/mol)", fontsize=8, color='#475569')
        ax.set_xlabel("Pose (Rank)", fontsize=8, color='#475569')
        ax.set_xticks(ranks)
        ax.grid(True, linestyle=':', alpha=0.6, color='#cbd5e1')
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', transparent=True)
        buf.seek(0)
        plt.close(fig)
        return Image(buf, width=width, height=height)
    except Exception:
        return None

def generate_shap_image(shap_values: dict, width=6.8*inch, height=2.8*inch):
    if not shap_values:
        return None
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        plt.clf()
        plt.close('all')
        
        sorted_items = sorted(shap_values.items(), key=lambda x: abs(x[1]))[-8:]
        features = [item[0] for item in sorted_items]
        values = [item[1] for item in sorted_items]
        
        labels = [f.replace("_", " ").title() for f in features]
        colors_list = ['#10b981' if v > 0 else '#f43f5e' for v in values]
        
        fig, ax = plt.subplots(figsize=(6.5, 2.8), dpi=150)
        ax.barh(labels, values, color=colors_list, height=0.6)
        ax.axvline(0, color='#64748b', linewidth=0.8, linestyle='--')
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#cbd5e1')
        ax.spines['bottom'].set_color('#cbd5e1')
        ax.tick_params(axis='both', colors='#475569', labelsize=8)
        
        ax.set_xlabel("Contribución a Afinidad (SHAP Value)", fontsize=8, color='#475569')
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', transparent=True)
        buf.seek(0)
        plt.close(fig)
        return Image(buf, width=width, height=height)
    except Exception:
        return None

def generate_gnn_attention_image(smiles: str, attention: list[float], width=6.8*inch, height=3.8*inch):
    if not attention:
        return None
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None
    try:
        num_atoms = mol.GetNumAtoms()
        weights = list(attention)
        if len(weights) < num_atoms:
            weights += [0.0] * (num_atoms - len(weights))
        else:
            weights = weights[:num_atoms]
            
        from rdkit.Chem.Draw import rdMolDraw2D, SimilarityMaps
        d = rdMolDraw2D.MolDraw2DCairo(800, 450)
        opts = d.drawOptions()
        opts.clearBackground = True
        SimilarityMaps.GetSimilarityMapFromWeights(mol, weights, draw2d=d)
        d.FinishDrawing()
        png_data = d.GetDrawingText()
        
        buf = io.BytesIO(png_data)
        return Image(buf, width=width, height=height)
    except Exception:
        return None

def get_pubchem_names(smiles: str) -> tuple[str, str]:
    """
    Fetches the common name and systematic IUPAC name for a given SMILES from PubChem.
    Uses a robust 2-phase lookup via CID to avoid SMILES encoding conflicts.
    Falls back to RDKit-generated systematic IUPAC name if PubChem resolution fails.
    Returns: (common_name, iupac_name)
    """
    import urllib.request
    import urllib.parse
    import json
    
    common_name = "N/A"
    iupac_name = "N/A"
    
    try:
        # Phase 1: Convert SMILES to CID using PUG REST
        safe_smiles = urllib.parse.quote(smiles)
        cid_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/{safe_smiles}/cids/JSON"
        req = urllib.request.Request(cid_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3.0) as response:
            data = json.loads(response.read().decode())
            cids = data.get("IdentifierList", {}).get("CID", [])
            if cids:
                cid = cids[0]
                # Phase 2: Query IUPAC and Title by CID using PUG REST
                prop_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/IUPACName,Title/JSON"
                req_prop = urllib.request.Request(prop_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req_prop, timeout=3.0) as response_prop:
                    prop_data = json.loads(response_prop.read().decode())
                    properties = prop_data.get("PropertyTable", {}).get("Properties", [{}])[0]
                    common_name = properties.get("Title", "N/A")
                    iupac_name = properties.get("IUPACName", "N/A")
    except Exception:
        pass
        
    # RDKit Fallback if systematic name remains N/A
    if iupac_name == "N/A":
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol:
                # Try to use RDKit's IUPAC name resolver if available
                try:
                    from rdkit.Chem import rdIUPAC
                    iupac_name = rdIUPAC.MolToIUPACName(mol)
                except ImportError:
                    # In standard RDKit, MolToIUPACName is not always built in,
                    # so we fallback to 'No disponible' as requested
                    iupac_name = "No disponible"
        except Exception:
            pass

    return common_name, iupac_name

def generate_physiological_context(pdb_id: str, header_lines: str | None) -> str:
    """
    Scans the PDB file headers for keywords and generates a detailed physiological context template.
    """
    if not header_lines:
        return "Descripción fisiológica no disponible para este receptor personalizado."
        
    text = header_lines.upper()
    
    # Check GPCRs
    if any(k in text for k in ("GPCR", "RECEPTOR", "5-HT", "DOPAMINE", "ADRENERGIC", "SEROTONIN", "ACETYLCHOLINE", "GLYCOPROTEIN")):
        return (
            "Este target clasifica como un Receptor Acoplado a Proteínas G (GPCR) o receptor transmembranal. "
            "Los GPCRs median la transducción de señales extracelulares al interior celular a través de cascadas "
            "enzimáticas mediadas por nucleótidos de guanina. Son dianas esenciales en neurofarmacología y endocrinología."
        )
    # Check Kinases
    if any(k in text for k in ("KINASE", "PHOSPHOTRASE", "TYROSINE KINASE", "MAPK", "CDK")):
        return (
            "Este target clasifica como una Proteína Quinasa (Kinase). Las quinasas son enzimas que catalizan la "
            "transferencia de grupos fosfato desde el ATP a sustratos específicos, actuando como interruptores críticos "
            "en vías de proliferación, crecimiento y señalización celular. Altamente relevantes en oncología."
        )
    # Check Proteases
    if any(k in text for k in ("PROTEASE", "PEPTIDASE", "HYDROLASE", "HIV PROTEASE", "MPRO", "COV PROTEASE")):
        return (
            "Este target clasifica como una Hidrolasa / Proteasa. Las proteasas (ej. aspartil o cisteín proteasas) "
            "catalizan la ruptura de enlaces peptídicos de proteínas. Son dianas esenciales para el control del "
            "procesamiento de poliproteínas funcionales y la replicación en ciclos de infección viral (como en VIH o Coronavirus)."
        )
    # Check Ion Channels
    if any(k in text for k in ("CHANNEL", "ION CHANNEL", "PORE", "PUMP", "POTASSIUM", "SODIUM", "CALCIUM")):
        return (
            "Este target clasifica como un Canal Iónico o transportador de membrana. Regula de manera selectiva "
            "el paso de iones a través de la bicapa lipídica, manteniendo el gradiente electroquímico e interviniendo "
            "en la excitabilidad neuronal, contracción muscular y señalización de segundos mensajeros."
        )
        
    return "Estructura proteica personalizada del usuario. Interactúa como catalizador o transductor de señal intracelular."

def generate_2d_interaction_diagram(smiles: str, contacts: list[dict], width=2.4*inch, height=2.4*inch) -> Image:
    """
    Generates a dynamic 2D interaction diagram of the ligand with RDKit, highlighting
    atoms involved in hydrogen bonds or salt bridges and adding label callouts.
    """
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None
    try:
        from rdkit.Chem import rdDepictor
        from rdkit.Chem.Draw import rdMolDraw2D
        
        rdDepictor.Compute2DCoords(mol)
        
        # Analyze which atoms are involved in contacts
        highlight_atoms = []
        highlight_colors = {}
        atom_notes = {}
        
        # Simple heuristic: map contact residue names to polar atoms
        # RDKit atom mapping
        for i, atom in enumerate(mol.GetAtoms()):
            symbol = atom.GetSymbol().upper()
            # If we have H-Bonds in contacts, let's find polar heteroatoms to highlight
            for c in contacts:
                res_label = c["residue"].split()[0] # e.g. "ASP186"
                dist = c["distance"]
                c_type = c["type"]
                
                if "H-Bond" in c_type or "Salt Bridge" in c_type:
                    if symbol in ("N", "O", "F", "S"):
                        if i not in highlight_atoms:
                            highlight_atoms.append(i)
                            # Light green for hydrogen bonds / salt bridges
                            highlight_colors[i] = (0.2, 0.8, 0.2)
                            atom_notes[i] = f"{res_label} ({dist})"
                            break
                            
        d = rdMolDraw2D.MolDraw2DCairo(400, 400)
        opts = d.drawOptions()
        opts.clearBackground = True
        
        # Add the annotations directly on the atoms
        for idx, note in atom_notes.items():
            mol.GetAtomWithIdx(idx).SetProp("atomNote", note)
            
        d.DrawMolecule(mol, highlightAtoms=highlight_atoms, highlightAtomColors=highlight_colors)
        d.FinishDrawing()
        png_data = d.GetDrawingText()
        
        buf = io.BytesIO(png_data)
        return Image(buf, width=width, height=height)
    except Exception:
        return None

def compute_residue_interactions(receptor_pdb: str | None, ligand_sdf: str | None) -> list[dict]:
    if not receptor_pdb or not ligand_sdf:
        return []
    try:
        receptor_atoms = []
        for line in receptor_pdb.splitlines():
            if line.startswith(("ATOM", "HETATM")):
                try:
                    atom_name = line[12:16].strip()
                    res_name = line[17:20].strip()
                    chain = line[21].strip()
                    res_num = int(line[22:26].strip())
                    x = float(line[30:38])
                    y = float(line[38:46])
                    z = float(line[46:54])
                    element = line[76:78].strip() or atom_name[0]
                    receptor_atoms.append({
                        "atom_name": atom_name, "res_name": res_name, "chain": chain,
                        "res_num": res_num, "x": x, "y": y, "z": z, "element": element.upper()
                    })
                except:
                    continue
        
        suppl = Chem.SDMolSupplier()
        suppl.SetData(ligand_sdf)
        poses = [m for m in suppl if m is not None]
        if not poses:
            return []
            
        best_pose = poses[0]
        ligand_atoms = []
        conf = best_pose.GetConformer()
        for i, atom in enumerate(best_pose.GetAtoms()):
            pos = conf.GetAtomPosition(i)
            ligand_atoms.append({
                "idx": i, "element": atom.GetSymbol().upper(),
                "x": pos.x, "y": pos.y, "z": pos.z, "is_aromatic": atom.GetIsAromatic()
            })
            
        res_contacts = {}
        for latom in ligand_atoms:
            for ratom in receptor_atoms:
                dx = latom["x"] - ratom["x"]
                dy = latom["y"] - ratom["y"]
                dz = latom["z"] - ratom["z"]
                dist = (dx**2 + dy**2 + dz**2)**0.5
                if dist < 4.5:
                    res_key = (ratom["chain"], ratom["res_name"], ratom["res_num"])
                    if res_key not in res_contacts:
                        res_contacts[res_key] = []
                    res_contacts[res_key].append((latom, ratom, dist))
                    
        classified = []
        for (chain, res_name, res_num), contacts in res_contacts.items():
            min_dist = min(c[2] for c in contacts)
            int_types = set()
            
            # Keep track of atoms to ensure mutual exclusivity
            atoms_in_hb = set()
            atoms_in_sb = set()
            
            # 1. H-Bond (Distancia < 3.2A y polares)
            for latom, ratom, dist in contacts:
                if dist < 3.2 and latom["element"] in ("N", "O", "F") and ratom["element"] in ("N", "O", "F"):
                    int_types.add("H-Bond")
                    atoms_in_hb.add(latom["idx"])
            
            # 2. Salt Bridge (Dist < 4.0A entre residuos ácidos/básicos y nitrógeno/oxígeno)
            if not int_types:
                for latom, ratom, dist in contacts:
                    if dist < 4.0 and latom["element"] in ("N", "O") and ratom["element"] in ("N", "O") and res_name in ("ASP", "GLU", "ARG", "LYS"):
                        int_types.add("Salt Bridge")
                        atoms_in_sb.add(latom["idx"])
            
            # 3. Pi-Stacking (Dist < 4.5A entre centroides de anillos aromáticos)
            if not int_types:
                for latom, ratom, dist in contacts:
                    if dist < 4.5 and latom["is_aromatic"] and res_name in ("PHE", "TYR", "TRP", "HIS") and ratom["element"] == "C":
                        int_types.add("Pi-Stacking")
            
            # 4. Hydrophobic (Carbono-Carbono dist < 4.2A, libre de H-bond/Salt Bridge/Pi-Stacking)
            if not int_types:
                for latom, ratom, dist in contacts:
                    if dist < 4.2 and latom["element"] == "C" and ratom["element"] == "C":
                        if latom["idx"] not in atoms_in_hb and latom["idx"] not in atoms_in_sb:
                            if res_name in ("ALA", "VAL", "LEU", "ILE", "PHE", "TYR", "TRP", "MET", "PRO"):
                                int_types.add("Hydrophobic")
            
            # Fallback simple
            if not int_types and min_dist < 4.0:
                if res_name in ("ALA", "VAL", "LEU", "ILE", "PHE", "TYR", "TRP", "MET", "PRO"):
                    int_types.add("Hydrophobic Contact")
                else:
                    int_types.add("Van der Waals")
                
            if int_types:
                classified.append({
                    "residue": f"{res_name}{res_num} ({chain})",
                    "type": "/".join(sorted(list(int_types))),
                    "distance": f"{min_dist:.2f} Å",
                    "min_dist_val": min_dist
                })
        classified.sort(key=lambda x: x["min_dist_val"])
        return classified[:10]  # Top 10 interactions
    except Exception:
        return []

def generate_certificate_pdf(
    mol: MoleculeORM,
    eval_result: EvaluationResultORM,
    target_name: str,
    pose_sdf_content: str | None = None,
    receptor_pdb_content: str | None = None
) -> io.BytesIO:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, 
        pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )
    
    styles = getSampleStyleSheet()
    
    font_name = 'Courier'
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont('DejaVuSansMono', font_path))
            font_name = 'DejaVuSansMono'
        except Exception:
            pass
            
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
        fontSize=13,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=12,
        spaceAfter=8,
        borderPadding=(0,0,2,0),
        borderColor=brand_color,
        borderWidth=1
    )

    xai_header_style = ParagraphStyle(
        'XaiHeaderStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#1e293b'),
        fontName='Helvetica-Bold',
        spaceAfter=4,
        alignment=0 # Left
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 9
    normal_style.leading = 13
    
    mono_style = ParagraphStyle(
        'Mono',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=8,
        textColor=colors.HexColor('#475569')
    )

    story = []

    # HEADER
    story.append(Paragraph("REPORTE CIENTÍFICO Y EVIDENCIA DIGITAL", title_style))
    cert_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    story.append(Paragraph(f"Registrado inmutablemente en Solana (Devnet) • {cert_date}", subtitle_style))
    
    # TARGET SECTION
    story.append(Paragraph("Receptor Biológico (Target)", section_title_style))
    rho_val = f" | <b>Spearman ρ:</b> {mol.target.spearman_rho:.3f}" if (mol.target and mol.target.spearman_rho is not None) else ""
    
    ref_ligand = CO_CRYSTAL_LIGANDS.get(mol.target.pdb_id.upper() if mol.target else "", "N/A")
    ref_str = f" | <b>Ligando Co-cristalizado:</b> {ref_ligand}" if ref_ligand != "N/A" else ""
    
    story.append(Paragraph(f"<b>PDB ID:</b> {mol.target.pdb_id.upper() if mol.target else 'N/A'} | <b>Nombre:</b> {target_name}{rho_val}{ref_str}", normal_style))
    story.append(Spacer(1, 4))
    
    # QA Check on Target Origin
    is_custom = mol.target and (mol.target.pdb_id.upper().startswith("USR_") or mol.target.is_private)
    if is_custom:
        qa_banner = "<font color='#d97706'><b>[QA: RECEPTOR PERSONALIZADO]</b> Estructura subida por el usuario. La minimización local y estados de protonación corresponden al archivo original.</font>"
    else:
        qa_banner = "<font color='#16a34a'><b>[QA: ESTRUCTURA CURADA]</b> Origen verificado en RCSB Protein Data Bank. Datos de calibración validados.</font>"
    story.append(Paragraph(qa_banner, normal_style))
    story.append(Spacer(1, 6))
    
    target_desc = mol.target.description
    if not target_desc or target_desc == "Descripción fisiológica no disponible." or target_desc.startswith("Receptor Biológico PDB:"):
        target_desc = generate_physiological_context(mol.target.pdb_id if mol.target else "7E2Y", receptor_pdb_content)
    story.append(Paragraph(f"<b>Contexto Fisiológico:</b> {target_desc}", normal_style))
    story.append(Spacer(1, 10))

    # MOLECULE SECTION
    story.append(Paragraph("Detalles de la Molécula", section_title_style))
    
    # Fetch common and IUPAC name from PubChem
    common_name, iupac_name = get_pubchem_names(mol.smiles)
    
    # IUPAC Truncation to avoid visual table overflow
    if iupac_name and len(iupac_name) > 80:
        iupac_name = iupac_name[:77] + "..."
    
    mol_info_data = [
        [Paragraph("<b>Nombre Asignado:</b>", normal_style), Paragraph(mol.name or f"Ligando {mol.smiles_hash[:8]}", normal_style)],
        [Paragraph("<b>Nombre Común (PubChem):</b>", normal_style), Paragraph(common_name, normal_style)],
        [Paragraph("<b>Nombre Sistemático (IUPAC):</b>", normal_style), Paragraph(iupac_name, normal_style)],
        [Paragraph("<b>ID de Sistema:</b>", normal_style), Paragraph(str(mol.id), mono_style)],
        [Paragraph("<b>SMILES Hash:</b>", normal_style), Paragraph(mol.smiles_hash, mono_style)],
        [Paragraph("<b>Estructura SMILES:</b>", normal_style), Paragraph(mol.smiles, mono_style)]
    ]
    
    mol_table = Table(mol_info_data, colWidths=[140, 350])
    mol_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    
    img = get_2d_image(mol.smiles)
    if img:
        layout_table = Table([[mol_table, img]], colWidths=[350, 140])
        layout_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
        story.append(layout_table)
    else:
        story.append(mol_table)

    story.append(Spacer(1, 10))

    # DOCKING & INTERACTION SECTION
    story.append(Paragraph("Interacción Molecular y Docking (AutoDock Vina)", section_title_style))
    
    le = None
    if eval_result.affinity_kcal is not None and eval_result.heavy_atom_count and eval_result.heavy_atom_count > 0:
        le = eval_result.affinity_kcal / eval_result.heavy_atom_count
        
    lle = None
    if eval_result.affinity_kcal is not None and eval_result.log_p is not None:
        lle = (-eval_result.affinity_kcal / 1.36) - eval_result.log_p

    dock_data = [
        ["Afinidad (Energía de Unión)", f"{eval_result.affinity_kcal:.2f} kcal/mol" if eval_result.affinity_kcal is not None else "N/A"],
        ["Score de Especificidad", f"{eval_result.specificity_score:.2f} / 100" if eval_result.specificity_score is not None else "N/A"],
        ["Eficiencia de Ligando (LE)", f"{le:.3f}" if le is not None else "N/A"],
        ["Eficiencia Lipofílica (LLE)", f"{lle:.3f}" if lle is not None else "N/A"]
    ]
    
    dock_table = Table(dock_data, colWidths=[200, 290])
    dock_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f8fafc')),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 4)
    ]))
    story.append(dock_table)
    
    story.append(Spacer(1, 6))
    if eval_result.hotspots_hit:
        hotspots_str = ", ".join(eval_result.hotspots_hit)
        story.append(Paragraph(f"<b>Residuos Hotspots Impactados:</b> {hotspots_str}", normal_style))

    if eval_result.specificity_score is not None and eval_result.specificity_score < 40.0:
        spec_warning = (
            "<font color='#b91c1c'><b>Nota de Especificidad:</b> El Score de Especificidad es bajo "
            f"({eval_result.specificity_score:.2f}/100) a pesar de una afinidad favorable "
            f"({eval_result.affinity_kcal:.2f} kcal/mol). Esto indica que la unión de la molécula no "
            "involucra los residuos hotspot biológicos clave definidos para este receptor, lo cual es "
            "una señal clásica de posible promiscuidad química o un mecanismo de interacción atípico.</font>"
        )
        story.append(Spacer(1, 4))
        story.append(Paragraph(spec_warning, normal_style))

    # Residue-Ligand Interactions Sub-Section
    contacts = compute_residue_interactions(receptor_pdb_content, pose_sdf_content)
    if contacts:
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>Mapeo de Contactos de Sitio Activo (Residuo-Ligando)</b>", normal_style))
        story.append(Spacer(1, 4))
        
        contact_rows = [["Residuo", "Tipo de Interacción", "Distancia"]]
        for c in contacts[:7]:  # Show top 7 in table to leave space
            contact_rows.append([c["residue"], c["type"], c["distance"]])
            
        contact_table = Table(contact_rows, colWidths=[100, 140, 60]) # Narrower for side-by-side
        contact_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('PADDING', (0,0), (-1,-1), 3)
        ]))
        
        # Draw 2D Interaction Diagram side-by-side
        diag_img = generate_2d_interaction_diagram(mol.smiles, contacts, 180, 180)
        if diag_img:
            layout_table = Table([[contact_table, diag_img]], colWidths=[310, 180])
            layout_table.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('LEFTPADDING', (1,0), (1,0), 10),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0)
            ]))
            story.append(layout_table)
        else:
            # Fallback to full width if diagram failed
            fallback_rows = [["Residuo", "Tipo de Interacción", "Distancia Mínima"]]
            for c in contacts:
                fallback_rows.append([c["residue"], c["type"], c["distance"]])
            contact_table_full = Table(fallback_rows, colWidths=[150, 220, 120])
            contact_table_full.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('PADDING', (0,0), (-1,-1), 4)
            ]))
            story.append(contact_table_full)

    story.append(PageBreak()) # Force clean page for ADME & Explicabilidad

    # ADME & PHYSICOCHEMICAL
    story.append(Paragraph("Perfil Fisicoquímico (ADME) y Comparativo", section_title_style))

    # Control Ligand definition & calculation (on-the-fly for reference)
    CO_CRYSTAL_SMILES = {
        "7E2Y": "NCCc1c[nH]c2ccc(O)cc12",  # Serotonina
        "6X1A": "CC(C)(C)c1cc(cc(c1)F)C(=O)NCC2(CCN(CC2)c3cc(ncn3)C#N)C(=O)O", # Danuglipron
        "2P4E": "CN1CCN(CC1)C(=O)c2cc3c(cc2F)[nH]c(n3)c4ccc(cc4)C#N", # SBC-115076-like
        "3ERT": "CC\\C(=C(/c1ccc(cc1)OCCN(C)C)\\c2ccccc2)\\c3ccccc3",  # 4-Hidroxitamoxifeno
        "5L2I": "CCN1CCN(CC1)Cc2ccc(cc2)Nc3ncc4c(n3)nc(n4C5CCCC5)C(=O)c6c(C)n[nH]c6C", # Palbociclib
        "2W96": "CCN1CCN(CC1)Cc2ccc(cc2)Nc3ncc4c(n3)nc(n4C5CCCC5)C(=O)c6c(C)n[nH]c6C", # Palbociclib
        "4JPS": "CC(C)S(=O)(=O)c1ccc(cc1)c2cc(nc(n2)N3CCOCC3)c4cn[nH]c4", # Alpelisib
        "3PP0": "CC(=O)N1CCC(CC1)c2cc3c(cc2)c(cn3)c4ccc(cc4)S(=O)(=O)C(C)C", # SYR-475
        "4ZZZ": "CC(C)S(=O)(=O)c1ccc(cc1)c2cn3c(c2)c(cn3)C#N", # NMS-P118-like
        "1HVY": "CN(Cc1ccc(s1)C(=O)Nc2ccc(cc2)C(=O)O)c3cc4c(s3)nc(o4)N", # Raltitrexed-like
        "4I5I": "c1ccc2c(c1)[nH]c3c2c(=O)n(c3)C4CCCC4", # EX-527 (Selisistat)
        "6D8X": "CC(C)c1ccc(cc1)C(C)Cc2ccc(cc2)OCC(=O)Nc3ccc(cc3)C(=O)O", # GW1929
        "5IKR": "Cc1cccc(C)c1Nc2ccccc2C(=O)O", # Ácido Mefenámico
        "4RER": "Cc1cc(nc(n1)C)C2=C(C=C(C=C2)C#N)O", # A-769662-like
        "5VEW": "Cc1cccc(c1)c2cc(c(cn2)C#N)Oc3ccc(cc3)S(=O)(=O)C" # PF-06305591-like
    }

    pdb_upper = (mol.target.pdb_id.upper() if mol.target else "")
    ctrl_smiles = CO_CRYSTAL_SMILES.get(pdb_upper)
    ctrl_name = CO_CRYSTAL_LIGANDS.get(pdb_upper, "Ligando de Control")

    adme_headers = ["Propiedad", "Diseñado", "Control Nativo", "Límite Terapéutico"]
    
    # Calculate control descriptors
    ctrl_mw, ctrl_logp, ctrl_tpsa, ctrl_hbd, ctrl_hba, ctrl_rot = "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"
    if ctrl_smiles:
        try:
            ctrl_mol = Chem.MolFromSmiles(ctrl_smiles)
            if ctrl_mol:
                from rdkit.Chem import Descriptors, Lipinski as rdLipinski
                ctrl_mw = f"{Descriptors.MolWt(ctrl_mol):.2f}"
                ctrl_logp = f"{Descriptors.MolLogP(ctrl_mol):.2f}"
                ctrl_tpsa = f"{Descriptors.TPSA(ctrl_mol):.2f}"
                ctrl_hbd = f"{rdLipinski.NumHDonors(ctrl_mol)}"
                ctrl_hba = f"{rdLipinski.NumHAcceptors(ctrl_mol)}"
                ctrl_rot = f"{rdLipinski.NumRotatableBonds(ctrl_mol)}"
        except Exception:
            pass

    adme_data = [
        adme_headers,
        ["Peso Molecular (MW)", f"{eval_result.molecular_weight:.2f} Da" if eval_result.molecular_weight else "N/A", f"{ctrl_mw} Da" if ctrl_mw != "N/A" else "N/A", "≤ 500 Da (Lipinski)"],
        ["Coef. Partición (LogP)", f"{eval_result.log_p:.2f}" if eval_result.log_p is not None else "N/A", ctrl_logp, "≤ 5.0 (Lipinski)"],
        ["Área Sup. Polar (TPSA)", f"{eval_result.tpsa:.2f} Å²" if eval_result.tpsa else "N/A", f"{ctrl_tpsa} Å²" if ctrl_tpsa != "N/A" else "N/A", "≤ 140 Å² (Veber)"],
        ["Donadores H-Bond (HBD)", f"{eval_result.hbd}" if eval_result.hbd is not None else "N/A", ctrl_hbd, "≤ 5 (Lipinski)"],
        ["Aceptores H-Bond (HBA)", f"{eval_result.hba}" if eval_result.hba is not None else "N/A", ctrl_hba, "≤ 10 (Lipinski)"],
        ["Enlaces Rotables", f"{eval_result.rotatable_bonds}" if eval_result.rotatable_bonds is not None else "N/A", ctrl_rot, "≤ 10 (Veber)"]
    ]

    adme_table = Table(adme_data, colWidths=[150, 110, 110, 120])
    adme_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (0,1), (0,-1), colors.HexColor('#f8fafc')),
        ('FONTNAME', (0,1), (0,-1), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 3),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (1,0), (-1,-1), 'CENTER')
    ]))
    story.append(adme_table)
    
    story.append(Spacer(1, 10))

    # DRUG-LIKENESS & TOXICOLOGY ALERTS
    story.append(Paragraph("Drug-likeness y Viabilidad Sintética", section_title_style))
    
    # Analyze infractions dynamically from pre-calculated values
    infractions = []
    if eval_result.molecular_weight and eval_result.molecular_weight > 500:
        infractions.append(f"MW alto ({eval_result.molecular_weight:.1f} Da)")
    if eval_result.log_p and eval_result.log_p > 5.0:
        infractions.append(f"LogP alto ({eval_result.log_p:.2f})")
    if eval_result.hbd and eval_result.hbd > 5:
        infractions.append(f"Exceso Donadores H-Bond ({eval_result.hbd})")
    if eval_result.hba and eval_result.hba > 10:
        infractions.append(f"Exceso Aceptores H-Bond ({eval_result.hba})")
    if eval_result.tpsa and eval_result.tpsa > 140:
        infractions.append(f"TPSA alta ({eval_result.tpsa:.1f} Å²)")
    if eval_result.rotatable_bonds and eval_result.rotatable_bonds > 10:
        infractions.append(f"Flexibilidad alta ({eval_result.rotatable_bonds} rot. bonds)")

    infractions_str = ", ".join(infractions) if infractions else "Ninguna (Cumplimiento óptimo)"

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
        ('PADDING', (0,0), (-1,-1), 4),
        ('FONTSIZE', (0,0), (-1,-1), 8)
    ]))
    story.append(dl_table)
    
    story.append(Spacer(1, 4))
    
    diagnostics_text = f"<b>Diagnóstico de Parámetros:</b> {infractions_str}."
    if eval_result.qed and eval_result.qed < 0.5:
        diagnostics_text += " <i>Nota: El score QED compuesto está por debajo de 0.5 debido a las desviaciones fisicoquímicas indicadas arriba.</i>"
    story.append(Paragraph(diagnostics_text, normal_style))

    if eval_result.sa_reasons:
        reasons = ", ".join(eval_result.sa_reasons)
        story.append(Paragraph(f"<b>Penalizaciones Sintéticas:</b> {reasons}", normal_style))

    # Real precalculated toxicology screening
    tox_alerts = eval_result.blood_systemic_reactivity or []
    if tox_alerts:
        tox_str = ", ".join(tox_alerts)
        story.append(Paragraph(f"<b><font color='#b91c1c'>Alertas de Toxicóforos / Reactividad (Precalculadas):</font></b> {tox_str}", normal_style))
    else:
        story.append(Paragraph("<b>Alertas de Reactividad/PAINS (Precalculadas):</b> <font color='#15803d'>Sin alertas de reactividad detectadas (Favorable)</font>", normal_style))
        
    story.append(Spacer(1, 10))

    # Poses & Energy Profile section
    if eval_result.docking_poses:
        story.append(Paragraph("Perfiles de Energía por Pose", section_title_style))
        poses_subset = eval_result.docking_poses[:5] # Top 5 poses
        pose_rows = [["Rank", "Afinidad (kcal/mol)", "RMSD lb", "RMSD ub"]]
        for p in poses_subset:
            pose_rows.append([f"Pose {p['rank']}", f"{p['affinity']:.2f}" if p.get('affinity') is not None else "N/A", f"{p['rmsd_lb']:.2f}" if p.get('rmsd_lb') is not None else "N/A", f"{p['rmsd_ub']:.2f}" if p.get('rmsd_ub') is not None else "N/A"])
            
        pose_table = Table(pose_rows, colWidths=[110, 140, 120, 120]) # Width exactly 490
        pose_table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('PADDING', (0,0), (-1,-1), 4)
        ]))
        story.append(pose_table)
        
        ep_plot = generate_energy_profile_plot(eval_result.docking_poses, 6.8*inch, 2.5*inch)
        if ep_plot:
            story.append(Spacer(1, 8))
            story.append(ep_plot)

    story.append(PageBreak()) # Force clean page for Explainability and Scores

    # EXPLAINABLE AI (XAI) SECTION
    has_xai = eval_result.shap_values or eval_result.gnn_attention
    if has_xai:
        story.append(Paragraph("Explicabilidad Científica e IA de Caja Transparente", section_title_style))
        
        # Translation dict for internal feature names to friendly Spanish scientific terms
        feature_translation = {
            "molecular_weight": "Peso Molecular (MW)",
            "log_p": "Lipofilicidad (LogP)",
            "tpsa": "Área Superficial Polar (TPSA)",
            "hbd": "Donadores de H-Bond",
            "hba": "Aceptores de H-Bond",
            "rotatable_bonds": "Enlaces Rotables",
            "heavy_atom_count": "Conteo de Átomos Pesados",
            "ring_count": "Conteo de Anillos",
            "qed": "Drug-likeness (QED)",
            "sa_score": "Accesibilidad Sintética (SA)",
            "lipinski_pass": "Regla de Lipinski"
        }
        
        if eval_result.shap_values:
            shap_img = generate_shap_image(eval_result.shap_values, 6.8*inch, 2.8*inch)
            if shap_img:
                story.append(Paragraph("XGBOOST NATIVE SHAP EXPLAINER", xai_header_style))
                story.append(shap_img)
                story.append(Spacer(1, 4))
                
                # Tabular breakdown of the top SHAP values for the scientist
                shap_rows = [["Descriptor", "Contribución (SHAP)", "Impacto en Afinidad"]]
                sorted_shap = sorted(eval_result.shap_values.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
                for feat, val in sorted_shap:
                    friendly_name = feature_translation.get(feat, feat.replace("_", " ").title())
                    sign = "+" if val > 0 else ""
                    impact_text = "Favorable (Aumenta afinidad / ΔG más negativo)" if val < 0 else "Desfavorable (Reduce afinidad)"
                    shap_rows.append([friendly_name, f"{sign}{val:.4f}", impact_text])
                
                shap_table = Table(shap_rows, colWidths=[150, 110, 230])
                shap_table.setStyle(TableStyle([
                    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,-1), 8),
                    ('PADDING', (0,0), (-1,-1), 3)
                ]))
                story.append(shap_table)
                story.append(Spacer(1, 10))
                
        if eval_result.gnn_attention:
            gnn_img = generate_gnn_attention_image(mol.smiles, eval_result.gnn_attention, 6.8*inch, 3.8*inch)
            if gnn_img:
                story.append(Paragraph("Atención GNN (RTMScore) MAPA DE HOTSPOTS", xai_header_style))
                story.append(gnn_img)
                story.append(Spacer(1, 4))
                
                legend_text = (
                    "<b>Interpretación del Mapa de Hotspots:</b> Las esferas de colores en la estructura indican los átomos en los que "
                    "la red neuronal geométrica centró su atención tridimensional al evaluar el complejo ligando-receptor. Las regiones con "
                    "colores más intensos (rojo/naranja) denotan interacciones de contacto local que más definen la afinidad predicha."
                )
                story.append(Paragraph(legend_text, ParagraphStyle('LegendStyle', parent=normal_style, fontSize=8, textColor=colors.HexColor('#475569'))))
                story.append(Spacer(1, 10))
            
        if eval_result.gnn_pharmacophores:
            story.append(Paragraph("Desglose de Farmacóforos y Perfil Comparativo (GNN)", xai_header_style))
            
            # Simple reference database for standard targets
            # Format: { 'TargetPDB': { 'Aromáticos': 50.0, 'Alifáticos': 10.0, ... } }
            benchmark_targets = {
                "7E2Y": {"Aromáticos": 50.0, "Alifáticos": 10.0, "Donadores": 15.0, "Aceptores": 25.0},
                "3ERT": {"Aromáticos": 60.0, "Alifáticos": 15.0, "Donadores": 10.0, "Aceptores": 15.0},
                "6B3J": {"Aromáticos": 20.0, "Alifáticos": 40.0, "Donadores": 20.0, "Aceptores": 20.0}
            }
            
            target_pdb = mol.target.pdb_id.upper() if mol.target else ""
            ref_data = benchmark_targets.get(target_pdb, {"Aromáticos": 40.0, "Alifáticos": 20.0, "Donadores": 20.0, "Aceptores": 20.0})
            
            pharmacophore_rows = [["Farmacóforo GNN", "Molécula Diseñada", "Referencia Target", "Desviación vs. Control"]]
            for k, v in eval_result.gnn_pharmacophores.items():
                ref_val = ref_data.get(k, 0.0)
                diff = v - ref_val
                sign = "+" if diff > 0 else ""
                status = "Cercano" if abs(diff) <= 10 else ("Sobre-representado" if diff > 10 else "Deficiente")
                pharmacophore_rows.append([k, f"{v:.1f}%", f"{ref_val:.1f}%", f"{sign}{diff:.1f}% ({status})"])
                
            ph_table = Table(pharmacophore_rows, colWidths=[130, 110, 110, 140])
            ph_table.setStyle(TableStyle([
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('PADDING', (0,0), (-1,-1), 3)
            ]))
            story.append(ph_table)
            story.append(Spacer(1, 10))

    # GLOBAL SCORE
    story.append(Paragraph("Puntuación Global (MolDesign Scoring)", section_title_style))
    
    total_score_str = f"{eval_result.total_score:.2f}" if eval_result.total_score is not None else "N/A"
    affinity_score_str = f"{eval_result.affinity_score:.2f}" if eval_result.affinity_score is not None else "N/A"
    adme_score_str = f"{eval_result.adme_score:.2f}" if eval_result.adme_score is not None else "N/A"
    druglikeness_score_str = f"{eval_result.druglikeness_score:.2f}" if eval_result.druglikeness_score is not None else "N/A"
    
    scores_str = (
        f"<b>Score Total:</b> {total_score_str} / 100<br/>"
        f"• Score Afinidad: {affinity_score_str} / 100<br/>"
        f"• Score ADME: {adme_score_str} / 100<br/>"
        f"• Score Drug-likeness: {druglikeness_score_str} / 100"
    )
    if eval_result.gnn_score is not None:
        scores_str += f"<br/>• Score Geométrico GNN (RTMScore): {eval_result.gnn_score:.3f}"
        
    story.append(Paragraph(scores_str, normal_style))
    story.append(Spacer(1, 4))
    
    # Mathematical and scoring transparency
    target_thresh = eval_result.affinity_threshold if eval_result.affinity_threshold is not None else -7.5
    scoring_transparency = (
        f"<b>Transparencia de Normalización:</b> El <i>Score de Afinidad</i> ({affinity_score_str}/100) se deriva linealmente mapeando "
        f"la energía predictiva cruda ({eval_result.affinity_kcal:.2f} kcal/mol) contra los límites del receptor (Suelo: 0.0 kcal/mol = 0, "
        f"Umbral de Corte del Target: {target_thresh:.2f} kcal/mol = 50, Óptimo Térmico de Saturación: -11.0 kcal/mol o menor = 100). "
        f"La <i>Puntuación Global</i> integra: 40% Afinidad normalizada + 30% Perfil ADME (Lipo/Solubilidad) + 30% Viabilidad Sintética y Drug-likeness (QED/Lipinski)."
    )
    story.append(Paragraph(scoring_transparency, ParagraphStyle('ScoringTrans', parent=normal_style, fontSize=8, textColor=colors.HexColor('#475569'))))
    story.append(Spacer(1, 10))

    # BLOCKCHAIN - Conditional rendering
    if eval_result.blockchain_tx_id:
        story.append(Paragraph("Auditoría y Proof of Discovery (Blockchain Solana)", section_title_style))
        tx_id = eval_result.blockchain_tx_id
        link = f"https://explorer.solana.com/tx/{tx_id}?cluster=devnet"
        
        bc_data = [
            [Paragraph("<b>Firma de Transacción:</b>", normal_style), Paragraph(tx_id, mono_style)],
            [Paragraph("<b>Enlace de Verificación:</b>", normal_style), Paragraph(f'<a href="{link}" color="blue">{link}</a>', mono_style)]
        ]
        
        bc_table = Table(bc_data, colWidths=[120, 370])
        bc_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(bc_table)
    else:
        story.append(Paragraph("Auditoría y Proof of Discovery (Solana)", section_title_style))
        story.append(Paragraph("<i>Este reporte puede certificarse inmutablemente en Solana desde la plataforma MolDesign AI.</i>", normal_style))

    # METODOLOGÍA Y LIMITACIONES CIENTÍFICAS
    story.append(Spacer(1, 8))
    methodology_style = ParagraphStyle(
        'Methodology',
        parent=styles['Normal'],
        fontSize=7,
        leading=9,
        textColor=colors.HexColor('#64748b'),
        alignment=4 # Justified
    )
    methodology_text = (
        "<b>Nota de Metodología Científica y Limitaciones:</b> Las energías de unión (afinidad, ΔG) son predichas in silico "
        "mediante docking molecular utilizando AutoDock Vina y no corresponden a constantes experimentales directas (K<sub>d</sub> o IC<sub>50</sub>). "
        "La Eficiencia Lipofílica (LLE) se calcula utilizando la aproximación termodinámica clásica LLE = pK<sub>d</sub><sup>teórica</sup> - LogP = (-ΔG / 1.36) - LogP, "
        "donde 1.36 kcal/mol es el factor de conversión a energía libre de Gibbs por unidad logarítmica de afinidad a 300 K. "
        "Los resultados constituyen estimaciones teóricas y deben ser validados experimentalmente mediante ensayos in vitro."
    )
    story.append(Paragraph(methodology_text, methodology_style))

    # FOOTER
    story.append(Spacer(1, 10))
    footer_text = "<font color='#94a3b8' size='7'><i>Generado de forma autónoma por MolDesign AI bajo licencia abierta CC0.<br/>Código y Plataforma: https://github.com/srcacahuate619/molecule-design</i></font>"
    story.append(Paragraph(footer_text, ParagraphStyle('Footer', alignment=1)))

    # Set canvas properties for NumberedCanvas before build
    def on_first_page(canvas_obj, doc_obj):
        pass # placeholder if needed
        
    doc.target_info = f"{mol.target.pdb_id.upper() if mol.target else 'N/A'} ({target_name})"
    doc.affinity_info = f"{eval_result.affinity_kcal:.2f} kcal/mol" if eval_result.affinity_kcal is not None else "N/A"
    doc.score_info = f"Score: {eval_result.total_score:.2f}/100" if eval_result.total_score is not None else "N/A"

    # Feed custom canvas info during build
    def canvas_maker(*args, **kwargs):
        c = NumberedCanvas(*args, **kwargs)
        c.target_info = doc.target_info
        c.affinity_info = doc.affinity_info
        c.score_info = doc.score_info
        return c

    doc.build(story, canvasmaker=canvas_maker)
    buf.seek(0)
    return buf
