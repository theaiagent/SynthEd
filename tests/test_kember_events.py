"""Kember current-week missed events, persistent feedback and engine integration."""

from copy import deepcopy
from dataclasses import replace

import pytest

from synthed.agents.persona import StudentPersona
from synthed.simulation.engine import SimulationEngine
from synthed.simulation.environment import Course, ODLEnvironment
from synthed.simulation.social_network import SocialNetwork
from synthed.simulation.state import CommunityOfInquiryState, InteractionRecord, SimulationState
from synthed.simulation.theories.kember import KemberCostBenefit


def _fixture(seed=42):
    """Keep non-assignment inputs neutral so the event's effect is observable."""
    student = StudentPersona(employment_intensity=0.0, family_responsibility_level=0.0)
    state = SimulationState(student_id=student.id, courses_active=["A"],
                            missed_assignments_streak=3, perceived_cost_benefit=0.6,
                            coi_state=CommunityOfInquiryState(0.35, 0.35, 0.5))
    engine = SimulationEngine(ODLEnvironment(courses=[
        Course(id="A", name="A", assignment_weeks=[1, 2]),
    ]), seed=seed)
    engine.network = SocialNetwork()
    return student, state, engine


def _context(student, state, engine, week, records=None):
    """Use the real protocol context, neutralizing only transactional distance."""
    ctx = engine._make_ctx(student, state, records or [], week,
                          engine.env.get_week_context(week), {student.id: state}, {})
    return replace(ctx, avg_td=0.5)


@pytest.mark.parametrize("memory", [
    [], [{"week": 3, "event_type": "missed_assignment"}],
    [{"week": 5, "event_type": "missed_assignment"}],
    [{"week": 4, "event_type": "assignment"}],
])
def test_no_current_miss_preserves_past_cost_benefit(memory):
    """A stale streak must not charge another missed-event penalty in week four."""
    student, state, engine = _fixture()
    state.memory = deepcopy(memory)
    before_student = deepcopy(student)
    before_rng = deepcopy(engine.rng.bit_generator.state)
    delta = KemberCostBenefit().contribute_engagement_delta(_context(student, state, engine, 4))
    assert state.perceived_cost_benefit == pytest.approx(0.6)
    assert delta == pytest.approx(0.002)  # Existing 0.6 value still feeds engagement.
    assert state.memory == memory and state.missed_assignments_streak == 3
    assert student == before_student and engine.rng.bit_generator.state == before_rng


@pytest.mark.parametrize("miss_count", [1, 3])
def test_current_misses_charge_one_weekly_penalty(miss_count):
    """One eligible weekly update incurs one penalty, even with several misses."""
    student, state, engine = _fixture()
    state.memory = [{"week": 4, "event_type": "missed_assignment"} for _ in range(miss_count)]
    KemberCostBenefit().contribute_engagement_delta(_context(student, state, engine, 4))
    assert state.perceived_cost_benefit == pytest.approx(0.57)


@pytest.mark.parametrize("streak, expected", [(0, 0.6), (1, 0.6), (2, 0.57)])
def test_new_miss_retains_existing_streak_threshold(streak, expected):
    """A new miss is necessary but does not replace the existing streak threshold."""
    student, state, engine = _fixture()
    state.missed_assignments_streak = streak
    state.memory = [{"week": 4, "event_type": "missed_assignment"}]
    KemberCostBenefit().contribute_engagement_delta(_context(student, state, engine, 4))
    assert state.perceived_cost_benefit == pytest.approx(expected)


@pytest.mark.parametrize("kind", ["assignment_submit", "exam"])
def test_positive_graded_item_keeps_priority_over_missed_penalty(kind):
    """Existing graded-item precedence is preserved when the week also has misses."""
    student, state, engine = _fixture()
    state.memory = [{"week": 4, "event_type": "missed_assignment"}]
    records = [InteractionRecord(student.id, 4, "A", kind, quality_score=0.75)]
    KemberCostBenefit().contribute_engagement_delta(_context(student, state, engine, 4, records))
    assert state.perceived_cost_benefit == pytest.approx(0.61)


def test_stale_streak_keeps_opportunity_cost_and_feedback_active():
    """Suppressing the missed-event charge must not skip the whole Kember update."""
    student, state, engine = _fixture()
    student = replace(student, employment_intensity=1.0, financial_stress=1.0)
    state.memory = [{"week": 2, "event_type": "missed_assignment"}]
    delta = KemberCostBenefit().contribute_engagement_delta(_context(student, state, engine, 4))
    # Existing opportunity cost: 0.015 * (0.5 + 0.5 * 4/14).
    assert state.perceived_cost_benefit == pytest.approx(0.5903571428571428)
    assert delta == pytest.approx(0.001807142857142856)


@pytest.mark.parametrize("week, context, expected", [
    (None, {}, 0.6), (None, {"week": 4}, 0.57), (5, {"week": 4}, 0.6),
])
def test_recalculate_requires_a_known_matching_week(week, context, expected):
    """Explicit week wins; the context can supply it, but missing time cannot replay history."""
    student, state, _ = _fixture()
    state.memory = [{"week": 4, "event_type": "missed_assignment"}]
    KemberCostBenefit().recalculate(student, state, context, [], 0.5, week=week)
    assert state.perceived_cost_benefit == pytest.approx(expected)


@pytest.mark.parametrize("seed", [42, 7, 123])
def test_engine_miss_events_stop_charging_between_due_dates(seed):
    """Real assignment outcomes reach Kember; an empty following week keeps their state effect."""
    student, state, engine = _fixture(seed)
    state.missed_assignments_streak = 0
    state.perceived_cost_benefit = 0.5
    course = engine.env.courses[0]
    observed = []
    for week in (1, 2, 3, 4):
        # Zero engagement gives zero submission probability for every seed.
        records = engine._sim_assignment(student, state, course, 0.0, week)
        delta = engine.kember.contribute_engagement_delta(_context(student, state, engine, week, records))
        observed.append((state.perceived_cost_benefit, delta))
    assert [v for v, _ in observed] == pytest.approx([0.5, 0.47, 0.47, 0.47])
    assert [d for _, d in observed] == pytest.approx([0.0, -0.0006, -0.0006, -0.0006])
    assert state.n_total_assignments == 2 and state.missed_assignments_streak == 2
