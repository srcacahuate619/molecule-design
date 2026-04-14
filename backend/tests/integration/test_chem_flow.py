"""Tests de integración mínimos del flujo químico existente."""

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_properties_endpoint_returns_adme_summary(client):
    response = await client.post(
        "/chem/properties",
        json={"smiles": "CC(=O)Oc1ccccc1C(=O)O"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["properties"]["molecular_weight"] > 0
    assert payload["adme_summary"]
