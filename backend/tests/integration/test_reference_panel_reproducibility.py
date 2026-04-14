import json
import os
from pathlib import Path

import pytest


pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.mark.skipif(
    os.getenv("RUN_DOCKING_BENCHMARK_TESTS", "0") != "1",
    reason="Set RUN_DOCKING_BENCHMARK_TESTS=1 to run docking reproducibility benchmark",
)
def test_reference_panel_benchmark_deterministic():
    from scripts.benchmark_reference_panel import _setup_env_defaults, run_benchmark
    import asyncio

    _setup_env_defaults()
    output = Path("artifacts") / "benchmark_reference_panel_test.json"
    report = asyncio.run(run_benchmark(repeats=2, output_path=output))

    for molecule_name, summary in report["summary"].items():
        assert summary["deterministic_with_fixed_seed"], molecule_name
        assert summary["all_same_seed"], molecule_name
        assert summary["parsing_sources"], molecule_name

    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["benchmark"] == "moldesign_reference_panel"
