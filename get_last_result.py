import requests
import subprocess
import json

def get_last_result():
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
        print(f"Total: {data.get('total_score')}")
        print(f"Affinity Score: {data.get('affinity_score')}")
        print(f"ADME Score (QED): {data.get('adme_score')}")
        print(f"Druglikeness Score (SA): {data.get('druglikeness_score')}")
        print(f"Affinity Kcal: {data.get('affinity_kcal')}")
        print(f"LogP: {data.get('log_p')}")
        print(f"MW: {data.get('molecular_weight')}")

if __name__ == "__main__":
    get_last_result()
