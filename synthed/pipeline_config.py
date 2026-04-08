"""Frozen PipelineConfig dataclass for SynthEdPipeline configuration.

Groups 16 serializable constructor parameters into a single immutable
config object.  Non-serializable items (``confirm_callback``) and
internal flags (``_calibration_mode``) remain as direct constructor args.

Usage::

    from synthed.pipeline_config import PipelineConfig
    config = PipelineConfig(seed=123, n_semesters=2)
    pipeline = SynthEdPipeline(config=config)
"""
from __future__ import annotations

import dataclasses
import enum
import types
from dataclasses import dataclass, field, fields
from typing import Any, Union

from .agents.persona import PersonaConfig
from .simulation.engine_config import EngineConfig
from .simulation.environment import Course, ODLEnvironment
from .simulation.grading import GradingConfig
from .simulation.institutional import InstitutionalConfig
from .validation import ReferenceStatistics


_DEFAULT_COST_THRESHOLD_USD: float = 1.0

# Maps field name -> nested dataclass type for from_dict() reconstruction.
_NESTED_FIELDS: dict[str, type] = {
    "persona_config": PersonaConfig,
    "environment": ODLEnvironment,
    "institutional_config": InstitutionalConfig,
    "grading_config": GradingConfig,
    "engine_config": EngineConfig,
    "reference_stats": ReferenceStatistics,
}


def _coerce_field_types(cls: type, raw: dict) -> dict:
    """Coerce serialized values back to their declared field types.

    Handles tuple fields (serialized as lists), enum fields (serialized
    as their value), and nested Course lists for ODLEnvironment.
    """
    import enum as _enum
    import typing

    hints = typing.get_type_hints(cls)
    coerced = dict(raw)
    for name, val in raw.items():
        if name not in hints or val is None:
            continue
        hint = hints[name]
        # Unwrap Optional / Union with None (e.g. tuple[float,float] | None)
        args = getattr(hint, "__args__", None)
        origin = getattr(hint, "__origin__", None)
        if origin is Union or isinstance(hint, types.UnionType) or (args and type(None) in args):
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                hint = non_none[0]
                origin = getattr(hint, "__origin__", None)
                args = getattr(hint, "__args__", None)
        # tuple fields: list -> tuple
        if origin is tuple and isinstance(val, list):
            coerced[name] = tuple(val)
        elif hint is tuple and isinstance(val, list):
            coerced[name] = tuple(val)
        # enum fields: int/str -> Enum
        elif isinstance(hint, type) and issubclass(hint, _enum.Enum):
            coerced[name] = hint(val)
    return coerced


def _reconstruct_nested(cls: type, raw: dict) -> Any:
    """Reconstruct a nested dataclass from a raw dict.

    Handles ODLEnvironment specially because its ``courses`` field
    is ``list[Course]`` which needs element-wise reconstruction.
    Coerces tuples and enums back to their declared types.
    """
    coerced = _coerce_field_types(cls, raw)
    if cls is ODLEnvironment and "courses" in coerced:
        courses = [Course(**_coerce_field_types(Course, c)) for c in coerced["courses"]]
        remaining = {k: v for k, v in coerced.items() if k != "courses"}
        return cls(courses=courses, **remaining)
    return cls(**coerced)


@dataclass(frozen=True)
class PipelineConfig:
    """Frozen configuration for :class:`SynthEdPipeline`.

    All 16 fields correspond to the former constructor parameters of
    ``SynthEdPipeline``.  At default values the pipeline behaves
    identically to the pre-PipelineConfig API.

    Use ``dataclasses.replace()`` for overrides::

        new_cfg = replace(config, seed=99, n_semesters=3)
    """

    # Domain configs (nested frozen dataclasses)
    persona_config: PersonaConfig = field(default_factory=PersonaConfig)
    environment: ODLEnvironment = field(default_factory=ODLEnvironment)
    institutional_config: InstitutionalConfig = field(
        default_factory=InstitutionalConfig,
    )
    grading_config: GradingConfig = field(default_factory=GradingConfig)
    engine_config: EngineConfig = field(default_factory=EngineConfig)
    reference_stats: ReferenceStatistics = field(
        default_factory=ReferenceStatistics,
    )

    # Simulation scalars
    seed: int = 42
    n_semesters: int = 1
    carry_over_config: Any | None = None
    target_dropout_range: tuple[float, float] | None = None

    # Output
    output_dir: str | None = "./output"
    export_oulad: bool = False

    # LLM
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None
    use_llm: bool = False

    # Cost
    cost_threshold: float = _DEFAULT_COST_THRESHOLD_USD

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError(f"seed must be >= 0, got {self.seed}")
        if self.n_semesters < 1:
            raise ValueError(
                f"n_semesters must be >= 1, got {self.n_semesters}",
            )
        if self.cost_threshold < 0:
            raise ValueError(
                f"cost_threshold must be >= 0, got {self.cost_threshold}",
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict.

        Nested dataclasses are converted recursively with enum support.
        """

        def _serialize(obj: Any) -> Any:
            if obj is None:
                return None
            if isinstance(obj, enum.Enum):
                return obj.value
            if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
                return {
                    k: _serialize(v)
                    for k, v in dataclasses.asdict(obj).items()
                }
            if isinstance(obj, dict):
                return {k: _serialize(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_serialize(v) for v in obj]
            return obj

        result: dict[str, Any] = {}
        for f in fields(self):
            result[f.name] = _serialize(getattr(self, f.name))
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineConfig:
        """Reconstruct from a dict produced by :meth:`to_dict`.

        Nested dataclass fields are reconstructed using the
        ``_NESTED_FIELDS`` registry.
        """
        kwargs: dict[str, Any] = {}
        for key, val in data.items():
            if key in _NESTED_FIELDS and isinstance(val, dict):
                kwargs[key] = _reconstruct_nested(_NESTED_FIELDS[key], val)
            elif key == "target_dropout_range" and isinstance(val, list):
                kwargs[key] = tuple(val)
            else:
                kwargs[key] = val
        return cls(**kwargs)
