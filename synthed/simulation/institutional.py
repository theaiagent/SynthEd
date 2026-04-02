"""Institution-level quality parameters for ODL simulation.

Provides :class:`InstitutionalConfig` (frozen dataclass) and the
:func:`scale_by` modulation helper used by theory modules.
"""
from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class InstitutionalConfig:
    """Institution-level quality parameters affecting all students.

    All parameters are floats in [0, 1] where 0.5 is the neutral default
    that reproduces current engine behaviour exactly (scale_by returns 1.0x).

    Frozen: use ``dataclasses.replace()`` for Sobol overrides.
    """

    instructional_design_quality: float = 0.5   # [inst] Kember _QUALITY_FACTOR
    teaching_presence_baseline: float = 0.5     # [inst] CoI state init (direct)
    support_services_quality: float = 0.5       # [inst] Gonzalez _RECOVERY_BASE
    technology_quality: float = 0.5             # [inst] Engine literacy floors
    curriculum_flexibility: float = 0.5         # [inst] Gonzalez _ASSIGNMENT_LOAD_WEIGHT (inverted)

    def __post_init__(self) -> None:
        for f in fields(self):
            val = getattr(self, f.name)
            if not isinstance(val, (int, float)):
                raise TypeError(f"{f.name} must be numeric, got {type(val).__name__}")
            if not 0.0 <= val <= 1.0:
                raise ValueError(
                    f"{f.name}={val} outside [0.0, 1.0]"
                )


def scale_by(
    constant: float,
    inst_param: float,
    low: float = 0.7,
    high: float = 1.3,
) -> float:
    """Scale a theory constant by an institutional parameter in [0, 1].

    At *inst_param* = 0.5 the return value equals *constant* exactly,
    preserving backward compatibility (0.7 + 0.6 * 0.5 = 1.0 in IEEE 754).

    Parameters
    ----------
    constant : float
        The class-level ``_UPPERCASE`` value to scale.
    inst_param : float
        Institutional parameter, 0.0 (worst) to 1.0 (best).
    low : float
        Multiplier applied when *inst_param* = 0.0. Default 0.7.
    high : float
        Multiplier applied when *inst_param* = 1.0. Default 1.3.

    Returns
    -------
    float
        ``constant * (low + (high - low) * inst_param)``
    """
    return constant * (low + (high - low) * inst_param)
