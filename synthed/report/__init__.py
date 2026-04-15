"""SynthEd report generation module.

Requires optional dependencies: pip install synthedu[report]
"""
try:
    from .generator import ReportGenerator
except ImportError:
    pass

__all__ = ["ReportGenerator"]
