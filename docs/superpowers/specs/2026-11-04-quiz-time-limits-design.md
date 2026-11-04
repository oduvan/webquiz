# Quiz time limits — design

Date: 2026-11-04
Branch: `quiz-time-limits` (separate from PR #113)

## Why

A teacher wants to limit how long students have, either for each question or for the whole quiz. The limit must be fair: the clock runs only while the student can actually see the question, and a short Wi-Fi delay must not cost a student an answer they sent in time. Afterwards the teacher must be able to see which questions a student failed because time ran out.

## Goals

- A quiz can set a time limit **per question** (with a default and per-question exceptions) or for the **whole quiz**.
- The clock for a question starts when the student's page shows that question.
- The student sees a countdown.
- When time runs out, the question is stored with **no answer** and counts as failed. "Empty answer" is the marker for "time ran out". The answers CSV keeps its current columns.
- Live stats and the student's results screen show timed-out questions clearly.
- The admin quiz editor can set all of this.

## Non-goals (not in this PR)

- Changing time limits when the admin starts a quiz. This is planned for later. Keep the quiz-level setting in one place (read once in `load_quiz_file`) so it is easy to override later.
- Extra time for a single student, pausing the clock, or showing remaining time in live stats.
- Combining both modes in one quiz.

## Anti-goals (would make this a failure even if it "works")

- The clock runs before the student can see the question. For example, today the first question's clock starts at registration or approval, which can be minutes before the student sees it.
- Reloading the page restarts the clock.
- An answer sent in time is lost because the Wi-Fi was slow for a few seconds.
- A student who closes the tab shows "thinking" in live stats forever, or blocks `show_answers_on_completion` forever, on a question that has a limit.
- Quizzes **without** `time_limit` behave differently. The one exception is the first-question timing fix below, which makes their CSV times more accurate.

## Quiz file format

All values are whole seconds. `0` always means "no limit".

```yaml
# Mode 1: per question
time_limit:
  per_question: 60        # default for questions without their own time_limit
questions:
  - question: "2+2?"
    time_limit: 20        # this question: 20 s
  - question: "Explain..."
    time_limit: 0         # this question: no limit
  - question: "3+3?"      # uses the default: 60 s
```

```yaml
# Mode 2: whole quiz
time_limit:
  whole_quiz: 900         # 15 minutes for the whole quiz
questions:
  - question: "2+2?"
    time_limit: 20        # ignored in this mode
```

### Effective limit of a question

| Quiz `time_limit` | Question `time_limit` | Result |
|---|---|---|
| not set | anything | no limit (the question value is ignored) |
| `per_question: D` | not set | `D` seconds (`D = 0` means no limit) |
| `per_question: D` | `T` | `T` seconds (`T = 0` means no limit) |
| `whole_quiz: W` | anything | the question has no own limit; the whole quiz has `W` seconds (`W = 0` means no limit at all) |

The server works out the effective limit once, when the quiz is loaded. The page does not need to know these rules.

## Timing rules (agreed with Oleksandr)

1. **Per-question clock.** It starts when the server receives `question-start` for that question. A repeated `question-start` (for example after a page reload) does not restart it. This is already how `question_start_times` behaves for later questions.
2. **First-question fix (all quizzes).** Registration and approval no longer start the clock. Today they set `question_start_times[user_id]` (`server.py`, in `register_user` and `admin_approve_user`). With approval on, the student only sees the question after pressing "Check status", so the clock can run for minutes before that. After this change, the first question's clock starts at its `question-start`, like every other question. Registration and approval still set the live stats "think" state as today.
3. **"Continue" screen.** In per-question mode, time on the "Continue" screen (when `show_right_answer: true`) does not count, because the next question's clock starts only at its `question-start`.
4. **Whole-quiz clock.** It starts at the student's first `question-start` and is never reset. It is plain clock time, so time on "Continue" screens counts.
5. **Grace of 5 seconds.** An answer that reaches the server within limit + 5 s counts as a normal answer. A later answer is stored as timed out: the submitted answer is dropped and stored as empty. Use one constant, `TIME_LIMIT_GRACE_SECONDS = 5`.

## Empty answer = timed out (agreed)

- On timeout, the page sends `selected_answer: null`. The server treats `null`, an empty or whitespace-only string, and an empty list as "empty".
- An empty answer is **always failed**, earns 0 points, and **the checker is not run**. Otherwise a text question whose checker accepts anything, or whose `correct_value` is `""`, could mark it as correct.
- An empty answer is accepted **only** on a question that has a limit: an effective per-question limit above 0, or any question in whole-quiz mode with `W > 0`. On any other question the server answers 400, as the page already blocks empty answers there. This keeps "empty in the CSV" a reliable sign of "time ran out".
- The server accepts an empty answer on a limited question at any moment. The page's clock may run slightly ahead of the server's, and giving up early only hurts the student.

### How a timed-out question is stored

- **Answers CSV:** `selected_answer` is empty, `is_correct` is `False`, and `time_taken_seconds` is the real time since the question was opened (0 for a question that was never opened, see whole-quiz end). The columns do not change. The same applies to `answers_with_users.csv`.
- **In memory (`user_answers`):** the entry also gets `"timed_out": True`, which the results screen uses. It is not written to the CSV.
- **Live stats:** a new state `"timeout"`, shown as ⏱. Everywhere live stats treats `"fail"` as "answered" or "finished" must treat `"timeout"` the same way (`live_stats.html` around lines 797, 827, 852, 864, 1090).
- **`answer_results`:** stores the result as today. If the stored result is a timeout, **any** later answer to that question, empty or not, gets the stored timeout response with status 200, not 409. Then a late retry lets the page move on calmly.

## Server behaviour

### `question-start`

The response adds the remaining time computed on the server, so the page never relies on its own idea of when the question opened:

- `remaining_seconds`: for a question with a per-question limit; leave it out otherwise.
- `quiz_remaining_seconds`: in whole-quiz mode; leave it out otherwise.

Both values are without the grace and never below 0. On resume after a reload, the page already calls `question-start`, so it gets the true remaining time.

### `submit-answer`

Before checking the answer:

1. If the answer is empty, apply the empty-answer rules above.
2. Per-question mode: if the question has limit `L > 0`, its clock started, and `now > start + L + 5`, store a timeout.
3. Whole-quiz mode: if `now > quiz_start + W + 5`, end the student's quiz (see below).

The response always includes `timed_out: true` for a timeout, even when `show_right_answer` is false, so the page can show "Time is up". When the whole quiz ended, the response also says the test is completed.

### End of the whole-quiz time

The current question and every unanswered question, in the student's order (`question_order` when randomized), are stored as timed out. Questions never opened get `time_taken` 0. Then the student is complete: `calculate_and_store_user_stats` runs, and live stats get the updates and `completed: true`.

### The once-a-second check (chosen approach)

A background task runs every second while a quiz with `time_limit` is loaded. It runs next to the existing 5-second CSV flush and is started and stopped the same way.

- **Per-question mode:** for each student whose current question has a running clock and limit `L > 0`, if `now > start + L + 5`, store a timeout for that question. Use the same code path as `submit-answer`, and broadcast to live stats. The next question's clock does **not** start until the student's page shows it.
- **Whole-quiz mode:** for each student who is not finished and whose quiz clock started, if `now > quiz_start + W + 5`, end their quiz as above.

The check must know which question each student is on. Today `question_start_times` stores only a time per user, so the builder may add the current question id next to it. That choice is left to the builder.

All new per-user state is cleared in `reset_server_state()`.

## Student page (`index.html`)

- The server injects each question's effective limit into the client question data as `time_limit` (seconds, 0 = none). It also injects the whole-quiz limit as a JS value (0 = none).
- **Per-question countdown** near the question, for example `⏱ 0:42`. It turns red in the last 10 seconds and stops when the answer is sent.
- **Whole-quiz countdown** at the top of the test area. It stays visible on every question and on "Continue" screens.
- The countdowns start from the `remaining_seconds` and `quiz_remaining_seconds` values of `question-start`.
- **At zero:** if an answer is not already being sent (`answerLocked`), the page sends the empty answer through the normal submit path, with the same retry, locking and waiting for `questionStartRequest`. Anything selected or typed is dropped.
  - With `show_right_answer: true`: show "Time is up", the correct answer as today, and the "Continue" button.
  - With `show_right_answer: false`: show "Time is up" briefly and move to the next question.
  - In whole-quiz mode: after the response, show the final results. Load them from `verify-user` (`final_results`), because the server wrote the remaining answers.
- **Results screen:** a timed-out question shows "⏱ Time is up" in place of the student's answer.
- New strings go in `translations.py` (uk and en).
- Mobile: the countdowns fit at ≤768px with no horizontal scroll.

## Admin quiz editor (`admin.html`, wizard)

- In the quiz settings section, add "Time limit" with a choice of "none / per question / whole quiz" and a seconds field.
- Each question gets a "Time limit (seconds)" field. Empty means "use the default", and 0 means "no limit". The field is shown only in per-question mode. When hidden, the field and its value stay in the form, and saving keeps the value. This matches the rule that question values are allowed and ignored outside per-question mode.
- Loading a quiz fills these fields. Saving writes `time_limit: {per_question: N}` or `{whole_quiz: N}`, or leaves `time_limit` out for "none".

## Checks on save (`_validate_quiz_data`)

- `time_limit` at the quiz level must be a mapping with exactly one key, `per_question` or `whole_quiz`. Unknown keys, or both keys at once, are errors.
- Values are whole numbers ≥ 0. Booleans are rejected; note that in Python `isinstance(True, int)` is true.
- A question's `time_limit` is a whole number ≥ 0. It is allowed even when the quiz has no `time_limit`, and then ignored.
- The error messages follow the style of the existing ones, for example `"'time_limit.per_question' must be a whole number of seconds (0 or more)"`.

## Other places

- **Unite quizzes:** copy `time_limit` from the first quiz, by adding it to `optional_fields`. A question's `time_limit` travels with the question. Note: PR #113 edits the same list and `_validate_quiz_data`, so whichever PR merges second needs a small rebase.
- **Startup log and quiz load log:** include the time limit setting.

## Docs and project rules

Per `CLAUDE.md`, every change updates:

- `docs/en/050_quiz_format.md` and `docs/uk/050_quiz_format.md`: a new `time_limit` section with the table above and examples.
- `docs/en/030_admin.md` and `docs/uk/030_admin.md`: the editor fields and the ⏱ in live stats.
- Any doc that describes the answers CSV: an empty answer means "time ran out".
- `README.md` and `CLAUDE.md`: the feature, the timing rules, and the changed first-question timing in the "Server-side timing" decision.

## Tests (written first)

- **Validation:** each rule in "Checks on save".
- **Effective limit:** each row of the table.
- **Timing:**
  - The first question's clock starts at `question-start`, not at registration or approval.
  - A repeated `question-start` does not reset the clock.
  - `remaining_seconds` and `quiz_remaining_seconds` are correct.
- **Submit:**
  - An answer within limit + 5 s counts.
  - A later answer is stored as timed out.
  - An empty answer on a limited question is a timeout, and on an unlimited question it gets 400.
  - The checker is not run for an empty answer.
  - A retry after a timeout gets the stored response.
- **Background check:**
  - A student who stops sending requests gets a timeout.
  - The whole-quiz end writes every remaining question and completes the student.
  - Live stats get a `"timeout"` state and `completed`.
- **CSV:** a timeout row has an empty answer, `False`, and the same columns as before.
- **Selenium (student page):** the countdown is shown, the page sends the empty answer at zero, "Time is up" is shown, the page moves on, the whole-quiz end shows results, and the layout works at mobile width.
- **Selenium (admin editor):** the time limit fields load, save and hide correctly.
- **Live stats:** the ⏱ icon is shown.

To keep tests fast, use short limits (1–2 s). Also make the grace and the check interval adjustable in tests, for example as class attributes the test fixture can set.

## Approaches considered (for the once-a-second check)

1. **One check every second (chosen).** It is simple, survives reloads, and follows the existing periodic flush pattern. A timeout may be recorded up to 1 s late, which is fine next to the 5 s grace.
2. **A separate timer for each student and question.** It is exact, but every timer must be cancelled on answer, quiz switch and restart. That is more places for mistakes and harder to test.
3. **Check only when the page sends a request.** It is the simplest, but a student who left shows "thinking" forever and can block `show_answers_on_completion`. Rejected.

Oleksandr left this choice to me.

## Left to the builder

- Where the current question id per student is stored.
- The exact look and position of the countdowns, within the rules above.
- The exact wording of the new uk/en strings.
- How long "Time is up" stays on screen before auto-advance when `show_right_answer: false`.
- Whether the collapsed question in the admin editor shows a ⏱ marker when it has its own limit.
