import subprocess

def check_last_score():
    query = "SELECT total_score, affinity_score, adme_score FROM evaluation_results ORDER BY evaluated_at DESC LIMIT 1;"
    cmd = [
        "ssh", "srcacahuate619@192.168.1.64",
        f"docker exec postgres_db psql -U admin -d moldesign_db -c \"{query}\""
    ]
    subprocess.run(cmd)

if __name__ == "__main__":
    check_last_score()
