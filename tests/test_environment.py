"""Tests for ODLEnvironment."""

from synthed.simulation.environment import ODLEnvironment


class TestODLEnvironment:
    def test_default_courses_created(self):
        env = ODLEnvironment()
        assert len(env.courses) == 4

    def test_week_context_exam_weeks(self):
        env = ODLEnvironment()
        ctx_7 = env.get_week_context(7)
        assert ctx_7["is_exam_week"] is True  # midterm week
        ctx_14 = env.get_week_context(14)
        assert ctx_14["is_exam_week"] is True  # final week
        ctx_5 = env.get_week_context(5)
        assert ctx_5["is_exam_week"] is False

    def test_positive_events_created(self):
        env = ODLEnvironment()
        assert len(env.positive_events) > 0

    def test_get_course_by_id(self):
        env = ODLEnvironment()
        course = env.get_course_by_id("CS101")
        assert course is not None
        assert course.name == "Introduction to Computer Science"
        assert env.get_course_by_id("NONEXIST") is None
