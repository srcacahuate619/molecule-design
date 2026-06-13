import redis
import json
import base64

def main():
    r1 = redis.Redis.from_url("redis://192.168.1.64:6379/1")
    # Obtener todas las tareas de la lista 'celery'
    tasks = r1.lrange("celery", 0, -1)
    print(f"\n=== SCANNED {len(tasks)} QUEUED TASKS ===")
    
    counts = {}
    target_counts = {}
    
    for idx, t in enumerate(tasks):
        try:
            data = json.loads(t.decode())
            headers = data.get("headers", {})
            task_name = headers.get("task", "unknown")
            counts[task_name] = counts.get(task_name, 0) + 1
            
            if task_name == "moldesign.run_full_evaluation":
                body = data.get("body")
                if isinstance(body, str):
                    decoded_body = base64.b64decode(body).decode()
                    body_data = json.loads(decoded_body)
                    kwargs = body_data[1] if len(body_data) > 1 else {}
                    target = kwargs.get("target_pdb_id", "unknown")
                    target_counts[target] = target_counts.get(target, 0) + 1
        except Exception as e:
            pass
            
    print("\nTask Names Counts:")
    for name, cnt in counts.items():
        print(f"  {name}: {cnt}")
        
    print("\nTarget PDB Counts for run_full_evaluation:")
    for target, cnt in sorted(target_counts.items()):
        print(f"  {target}: {cnt}")
    print("==========================================\n")

if __name__ == "__main__":
    main()
