"""TheoryModule Protocol and TheoryContext for phase-based dispatch.

Defines the structural protocol that theory modules implement and the
frozen context object passed to phase methods.

Theory modules implement whichever phase methods they participate in.
The engine iterates over discovered theories and calls only the methods
that exist (via ``hasattr`` checks).

Phase execution order:
    Phase 1 (per-student): on_individual_step
    Phase 2 (collective):  on_network_step (ctx.student is None)
    Phase 2 (per-student): on_post_peer_step
    Engagement:            handled inline in engine (not protocol-dispatched)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

import numpy as np

if TYPE_CHECKING:
    from ...agents.persona import StudentPersona
    from ..engine import InteractionRecord, SimulationState
    from ..engine_config import EngineConfig
    from ..environment import Course, ODLEnvironment
    from ..institutional import InstitutionalConfig
    from ..social_network import SocialNetwork


@dataclass(frozen=True, slots=True)
class TheoryContext:
    """Frozen context object passed to theory phase methods.

    Per-student fields (``student``, ``state``, ``records``) are ``None``
    during ``on_network_step`` which operates collectively on all students.

    Field usage by theory:
        student:        Tinto, Garrison, SDT, Gonzalez, Baulke, Epstein(peer), Bean
        state:          All theories
        week:           Tinto, Garrison, SDT, Gonzalez, Baulke
        context:        Tinto (week_context dict)
        records:        Tinto, Garrison, SDT, Gonzalez
        env:            Baulke, Moore
        rng:            Baulke, Epstein(network)
        inst:           Baulke, Gonzalez, Kember
        network:        Epstein (both phases)
        all_states:     Epstein (peer influence)
        week_records_by_student: Epstein (network formation)
        active_courses: Garrison
        cfg:            (reserved for P10)
        total_weeks:    Kember
        avg_td:         Kember, Baulke (pre-computed from Moore.average)
    """

    # Per-student (None during on_network_step)
    student: StudentPersona | None
    state: SimulationState | None
    records: list[InteractionRecord] | None

    # Always populated
    week: int
    context: dict[str, Any]
    env: ODLEnvironment
    rng: np.random.Generator
    inst: InstitutionalConfig
    network: SocialNetwork
    all_states: dict[str, SimulationState]
    week_records_by_student: dict[str, list[InteractionRecord]]
    active_courses: list[Course]
    cfg: EngineConfig
    total_weeks: int
    avg_td: float


class TheoryModule(Protocol):
    """Structural protocol for theory modules.

    Theories implement whichever phase methods they participate in.
    Unimplemented phases are skipped via ``hasattr`` checks.

    Each theory that participates in engagement composition should
    define ``_PHASE_ORDER: int`` for deterministic ordering.
    """

    def on_individual_step(self, ctx: TheoryContext) -> None:
        """Called per-student in Phase 1 (individual behavior)."""
        ...

    def on_network_step(self, ctx: TheoryContext) -> None:
        """Called once per week in Phase 2 (collective network update).

        ``ctx.student``, ``ctx.state``, and ``ctx.records`` are ``None``.
        Use ``ctx.week_records_by_student`` and ``ctx.network``.
        """
        ...

    def on_post_peer_step(self, ctx: TheoryContext) -> None:
        """Called per-student in Phase 2 (after peer influence)."""
        ...
