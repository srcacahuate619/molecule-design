import asyncio
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import sys
import os

# Añadir el path del backend para poder importar core.models
sys.path.append(os.path.join(os.getcwd(), "backend"))

from core.models import TargetORM
from core.config import get_settings

settings = get_settings()

async def update_hotspots():
    engine = create_async_engine(str(settings.database_url))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    HOTSPOTS_DATA = {
        "7E2Y": [
            {"name": "MET97", "importance": 0.8},
            {"name": "ASP116", "importance": 1.0},
            {"name": "VAL117", "importance": 0.7},
            {"name": "SER190", "importance": 0.6},
            {"name": "PHE361", "importance": 0.9}
        ],
        "6B3J": [
            {"name": "TYR152", "importance": 0.9},
            {"name": "ARG190", "importance": 1.0},
            {"name": "LYS197", "importance": 0.8},
            {"name": "ASP198", "importance": 1.0},
            {"name": "GLN210", "importance": 0.7}
        ]
    }

    async with async_session() as session:
        for pdb_id, hotspots in HOTSPOTS_DATA.items():
            stmt = select(TargetORM).where(TargetORM.pdb_id == pdb_id)
            result = await session.execute(stmt)
            target = result.scalar_one_or_none()
            
            if target:
                print(f"Actualizando hotspots para {pdb_id}...")
                target.hotspots = hotspots
                session.add(target)
            else:
                print(f"Target {pdb_id} no encontrado en la DB.")
        
        await session.commit()
        print("Sincronización de hotspots completada.")

if __name__ == "__main__":
    asyncio.run(update_hotspots())
