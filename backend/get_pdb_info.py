import httpx

def get_chains():
    url = "https://data.rcsb.org/rest/v1/core/entry/6B3J"
    data = httpx.get(url).json()
    for poly in data.get('polymer_entities', []):
        pass

    # Better query:
    url_gql = "https://data.rcsb.org/graphql"
    query = """
    {
      entry(entry_id: "6B3J") {
        polymer_entities {
          rcsb_polymer_entity_container_identifiers {
            auth_asym_ids
          }
          rcsb_polymer_entity {
            pdbx_description
          }
        }
      }
    }
    """
    resp = httpx.post(url_gql, json={"query": query}).json()
    for entity in resp['data']['entry']['polymer_entities']:
        desc = entity['rcsb_polymer_entity']['pdbx_description']
        chains = entity['rcsb_polymer_entity_container_identifiers']['auth_asym_ids']
        print(f"{desc}: Chains {chains}")

get_chains()
