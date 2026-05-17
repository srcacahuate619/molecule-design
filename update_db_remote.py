import subprocess
import os

def load_env():
    env = {}
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        env[parts[0].strip()] = parts[1].strip()
    return env

env = load_env()
REMOTE_USER = env.get("REMOTE_USER", "srcacahuate619")
REMOTE_HOST = env.get("REMOTE_HOST", "192.168.100.12")

def run_db_update():
    queries = [
        "UPDATE targets SET spearman_rho = 0.512 WHERE pdb_id = '7E2Y';",
        "UPDATE targets SET spearman_rho = 0.485 WHERE pdb_id = '6B3J';",
        "UPDATE targets SET spearman_rho = 0.0 WHERE pdb_id IN ('2P4E', '6U26', '3OSK', '4NC3');"
    ]
    for query in queries:
        cmd = [
            "ssh", f"{REMOTE_USER}@{REMOTE_HOST}",
            f"docker exec postgres_db psql -U admin -d moldesign_db -c \"{query}\""
        ]
        print(f"Running: {' '.join(cmd)}")
        subprocess.run(cmd, shell=True)

if __name__ == "__main__":
    run_db_update()
