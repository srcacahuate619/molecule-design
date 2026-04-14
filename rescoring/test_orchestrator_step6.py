"""
Mini-test: replicate orchestrator Step 6 logic on 5 complexes.
Diagnoses whether ProcessPoolExecutor + cache + path resolution works.
"""
import sys
import os
import time
import json
import concurrent.futures
from pathlib import Path


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    data_dir = Path(r"d:\molecular-design\data\pdbbind")
    cache_dir = data_dir / "feature_cache_test"
    cache_dir.mkdir(parents=True, exist_ok=True)

    print("[1] Importing feature_extractor...", flush=True)
    t0 = time.time()
    from feature_extractor import (
        InteractionFeatureExtractor, INTERACTION_FEATURES,
        zero_interaction_features, extract_single_complex,
    )
    print(f"    Import OK ({time.time()-t0:.1f}s)", flush=True)

    print("[2] Creating extractor + checking availability...", flush=True)
    extractor = InteractionFeatureExtractor()
    print(f"    is_available={extractor.is_available}", flush=True)

    # Find first 5 complexes with both protein.pdb and ligand.sdf
    print("[3] Scanning for complexes with PDB+SDF...", flush=True)
    dirs = sorted([
        d for d in data_dir.iterdir()
        if d.is_dir() and d.name not in (
            "feature_cache", "feature_cache_test", "artifacts", "INDEX"
        )
    ])
    print(f"    Total dirs: {len(dirs)}", flush=True)

    jobs = []
    for d in dirs:
        pdb_id = d.name
        prot = d / f"{pdb_id}_protein.pdb"
        lig = d / f"{pdb_id}_ligand.sdf"
        if prot.exists() and lig.exists():
            jobs.append((pdb_id, str(prot), str(lig)))
        if len(jobs) >= 5:
            break

    print(f"    Found {len(jobs)} complexes with both files:", flush=True)
    for pdb_id, prot, lig in jobs:
        print(f"      {pdb_id}: prot={os.path.exists(prot)}, lig={os.path.exists(lig)}", flush=True)

    if not jobs:
        print("[FAIL] No complexes with PDB+SDF found!", flush=True)
        first_dir = dirs[0] if dirs else None
        if first_dir:
            print(f"  Files in {first_dir.name}:", flush=True)
            for f in first_dir.iterdir():
                print(f"    {f.name}", flush=True)
        sys.exit(1)

    # Test ProcessPoolExecutor with 2 workers on 5 jobs
    print(f"\n[4] Submitting {len(jobs)} jobs to ProcessPoolExecutor(max_workers=2)...", flush=True)
    t_start = time.time()

    with concurrent.futures.ProcessPoolExecutor(max_workers=2) as executor:
        future_to_id = {
            executor.submit(extract_single_complex, prot, lig): pdb_id
            for pdb_id, prot, lig in jobs
        }
        print(f"    All {len(future_to_id)} futures submitted ({time.time()-t_start:.1f}s)", flush=True)

        for future in concurrent.futures.as_completed(future_to_id):
            pdb_id = future_to_id[future]
            try:
                feats = future.result(timeout=120)
                nonzero = sum(1 for v in feats.values() if v > 0)
                elapsed = time.time() - t_start
                print(f"    {pdb_id}: OK ({elapsed:.1f}s) nonzero={nonzero} cc4A={feats.get('close_contacts_4A', 0)}", flush=True)

                cf = cache_dir / f"{pdb_id}.json"
                cf.write_text(json.dumps(feats))
                print(f"    -> cached {cf.name}", flush=True)
            except Exception as e:
                elapsed = time.time() - t_start
                print(f"    {pdb_id}: FAIL ({elapsed:.1f}s) error={e}", flush=True)

    total = time.time() - t_start
    print(f"\n[5] Done! Total: {total:.1f}s", flush=True)

    cached = list(cache_dir.glob("*.json"))
    print(f"    Cache files: {len(cached)}", flush=True)
    for cf in cached:
        data = json.loads(cf.read_text())
        nonzero = sum(1 for v in data.values() if v > 0)
        print(f"      {cf.name}: nonzero={nonzero}", flush=True)

    print("\nALL DONE", flush=True)


if __name__ == "__main__":
    main()
