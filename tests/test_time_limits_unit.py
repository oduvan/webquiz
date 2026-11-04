"""Unit tests for webquiz.time_limits (reading and checking the time_limit setting)."""

from webquiz.time_limits import (
    TimeLimitSettings,
    is_empty_answer,
    parse_time_limit,
    question_limits,
    validate_time_limits,
)


def make_question(**extra):
    return {"question": "Q?", "options": ["A", "B"], "correct_answer": 0, **extra}


def test_question_limits_follow_spec_table():
    questions = [
        dict(make_question(), id=1),
        dict(make_question(time_limit=20), id=2),
        dict(make_question(time_limit=0), id=3),
    ]
    assert question_limits(TimeLimitSettings(), questions) == {1: 0, 2: 0, 3: 0}
    assert question_limits(TimeLimitSettings("per_question", 60), questions) == {1: 60, 2: 20, 3: 0}
    assert question_limits(TimeLimitSettings("per_question", 0), questions) == {1: 0, 2: 20, 3: 0}
    assert question_limits(TimeLimitSettings("whole_quiz", 900), questions) == {1: 0, 2: 0, 3: 0}


def test_malformed_question_value_uses_default():
    questions = [dict(make_question(time_limit="x"), id=1)]
    assert question_limits(TimeLimitSettings("per_question", 60), questions) == {1: 60}


def test_parse_time_limit():
    assert parse_time_limit({"time_limit": {"whole_quiz": 900}}) == (TimeLimitSettings("whole_quiz", 900), None)
    assert parse_time_limit({"time_limit": {"per_question": 30}}) == (TimeLimitSettings("per_question", 30), None)
    assert parse_time_limit({}) == (TimeLimitSettings(), None)
    settings, warning = parse_time_limit({"time_limit": {"per_question": 5, "whole_quiz": 9}})
    assert settings == TimeLimitSettings()
    assert warning


def test_validate_time_limits_accepts_good_values():
    assert validate_time_limits({"time_limit": {"per_question": 30}, "questions": [make_question(time_limit=0)]}) == []
    assert validate_time_limits({"time_limit": {"whole_quiz": 0}, "questions": [make_question()]}) == []
    # A question time_limit without a quiz time_limit is allowed (and ignored when the quiz runs)
    assert validate_time_limits({"questions": [make_question(time_limit=10)]}) == []


def test_validate_time_limits_rejects_bad_quiz_values():
    bad_values = [
        30,
        {},
        {"per_question": 1, "whole_quiz": 1},
        {"minutes": 1},
        {"per_question": -1},
        {"whole_quiz": 1.5},
        {"per_question": True},
        {"per_question": "60"},
    ]
    for value in bad_values:
        errors = validate_time_limits({"time_limit": value, "questions": [make_question()]})
        assert errors, value
        assert all("time_limit" in error for error in errors), errors


def test_validate_time_limits_rejects_bad_question_values():
    for value in (-5, 2.5, False, "10"):
        errors = validate_time_limits({"questions": [make_question(), make_question(time_limit=value)]})
        assert any("Question 2" in error and "time_limit" in error for error in errors), (value, errors)


def test_is_empty_answer():
    assert all(is_empty_answer(value) for value in (None, "", "   ", []))
    assert not any(is_empty_answer(value) for value in (0, [0], "a"))
