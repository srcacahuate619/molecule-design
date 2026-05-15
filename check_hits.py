import requests
import subprocess
import json

def check_last_hits():
    query = "SELECT molecule_id FROM evaluation_results ORDER BY evaluated_at DESC LIMIT 1;"
    cmd = [
        "ssh", "srcacahuate619@192.168.1.64",
        f"docker exec postgres_db psql -U admin -d moldesign_db -t -c \"{query}\""
    ]
    mol_id = subprocess.check_output(cmd).decode().strip()
    
    url = f"http://192.168.1.64:8010/evaluation/result/{mol_id}"
    resp = requests.get(url)
    if resp.status_code == 200:
        data = resp.json()
        print(f"Total Score: {data.get('total_score')}")
        print(f"Specificity Score: {data.get('specificity_score')}")
        print(f"Hotspots Hit: {data.get('hotspots_hit')}")
        print(f"Target Hotspots: {data.get('target_pdb_id')}")

if __name__ == "__main__":
    check_last_hits()
