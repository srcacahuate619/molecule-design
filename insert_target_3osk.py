import subprocess
import uuid

def insert_target_3osk():
    target_id = str(uuid.uuid4())
    query = f"""
    INSERT INTO targets (
        id, pdb_id, name, chain, description, 
        grid_center_x, grid_center_y, grid_center_z, 
        grid_size_x, grid_size_y, grid_size_z, 
        requires_cns, structural_family, organism, resolution, is_prepared
    ) VALUES (
        '{target_id}', '3OSK', 'CTLA-4 Immune Checkpoint', 'A', 
        'Receptor inmunitario (Checkpoint). Sitio de unión B7 (Loop MYPPPY).', 
        -2.132, -19.592, 22.149, 25.0, 25.0, 25.0, 
        false, 'checkpoint', 'Homo sapiens', 2.5, false
    ) ON CONFLICT (pdb_id) DO UPDATE SET 
        name = EXCLUDED.name, 
        description = EXCLUDED.description,
        grid_center_x = EXCLUDED.grid_center_x,
        grid_center_y = EXCLUDED.grid_center_y,
        grid_center_z = EXCLUDED.grid_center_z,
        structural_family = EXCLUDED.structural_family,
        organism = EXCLUDED.organism,
        resolution = EXCLUDED.resolution;
    """
    
    cmd = [
        "ssh", "srcacahuate619@192.168.1.64",
        f"docker exec postgres_db psql -U admin -d moldesign_db -c \"{query}\""
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd)

if __name__ == "__main__":
    insert_target_3osk()
