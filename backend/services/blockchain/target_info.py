import httpx
from deep_translator import GoogleTranslator

async def fetch_and_translate_target_info(pdb_id: str) -> str:
    """
    Fetches protein function from PDB -> UniProt and translates it to Spanish.
    Falls back to PDB title if UniProt function is not found.
    """
    try:
        # 1. Fetch UniProt ID from PDB
        pdb_url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id.upper()}"
        async with httpx.AsyncClient() as client:
            pdb_res = await client.get(pdb_url, timeout=10.0)
            pdb_res.raise_for_status()
            pdb_data = pdb_res.json()
            
            # Extract basic title as fallback
            title = pdb_data.get("struct", {}).get("title", "")
            
            # Extract UniProt ID
            uniprot_ids = []
            try:
                uniprot_ids = pdb_data["rcsb_polymer_entity_container_identifiers"][0]["uniprot_ids"]
            except (KeyError, IndexError):
                pass
                
        # 2. If UniProt ID exists, fetch Function from UniProt
        english_text = title
        if uniprot_ids:
            uniprot_id = uniprot_ids[0]
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

        # 3. Translate to Spanish
        translator = GoogleTranslator(source='en', target='es')
        # Translate in chunks if it's too long, but function descriptions are usually < 5000 chars
        spanish_text = translator.translate(english_text)
        return spanish_text

    except Exception as e:
        print(f"Error fetching target info for {pdb_id}: {e}")
        return f"Receptor Biológico PDB: {pdb_id.upper()}"
