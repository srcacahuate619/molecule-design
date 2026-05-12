"""
Script de auditoría completa del pipeline IA para MolDesign.
Prueba Gemini 2.0 Flash desde dentro del contenedor worker.
"""
import asyncio
import os
import sys

# Forzar carga de .env del backend
env_path = "/app/backend/.env"
if os.path.exists(env_path):
    from dotenv import load_dotenv
    load_dotenv(env_path)

# Si no tenemos key, intentar leerla directamente
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    # Intentar leer el .env directamente
    env_file = "/app/.env"
    if os.path.exists(env_file):
        for line in open(env_file):
            if line.startswith("GEMINI_API_KEY="):
                GEMINI_API_KEY = line.strip().split("=", 1)[1]
                break

print(f"=== AUDIT DE PIPELINE IA ===")
print(f"API Key encontrada: {'SÍ (' + GEMINI_API_KEY[:10] + '...)' if GEMINI_API_KEY else 'NO'}")

# ─── PASO 1: Verificar que la config de settings cargue la key ───────────────
print("\n[PASO 1] Verificando Settings...")
try:
    from core.config import get_settings
    settings = get_settings()
    print(f"  settings.gemini_api_key = {'SET (' + settings.gemini_api_key[:10] + '...)' if settings.gemini_api_key else 'NONE ← PROBLEMA'}")
    print(f"  settings.gemini_model   = {settings.gemini_model}")
    GEMINI_API_KEY = settings.gemini_api_key
except Exception as e:
    print(f"  ERROR cargando settings: {e}")

# ─── PASO 2: Llamar a Gemini directamente ────────────────────────────────────
print("\n[PASO 2] Llamando a Gemini...")
if not GEMINI_API_KEY:
    print("  SALTANDO: No hay API key.")
else:
    import httpx
    model = getattr(settings, 'gemini_model', 'gemini-2.0-flash')
    url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": "Responde solo con la palabra HOLA"}]}]}
    
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(url, json=payload)
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            text = data['candidates'][0]['content']['parts'][0]['text']
            print(f"  ✅ Gemini respondió: {text.strip()[:100]}")
        else:
            print(f"  ❌ Error Gemini: {r.text[:500]}")
    except Exception as e:
        print(f"  ❌ Excepción: {e}")

# ─── PASO 3: Verificar interpreter.py directamente ───────────────────────────
print("\n[PASO 3] Verificando interpreter.safe_generate_ai_report...")
async def test_interpreter():
    try:
        from core.models import AIReportRequest, ScoreBreakdown, PhysicochemicalProperties
        from services.ai.interpreter import safe_generate_ai_report
        
        # Crear un request mínimo
        props = PhysicochemicalProperties(
            molecular_weight=176.12,
            log_p=-0.35,
            tpsa=83.06,
            hbd=3,
            hba=4,
            rotatable_bonds=3,
            heavy_atom_count=13,
            ring_count=1,
            lipinski_pass=True,
            veber_pass=True,
            qed=0.55,
        )
        breakdown = ScoreBreakdown(
            affinity_score=55.0,
            adme_score=60.0,
            druglikeness_score=65.0,
            total_score=35.1,
        )
        request = AIReportRequest(
            molecule_smiles="NCCc1c[nH]c2ccc(O)cc12",
            target_name="5-HT1A serotonin receptor",
            affinity_kcal=-6.1,
            affinity_score=55.0,
            properties=props,
            score_breakdown=breakdown,
            is_control=True,
        )
        
        print("  Enviando request a safe_generate_ai_report...")
        report = await safe_generate_ai_report(request)
        if report:
            print(f"  ✅ Reporte generado ({len(report)} chars):")
            print(f"  {report[:300]}...")
        else:
            print("  ❌ safe_generate_ai_report devolvió None")
    except Exception as e:
        import traceback
        print(f"  ❌ Excepción: {e}")
        traceback.print_exc()

asyncio.run(test_interpreter())

# ─── PASO 4: Verificar DB ─────────────────────────────────────────────────────
print("\n[PASO 4] Verificando si ai_report existe en la última evaluación en BD...")
async def check_db():
    try:
        from db.database import get_db_session
        from sqlalchemy import select, desc
        from core.models import EvaluationResultORM
        
        async with get_db_session() as db:
            result = await db.execute(
                select(EvaluationResultORM).order_by(desc(EvaluationResultORM.evaluated_at)).limit(1)
            )
            row = result.scalar_one_or_none()
            if row:
                print(f"  Último resultado - molecule_id: {row.molecule_id}")
                print(f"  total_score: {row.total_score}")
                print(f"  ai_report: {'PRESENTE (' + str(len(row.ai_report or '')) + ' chars)' if row.ai_report else 'NULL ← PROBLEMA'}")
            else:
                print("  No hay evaluaciones en la BD.")
    except Exception as e:
        import traceback
        print(f"  ❌ Error: {e}")
        traceback.print_exc()

asyncio.run(check_db())

print("\n=== FIN AUDITORÍA ===")
