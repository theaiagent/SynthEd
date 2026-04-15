"""SynthEd report generation module.

Requires optional dependencies: pip install synthedu[report]
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
