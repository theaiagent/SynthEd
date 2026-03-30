"""Shared input validation utilities for SynthEd."""

from __future__ import annotations


def validate_range(value: float, lo: float, hi: float, name: str) -> None:
    """Raise ValueError if value is outside [lo, hi]."""
    if not lo <= value <= hi:
        raise ValueError(f"{name} must be between {lo} and {hi}, got {value}")


def validate_positive_int(value: int, name: str) -> None:
    """Raise ValueError if value is not a positive integer."""
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value}")


def validate_probability_distribution(dist: dict[str, float], name: str) -> None:
    """Raise ValueError if distribution values don't sum to ~1.0."""
    total = sum(dist.values())
    if abs(total - 1.0) > 0.01:
        raise ValueError(f"{name} must sum to 1.0, got {total:.4f}")
