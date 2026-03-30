"""Logging configuration for SynthEd."""

import logging
import sys


def configure_logging(level: int = logging.INFO, verbose: bool = False) -> None:
    """Configure SynthEd logging with sensible defaults."""
    effective_level = logging.DEBUG if verbose else level
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
        if effective_level <= logging.DEBUG
        else "%(message)s"
    ))
    root = logging.getLogger("synthed")
    root.setLevel(effective_level)
    if not root.handlers:
        root.addHandler(handler)
