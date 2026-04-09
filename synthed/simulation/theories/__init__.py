"""Theory-specific modules extracted from SimulationEngine."""
from __future__ import annotations

from .tinto import TintoIntegration
from .bean_metzner import BeanMetznerPressure
from .kember import KemberCostBenefit
from .baulke import BaulkeDropoutPhase
from .garrison_coi import GarrisonCoI
from .moore_td import MooreTransactionalDistance
from .epstein_axtell import EpsteinAxtellPeerInfluence
from .rovai import RovaiPersistence
from .sdt_motivation import SDTMotivationDynamics, SDTNeedSatisfaction
from .positive_events import PositiveEventHandler
from .academic_exhaustion import GonzalezExhaustion, ExhaustionState
from .unavoidable_withdrawal import UnavoidableWithdrawal
from .protocol import TheoryContext, TheoryModule

__all__ = [
    "TintoIntegration",
    "BeanMetznerPressure",
    "KemberCostBenefit",
    "BaulkeDropoutPhase",
    "GarrisonCoI",
    "MooreTransactionalDistance",
    "EpsteinAxtellPeerInfluence",
    "RovaiPersistence",
    "SDTMotivationDynamics",
    "SDTNeedSatisfaction",
    "PositiveEventHandler",
    "GonzalezExhaustion",
    "ExhaustionState",
    "UnavoidableWithdrawal",
    "TheoryContext",
    "TheoryModule",
    "discover_theories",
]

# Classes excluded from auto-discovery (special lifecycle or data-only).
_EXCLUDED = frozenset({
    "TheoryContext", "TheoryModule", "SDTNeedSatisfaction",
    "ExhaustionState", "UnavoidableWithdrawal", "PositiveEventHandler",
})

_PHASE_METHODS = ("on_individual_step", "on_network_step", "on_post_peer_step")


def discover_theories() -> list[type]:
    """Discover theory classes that implement at least one protocol phase method.

    Returns classes sorted by module name for deterministic ordering.
    Excludes: data classes, special-lifecycle modules, protocol types.
    """
    import importlib
    import pkgutil

    theories: list[type] = []
    package = importlib.import_module(__name__)
    for importer, modname, _ispkg in pkgutil.iter_modules(package.__path__):
        if modname == "protocol":
            continue
        mod = importlib.import_module(f"{__name__}.{modname}")
        for attr_name in dir(mod):
            if attr_name.startswith("_") or attr_name in _EXCLUDED:
                continue
            obj = getattr(mod, attr_name)
            if isinstance(obj, type) and any(hasattr(obj, m) for m in _PHASE_METHODS):
                if obj not in theories:
                    theories.append(obj)
    return sorted(
        theories,
        key=lambda c: (getattr(c, "_PHASE_ORDER", 10_000), c.__module__, c.__name__),
    )
