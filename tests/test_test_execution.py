"""Integration checks for bounded parallel defaults and the serial override."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


def _run_execution_probe(tmp_path, available_workers, *options):
    """Run real pytest against the repository config in an isolated directory."""
    (tmp_path / "conftest.py").write_text(
        'from pathlib import Path\n'
        'def pytest_sessionstart(session):\n'
        '    worker = getattr(session.config, "workerinput", {}).get("workerid", "master")\n'
        '    Path(__file__).with_name(f"started-{worker}.txt").write_text(worker)\n',
        encoding="utf-8",
    )
    probe = tmp_path / "test_probe.py"
    probe.write_text(
        'from pathlib import Path\n'
        'import pytest\n'
        '@pytest.mark.parametrize("index", range(8))\n'
        'def test_probe(index, worker_id):\n'
        '    Path(__file__).with_name(f"result-{index}.txt").write_text(worker_id)\n',
        encoding="utf-8",
    )
    env = os.environ.copy()
    for key in ("PYTEST_ADDOPTS", "PYTEST_XDIST_WORKER", "PYTEST_XDIST_WORKER_COUNT",
                "PYTEST_XDIST_TESTRUNUID"):
        env.pop(key, None)
    env["PYTEST_XDIST_AUTO_NUM_WORKERS"] = str(available_workers)
    config = Path(__file__).resolve().parents[1] / "pyproject.toml"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-c", str(config), "--confcutdir", str(tmp_path),
         str(probe), "-q", "--tb=short", "-p", "no:cov", *options],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "8 passed" in result.stdout
    results = list(tmp_path.glob("result-*.txt"))
    assert {p.name for p in results} == {f"result-{i}.txt" for i in range(8)}
    started = {p.read_text() for p in tmp_path.glob("started-*.txt")}
    executed = {p.read_text() for p in results}
    return started, executed


@pytest.mark.parametrize("available_workers, expected_workers", [(2, 2), (16, 4)])
def test_default_execution_uses_available_workers_with_a_resource_cap(tmp_path, available_workers, expected_workers):
    """Real workers start automatically, with a cap even on a larger machine."""
    started, executed = _run_execution_probe(tmp_path, available_workers)
    workers = {f"gw{i}" for i in range(expected_workers)}
    assert started == workers | {"master"}
    assert executed <= workers
    assert executed


def test_explicit_serial_override_executes_every_case_in_the_controller(tmp_path):
    """The documented -n 0 override keeps all cases and starts no workers."""
    started, executed = _run_execution_probe(tmp_path, 16, "-n", "0")
    assert started == executed == {"master"}
