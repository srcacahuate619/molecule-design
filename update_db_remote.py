import subprocess

def run_db_update():
    query = "UPDATE targets SET organism = 'Homo sapiens', resolution = 2.8, structural_family = 'gpcr', requires_cns = true WHERE pdb_id = '7E2Y';"
    cmd = [
        "ssh", "srcacahuate619@192.168.1.64",
        f"docker exec postgres_db psql -U admin -d moldesign_db -c \"{query}\""
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd)

if __name__ == "__main__":
    run_db_update()
