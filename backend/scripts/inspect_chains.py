import os

path = "/data/targets/6B3J.pdb"
if not os.path.exists(path):
    path = "data/targets/6B3J.pdb"

print(f"Reading {path}...")
seen = set()
with open(path, "r") as f:
    for line in f:
        if line.startswith("ATOM") and "CA" in line:
            res_name = line[17:20].strip()
            res_seq = line[22:26].strip()
            chain = line[21]
            seen.add(f"{res_name} {chain} {res_seq}")

print("All residues found in 6B3J.pdb:")
for item in sorted(list(seen), key=lambda x: int(x.split()[-1]) if x.split()[-1].isdigit() else 999):
    print(f"  {item}")
