import redis

def main():
    r = redis.Redis.from_url("redis://192.168.1.64:6379/0")
    keys = r.keys("*celery*")
    print(f"\n=== REDIS KEYS WITH 'CELERY' ===")
    print(f"Total keys found: {len(keys)}")
    for k in keys[:50]:
        print(f"  Key: {k.decode()} | Type: {r.type(k).decode()}")
    print("=================================\n")

if __name__ == "__main__":
    main()
