import subprocess
import json

HOTSPOTS_3OSK = [
    {"name": "MET97", "importance": 1.0},
    {"name": "TYR99", "importance": 1.0},
    {"name": "PRO101", "importance": 0.5},
    {"name": "TYR103", "importance": 0.8}
]

HOTSPOTS_7E2Y = [
    {"name": "ASP116", "importance": 1.0},
    {"name": "PHE361", "importance": 0.7},
    {"name": "SER199", "importance": 0.6}
]

def update_hotspots():
    for pdb_id, hotspots in [("3OSK", HOTSPOTS_3OSK), ("7E2Y", HOTSPOTS_7E2Y)]:
        json_data = json.dumps(hotspots).replace('"', '\\"')
        query = f"UPDATE targets SET hotspots = '{json_data}' WHERE pdb_id = '{pdb_id}';"
        cmd = [
            "ssh", "srcacahuate619@192.168.1.64",
            f"docker exec postgres_db psql -U admin -d moldesign_db -c \"{query}\""
        ]
        subprocess.run(cmd)

if __name__ == "__main__":
    update_hotspots()
