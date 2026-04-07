from __future__ import annotations

import pytest
from dataclasses import fields

from synthed.analysis.pareto_utils import (
    ParetoSolution, ParetoResult, find_knee_point,
)


def _sol(dropout_err: float, gpa_err: float, **kw) -> ParetoSolution:
    return ParetoSolution(
        params=kw.get("params", {}),
        dropout_error=dropout_err,
        gpa_error=gpa_err,
        engagement_error=kw.get("engagement_error", 0.0),
        achieved_dropout=kw.get("achieved_dropout", 0.3),
        achieved_gpa=kw.get("achieved_gpa", 2.5),
        achieved_engagement=kw.get("achieved_engagement", 0.5),
    )


class TestParetoSolution:
    def test_frozen(self):
        sol = _sol(0.1, 0.2)
        with pytest.raises(AttributeError):
            sol.dropout_error = 0.5

    def test_fields_present(self):
        sol = _sol(0.1, 0.2)
        names = {f.name for f in fields(sol)}
        assert names == {
            "params", "dropout_error", "gpa_error", "engagement_error",
            "achieved_dropout", "achieved_gpa", "achieved_engagement",
        }


class TestParetoResult:
    def test_frozen(self):
        sol = _sol(0.1, 0.2)
        result = ParetoResult(
            profile_name="test",
            pareto_front=(sol,),
            knee_point=sol,
            n_evaluations=100,
            parameter_names=("engine._X",),
        )
        with pytest.raises(AttributeError):
            result.profile_name = "other"

    def test_validation_fields_default_none(self):
        sol = _sol(0.1, 0.2)
        result = ParetoResult(
            profile_name="test",
            pareto_front=(sol,),
            knee_point=sol,
            n_evaluations=100,
            parameter_names=("engine._X",),
        )
        assert result.validation_dropout_mean is None
        assert result.validation_gpa_mean is None
        assert result.validation_seeds == ()


class TestFindKneePoint:
    def test_empty_front_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            find_knee_point(())

    def test_single_solution(self):
        sol = _sol(0.1, 0.2)
        assert find_knee_point((sol,)) is sol

    def test_two_solutions_returns_first(self):
        s1, s2 = _sol(0.1, 0.5), _sol(0.5, 0.1)
        assert find_knee_point((s1, s2)) is s1

    def test_three_solutions_finds_elbow(self):
        s1 = _sol(0.0, 1.0)
        s2 = _sol(0.3, 0.3)
        s3 = _sol(1.0, 0.0)
        knee = find_knee_point((s1, s2, s3))
        assert knee.dropout_error == pytest.approx(0.3)
        assert knee.gpa_error == pytest.approx(0.3)

    def test_unsorted_front_still_finds_correct_knee(self):
        s1 = _sol(0.5, 0.3)
        s2 = _sol(0.9, 0.1)
        s3 = _sol(0.1, 0.9)
        knee = find_knee_point((s1, s2, s3))
        assert knee.dropout_error == pytest.approx(0.5)

    def test_collinear_points_returns_first_sorted(self):
        s1 = _sol(0.0, 1.0)
        s2 = _sol(0.5, 0.5)
        s3 = _sol(1.0, 0.0)
        knee = find_knee_point((s1, s2, s3))
        assert knee.dropout_error == pytest.approx(0.0)

