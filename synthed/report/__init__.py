"""SynthEd report generation module.

Install optional report dependencies with ``pip install jinja2 plotly playwright``
and the browser with ``python -m playwright install chromium``. The package does
not currently define a ``report`` extra.
"""
from __future__ import annotations

_OPTIONAL_DEPS = ("jinja2", "playwright")

__all__: list[str] = []

try:
    from .generator import ReportGenerator  # noqa: F401
    __all__.append("ReportGenerator")
except ImportError as exc:
    # Only swallow missing optional deps; re-raise real bugs
    if any(dep in str(exc) for dep in _OPTIONAL_DEPS):
        pass
    else:
        raise
