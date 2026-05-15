import subprocess
import os

FILES = [
    "backend/api/main.py",
    "backend/api/routers/targets.py",
    "backend/core/models.py",
    "backend/db/migrations/001_initial.sql",
    "backend/db/repository.py",
    "backend/scoring/engine.py",
    "backend/scoring/normalizer.py",
    "backend/services/docking/queue_handler.py",
    "backend/services/docking/vina_service.py",
    "docker-compose.yml",
    "frontend/app/evaluation/page.tsx",
    "frontend/components/MethodDisclaimer.tsx",
    "frontend/components/MolecularInsight.tsx",
    "frontend/components/ReproducibilityInfo.tsx",
    "frontend/components/MoleculeViewer3D.tsx",
    "frontend/lib/api.ts",
    "frontend/lib/config.ts",
    "frontend/lib/types.ts",
    "frontend/components/ScoreCard.tsx",
    "backend/utils/structural.py",
    "backend/scripts/prepare_new_targets.py",
]

REMOTE_USER = "srcacahuate619"
REMOTE_HOST = "192.168.1.64"
REMOTE_DIR = "/home/srcacahuate619/molecular-design"

def sync_files():
    for file_path in FILES:
        local_path = file_path.replace("/", os.sep)
        remote_path = f"{REMOTE_USER}@{REMOTE_HOST}:{REMOTE_DIR}/{file_path}"
        
        print(f"Syncing {file_path}...")
        try:
            # Create remote directory if it doesn't exist
            remote_subdir = os.path.dirname(f"{REMOTE_DIR}/{file_path}")
            subprocess.run(["ssh", f"{REMOTE_USER}@{REMOTE_HOST}", f"mkdir -p {remote_subdir}"], check=True)
            
            # Copy file
            subprocess.run(["scp", local_path, remote_path], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error syncing {file_path}: {e}")

if __name__ == "__main__":
    sync_files()
