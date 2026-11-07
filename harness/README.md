# Test harness: a classroom with real browsers

The harness runs a real WebQuiz server and lets a class of students take a quiz in real browsers at the same time:

- a **scripted teacher** starts the quiz through the start pop-up (with the scenario's settings);
- **scripted students** (no AI) act at exact times, for the timing edges: an answer one second before the limit, an answer that arrives inside or after the 5 s grace because the Wi-Fi was off, a reload, a closed tab;
- **AI agent students** (small models, e.g. Haiku) take the quiz like people would and report, step by step, what they did and what they saw.

It is not part of the normal test suite. It lives outside `tests/`, so `pytest` and GitHub Actions never start it. Only `tests/test_harness_checks.py` (the pure check functions) runs with the normal tests.

## The three records

Every run keeps three records of the same lesson, and the analysis checks that they tell the same story:

1. **The agent's report.** For each command: `STEP 7 | DID: click 56 | SAW: "✓ Правильна відповідь"`. Facts only.
2. **The driver's record** (`events.jsonl`, `shots/`). The driver runs every command, so it records each step itself: start and end time, command, the screen text after it, a screenshot, and every `/api/` request the page sent with the reply. It also records every live stats message.
3. **The server's data**: the answers CSV, the server log, and the live stats messages.

The step number joins records 1 and 2. The `user_id` and question id in the requests join them to the CSV rows and log lines.

What a disagreement means:

| Disagreement | Meaning |
|---|---|
| Agent's report vs driver's record | The agent misread or misclicked. Noise, not an app bug. |
| Screen vs server data (score, correct/wrong, "time is up") | A real bug. |
| A request was accepted but no answer is stored | A lost answer. |
| An answer is stored but nothing sent it | A phantom answer (only the server's own timeouts are expected). |
| Live stats vs stored answers | A live stats bug. |

## Running it

```bash
source venv/bin/activate
pip install -r harness/requirements.txt      # Playwright for Python
python -m playwright install chromium        # skip if a shared browser is set in PLAYWRIGHT_BROWSERS_PATH

# Scripted students only (no AI):
python -m harness.run time-edges --no-agents

# A class of 100 students (scripted only):
python -m harness.run big-class --class-size 100 --no-agents
```

With AI agent students:

1. `python -m harness.run normal-lesson` and wait for `READY <run_dir>`.
2. Start one agent per name in the scenario's `agents` (see `harness/scenarios.py`), each with `harness/AGENT_PROMPT.md`, `{name}` and `{persona}` filled in. Agents only run `python -m harness.student <name> <command>`.
3. Save each agent's final message as `<run_dir>/agents/<name>.md`, then create the file `<run_dir>/agents_done`.
4. The run waits for the server's own time checks, stops, and writes `<run_dir>/report.md` and `<run_dir>/timelines/<student>.md`.

To check a run again after adding agent reports: `python -m harness.checks <run_dir>`.

Runs are saved in `harness/runs/` (not committed). The server uses port 8199 and the agents' API port 8198, away from the test ports.

## Scenarios

| Name | What it covers |
|---|---|
| `normal-lesson` | A normal lesson: limit changed in the start pop-up, mixed question types, different speeds, a reload, a student who leaves |
| `time-edges` | Answers just before the limit, inside and after the grace, a picked but unsent option, no answer, a reload, a closed tab, a question with no limit |
| `whole-quiz-wifi` | Whole-quiz limit chosen in the pop-up: students finish early, run out of time, lose Wi-Fi when time runs out, close the tab, reload a lot |
| `approval-whole-quiz` | Approval mode with a whole-quiz limit: a scripted teacher approves students in the admin panel at planned times; students press "Check" early, 40 s after approval, or are never approved. Waiting must never use up quiz time |
| `big-class` | A big class at once (40 scripted students, `--class-size N` for more) plus agents, random question order, 30 s per question; some reload, leave, or lose Wi-Fi. The report adds the server's reply times and checks the server's time per answer against the browser's |

## Files

| File | What it does |
|---|---|
| `classroom.py` | The browser driver: one browser session per student, the commands, the record |
| `student.py` | The command-line tool the agents use |
| `scripted.py` | Scripted students and the scripted teacher |
| `scenarios.py` | Scenario quizzes, start settings, student plans, agent personas |
| `run.py` | Runs a scenario end to end |
| `checks.py` | The checks, the report and the timelines |
| `AGENT_PROMPT.md` | The instructions for an AI agent student |

A suspected bug is only a bug once a scripted student or a normal test reproduces it. That test then stays in the test suite.
