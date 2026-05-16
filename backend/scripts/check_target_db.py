import asyncio
import os
import sys

# Añadir el path raíz
sys.path.append("/app")

from db.repository import Repository
from core.database import get_db

async def check():
    async for db in get_db():
        repo = Repository(db)
        t = await repo.get_target_by_pdb_id('6B3J')
        if t:
            print(f"Center: ({t.grid_center_x}, {t.grid_center_y}, {t.grid_center_z})")
            print(f"Size: ({t.grid_size_x}, {t.grid_size_y}, {t.grid_size_z})")
            print(f"Chain: {t.chain}")
            print(f"Hotspots: {t.hotspots}")
        else:
            print("Target 6B3J not found in DB")
        break

if __name__ == "__main__":
    asyncio.run(check())
