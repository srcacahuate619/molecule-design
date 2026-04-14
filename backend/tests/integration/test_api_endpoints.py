"""Tests mínimos de integración HTTP para el entrypoint del MVP."""

import pytest
from unittest.mock import patch


@pytest.mark.integration
@pytest.mark.asyncio
async def test_root_endpoint_returns_metadata(client):
    response = await client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "MolDesign API"
    assert "mission" in payload


@pytest.mark.integration
@pytest.mark.asyncio
async def test_validate_endpoint_works(client):
    response = await client.post(
        "/chem/validate",
        json={"smiles": "CC(=O)Oc1ccccc1C(=O)O"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_valid"] is True
    assert payload["canonical_smiles"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_submit_evaluation_accepts_job(client):
    with patch("services.docking.queue_handler.submit_evaluation_job") as mocked_submit:
        mocked_submit.return_value.id = "task-mock-123"
        response = await client.post(
            "/evaluation/submit",
            json={
                "smiles": "CC(=O)Oc1ccccc1C(=O)O",
                "target_pdb_id": "7E2Y",
                "molecule_name": "Aspirina MVP",
            },
        )

    assert response.status_code == 202
    payload = response.json()
    assert payload["task_id"] == "task-mock-123"
    assert payload["status"] == "submitted"
