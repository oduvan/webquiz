# Quiz Time Limits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a quiz limit the time per question or for the whole quiz. Store a timed-out question as an empty, failed answer, and show it clearly to students and in live stats.

**Architecture:** The rules for reading and checking `time_limit` live in a new small module, `webquiz/time_limits.py`, made of pure functions. The server keeps clocks per student. One shared method stores both normal answers and timeouts. A background task runs every second and writes timeouts for students whose page went quiet. The student page shows countdowns based on the remaining time that the server sends back from `question-start`.

**Tech Stack:** Python 3.9+, aiohttp, PyYAML, vanilla JS/HTML, pytest + pytest-xdist, Selenium (already used in `tests/`).

**Spec:** `docs/superpowers/specs/2026-11-04-quiz-time-limits-design.md`. Read it first. This plan does not repeat its reasons.

## Global Constraints

- All values are whole seconds, and `0` always means "no limit".
- Grace is `5` seconds, read from env `WEBQUIZ_TIME_LIMIT_GRACE_SECONDS` (float, default `5`).
- Background check interval is `1` second, read from env `WEBQUIZ_TIME_LIMIT_CHECK_INTERVAL` (float, default `1`). Neither env var is documented for users.
- The answers CSV columns do not change. A timed-out row has an empty `selected_answer` and `is_correct` `False`.
- The code must work on Python 3.9: no `match`, and no `X | Y` type hints.
- Format with black, line length 120 (`pyproject.toml`).
- Run every Python command inside the venv: `source venv/bin/activate && ...`.
- Student-facing strings go in `webquiz/translations.py`, in both `uk` and `en`. Admin editor labels are in Ukrainian, like the rest of `admin.html`.
- Mobile: new UI must work at ≤768px with no horizontal scroll.
- Every task updates `CLAUDE.md`, `README.md` and `docs/en` + `docs/uk` (kept in sync) for what it adds. Use plain, simple language in docs, comments and commit messages.
- Commit messages end with:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_018yZA3xZPtSUHtrPB61f8ij
  ```

## Review Focus

1. **Page reload in the middle of a limited question.** The countdown must continue from the server's remaining time, not start again from the full limit. Tests: Task 2 (repeated `question-start` returns less time) and Task 5 (Selenium reload).
2. **Randomized order (`randomize_questions: true`).** The whole-quiz end and the background check must use the student's `question_order`, and the order check must not block a stored timeout. Tests: Task 3 (retry after timeout in a randomized quiz) and Task 4 (whole-quiz end in a randomized quiz).
3. **Approval on (`registration.approve: true`).** The first question's clock and the whole-quiz clock start at `question-start`, not at approval. Test: Task 2.
4. **`show_answers_on_completion: true`.** Timed-out answers count toward completion, so the class is not blocked by a student whose whole-quiz time ran out. Test: Task 4.
5. **Quiz switch or restart while clocks run.** The background check must not touch students from the old quiz or crash. Test: Task 4.

---

### Task 1: `time_limit` format, checks on save, unite

**Files:**
- Create: `webquiz/time_limits.py`
- Modify: `webquiz/server.py`: `_validate_quiz_data` (around line 3078) and `optional_fields` in `admin_unite_quizzes` (around line 2994)
- Test: `tests/test_time_limits_unit.py` (new), `tests/test_time_limits_validation.py` (new)
- Docs: `docs/en/050_quiz_format.md`, `docs/uk/050_quiz_format.md` (new `time_limit` section with the spec's table and both YAML examples), `README.md` (quiz options), `CLAUDE.md` (config options list and a "Quiz time limits" technical decision line)

**Interfaces:**
- Produces, in `webquiz/time_limits.py`:
  - `@dataclass(frozen=True) class TimeLimitSettings: mode: str = "none"; seconds: int = 0`. `mode` is one of `"none"`, `"per_question"` or `"whole_quiz"`.
  - `def is_whole_seconds(value) -> bool`: true for an `int` that is not a `bool` and is `>= 0`.
  - `def validate_time_limits(data: dict) -> List[str]`: error messages for the quiz level and every question.
  - `def parse_time_limit(data: dict) -> Tuple[TimeLimitSettings, Optional[str]]`: returns the settings and a warning text when `time_limit` is malformed (then the settings are `TimeLimitSettings()`).
  - `def question_limits(settings: TimeLimitSettings, questions: List[dict]) -> Dict[int, int]`: effective seconds per question `id` (0 = none). In `whole_quiz` and `none` modes, every value is 0. A malformed question value counts as "not set" and uses the default.
  - `def is_empty_answer(selected_answer) -> bool`: true for `None`, a string that is empty after `strip()`, or an empty list.
  - `def grace_seconds() -> float` and `def check_interval_seconds() -> float`: read the env vars from Global Constraints.

- [ ] **Step 1: Write the failing unit tests** in `tests/test_time_limits_unit.py`

```python
from webquiz.time_limits import (TimeLimitSettings, validate_time_limits, parse_time_limit,
                                 question_limits, is_empty_answer)

Q = lambda **kw: {"question": "Q?", "options": ["A", "B"], "correct_answer": 0, **kw}

def test_question_limits_follow_spec_table():
    qs = [dict(Q(), id=1), dict(Q(time_limit=20), id=2), dict(Q(time_limit=0), id=3)]
    assert question_limits(TimeLimitSettings(), qs) == {1: 0, 2: 0, 3: 0}
    assert question_limits(TimeLimitSettings("per_question", 60), qs) == {1: 60, 2: 20, 3: 0}
    assert question_limits(TimeLimitSettings("per_question", 0), qs) == {1: 0, 2: 20, 3: 0}
    assert question_limits(TimeLimitSettings("whole_quiz", 900), qs) == {1: 0, 2: 0, 3: 0}

def test_malformed_question_value_uses_default():
    assert question_limits(TimeLimitSettings("per_question", 60), [dict(Q(time_limit="x"), id=1)]) == {1: 60}

def test_parse_time_limit():
    assert parse_time_limit({"time_limit": {"whole_quiz": 900}}) == (TimeLimitSettings("whole_quiz", 900), None)
    assert parse_time_limit({}) == (TimeLimitSettings(), None)
    settings, warning = parse_time_limit({"time_limit": {"per_question": 5, "whole_quiz": 9}})
    assert settings == TimeLimitSettings() and warning

def test_validate_time_limits_errors():
    ok = {"time_limit": {"per_question": 30}, "questions": [Q(time_limit=0)]}
    assert validate_time_limits(ok) == []
    assert validate_time_limits({"questions": [Q(time_limit=10)]}) == []  # allowed, ignored
    bad = [{"time_limit": 30}, {"time_limit": {}}, {"time_limit": {"per_question": 1, "whole_quiz": 1}},
           {"time_limit": {"minutes": 1}}, {"time_limit": {"per_question": -1}},
           {"time_limit": {"whole_quiz": 1.5}}, {"time_limit": {"per_question": True}}]
    for data in bad:
        assert validate_time_limits({**data, "questions": [Q()]}), data
    assert any("Question 1" in e for e in validate_time_limits({"questions": [Q(time_limit=-5)]}))

def test_is_empty_answer():
    assert all(is_empty_answer(v) for v in (None, "", "   ", []))
    assert not any(is_empty_answer(v) for v in (0, [0], "a"))
```

- [ ] **Step 2: Run them and check that they fail**

Run: `source venv/bin/activate && python -m pytest tests/test_time_limits_unit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webquiz.time_limits'`

- [ ] **Step 3: Implement `webquiz/time_limits.py`** with the interfaces above. Use these error texts:
  - `"'time_limit' must have exactly one of 'per_question' or 'whole_quiz'"` (for a non-mapping, an empty mapping, or both keys);
  - `"'time_limit' has an unknown key: '<key>'"`;
  - `"'time_limit.<key>' must be a whole number of seconds (0 or more)"`;
  - `"Question <n> 'time_limit' must be a whole number of seconds (0 or more)"`, where `<n>` is 1-based.

- [ ] **Step 4: Run the unit tests and check that they pass.** Same command. Expected: PASS.

- [ ] **Step 5: Write the failing integration tests** in `tests/test_time_limits_validation.py`. Follow the pattern in `tests/test_quiz_validation_edge_cases.py` (`POST /api/admin/validate-quiz` with `{"content": yaml}`).
  - `test_validate_quiz_rejects_both_time_limit_modes`: `valid` is `False`, and an error contains `"time_limit"`.
  - `test_validate_quiz_rejects_negative_question_time_limit`: an error contains `"Question 1"` and `"time_limit"`.
  - `test_validate_quiz_accepts_question_time_limit_without_quiz_time_limit`: `valid` is `True`.
  - `test_unite_copies_time_limit_from_first_quiz`: follow `tests/test_admin_unite_quizzes.py`. The first quiz has `time_limit: {per_question: 30}` and a question with `time_limit: 10`. The united file has `time_limit == {"per_question": 30}` and `questions[0]["time_limit"] == 10`.

- [ ] **Step 6: Run them and check that they fail**

Run: `source venv/bin/activate && python -m pytest tests/test_time_limits_validation.py -v -n 4`
Expected: FAIL. The rejection tests get `valid: True`, and the unite test hits a `KeyError` on `time_limit`.

- [ ] **Step 7: Wire it in.** In `_validate_quiz_data`, add `errors.extend(validate_time_limits(data))` after the structure checks have passed. Add `"time_limit"` to `optional_fields` in `admin_unite_quizzes`.

- [ ] **Step 8: Run both test files, plus `tests/test_quiz_validation_edge_cases.py` and `tests/test_admin_unite_quizzes.py`.** Expected: all PASS.

- [ ] **Step 9: Update the docs listed under Files, then commit**

```bash
git add webquiz/time_limits.py webquiz/server.py tests/test_time_limits_unit.py tests/test_time_limits_validation.py docs/en/050_quiz_format.md docs/uk/050_quiz_format.md README.md CLAUDE.md
git commit -m "Add time_limit quiz setting: format, checks on save, unite"
```

---

### Task 2: Load limits, start clocks when the page shows a question, send remaining time

**Files:**
- Modify: `webquiz/server.py`:
  - `__init__` (around line 586): new state;
  - `reset_server_state` (line 726);
  - `load_questions_from_file` (line 1025);
  - `create_default_index_html` (client question dicts around line 1120, and placeholder injection around line 1192);
  - `register_user` (line 1804) and `admin_approve_user` (line 2616): remove `self.question_start_times[user_id] = datetime.now()`;
  - `question_start` (line 2152);
  - startup environment log.
- Modify: `webquiz/templates/index.html`: add `const quizTimeLimit = {{QUIZ_TIME_LIMIT}};` next to `showRightAnswer` (line 844).
- Modify: `tests/conftest.py`: add a helper.
- Test: `tests/test_time_limits_timing.py` (new)
- Docs: `CLAUDE.md` (update the "Server-side timing" decision: the clock starts at `question-start`, also for the first question; describe the new `question-start` response fields under API Endpoints)

**Interfaces:**
- Consumes: Task 1 `parse_time_limit`, `question_limits`, `TimeLimitSettings`.
- Produces, on `TestingServer`:
  - `self.time_limit_settings: TimeLimitSettings`
  - `self.question_time_limits: Dict[int, int]`
  - `self.current_question_ids: Dict[str, int]`: user → the question whose clock is running. It is set together with `question_start_times`, and removed together with it.
  - `self.quiz_start_times: Dict[str, datetime]`: set at the student's first `question-start`, and never reset during the quiz.
  - `def _question_is_limited(self, question_id: int) -> bool`: true when `question_time_limits[question_id] > 0`, or when the mode is `whole_quiz` with `seconds > 0`.
  - `def _remaining_times(self, user_id: str, question_id: int, now: datetime) -> dict`: returns `{"remaining_seconds": float}` when the question has a per-question limit, and `{"quiz_remaining_seconds": float}` in whole-quiz mode with `seconds > 0`. Values are without grace and floored at 0.
  - `question_start` response: `{"status": "success", **self._remaining_times(...)}`.
  - Client question dict key `"time_limit": int`, always present (0 = none). Placeholder `{{QUIZ_TIME_LIMIT}}` is the whole-quiz seconds, or `0`.
  - `tests/conftest.py`: `def register_student(port: int, username: str = "Student") -> str`. It POSTs `/api/register` and returns `user_id`.

- [ ] **Step 1: Write the failing tests** in `tests/test_time_limits_timing.py` (use `custom_webquiz_server`, `register_student`, `requests`)
  - `test_first_question_clock_starts_at_question_start`: no limits. Register, `time.sleep(1.2)`, `question-start` for Q1, submit at once. Assert `response["time_taken"] < 1.0`.
  - `test_first_question_clock_starts_after_approval_at_question_start`: config `registration.approve: true`. Register, approve with `PUT /api/admin/approve-user` (see `tests/test_registration_approval.py`), `time.sleep(1.2)`, `question-start`, submit. Assert `time_taken < 1.0`.
  - `test_question_start_returns_remaining_and_reload_does_not_reset`: `time_limit: {per_question: 30}`. First `question-start`: `29 < remaining_seconds <= 30`, and `"quiz_remaining_seconds"` is not in the response. Then `time.sleep(1.1)`. A second `question-start` for the same question returns `remaining_seconds <= 29`.
  - `test_question_start_returns_quiz_remaining`: `time_limit: {whole_quiz: 600}`. `599 < quiz_remaining_seconds <= 600`, and `"remaining_seconds"` is not in the response.
  - `test_unlimited_question_has_no_remaining`: `per_question: 30`, and the question has `time_limit: 0`. The response is exactly `{"status": "success"}`.
  - `test_page_contains_time_limits`: `per_question: 60`, and Q2 has `time_limit: 20`. `GET /` matches the regex `"time_limit":\s*20` and contains `const quizTimeLimit = 0`.
  - `test_malformed_time_limit_loads_without_limits`: write the quiz with `time_limit: "soon"`. The server starts, `question-start` returns exactly `{"status": "success"}`, and `GET /` contains `const quizTimeLimit = 0`.

- [ ] **Step 2: Run them and check that they fail**

Run: `source venv/bin/activate && python -m pytest tests/test_time_limits_timing.py -v -n 4`
Expected: FAIL. `time_taken` is about 1.2, `remaining_seconds` is missing, and the placeholder is missing.

- [ ] **Step 3: Implement the interfaces.** In `load_questions_from_file`, call `parse_time_limit`, log its warning with `logger.warning`, and compute `question_time_limits` after the ids are assigned. Clear `current_question_ids` and `quiz_start_times` in `reset_server_state`. Include the time limit in the "Loaded N questions" log line and in the startup environment log.

- [ ] **Step 4: Run the new tests, plus `tests/test_registration_approval.py`, `tests/test_live_stats_websocket.py` and `tests/test_index_generation.py`.** Expected: all PASS. If an old test asserted that the clock starts at registration or approval, update it to the new rule and say so in the commit.

- [ ] **Step 5: Update CLAUDE.md, then commit**

```bash
git add webquiz/server.py webquiz/templates/index.html tests/conftest.py tests/test_time_limits_timing.py CLAUDE.md
git commit -m "Start question clocks when the page shows the question; send remaining time"
```

---

### Task 3: Timeouts on submit (per question and whole quiz)

**Files:**
- Modify: `webquiz/server.py`: `submit_answer` (line 1928). Move its "store and broadcast" part into a shared method.
- Modify: `webquiz/translations.py`: add the key `server_empty_answer` (uk: `"Порожня відповідь не приймається"`, en: `"An empty answer is not accepted"`).
- Modify: `tests/conftest.py`: `custom_webquiz_server(config=None, quizzes=None, env=None)`; `env` is a dict merged into the subprocess env.
- Test: `tests/test_time_limits_submit.py` (new)
- Docs: wherever `docs/en`/`docs/uk` describe the answers CSV, add "an empty answer means time ran out". In `CLAUDE.md`, describe the `submit-answer` timeout rules.

**Interfaces:**
- Consumes: Task 1 `is_empty_answer`, `grace_seconds`. Task 2 state and `_question_is_limited`.
- Produces, on `TestingServer`:
  - `async def _record_answer(self, user_id: str, question: dict, selected_answer, time_taken: float, timed_out: bool = False) -> dict`. It does everything `submit_answer` does today after the time is known: check the answer, store it in `user_responses`, `user_answers`, `user_progress`, live stats, completion stats and `answer_results`, broadcast, and return the response dict. When `timed_out` is true:
    - the checker is not run, `is_correct` is `False`, and `earned_points` is `0`;
    - the CSV `selected_answer` text is `""`, and the `user_answers` entry has `"timed_out": True`;
    - the live stats state is `"timeout"`, and the response has `"timed_out": True` (always, even when `show_right_answer` is false);
    - `answer_results[user_id][qid]` gets `"timed_out": True`.
    
    Every response has `"test_completed": bool`.
  - `def _question_elapsed(self, user_id: str, question_id: int, now: datetime) -> float`: seconds since that question's clock started. It returns 0 if that question's clock is not running.
  - `def _unanswered_question_ids(self, user_id: str) -> List[int]`: the ids not yet answered, in the student's order (`question_order` when randomized).
  - `async def _end_whole_quiz(self, user_id: str, now: datetime) -> dict`: stores a timeout for every unanswered question. The open question gets its real elapsed time, and the others get 0. It returns the response for the first of them, with `test_completed: True`.
- Order inside `submit_answer`:
  0. If a stored result for this question has `timed_out`, return its response at once (before the randomized-order check).
  1. Today's same-answer repeat check, the randomized-order check, and the 409 check.
  2. Whole-quiz mode with `seconds > 0`: if the answer is empty, or the quiz clock started and `now > quiz_start + seconds + grace` → `_end_whole_quiz`.
  3. Otherwise, if the answer is empty: if the question is not limited → 400 with `server_empty_answer`; otherwise store a timeout.
  4. Otherwise, if the question has `L > 0`, its clock is running, and `now > start + L + grace` → store a timeout (the submitted answer is dropped).
  5. Otherwise, a normal answer.

  Remove the clock entries (`question_start_times`, `current_question_ids`) whenever an answer or timeout is stored for that question.

- [ ] **Step 1: Write the failing tests** in `tests/test_time_limits_submit.py`. Use `env={"WEBQUIZ_TIME_LIMIT_GRACE_SECONDS": "0.5"}` and limits of 1 s. Read final rows from `GET /api/verify-user/{id}` → `final_results["test_results"]`.
  - `test_answer_within_grace_counts`: `per_question: 1`; `question-start`; `sleep(1.2)`; submit the correct answer. Assert `is_correct is True` and `"timed_out" not in response`.
  - `test_late_answer_is_stored_as_timeout`: as above, but `sleep(1.8)`. Assert `timed_out is True` and `is_correct is False`. The final row has `selected_answer == ""` and `timed_out is True`.
  - `test_empty_answer_on_limited_question_is_timeout`: submit `selected_answer: None` at once. Assert `timed_out is True`.
  - `test_empty_answer_on_unlimited_question_is_rejected`: run with no `time_limit`, and again with `per_question: 30` plus question `time_limit: 0`. Both get status 400.
  - `test_empty_answer_skips_checker`: a text question with `checker: "x = 1"` (accepts anything), `per_question: 30`, `show_right_answer: true`. Submit `""`. Assert `is_correct is False`.
  - `test_answer_after_timeout_returns_stored_timeout`: `randomize_questions: true`, 2 questions. After a timeout on the first question in the student's order, submit a real answer to the same question. Assert status 200 and `timed_out is True`.
  - `test_whole_quiz_empty_answer_ends_quiz`: `whole_quiz: 600`, 3 questions. `question-start` Q1, submit `None` for Q1. Assert `test_completed is True`. Verify-user shows 3 rows, all with `selected_answer == ""` and `timed_out`, and the rows for Q2 and Q3 have `time_taken == 0`.
  - `test_whole_quiz_empty_answer_from_continue_screen`: `whole_quiz: 600`. Answer Q1 normally, then submit `None` for Q2 with no `question-start`. Assert `test_completed`. Row 1 keeps its real answer, and rows 2–3 are timed out.
  - `test_whole_quiz_late_answer_ends_quiz`: `whole_quiz: 1`; `question-start`; `sleep(1.8)`; submit a real answer. Assert `timed_out` and `test_completed`.
  - `test_timeout_row_in_answers_csv`: after a timeout, `sleep(6)` for the flush. Read the answers CSV in `data_{port}/` (pattern in `tests/test_show_answers_on_completion.py`). The header is exactly `user_id,question,selected_answer,correct_answer,is_correct,time_taken_seconds`, and the row has an empty `selected_answer` and `is_correct` `False`.
  - `test_live_stats_gets_timeout_state`: follow `tests/test_live_stats_websocket.py`. After a timeout, a `state_update` message arrives with `state == "timeout"`.

- [ ] **Step 2: Run them and check that they fail**

Run: `source venv/bin/activate && python -m pytest tests/test_time_limits_submit.py -v -n 4`
Expected: FAIL. `timed_out` is missing, and the empty answers are checked like normal answers.

- [ ] **Step 3: Implement the interfaces and the order above.** Keep the comment from the existing code: `answer_results` is stored before the broadcast `await`.

- [ ] **Step 4: Run the new tests and the whole non-Selenium suite**

Run: `source venv/bin/activate && python -m pytest tests/ -n 4 -k "not selenium"`
Expected: all PASS. The refactor of `submit_answer` must not change any existing behavior.

- [ ] **Step 5: Update the docs, then commit**

```bash
git add webquiz/server.py webquiz/translations.py tests/conftest.py tests/test_time_limits_submit.py docs CLAUDE.md README.md
git commit -m "Store timed-out answers as empty and failed; end whole quiz when time is up"
```

---

### Task 4: Background check for students whose page went quiet

**Files:**
- Modify: `webquiz/server.py`: new methods, and start the task next to `periodic_flush` (around line 4378)
- Test: `tests/test_time_limits_watcher.py` (new)
- Docs: `CLAUDE.md` (Key Flows: a "Time limits" line), plus the "students who leave stay unfinished" note in `docs/*/050_quiz_format.md`

**Interfaces:**
- Consumes: Task 3 `_record_answer`, `_end_whole_quiz`, `_question_elapsed`. Task 2 state.
- Produces:
  - `async def check_time_limits(self, now: datetime) -> None`:
    - Per-question mode: for each `user_id` in `current_question_ids` whose question has `L > 0` and `now > start + L + grace`, store a timeout.
    - Whole-quiz mode with `seconds > 0`: for each user in `quiz_start_times` who is not finished and `now > quiz_start + seconds + grace`, call `_end_whole_quiz`.
    - Iterate over a copy of the dicts. Skip users no longer in `self.users`.
  - `async def time_limit_watcher(self) -> None`: loops forever. It sleeps `check_interval_seconds()`, then calls `check_time_limits(datetime.now())` inside `try/except` with `logger.exception`, the same way `periodic_flush` does.

- [ ] **Step 1: Write the failing tests** in `tests/test_time_limits_watcher.py`. Use `env={"WEBQUIZ_TIME_LIMIT_GRACE_SECONDS": "0.3", "WEBQUIZ_TIME_LIMIT_CHECK_INTERVAL": "0.2"}`.
  - `test_quiet_student_gets_timeout`: `per_question: 1`, 2 questions. `question-start` Q1, then `sleep(2)`. Verify-user shows `next_question_index == 1` and `test_completed is False`.
  - `test_next_question_clock_does_not_start_on_its_own`: continue from above with another `sleep(2)`. Still `next_question_index == 1`.
  - `test_whole_quiz_ends_for_quiet_student_in_student_order`: `whole_quiz: 1`, `randomize_questions: true`, 3 questions. `question-start` for the first id in `question_order`, then `sleep(2)`. `test_completed is True`, 3 rows are timed out, and the row questions follow `question_order`.
  - `test_whole_quiz_timeouts_complete_the_class`: `whole_quiz: 1`, `show_right_answer: false`, `show_answers_on_completion: true`, one student. After `sleep(2)`, `final_results["all_completed"] is True`.
  - `test_quiz_switch_while_clock_runs`: `per_question: 1`. `question-start`, then switch to another quiz with `POST /api/admin/switch-quiz`, then `sleep(1.5)`. `proc.poll() is None`, and a new `register_student` succeeds.

- [ ] **Step 2: Run them and check that they fail**

Run: `source venv/bin/activate && python -m pytest tests/test_time_limits_watcher.py -v -n 4`
Expected: FAIL. Nothing times out, so `next_question_index == 0` and `test_completed` is `False`.

- [ ] **Step 3: Implement both methods and start the task.**

- [ ] **Step 4: Run the new tests, plus `tests/test_time_limits_submit.py`.** Expected: all PASS.

- [ ] **Step 5: Update the docs, then commit**

```bash
git add webquiz/server.py tests/test_time_limits_watcher.py CLAUDE.md docs
git commit -m "Write timeouts for students whose page went quiet"
```

---

### Task 5: Student page: countdowns, time up, results

**Files:**
- Modify: `webquiz/templates/index.html`:
  - `notifyQuestionStart` (line 964) now reads the JSON and starts the countdowns;
  - `showCurrentQuestion` (line 1415);
  - `submitCurrentAnswer` (line 1558);
  - `showAnswerFeedback` (line 1682);
  - `continueToNextQuestion` (line 1795);
  - results rendering in `showFinalResults` (line 1914) and `showCompletedTestResults` (line 1975);
  - CSS, with a `@media (max-width: 768px)` rule.
- Modify: `webquiz/translations.py`: `time_left` (uk `"Залишилось часу"`, en `"Time left"`) and `time_is_up` (uk `"Час вичерпано"`, en `"Time is up"`).
- Test: `tests/test_selenium_time_limits.py` (new; follow `tests/test_selenium_multiple_choice.py` and `tests/selenium_helpers.py`)
- Docs: `docs/*/050_quiz_format.md` (what the student sees), `README.md`

**Interfaces:**
- Consumes: Task 2 client `time_limit`, `quizTimeLimit`, and the `question-start` fields. Task 3 `timed_out` and `test_completed`.
- Produces (DOM, used by the tests):
  - `#question-timer`, shown inside the current question only when it has a per-question limit;
  - `#quiz-timer`, shown at the top of `#test-section` only when `quizTimeLimit > 0`;
  - both show `M:SS` and get the class `timer-warning` in the last 10 seconds;
  - "Time is up" text in an element with class `time-up-message`;
  - on the results screen, a timed-out row shows `⏱ ` + `T.time_is_up` inside `.time-up-message`.
- Behavior:
  - At zero, if no answer is being sent (`answerLocked` is false), call the normal submit path with `selected_answer: null`. Never have two answers in flight.
  - `show_right_answer: true`: show the feedback, the "Time is up" message and "Continue".
  - `show_right_answer: false`: show the message for 1500 ms, then `continueToNextQuestion(false)`.
  - Whole quiz at zero: send `null` for the open question, or for the next unanswered question if the open one already has an answer. Then call `fetchAndShowFinalResults()`.
  - Stop the question countdown when an answer is sent.

- [ ] **Step 1: Write the failing Selenium tests.** Use config `language: en` so the texts are English.
  - `test_question_countdown_is_shown`: `per_question: 5`. After register, `#question-timer` is visible, and its text matches `^\d:\d\d$`.
  - `test_time_up_shows_message_and_continue`: `per_question: 2`, `show_right_answer: true`. Wait 4 s. `.time-up-message` contains `Time is up`, and the continue button is visible.
  - `test_time_up_auto_advances_without_right_answer`: `per_question: 2`, `show_right_answer: false`, 2 questions. Within 6 s the second question's text is shown.
  - `test_whole_quiz_time_up_shows_results`: `whole_quiz: 3`, 3 questions. Within 8 s the results screen is shown, with 3 `.time-up-message` elements.
  - `test_reload_keeps_counting_down`: `per_question: 20`. Wait 4 s, reload, and the `#question-timer` seconds are `<= 17`.
  - `test_timer_fits_mobile_width`: window 375×800, `per_question: 30`. `document.documentElement.scrollWidth <= window.innerWidth`.

- [ ] **Step 2: Run them and check that they fail**

Run: `source venv/bin/activate && python -m pytest tests/test_selenium_time_limits.py -v -n 4`
Expected: FAIL with timeouts waiting for `#question-timer`.

- [ ] **Step 3: Implement the page changes and translations.**

- [ ] **Step 4: Run the new tests, plus `tests/test_selenium_multiple_choice.py`, `tests/test_user_journey_selenium.py` and `tests/test_selenium_connection_retry.py`.** Expected: all PASS.

- [ ] **Step 5: Update the docs, then commit**

```bash
git add webquiz/templates/index.html webquiz/translations.py tests/test_selenium_time_limits.py docs README.md
git commit -m "Show countdowns and 'Time is up' on the quiz page"
```

---

### Task 6: Live stats ⏱

**Files:**
- Modify: `webquiz/templates/live_stats.html`: `getStateIcon` (line 1088) adds `case 'timeout': return '⏱';`. Every `state === 'ok' || state === 'fail'` check (around lines 797, 827, 852, 864) also accepts `'timeout'`, through a helper `isAnsweredState(state)`.
- Test: add `test_live_stats_shows_timeout_icon` to `tests/test_selenium_time_limits.py` (follow `tests/test_selenium_live_stats_decimal_points.py`).
- Docs: `docs/en/030_admin.md`, `docs/uk/030_admin.md` (⏱ in live stats)

- [ ] **Step 1: Write the failing test.** `per_question: 1`. A student times out through the API (`question-start`, then submit `None`). The live stats page shows `⏱` for that student, and the student is still counted as having answered 1 question.
- [ ] **Step 2: Run it and check that it fails.** Expected: FAIL, because `⚪` is shown.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run it, plus `tests/test_selenium_live_stats_decimal_points.py` and `tests/test_live_stats_two_groups.py`.** Expected: PASS.
- [ ] **Step 5: Update the docs, then commit**

```bash
git add webquiz/templates/live_stats.html tests/test_selenium_time_limits.py docs
git commit -m "Show timed-out answers with a stopwatch in live stats"
```

---

### Task 7: Admin quiz editor fields

**Files:**
- Modify: `webquiz/templates/admin.html`:
  - quiz settings block (around line 1318): add a select and a seconds input;
  - `addQuestion` (line 1923) and the question HTML in `loadQuizDataToWizard` (around line 2619): add the per-question input;
  - `loadQuizDataToWizard` (line 2447) and `getWizardData` (line 2667).
- Test: `tests/test_selenium_admin_time_limits.py` (new; follow `tests/test_selenium_admin_decimal_points.py`)
- Docs: `docs/en/030_admin.md`, `docs/uk/030_admin.md`

**Interfaces:**
- Consumes: Task 1 file format and checks on save. The server rejects invalid values.
- Produces (DOM):
  - `<select id="time-limit-mode">` with values `none`, `per_question`, `whole_quiz` (labels "Без обмеження часу", "На кожне питання", "На весь тест");
  - `<input type="number" id="time-limit-seconds" min="0" step="1">` labelled "Обмеження часу (секунди)", hidden when the mode is `none`;
  - per question: `<input type="number" class="question-time-limit-input" min="0" step="1" placeholder="за замовчуванням">` inside `.question-time-limit-group`. The group is shown only for `per_question`, and is hidden (not removed) otherwise;
  - `function toggleTimeLimitFields()`.
- Saving: `getWizardData` writes `time_limit: {<mode>: <int>}`, or leaves it out for `none`. A question gets `time_limit: <int>` only when its input is not empty, in any mode.

- [ ] **Step 1: Write the failing tests**
  - `test_editor_loads_and_saves_per_question_time_limit`: the quiz file has `per_question: 30` and Q1 has `time_limit: 10`. Open the editor and save without changes. The file on disk still has both values.
  - `test_editor_hides_question_field_outside_per_question_mode`: switch the mode to `whole_quiz`. `.question-time-limit-group` is not displayed. Save. The file has `time_limit == {"whole_quiz": <value>}`, and Q1 still has `time_limit: 10`.
  - `test_editor_sets_none_removes_time_limit`: choose `none` and save. The file has no top-level `time_limit`.
- [ ] **Step 2: Run them and check that they fail.**

Run: `source venv/bin/activate && python -m pytest tests/test_selenium_admin_time_limits.py -v -n 4`
Expected: FAIL. `#time-limit-mode` is not found.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the new tests, plus `tests/test_selenium_quiz_editor.py` and `tests/test_selenium_admin_decimal_points.py`.** Expected: PASS.
- [ ] **Step 5: Update the docs, then commit**

```bash
git add webquiz/templates/admin.html tests/test_selenium_admin_time_limits.py docs
git commit -m "Add time limit fields to the admin quiz editor"
```

---

### Task 8: Final check

- [ ] **Step 1:** Add a "Time Limits (N tests)" line to the README "Test Coverage" list, with the real count from `python -m pytest tests/ --collect-only -q -k time_limit`.
- [ ] **Step 2:** Run `source venv/bin/activate && black --check webquiz/time_limits.py tests/test_time_limits_*.py tests/test_selenium_time_limits.py tests/test_selenium_admin_time_limits.py`. Expected: no files would be reformatted.
- [ ] **Step 3:** Run the full suite: `source venv/bin/activate && python -m pytest tests/ -n 4 -p no:cacheprovider; echo exit=$?`. Expected: `exit=0`.
- [ ] **Step 4:** Commit and push the branch `quiz-time-limits`. The PR is opened after the final review.
