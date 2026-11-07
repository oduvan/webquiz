"""Unit tests for the agent test harness checks (harness/checks.py).

They use small fake records only: no server, browser or AI agents.
"""

from harness.checks import (
    check_agent_alignment,
    check_expectations,
    check_time_accuracy,
    check_answer_times,
    check_live_stats,
    check_screen_scores,
    check_submits_match_rows,
    check_timeout_rows,
    check_unique_answers,
    parse_agent_report,
    parse_screen_score,
)


def row(user="u1", question="Q1?", selected="A", correct=True, time_taken=3.0):
    return {
        "user_id": user,
        "question": question,
        "selected_answer": selected,
        "is_correct": correct,
        "time_taken": time_taken,
    }


# ---- agent reports ----


def test_parse_agent_report_reads_step_lines_and_quotes():
    text = """Some intro the agent wrote.
STEP 1 | DID: open | SAW: "Математика"; "Ім'я користувача"
STEP 2 | DID: type Олена | SAW: "Олена"
step 3 | did: click 56 | saw: "✓ Правильна відповідь"
NOTES: the timer showed 0:28
"""
    steps = parse_agent_report(text)
    assert [s["step"] for s in steps] == [1, 2, 3]
    assert steps[0]["did"] == "open"
    assert steps[0]["quotes"] == ["Математика", "Ім'я користувача"]
    assert steps[2]["quotes"] == ["✓ Правильна відповідь"]


def test_agent_alignment_finds_wrong_quote_and_wrong_action():
    driver_steps = {
        1: {"cmd": "open", "arg": None, "screen": "Математика\nІм'я користувача"},
        2: {"cmd": "click", "arg": "56", "screen": "✓ Правильна відповідь\nПродовжити"},
    }
    agent_steps = [
        {"step": 1, "did": "open", "quotes": ["Математика"]},
        {"step": 2, "did": "click 54", "quotes": ["Неправильна відповідь"]},
        {"step": 9, "did": "look", "quotes": []},
    ]
    problems = check_agent_alignment(agent_steps, driver_steps)
    assert any("step 2" in p and "click 54" in p for p in problems)
    assert any("step 2" in p and "Неправильна відповідь" in p for p in problems)
    assert any("step 9" in p for p in problems)
    assert not any("step 1" in p for p in problems)


def test_agent_alignment_ignores_spaces_and_case_in_quotes():
    driver_steps = {1: {"cmd": "look", "arg": None, "screen": "⏱ Залишилось часу   0:28"}}
    assert check_agent_alignment([{"step": 1, "did": "look", "quotes": ["залишилось часу 0:28"]}], driver_steps) == []


# ---- server data ----


def test_unique_answers():
    assert check_unique_answers([row(), row(question="Q2?")]) == []
    assert check_unique_answers([row(), row(selected="B")])


def test_timeout_rows_must_be_failed():
    assert check_timeout_rows([row(selected="", correct=False)]) == []
    assert check_timeout_rows([row(selected="", correct=True)])


def test_answer_times_respect_limit_and_grace():
    limits = {"Q1?": 20, "Q2?": 0}
    rows = [
        row(question="Q1?", time_taken=24.0),  # inside the 5 s grace
        row(question="Q2?", time_taken=300.0),  # no limit
        row(question="Q1?", user="u2", selected="", correct=False, time_taken=40.0),  # timeout rows are skipped
    ]
    assert check_answer_times(rows, limits, grace=5) == []
    assert check_answer_times([row(question="Q1?", time_taken=27.5)], limits, grace=5)


def test_submits_match_rows():
    rows = [row(question="Q1?", correct=True), row(question="Q2?", selected="", correct=False)]
    submits = [
        {"user_id": "u1", "question": "Q1?", "status": 200, "response": {"is_correct": True}},
        {"user_id": "u1", "question": "Q2?", "status": 200, "response": {"timed_out": True}},
    ]
    assert check_submits_match_rows(submits, rows, allowed_without_submit=set()) == []

    # A stored row nobody sent, and not written by the background check
    extra = rows + [row(question="Q3?", selected="", correct=False)]
    assert check_submits_match_rows(submits, extra, allowed_without_submit=set())
    assert check_submits_match_rows(submits, extra, allowed_without_submit={("u1", "Q3?")}) == []

    # An accepted answer with no row (lost answer)
    assert check_submits_match_rows(
        submits + [{"user_id": "u1", "question": "Q4?", "status": 200, "response": {}}], rows, set()
    )

    # The screen was told "correct", the data says wrong
    wrong = [row(question="Q1?", correct=False), rows[1]]
    assert check_submits_match_rows(submits, wrong, allowed_without_submit=set())

    # The screen was told "time is up", the data has an answer
    answered = [rows[0], row(question="Q2?", selected="B", correct=False)]
    assert check_submits_match_rows(submits, answered, allowed_without_submit=set())


def test_parse_screen_score():
    assert parse_screen_score("Математика\nРезультат: 2/3 (67%)\nПитання") == (2, 3)
    assert parse_screen_score("Result: 5/5 (100%)") == (5, 5)
    assert parse_screen_score("Питання 2 з 3") is None


def test_screen_scores_match_rows():
    rows = [row(question="Q1?"), row(question="Q2?", correct=False), row(question="Q3?")]
    assert check_screen_scores({"u1": (2, 3)}, rows, total_questions=3) == []
    assert check_screen_scores({"u1": (3, 3)}, rows, total_questions=3)


def test_live_stats_final_states_match_rows():
    rows = [row(question="Q1?"), row(question="Q2?", correct=False), row(question="Q3?", selected="", correct=False)]
    states = {("u1", "Q1?"): "ok", ("u1", "Q2?"): "fail", ("u1", "Q3?"): "timeout"}
    assert check_live_stats(states, rows) == []
    assert check_live_stats({**states, ("u1", "Q3?"): "fail"}, rows)
    assert check_live_stats({**states, ("u1", "Q2?"): "think"}, rows)


def test_parse_agent_report_ignores_punctuation_left_by_nested_quotes():
    line = (
        'STEP 13 | DID: type "6" | SAW: "TYPE INTO: [textarea] Введіть відповідь... = "6""; "✍️ Введіть вашу відповідь:"'
    )
    quotes = parse_agent_report(line)[0]["quotes"]
    assert ";" not in [q.strip() for q in quotes]
    assert "✍️ Введіть вашу відповідь:" in quotes


def test_expectations_compare_the_planned_outcome_with_the_stored_answer():
    question_text = {1: "Q1?", 2: "Q2?", 3: "Q3?"}
    user_of = {"e02": "u2"}
    rows = [
        row(user="u2", question="Q1?", correct=True),
        row(user="u2", question="Q2?", selected="", correct=False),
    ]
    good = {"e02": {1: "correct", 2: "timeout", 3: "missing"}}
    assert check_expectations(good, rows, user_of, question_text) == []

    problems = check_expectations({"e02": {1: "timeout", 2: "wrong", 3: "correct"}}, rows, user_of, question_text)
    assert len(problems) == 3
    assert any("Q1?" in p and "timeout" in p and "correct" in p for p in problems)

    assert check_expectations({"nobody": {1: "correct"}}, rows, user_of, question_text)


def test_time_accuracy_compares_server_time_with_browser_time():
    rows = [
        row(question="Q1?", time_taken=5.2),
        row(question="Q2?", time_taken=9.0),
        row(question="Q3?", selected="", correct=False, time_taken=30.0),  # timeouts are skipped
    ]
    measured = {("u1", "Q1?"): 5.0, ("u1", "Q2?"): 6.0, ("u1", "Q3?"): 3.0}
    problems = check_time_accuracy(rows, measured, tolerance=1.5)
    assert len(problems) == 1
    assert "Q2?" in problems[0] and "9.0" in problems[0] and "6.0" in problems[0]
    assert check_time_accuracy(rows[:1], measured, tolerance=1.5) == []
