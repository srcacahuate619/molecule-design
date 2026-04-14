"""Quick test: extract v4 features from one PDBbind complex."""
import os
import time
from feature_extractor import InteractionFeatureExtractor, ALL_3D_FEATURES

e = InteractionFeatureExtractor()
print(f"Available: {e.is_available}")

data_dir = r"d:\molecular-design\data\pdbbind"
for d in os.listdir(data_dir):
    pdb = os.path.join(data_dir, d, f"{d}_protein.pdb")
    sdf = os.path.join(data_dir, d, f"{d}_ligand.sdf")
    if os.path.exists(pdb) and os.path.exists(sdf):
        print(f"Testing complex: {d}")
        t = time.time()
        feats = e.extract_from_files(pdb, sdf)
        dt = time.time() - t
        print(f"Extraction time: {dt:.2f}s")
        print(f"Features returned: {len(feats)}")

        shell_nz = sum(1 for k, v in feats.items() if k.startswith("shell_") and v > 0)
        ecif_nz = sum(1 for k, v in feats.items() if k.startswith("ecif_") and v > 0)
        print(f"Shell nonzero: {shell_nz}/96")
        print(f"ECIF nonzero: {ecif_nz}/56")
        print(f"heavy_atom_count: {feats.get('heavy_atom_count', 0)}")
        print(f"contacts_per_ha_4A: {feats.get('contacts_per_ha_4A', 0):.2f}")
        print(f"contacts_per_ha_6A: {feats.get('contacts_per_ha_6A', 0):.2f}")
        print(f"hbond_donor: {feats.get('hbond_donor_count', 0)}")
        print(f"close_contacts_4A: {feats.get('close_contacts_4A', 0)}")

        # Top shell features
        shell_feats = [(k, v) for k, v in feats.items() if k.startswith("shell_") and v > 0]
        shell_feats.sort(key=lambda x: -x[1])
        print("Top 5 shell features:")
        for k, v in shell_feats[:5]:
            print(f"  {k}: {v}")

        # Top ECIF features
        ecif_feats_nz = [(k, v) for k, v in feats.items() if k.startswith("ecif_") and v > 0]
        ecif_feats_nz.sort(key=lambda x: -x[1])
        print("Top 5 ECIF features:")
        for k, v in ecif_feats_nz[:5]:
            print(f"  {k}: {v}")

        break
