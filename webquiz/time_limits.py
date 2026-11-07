"""Time limits for quizzes.

A quiz can limit time in one of two modes:

- ``per_question``: a default number of seconds for every question.
  A question can set its own ``time_limit``.
- ``whole_quiz``: one number of seconds for the whole quiz.
  Question values are ignored in this mode.

All values are whole seconds, and 0 always means "no limit".
This module only reads and checks the settings. The server keeps the clocks.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

MODES = ("per_question", "whole_quiz")

DEFAULT_GRACE_SECONDS = 5.0
DEFAULT_CHECK_INTERVAL_SECONDS = 1.0


@dataclass(frozen=True)
class TimeLimitSettings:
    """Quiz-level time limit: mode is "none", "per_question" or "whole_quiz"."""

    mode: str = "none"
    seconds: int = 0


def is_whole_seconds(value) -> bool:
    """True for a whole number that is 0 or more. True/False do not count as numbers here."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _quiz_level_errors(time_limit) -> List[str]:
    """Return the problems with the quiz-level time_limit value."""
    if not isinstance(time_limit, dict) or len(time_limit) == 0:
        return ["'time_limit' must have exactly one of 'per_question' or 'whole_quiz'"]

    errors = []
    unknown_keys = [key for key in time_limit if key not in MODES]
    for key in unknown_keys:
        errors.append(f"'time_limit' has an unknown key: '{key}'")

    known_keys = [key for key in time_limit if key in MODES]
    if len(known_keys) > 1:
        errors.append("'time_limit' must have exactly one of 'per_question' or 'whole_quiz'")
    for key in known_keys:
        if not is_whole_seconds(time_limit[key]):
            errors.append(f"'time_limit.{key}' must be a whole number of seconds (0 or more)")

    if not known_keys and not errors:
        errors.append("'time_limit' must have exactly one of 'per_question' or 'whole_quiz'")
    return errors


def validate_time_limits(data: dict) -> List[str]:
    """Check the quiz-level and per-question time_limit values before a quiz is saved."""
    errors = []
    if "time_limit" in data:
        errors.extend(_quiz_level_errors(data["time_limit"]))

    questions = data.get("questions")
    if isinstance(questions, list):
        for index, question in enumerate(questions):
            if isinstance(question, dict) and "time_limit" in question:
                if not is_whole_seconds(question["time_limit"]):
                    errors.append(f"Question {index + 1} 'time_limit' must be a whole number of seconds (0 or more)")
    return errors


def parse_time_limit(data: dict) -> Tuple[TimeLimitSettings, Optional[str]]:
    """Read the quiz-level time_limit from loaded quiz data.

    Loading a quiz does not run the save checks. A malformed value means
    "no time limits", and the second item of the result is a warning for the log.
    """
    if "time_limit" not in data:
        return TimeLimitSettings(), None

    errors = _quiz_level_errors(data["time_limit"])
    if errors:
        return TimeLimitSettings(), "Ignoring malformed time_limit, quiz runs without time limits: " + "; ".join(errors)

    mode, seconds = next(iter(data["time_limit"].items()))
    return TimeLimitSettings(mode, seconds), None


def question_limits(settings: TimeLimitSettings, questions: List[dict]) -> Dict[int, int]:
    """Return the effective per-question limit in seconds for every question id (0 = no limit).

    Only per_question mode gives questions their own limits. A malformed
    question value counts as "not set" and uses the quiz default.
    """
    limits = {}
    for question in questions:
        limit = 0
        if settings.mode == "per_question":
            own_value = question.get("time_limit")
            limit = own_value if is_whole_seconds(own_value) else settings.seconds
        limits[question["id"]] = limit
    return limits


def is_empty_answer(selected_answer) -> bool:
    """True when no answer was given: None, an empty or blank string, or an empty list."""
    if selected_answer is None:
        return True
    if isinstance(selected_answer, str):
        return selected_answer.strip() == ""
    if isinstance(selected_answer, list):
        return len(selected_answer) == 0
    return False


def _float_from_env(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def grace_seconds() -> float:
    """Extra seconds an answer may arrive after the limit and still count (tests can shorten it)."""
    return _float_from_env("WEBQUIZ_TIME_LIMIT_GRACE_SECONDS", DEFAULT_GRACE_SECONDS)


def check_interval_seconds() -> float:
    """How often the server checks for timed-out students (tests can shorten it)."""
    return _float_from_env("WEBQUIZ_TIME_LIMIT_CHECK_INTERVAL", DEFAULT_CHECK_INTERVAL_SECONDS)
