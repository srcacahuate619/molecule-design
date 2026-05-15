import subprocess
import json

HOTSPOTS_3OSK = [
    {"name": "MET99", "importance": 1.0},
    {"name": "TYR100", "importance": 1.0},
    {"name": "PRO102", "importance": 0.5},
    {"name": "TYR104", "importance": 0.8}
]

def update_hotspots():
    json_data = json.dumps(HOTSPOTS_3OSK).replace('"', '\\"')
    query = f"UPDATE targets SET hotspots = '{json_data}' WHERE pdb_id = '3OSK';"
    cmd = [
        "ssh", "srcacahuate619@192.168.1.64",
        f"docker exec postgres_db psql -U admin -d moldesign_db -c \"{query}\""
    ]
    subprocess.run(cmd)

if __name__ == "__main__":
    update_hotspots()
