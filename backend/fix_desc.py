import asyncio
from core.database import SessionLocal
from core.models import TargetORM
from services.blockchain.target_info import fetch_and_translate_target_info

async def force_fix():
    db = SessionLocal()
    t = db.query(TargetORM).first()
    if t:
        print(f"Current description: {t.description}")
        # Force it
        print("Fetching new description...")
        desc = await fetch_and_translate_target_info(t.pdb_id)
        print(f"New description: {desc}")
        t.description = desc
        db.commit()
    db.close()

if __name__ == "__main__":
    asyncio.run(force_fix())
