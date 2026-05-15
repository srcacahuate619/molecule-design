import asyncio
import sys
import os
import json

# Añadir el path del backend
sys.path.append(os.getcwd())

from sqlalchemy import text
from db.repository import Repository
from core.database import get_db

async def audit():
    print("🔬 Iniciando Auditoría Científica de Hotspots...")
    
    async for db in get_db():
        repo = Repository(db)
        # Obtener todos los targets preparados
        query = await db.execute(text("SELECT pdb_id, name, hotspots FROM targets WHERE hotspots IS NOT NULL"))
        targets = query.fetchall()
        
        audit_report = []
        
        for t in targets:
            pdb_id, name, hotspots = t
            print(f"🧐 Auditando {pdb_id} ({name})...")
            
            # En un entorno real, aquí llamaríamos a Gemini para validar
            # Por ahora, simularemos la auditoría comparando con una 'gold standard' lógica
            # o preparando el prompt para el reporte final.
            
            hotspot_list = [h['name'] for h in hotspots]
            
            audit_report.append({
                "pdb_id": pdb_id,
                "name": name,
                "mined_hotspots": hotspot_list,
                "count": len(hotspot_list)
            })
            
        print("\n📊 RESULTADOS PRELIMINARES DE LA MINERÍA:")
        print(json.dumps(audit_report, indent=2))
        
        # Guardar en un archivo para que el Asistente lo procese
        with open("hotspot_audit_data.json", "w") as f:
            json.dump(audit_report, f)
        
        break

if __name__ == "__main__":
    asyncio.run(audit())
