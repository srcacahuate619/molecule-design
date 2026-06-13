import os
import sys
import json
import asyncio
import time
from datetime import datetime
import redis

# Add backend to path
sys.path.append(os.getcwd())

from recover_global_benchmark import recover_and_sync, run_statistics

def get_queue_length():
    try:
        r1 = redis.Redis.from_url("redis://192.168.1.64:6379/1")
        return r1.llen("celery")
    except Exception as e:
        print(f"[MONITOR] Error connecting to Redis DB 1: {e}")
        return -1

async def main():
    run_id = "spearman_run_20260609_003641"
    print(f"\n[MONITOR] Iniciando daemon de monitoreo para la corrida: {run_id}")
    
    while True:
        q_len = get_queue_length()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[MONITOR] [{timestamp}] Tareas restantes en cola: {q_len}")
        
        # 1. Sincronizar y recalcular
        try:
            await recover_and_sync(run_id)
            await run_statistics(run_id)
        except Exception as e:
            print(f"[MONITOR] Error durante la actualizacion: {e}")
            
        # 2. Si la cola esta vacia y no hay mas tareas, podriamos terminar, 
        # pero es mejor dejarlo correr o verificar si ya completamos los 1400.
        if q_len == 0:
            # Hacemos una ultima verificacion de si todos los targets tienen N=100
            print("[MONITOR] Cola vacia. Verificando si terminamos todo...")
            # En recover_global_benchmark se calcula el total_evals.
            # Dejaremos que el daemon siga corriendo para asegurar que si hay algun retraso se procese, 
            # o podemos dormir mas tiempo.
            time.sleep(300) # Dormir 5 minutos si la cola esta vacia
        else:
            time.sleep(120) # Dormir 2 minutos normalmente

if __name__ == "__main__":
    asyncio.run(main())
