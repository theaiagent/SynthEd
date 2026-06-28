"""Picklable fake workers for exercising the Sobol parallel/retry path.

These live in their own importable module (not inside a ``test_*`` file) so
that ``ProcessPoolExecutor`` workers can unpickle them by qualified name when
the tests monkeypatch ``run_simulation_with_overrides``.
"""

from __future__ import annotations

import hashlib
import os
import time

# A first-sighting sample sleeps this long — must exceed the (test-shrunk)
# worker timeout so its future is still unfinished when FuturesTimeout fires.
_HANG_SECONDS = 5

# A structurally valid metrics dict (same keys the real worker returns).
VALID_METRICS = {
    "dropout_rate": 0.30,
    "mean_engagement": 0.50,
    "mean_gpa": 2.50,
    "std_engagement": 0.10,
    "pass_rate": 0.50,
    "distinction_rate": 0.10,
    "fail_rate": 0.20,
}


def always_failing_worker(overrides, n_students, seed, default_config, calibration_mode=True):
    """Always raise — used to verify fail-fast (the run must abort, not zero-fill)."""
    raise RuntimeError("deterministic worker failure")


def hang_first_then_succeed_worker(overrides, n_students, seed, default_config, calibration_mode=True):
    """Hang past the timeout the first time a sample is seen, then succeed.

    The first execution per sample creates an ``O_EXCL`` marker and sleeps long
    enough to exceed the (test-shrunk) worker timeout, leaving its future
    unfinished so the parallel pass raises ``FuturesTimeout``; later executions
    find the marker and return immediately. Verifies the timeout branch routes
    unfinished samples to isolated retry and recovers them.
    """
    key = hashlib.md5(repr(sorted(overrides.items())).encode()).hexdigest()
    marker = os.path.join(os.environ["SOBOL_FLAKY_DIR"], key)
    try:
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return dict(VALID_METRICS)
    os.close(fd)
    time.sleep(_HANG_SECONDS)
    return dict(VALID_METRICS)


def echo_first_param_worker(overrides, n_students, seed, default_config, calibration_mode=True):
    """Return valid metrics whose ``dropout_rate`` echoes the single override value.

    Lets a test assert ``outputs[i]`` maps to ``samples[i]`` (the future→index
    mapping must preserve order through the parallel pass).
    """
    metrics = dict(VALID_METRICS)
    (only_value,) = overrides.values()
    metrics["dropout_rate"] = float(only_value)
    return metrics


def die_on_first_sighting_worker(overrides, n_students, seed, default_config, calibration_mode=True):
    """Kill this worker process the first time a given sample is seen, then succeed.

    The first execution per sample atomically creates an ``O_EXCL`` marker and
    calls ``os._exit`` (abrupt death → breaks its ProcessPoolExecutor, the way a
    real worker crash does); any later execution finds the marker and returns
    valid metrics. This forces retries to recover from a *broken pool*, which is
    only possible if each retry runs on a fresh executor.

    The marker directory is passed via the ``SOBOL_FLAKY_DIR`` env var so it is
    visible to spawned worker processes.
    """
    key = hashlib.md5(repr(sorted(overrides.items())).encode()).hexdigest()
    marker = os.path.join(os.environ["SOBOL_FLAKY_DIR"], key)
    try:
        fd = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return dict(VALID_METRICS)
    os.close(fd)
    os._exit(1)
