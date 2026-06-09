import os
import sys
import json
import requests
import math
import hashlib
import asyncio
from rdkit import Chem
from rdkit import RDLogger
from rdkit.Chem import Descriptors
from sqlalchemy import text

# Disable RDKit warnings
RDLogger.DisableLog("rdApp.*")

# Configure UTF-8 output
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Add backend directory to path
sys.path.append(os.getcwd())
# Also append /app just in case it is run within docker and cwd is different
sys.path.append("/app")

from core.database import get_db

TARGET_CHEMBL_ID = "CHEMBL4017"  # PIK3CA WT
PDB_ID = "4JPS"

def clean_smiles(smiles):
    if not smiles or len(smiles) > 120 or "." in smiles:
        return False
    # Exclude metals and other non-standard atoms to protect the docking engine
    metals_and_salts = ["[Na+]", "[Cl-]", "[B]", "[Fe]", "[Pt]", "[Li+]", "[K+]", "[Mg2+]", "[Ca2+]", "[Br-]", "[I-]"]
    if any(metal in smiles for metal in metals_and_salts):
        return False
    
    # Simple check with RDKit to ensure it is parseable
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return False
        # Exclude molecules with unsupported elements
        allowed_atoms = {"C", "N", "O", "S", "P", "F", "Cl", "Br", "I", "H"}
        atoms = {atom.GetSymbol() for atom in mol.GetAtoms()}
        if not atoms.issubset(allowed_atoms):
            return False
        # Exclude very small/large heavy atom counts
        hac = mol.GetNumHeavyAtoms()
        if hac < 10 or hac > 60:
            return False
    except Exception:
        return False
        
    return True

def get_smiles_hash(smiles):
    try:
        mol = Chem.MolFromSmiles(smiles)
        canonical = Chem.MolToSmiles(mol, canonical=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    except Exception:
        return None

async def get_existing_hashes():
    print("🗄️ Querying database for existing molecules...")
    existing_hashes = set()
    try:
        async for db in get_db():
            q = text("SELECT DISTINCT smiles_hash FROM molecules")
            res = await db.execute(q)
            rows = res.fetchall()
            for row in rows:
                if row[0]:
                    existing_hashes.add(row[0])
            print(f"   Found {len(existing_hashes)} existing molecules in the database.")
            break
    except Exception as e:
        print(f"   ⚠️ Could not read database (perhaps running locally or offline): {e}")
    return existing_hashes

def fetch_chembl_candidates():
    print(f"\n📡 Querying ChEMBL for target {TARGET_CHEMBL_ID}...")
    url = "https://www.ebi.ac.uk/chembl/api/data/activity.json"
    
    # We fetch up to 1000 activities, relaxed years
    params = {
        "target_chembl_id": TARGET_CHEMBL_ID,
        "standard_type__in": "Ki,IC50",
        "standard_units": "nM",
        "limit": 1000
    }
    
    candidates = []
    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            fetched = data.get("activities", [])
            print(f"   ChEMBL API returned {len(fetched)} activities.")
            
            for act in fetched:
                smiles = act.get("canonical_smiles")
                val_str = act.get("standard_value")
                
                if not smiles or not val_str:
                    continue
                    
                try:
                    val = float(val_str)
                    if val <= 0:
                        continue
                except ValueError:
                    continue
                    
                if not clean_smiles(smiles):
                    continue
                    
                p_val = round(-math.log10(val * 1e-9), 3)
                
                candidates.append({
                    "smiles": smiles,
                    "experimental_value_nm": val,
                    "p_value": p_val,
                    "type": act.get("standard_type"),
                    "year": act.get("document_year")
                })
        else:
            print(f"   ❌ ChEMBL API error: {response.status_code}")
    except Exception as e:
        print(f"   ❌ ChEMBL API exception: {e}")
        
    return candidates

async def main():
    print("=" * 60)
    print("🧪 PREPARING 100 NEW PIK3CA WT MOLECULES (No Database Overlap)")
    print("=" * 60)
    
    # 1. Fetch from ChEMBL
    candidates = fetch_chembl_candidates()
    if not candidates:
        print("❌ No candidates fetched. Abort.")
        return
        
    # 2. Query database for existing hashes to guarantee novelty
    existing_hashes = await get_existing_hashes()
    
    # 3. Filter and calculate hashes
    new_compounds = []
    seen_hashes = set()
    
    for c in candidates:
        h = get_smiles_hash(c["smiles"])
        if not h:
            continue
        # Check database overlap AND local duplication in this run
        if h not in existing_hashes and h not in seen_hashes:
            c["smiles_hash"] = h
            new_compounds.append(c)
            seen_hashes.add(h)
            
    print(f"\n✨ Identified {len(new_compounds)} brand new compounds (not in DB).")
    
    if len(new_compounds) < 100:
        print(f"❌ Error: Only {len(new_compounds)} new molecules found. Need at least 100. Abort.")
        return
        
    # 4. Sample exactly 100 compounds uniformly across the pValue range
    new_compounds.sort(key=lambda x: x["p_value"], reverse=True)
    
    sampled = []
    target_size = 100
    step = (len(new_compounds) - 1) / (target_size - 1)
    for i in range(target_size):
        idx = int(round(i * step))
        sampled.append(new_compounds[idx])
        
    # Show spread
    print(f"📊 Sampled {len(sampled)} compounds across range pKi/pIC50 [{sampled[-1]['p_value']} - {sampled[0]['p_value']}]")
    
    # 5. Save directly to output
    out_dir = "data/benchmark"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{PDB_ID}_panel.json")
    
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(sampled, f, indent=4, ensure_ascii=False)
        
    print(f"💾 Saved 100 molecules for {PDB_ID} to {out_path} ✅")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
