"""
tests/integration/test_e2e_pipeline.py

Test end-to-end completo: SMILES → validación → propiedades → conformer → docking → scoring → IA.

Este test valida que el flujo científico íntegro funciona correctamente.

Ejecutar contra servidor remoto:
    python -m pytest tests/integration/test_e2e_pipeline.py -v -s --timeout=600 \
        -k test_e2e_aspirin

O contra localhost (si está levantado):
    pytest tests/integration/test_e2e_pipeline.py -v -s
"""

import asyncio
import json
import time
from typing import Any, Optional

import aiohttp
import pytest


# Configuración de servidor
API_BASE_URL = "http://192.168.1.64:8000"  # Servidor remoto
TIMEOUT = aiohttp.ClientTimeout(total=600)  # 10 minutos para docking
MAX_RETRIES = 60  # 60 intentos de polling
POLL_INTERVAL = 5  # segundos


class APIClient:
    """Cliente HTTP asíncrono para la API."""

    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=TIMEOUT)
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        json_data: Optional[dict] = None,
    ) -> tuple[int, Any]:
        """Ejecuta un request y retorna (status_code, body)."""
        if not self.session:
            raise RuntimeError("Session no inicializada")

        url = f"{self.base_url}{endpoint}"
        kwargs = {}
        if json_data:
            kwargs["json"] = json_data
        if data:
            kwargs["data"] = data

        async with self.session.request(method, url, **kwargs) as resp:
            try:
                body = await resp.json()
            except (aiohttp.ContentTypeError, json.JSONDecodeError):
                body = await resp.text()
            return resp.status, body

    async def validate(self, smiles: str) -> tuple[int, dict]:
        """POST /chem/validate"""
        return await self.request("POST", "/chem/validate", json_data={"smiles": smiles})

    async def properties(self, smiles: str) -> tuple[int, dict]:
        """POST /chem/properties"""
        return await self.request("POST", "/chem/properties", json_data={"smiles": smiles})

    async def conformer(self, smiles: str) -> tuple[int, dict]:
        """POST /chem/conformer"""
        return await self.request("POST", "/chem/conformer", json_data={"smiles": smiles})

    async def submit_evaluation(
        self, smiles: str, target_pdb_id: str = "7E2Y", is_control: bool = False
    ) -> tuple[int, dict]:
        """POST /evaluation/submit"""
        return await self.request(
            "POST",
            "/evaluation/submit",
            json_data={
                "smiles": smiles,
                "target_pdb_id": target_pdb_id,
                "is_control": is_control,
            },
        )

    async def evaluation_status(self, task_id: str) -> tuple[int, dict]:
        """GET /evaluation/status/{task_id}"""
        return await self.request("GET", f"/evaluation/status/{task_id}")

    async def health(self) -> tuple[int, dict]:
        """GET /health"""
        return await self.request("GET", "/health")


async def wait_for_evaluation(
    client: APIClient, task_id: str, timeout_sec: int = 600
) -> dict:
    """
    Polling hasta que el job esté completo.
    Retorna el objeto de resultado final.
    """
    start = time.time()
    attempt = 0

    while time.time() - start < timeout_sec:
        attempt += 1
        status_code, body = await client.evaluation_status(task_id)

        if status_code != 200:
            print(f"[Attempt {attempt}] Status check failed: {status_code}")
            await asyncio.sleep(POLL_INTERVAL)
            continue

        status = body.get("status", "unknown")
        progress = body.get("progress", 0)

        print(f"[Attempt {attempt}] Status: {status}, Progress: {progress}%")

        if status in ["completed", "success"]:
            return body
        elif status == "failed":
            raise RuntimeError(f"Job failed: {body.get('error', 'unknown error')}")

        await asyncio.sleep(POLL_INTERVAL)

    raise TimeoutError(f"Job {task_id} did not complete within {timeout_sec}s")


@pytest.mark.asyncio
async def test_e2e_aspirin():
    """
    Test E2E completo: Aspirina (SMILES conocida).

    Flujo:
    1. POST /chem/validate → validar SMILES
    2. POST /chem/properties → calcular física/química
    3. POST /chem/conformer → generar 3D
    4. POST /evaluation/submit → encolar docking
    5. GET /evaluation/status/{task_id} → polling hasta completado
    6. Verificar resultado final (scoring, IA report)
    """
    aspirin_smiles = "CC(=O)Oc1ccccc1C(=O)O"

    async with APIClient() as client:
        # Health check
        print("\n[1/6] Health check...")
        status_code, health = await client.health()
        assert status_code == 200, f"Health check failed: {health}"
        print(f"✓ API healthy: {json.dumps(health, indent=2)}")

        # Step 1: Validación
        print("\n[2/6] Validar SMILES...")
        status_code, validate_result = await client.validate(aspirin_smiles)
        assert status_code == 200, f"Validate failed: {validate_result}"
        assert validate_result["is_valid"] is True, f"SMILES inválido: {validate_result}"
        smiles_hash = validate_result["smiles_hash"]
        print(f"✓ SMILES válido: {validate_result['canonical_smiles']}")
        print(f"  - Fórmula: {validate_result['molecular_formula']}")
        print(f"  - Hash: {smiles_hash[:8]}...")

        # Step 2: Propiedades fisicoquímicas
        print("\n[3/6] Calcular propiedades fisicoquímicas...")
        status_code, props_result = await client.properties(aspirin_smiles)
        assert status_code == 200, f"Properties failed: {props_result}"
        props = props_result["properties"]
        print(f"✓ Propiedades calculadas:")
        print(f"  - MW: {props['molecular_weight']:.2f}")
        print(f"  - logP: {props['log_p']:.2f}")
        print(f"  - TPSA: {props['tpsa']:.2f} Ų")
        print(f"  - Lipinski pass: {props['lipinski_pass']}")
        print(f"  - ADME summary: {props_result['adme_summary'][:100]}...")

        # Step 3: Conformer 3D
        print("\n[4/6] Generar conformer 3D...")
        status_code, conformer_result = await client.conformer(aspirin_smiles)
        assert status_code == 200, f"Conformer failed: {conformer_result}"
        print(f"✓ Conformer generado:")
        print(f"  - Ruta MinIO: {conformer_result['conformer_path']}")

        # Step 4: Enviar evaluación (docking asíncrono)
        print("\n[5/6] Enviar evaluación (docking asíncrono)...")
        status_code, submit_result = await client.submit_evaluation(aspirin_smiles)
        assert status_code == 202, f"Submit failed: {submit_result}"
        task_id = submit_result["task_id"]
        print(f"✓ Job encolado: {task_id}")
        print(f"  - Target: {submit_result['target_pdb_id']}")
        print(f"  - Estado inicial: {submit_result['status']}")

        # Step 5: Polling hasta completado
        print("\n[6/6] Esperando docking (esto puede tardar varios minutos)...")
        result = await wait_for_evaluation(client, task_id, timeout_sec=600)

        print(f"\n✓ ¡Evaluación completada!")
        print(f"\nResultado final:")
        print(f"  - Status: {result['status']}")
        print(f"  - Progress: {result['progress']}%")

        if result.get("result"):
            evaluation = result["result"]
            print(f"\n  Docking:")
            print(f"    - Afinidad: {evaluation.get('affinity_kcal', 'N/A')} kcal/mol")
            print(f"    - Score total: {evaluation.get('total_score', 'N/A')}")
            print(f"    - Score afinidad: {evaluation.get('affinity_score', 'N/A')}")
            print(f"    - Score ADME: {evaluation.get('adme_score', 'N/A')}")
            print(f"    - Score drug-likeness: {evaluation.get('druglikeness_score', 'N/A')}")
            print(f"    - Dimensión más fuerte: {evaluation.get('strongest_dimension', 'N/A')}")
            print(f"    - Dimensión más débil: {evaluation.get('weakest_dimension', 'N/A')}")
            print(f"    - Hint mejora: {evaluation.get('improvement_hint', 'N/A')}")

            if evaluation.get("ai_report"):
                print(f"\n  Reporte IA (primeras 300 chars):")
                print(f"    {evaluation['ai_report'][:300]}...")

        assert result["status"] in ["completed", "success"], f"Job no completó: {result}"


@pytest.mark.asyncio
async def test_e2e_cafeina():
    """Test E2E con cafeína (otra molécula conocida)."""
    cafeina_smiles = "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"

    async with APIClient() as client:
        print("\n━━━ Test E2E: CAFEÍNA ━━━")

        # Validar
        status_code, validate_result = await client.validate(cafeina_smiles)
        assert status_code == 200
        assert validate_result["is_valid"] is True
        print(f"✓ Cafeína válida: {validate_result['canonical_smiles']}")
        print(f"  Fórmula: {validate_result['molecular_formula']}")

        # Propiedades
        status_code, props_result = await client.properties(cafeina_smiles)
        assert status_code == 200
        print(f"✓ MW cafeína: {props_result['properties']['molecular_weight']:.2f}")

        # Submit
        status_code, submit_result = await client.submit_evaluation(cafeina_smiles)
        assert status_code == 202
        task_id = submit_result["task_id"]
        print(f"✓ Job encolado: {task_id}")

        # Esperar
        result = await wait_for_evaluation(client, task_id, timeout_sec=600)
        assert result["status"] in ["completed", "success"]
        print(f"✓ Evaluación completada: Score={result['result'].get('total_score', 'N/A')}")


@pytest.mark.asyncio
async def test_e2e_ligando_control():
    """
    Test E2E con ligando de control (serotonina 5-HT co-cristalizada).

    Para control, el flag is_control=True hace que el scoring ignore
    propiedades ADME/Drug-likeness y solo use afinidad de docking.
    """
    serotonin_smiles = "NCCc1c[nH]c2ccc(O)cc12"

    async with APIClient() as client:
        print("\n━━━ Test E2E: LIGANDO CONTROL (SEROTONINA) ━━━")

        # Submit con is_control=True
        status_code, submit_result = await client.submit_evaluation(
            serotonin_smiles, is_control=True
        )
        assert status_code == 202
        task_id = submit_result["task_id"]
        print(f"✓ Job control encolado: {task_id}")

        # Esperar
        result = await wait_for_evaluation(client, task_id, timeout_sec=600)
        assert result["status"] in ["completed", "success"]

        evaluation = result["result"]
        print(f"✓ Ligando control evaluado:")
        print(f"  - Afinidad: {evaluation.get('affinity_kcal', 'N/A')} kcal/mol")
        print(f"  - Score (solo afinidad): {evaluation.get('total_score', 'N/A')}")
        # Para ligando control, el score debe ser igual a affinity_score
        assert evaluation.get("total_score") == evaluation.get(
            "affinity_score"
        ), "Score control debe igualar score afinidad"


@pytest.mark.asyncio
async def test_invalid_smiles():
    """Test que un SMILES inválido es rechazado correctamente."""
    invalid_smiles = "CCCinvalid"

    async with APIClient() as client:
        print("\n━━━ Test: SMILES INVÁLIDO ━━━")

        status_code, result = await client.validate(invalid_smiles)
        assert status_code == 200  # No es HTTP error, es información estructurada
        assert result["is_valid"] is False
        print(f"✓ SMILES rechazado correctamente")
        print(f"  Errores: {result['errors']}")

        # Intentar propiedades con SMILES inválido debe fallar
        status_code, result = await client.properties(invalid_smiles)
        assert status_code == 422  # Unprocessable Entity
        print(f"✓ Propiedades correctamente rechazadas (422)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--timeout=600"])
