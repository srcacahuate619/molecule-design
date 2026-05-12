import io
from datetime import datetime
from rdkit import Chem
from rdkit.Chem import Draw
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from core.models import MoleculeORM, EvaluationResultORM

def get_2d_image_bytes(smiles: str) -> io.BytesIO:
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        return None
    # Generate 2D image
    img = Draw.MolToImage(mol, size=(400, 400))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

def generate_certificate_pdf(mol: MoleculeORM, eval_result: EvaluationResultORM, target_name: str) -> io.BytesIO:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    
    # Color palette
    brand_color = (0.23, 0.51, 0.96) # Hex #3b82f6 (blue-500)
    
    # Title
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2.0, height - 80, "CERTIFICADO DE DESCUBRIMIENTO MOLECULAR")
    
    c.setFont("Helvetica", 14)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawCentredString(width / 2.0, height - 105, "Registrado inmutablemente en Solana (Devnet)")
    c.setFillColorRGB(0, 0, 0)
    
    # Date
    cert_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    c.setFont("Helvetica-Oblique", 11)
    c.drawCentredString(width / 2.0, height - 130, f"Fecha de Certificación: {cert_date}")
    
    # Image (Centered)
    img_buf = get_2d_image_bytes(mol.smiles)
    if img_buf:
        img_reader = ImageReader(img_buf)
        c.drawImage(img_reader, (width - 250) / 2.0, height - 400, width=250, height=250, preserveAspectRatio=True, mask='auto')
        
    # Molecule Data
    c.setFont("Helvetica-Bold", 14)
    c.setFillColorRGB(*brand_color)
    c.drawString(60, height - 430, "Detalles de la Molécula")
    c.setFillColorRGB(0, 0, 0)
    
    c.setFont("Helvetica", 11)
    c.drawString(60, height - 455, f"ID de Sistema: {mol.id}")
    smiles_disp = f"{mol.smiles[:60]}..." if len(mol.smiles) > 60 else mol.smiles
    c.drawString(60, height - 475, f"SMILES: {smiles_disp}")
    c.drawString(60, height - 495, f"Target Biológico: {target_name}")
    
    # Scores
    c.setFont("Helvetica-Bold", 14)
    c.setFillColorRGB(*brand_color)
    c.drawString(60, height - 535, "Resultados de Evaluación")
    c.setFillColorRGB(0, 0, 0)
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, height - 560, f"Puntuación Total: {eval_result.total_score:.2f} / 100")
    c.setFont("Helvetica", 11)
    c.drawString(60, height - 580, f"Afinidad (AutoDock Vina): {eval_result.affinity_kcal:.2f} kcal/mol")
    c.drawString(60, height - 600, f"Score ADME: {eval_result.adme_score:.2f} / 100")
    c.drawString(60, height - 620, f"Score Drug-likeness: {eval_result.druglikeness_score:.2f} / 100")
    
    # Blockchain Details
    c.setFont("Helvetica-Bold", 14)
    c.setFillColorRGB(*brand_color)
    c.drawString(60, height - 660, "Blockchain (Proof of Discovery)")
    c.setFillColorRGB(0, 0, 0)
    
    tx_id = eval_result.blockchain_tx_id or "No certificado"
    
    c.setFont("Helvetica-Bold", 11)
    c.drawString(60, height - 685, "Firma de Transacción:")
    c.setFont("Helvetica", 10)
    c.drawString(60, height - 700, f"{tx_id}")
    
    if eval_result.blockchain_tx_id:
        c.setFont("Helvetica-Bold", 11)
        c.setFillColorRGB(0.1, 0.1, 0.9)
        c.drawString(60, height - 725, "Enlace de Verificación:")
        c.setFont("Helvetica", 10)
        c.drawString(60, height - 740, f"https://explorer.solana.com/tx/{tx_id}?cluster=devnet")
        c.setFillColorRGB(0, 0, 0)
        
    # Footer
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    footer_text_1 = "Generado de forma autónoma por MolDesign AI bajo licencia abierta CC0."
    footer_text_2 = "Código y Plataforma: https://github.com/srcacahuate619/molecule-design"
    c.drawCentredString(width / 2.0, 50, footer_text_1)
    c.drawCentredString(width / 2.0, 35, footer_text_2)
    
    c.showPage()
    c.save()
    
    buf.seek(0)
    return buf
