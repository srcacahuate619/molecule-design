"""Quick diagnostic: can extract_single_complex work via ProcessPoolExecutor?"""
import sys
import time
import os

# Ensure we're in the right dir
os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("Importing feature_extractor...", flush=True)
t0 = time.time()
from feature_extractor import extract_single_complex
print(f"Import OK: {time.time()-t0:.1f}s", flush=True)

prot = r"d:\molecular-design\data\pdbbind\10gs\10gs_protein.pdb"
lig  = r"d:\molecular-design\data\pdbbind\10gs\10gs_ligand.sdf"

if not os.path.exists(prot):
    print(f"MISSING: {prot}", flush=True)
    sys.exit(1)
if not os.path.exists(lig):
    print(f"MISSING: {lig}", flush=True)
    sys.exit(1)

print("Test 1: direct call...", flush=True)
t0 = time.time()
r1 = extract_single_complex(prot, lig)
print(f"Direct: {time.time()-t0:.1f}s  nonzero={sum(1 for v in r1.values() if v > 0)}", flush=True)
print(f"  result={r1}", flush=True)

print("Test 2: ProcessPoolExecutor (1 worker)...", flush=True)
import concurrent.futures
t0 = time.time()
with concurrent.futures.ProcessPoolExecutor(max_workers=1) as pool:
    fut = pool.submit(extract_single_complex, prot, lig)
    try:
        r2 = fut.result(timeout=120)
        print(f"Pool: {time.time()-t0:.1f}s  nonzero={sum(1 for v in r2.values() if v > 0)}", flush=True)
        print(f"  result={r2}", flush=True)
    except Exception as e:
        print(f"Pool FAILED: {time.time()-t0:.1f}s  error={e}", flush=True)

print("ALL DONE", flush=True)
