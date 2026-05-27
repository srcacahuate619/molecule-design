import httpx
from deep_translator import GoogleTranslator
import re

async def fetch_and_translate_target_info(pdb_id: str) -> str:
    """
    Fetches protein function from PDB -> UniProt and translates it to Spanish.
    Falls back to PDB title if UniProt function is not found.
    """
    try:
        title = ""
        uniprot_id = None
        
        # 1. Fetch from PDB to get title and entities
        pdb_url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id.upper()}"
        async with httpx.AsyncClient() as client:
            pdb_res = await client.get(pdb_url, timeout=10.0)
            pdb_res.raise_for_status()
            pdb_data = pdb_res.json()
            title = pdb_data.get("struct", {}).get("title", "")
            
            entities = pdb_data.get("rcsb_entry_container_identifiers", {}).get("polymer_entity_ids", [])
            
            best_uniprot = None
            best_score = -1
            
            # Dynamically find the best UniProt ID among all entities in the complex
            for ent_id in entities:
                ent_url = f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id.upper()}/{ent_id}"
                ent_res = await client.get(ent_url, timeout=10.0)
                if ent_res.status_code == 200:
                    ent_data = ent_res.json()
                    
                    # Check taxonomy (prefer human 9606)
                    orgs = ent_data.get("rcsb_entity_source_organism", [])
                    is_human = any(org.get("ncbi_taxonomy_id") == 9606 for org in orgs)
                    
                    # Check description for keywords
                    desc = ent_data.get("rcsb_polymer_entity", {}).get("pdbx_description", "").lower()
                    is_receptor = "receptor" in desc or "channel" in desc or "kinase" in desc
                    
                    # Get uniprot id (handle fusion proteins by picking the longest aligned region)
                    uid = None
                    max_len = 0
                    aligns = ent_data.get("rcsb_polymer_entity_align", [])
                    for align in aligns:
                        if align.get("reference_database_name") == "UniProt":
                            current_uid = align.get("reference_database_accession")
                            regions = align.get("aligned_regions", [])
                            total_len = sum(r.get("length", 0) for r in regions)
                            if total_len > max_len:
                                max_len = total_len
                                uid = current_uid
                            
                    if uid:
                        score = 0
                        if is_human: score += 10
                        if is_receptor: score += 20
                        
                        if score > best_score:
                            best_score = score
                            best_uniprot = uid
                            
            uniprot_id = best_uniprot
        # 2. If UniProt ID exists, fetch Function from UniProt
        english_text = title
        if uniprot_id:
            uniprot_url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"
            async with httpx.AsyncClient() as client:
                up_res = await client.get(uniprot_url, timeout=10.0)
                if up_res.status_code == 200:
                    up_data = up_res.json()
                    for comment in up_data.get("comments", []):
                        if comment.get("commentType") == "FUNCTION":
                            texts = [t.get("value") for t in comment.get("texts", []) if t.get("value")]
                            if texts:
                                english_text = " ".join(texts)
                                break

        if not english_text:
            return "Descripción del receptor no disponible."

        # Strip PubMed citations e.g. (PubMed:12345) or (PubMed:123, PubMed:456)
        english_text = re.sub(r'\(PubMed:[\d\s,a-zA-Z:-]+\)', '', english_text).replace('  ', ' ').strip()

        # 3. Translate to Spanish
        translator = GoogleTranslator(source='en', target='es')
        # Translate in chunks if it's too long, but function descriptions are usually < 5000 chars
        spanish_text = translator.translate(english_text)
        return spanish_text

    except Exception as e:
        print(f"Error fetching target info for {pdb_id}: {e}")
        return f"Receptor Biológico PDB: {pdb_id.upper()}"
