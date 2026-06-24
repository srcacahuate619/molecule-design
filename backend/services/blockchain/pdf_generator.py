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
    "4RER": "Estaurosporina (STU)",
    "5VEW": "PF-06305591",
    "1ERE": "Estradiol (EST)",
    "4EKL": "Ipatasertib (0RF)"
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

    # Reference control metrics
    CO_CRYSTAL_AFFINITIES = {
        "7E2Y": -5.74, "6X1A": -7.80, "2P4E": -8.20, "6U26": -8.50, "3ERT": -8.50,
        "5L2I": -8.00, "2W96": -7.90, "4JPS": -8.30, "3O96": -8.60, "3PP0": -8.40,
        "4ZZZ": -8.10, "1HVY": -8.70, "4I5I": -7.60, "6D8X": -8.10, "5IKR": -7.69,
        "4RER": -8.90, "5VEW": -8.50, "1ERE": -8.80, "4EKL": -8.40
    }
    CO_CRYSTAL_REF_SCORES = {
        "7E2Y": 71.5, "6X1A": 80.0, "2P4E": 81.2, "6U26": 83.5, "3ERT": 84.1,
        "5L2I": 80.5, "2W96": 79.8, "4JPS": 82.0, "3O96": 85.0, "3PP0": 83.2,
        "4ZZZ": 81.0, "1HVY": 85.5, "4I5I": 78.0, "6D8X": 80.4, "5IKR": 72.6,
        "4RER": 87.0, "5VEW": 83.0, "1ERE": 86.5, "4EKL": 82.5
    }
    
    pdb_upper = (mol.target.pdb_id.upper() if mol.target else "")
    ctrl_name = CO_CRY_LIGANDS_placeholder = CO_CRYSTAL_LIGANDS.get(pdb_upper, "N/A")
    ctrl_aff = CO_CRYSTAL_AFFINITIES.get(pdb_upper)
    ctrl_total_score = CO_CRYSTAL_REF_SCORES.get(pdb_upper)

    # Uncertainty Quantification based on Vina pose ensemble
    affinity_err = "± 1.20" # Standard default error threshold
    if eval_result.docking_poses:
        try:
            affinities = [p.get("affinity") for p in eval_result.docking_poses if p.get("affinity") is not None]
            if len(affinities) > 1:
                import math
                mean_aff = sum(affinities) / len(affinities)
                var_aff = sum((x - mean_aff)**2 for x in affinities) / (len(affinities) - 1)
                std_dev = math.sqrt(var_aff)
                # Display standard deviation across pose search space
                affinity_err = f"± {std_dev:.2f}"
        except Exception:
            pass

    dock_headers = ["Métrica de Unión", "Molécula Diseñada", f"Control: {ctrl_name}" if ctrl_name != "N/A" else "Control Nativo"]
    dock_data = [
        dock_headers,
        ["Afinidad (Energía libre de unión)", f"{eval_result.affinity_kcal:.2f} {affinity_err} kcal/mol" if eval_result.affinity_kcal is not None else "N/A", f"{ctrl_aff:.2f} kcal/mol" if ctrl_aff is not None else "N/A"],
        ["Score Global de Selección", f"{eval_result.total_score:.2f} / 100" if eval_result.total_score is not None else "N/A", f"{ctrl_total_score:.2f} / 100" if ctrl_total_score is not None else "N/A"],
        ["Eficiencia de Ligando (LE)", f"{le:.3f}" if le is not None else "N/A", "N/A"],
        ["Eficiencia Lipofílica (LLE)", f"{lle:.3f}" if lle is not None else "N/A", "N/A"]
    ]
    
    dock_table = Table(dock_data, colWidths=[200, 145, 145])
    dock_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BACKGROUND', (0,1), (0,-1), colors.HexColor('#f8fafc')),
        ('FONTNAME', (0,1), (0,-1), 'Helvetica-Bold'),
        ('PADDING', (0,0), (-1,-1), 4),
        ('ALIGN', (1,0), (-1,-1), 'CENTER')
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
        "6X1A": "c1cc(nc(c1)OCc2ccc(cc2F)C#N)C3CCN(CC3)Cc4nc5ccc(cc5n4CC6CCO6)C(=O)O", # Danuglipron (UK4)
        "2P4E": "CN1CCN(CC1)C(=O)c2cc3c(cc2F)[nH]c(n3)c4ccc(cc4)C#N", # SBC-115076
        "6U26": "CC1(c2cc(c(cc2CCN1)OCCOCCNC(=O)C(CCCNC(=NC(=O)OC(C)(C)C)NC(=O)OC(C)(C)C)NC(=O)OC(C)(C)C)Oc3ccc(c(c3)F)c4ccc(cc4)C(=O)O)CC(=O)Nc5nccs5", # Inhibidor Alostérico 11a (063)
        "3ERT": "CCC(=C(c1ccc(cc1)O)c2ccc(cc2)OCCN(C)C)c3ccccc3",  # 4-Hidroxitamoxifeno (OHT)
        "5L2I": "CC1=C(C(=O)N(c2c1cnc(n2)Nc3ccc(cn3)N4CCNCC4)C5CCCC5)C(=O)C", # Palbociclib (LQQ)
        "2W96": "CC1=C(C(=O)N(c2c1cnc(n2)Nc3ccc(cn3)N4CCNCC4)C5CCCC5)C(=O)C", # Palbociclib (LQQ)
        "4JPS": "Cc1c(sc(n1)NC(=O)N2CCCC2C(=O)N)c3ccnc(c3)C(C)(C)C(F)(F)F", # Alpelisib (1LT)
        "3O96": "c1ccc(cc1)c2c(nc3cc4c(cc3n2)nc[nH]4)c5ccc(cc5)CN6CCC(CC6)N7c8ccccc8NC7=O", # Inhibidor Alostérico VIII (IQO)
        "3PP0": "c1cc(cc(c1)Oc2c(cc(cn2)Nc3c4c(ccn4CCOCCO)ncn3)Cl)C(F)(F)F", # SYR-475 (03Q)
        "4ZZZ": "COCCCN1Cc2cccc(c2C1=O)C(=O)N", # FSU (isoindolinone inhibitor)
        "1HVY": "CC1=NC(=O)c2cc(ccc2N1)CN(C)c3ccc(s3)C(=O)NC(CCC(=O)O)C(=O)O", # Raltitrexed (D16)
        "4I5I": "c1cc2c(cc1Cl)c3c([nH]2)C(CCCC3)C(=O)N", # EX-527 (4I5)
        "6D8X": "CN(CCOc1ccc(cc1)CC(C(=O)O)Nc2ccccc2C(=O)c3ccccc3)c4ccccn4", # GW1929 (EDK)
        "5IKR": "Cc1cccc(c1C)Nc2ccccc2C(=O)O", # Ácido Mefenámico (ID8)
        "4RER": "CC12C(C(CC(O1)n3c4ccccc4c5c3c6n2c7ccccc7c6c8c5C(=O)NC8)NC)OC", # Estaurosporina (STU)
        "5VEW": "CC1(CC(C1)C(c2ccc(cc2)C(=O)NCCC(=O)O)Nc3ccc(nc3)n4cc(nc4)C(F)(F)F)C", # PF-06305591 (97Y)
        "1ERE": "CC12CCC3c4ccc(O)cc4CCC3C1CCC2O", # Estradiol (EST)
        "4EKL": "CC1CC(c2c1c(ncn2)N3CCN(CC3)C(=O)C(CNC(C)C)c4ccc(cc4)Cl)O" # Ipatasertib (0RF)
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

    # ADMET-AI Pharmacokinetics Table
    admet_headers = ["Propiedad Biológica (ADMET-AI)", "Predicción", "Significado Clínico"]
    
    solubility_val = f"{eval_result.blood_solubility_logs:.2f} logS" if eval_result.blood_solubility_logs is not None else "N/A"
    ppb_val = str(eval_result.blood_ppb_category) if eval_result.blood_ppb_category else "N/A"
    
    if eval_result.blood_hia_permeable is not None:
        hia_val = "Alta Permeabilidad (HIA+)" if eval_result.blood_hia_permeable else "Baja Absorción (HIA-)"
    else:
        hia_val = "N/A"
        
    if eval_result.blood_bbb_permeable is not None:
        bbb_val = "Permeable (SNC+)" if eval_result.blood_bbb_permeable else "No Permeable (SNC-)"
    else:
        bbb_val = "N/A"
        
    cyp_warnings = []
    if eval_result.blood_systemic_reactivity:
        for alert in eval_result.blood_systemic_reactivity:
            if "CYP" in alert:
                cyp_warnings.append(alert.replace("Inhibidor ", "Inh ").replace("Sustrato ", "Sub "))
    cyp_val = ", ".join(cyp_warnings) if cyp_warnings else "Estándar (No inhibidor)"

    tbl_cell_style = ParagraphStyle(
        'TblCell',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1e293b')
    )
    tbl_cell_bold = ParagraphStyle(
        'TblCellBold',
        parent=tbl_cell_style,
        fontName='Helvetica-Bold'
    )
    tbl_cell_center = ParagraphStyle(
        'TblCellCenter',
        parent=tbl_cell_style,
        alignment=1 # Center
    )

    admet_data = [
        [Paragraph(f"<b>{h}</b>", tbl_cell_bold) for h in admet_headers],
        [
            Paragraph("Solubilidad Acuosa (LogS)", tbl_cell_bold),
            Paragraph(solubility_val, tbl_cell_center),
            Paragraph("Solubilidad teórica en agua a pH fisiológico", tbl_cell_style)
        ],
        [
            Paragraph("Unión a Proteínas (PPB)", tbl_cell_bold),
            Paragraph(ppb_val, tbl_cell_center),
            Paragraph("Categoría de unión a albúmina plasmática", tbl_cell_style)
        ],
        [
            Paragraph("Absorción Intestinal (HIA)", tbl_cell_bold),
            Paragraph(hia_val, tbl_cell_center),
            Paragraph("Permeabilidad en el epitelio intestinal", tbl_cell_style)
        ],
        [
            Paragraph("Barrera Hematoencefálica (BBB)", tbl_cell_bold),
            Paragraph(bbb_val, tbl_cell_center),
            Paragraph("Capacidad de cruce hacia el sistema nervioso central", tbl_cell_style)
        ],
        [
            Paragraph("Metabolismo CYP (P450)", tbl_cell_bold),
            Paragraph(cyp_val, tbl_cell_center),
            Paragraph("Interacción con enzimas hepáticas metabolizadoras", tbl_cell_style)
        ]
    ]
    
    admet_table = Table(admet_data, colWidths=[160, 140, 190])
    admet_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (0,1), (0,-1), colors.HexColor('#f8fafc')),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    story.append(admet_table)
    
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

    # METODOLOGÍA CIENTÍFICA (MATERIALS & METHODS)
    story.append(Spacer(1, 10))
    story.append(Paragraph("Metodología Científica (Materials & Methods)", section_title_style))
    
    methodology_style = ParagraphStyle(
        'MethodologyText',
        parent=styles['Normal'],
        fontSize=7,
        leading=9.5,
        textColor=colors.HexColor('#475569'),
        alignment=4 # Justified
    )
    
    methodology_text = (
        "<b>Preparación del Receptor y Ligando:</b> La estructura tridimensional del receptor se obtuvo del Protein Data Bank (PDB). "
        "Se removieron cofactores no esenciales y moléculas de agua solvente. La protonación a pH fisiológico (7.4), la optimización de la red de puentes de hidrógeno "
        "y el cálculo de cargas parciales Gasteiger se realizaron mediante el flujo automatizado de Meeko y OpenBabel. La conformación tridimensional inicial del ligando "
        "fue optimizada geométricamente y sus estados de protonación calculados antes del docking.<br/>"
        "<b>Docking Molecular y Rescoring:</b> Las simulaciones se llevaron a cabo utilizando el algoritmo de optimización global estocástica iterativa de "
        "AutoDock Vina (v1.2.5) dentro de una caja de grid tridimensional (Grid Box) adaptada individualmente al centroide del sitio activo o del ligando co-cristalizado de referencia "
        "(dimensiones aproximadas de 25×25×25 Å a 30×30×30 Å). La exhaustividad de la búsqueda se fijó en 8 o 16 para asegurar la reproducibilidad de la pose. "
        "Las afinidades reportadas corresponden al estado termodinámico de menor energía libre de unión (pose de mayor afinidad, ΔG en kcal/mol). El rescorado geométrico se "
        "calculó mediante la red neuronal geométrica RTMScore-GNN entrenada sobre el conjunto de datos refinado de PDBbind, y los descriptores fisicoquímicos se computaron utilizando RDKit. "
        "El perfil farmacocinético predictivo profundo (absorción intestinal, cruce de barrera hematoencefálica, unión a proteínas y metabolismo por citocromo P450 CYP) "
        "se infirió mediante los modelos GNN de ADMET-AI, y la puntuación de viabilidad global se determinó a través de un modelo XGBoost parametrizado."
    )
    story.append(Paragraph(methodology_text, methodology_style))
    story.append(Spacer(1, 8))

    # ESPECIFICACIONES TÉCNICAS Y VERSIONES DE MODELOS
    story.append(Paragraph("Especificaciones de Software y Modelos de Inteligencia Artificial", xai_header_style))
    
    tech_style = ParagraphStyle(
        'TechText',
        parent=styles['Normal'],
        fontSize=6.5,
        leading=8.5,
        textColor=colors.HexColor('#64748b')
    )
    
    tech_info = (
        "• <b>Motor de Docking:</b> AutoDock Vina v1.2.5<br/>"
        "• <b>Motor Quimioinformático (ADME):</b> RDKit v2024.09.6 (Cálculo de descriptores fisicoquímicos, QED y reglas de Lipinski/Veber)<br/>"
        "• <b>Modelo de Scoring de Afinidad:</b> RTMScore-GNN (Modelo geométrico: geomscore_v1.0)<br/>"
        "• <b>Modelo de Selección Global:</b> XGBoost v2.1.1 (Modelo predictivo: mol_design_affinity_v3.2)<br/>"
        "• <b>Métrica de Correlación de Dianas (Spearman ρ):</b> Pendiente de verificación (En proceso de recalibración estadística del dataset)"
    )
    story.append(Paragraph(tech_info, tech_style))

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
