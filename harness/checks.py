"""Checks for a harness run, and the report that lines up the three records.

The three records of one run:
1. what each AI agent says it did and saw (its report, by step number);
2. what the driver recorded (each step's command, screen text, screenshot,
   and every request the page sent, with the reply);
3. what the server stored (answers CSV, server log, live stats messages).

The check functions are pure: they take plain lists and dicts and return a
list of problem descriptions (empty = fine). Run the analysis with:

    python -m harness.checks <run_dir>
"""

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from harness.classroom import format_step

STEP_LINE = re.compile(r"^\s*step\s+(\d+)\s*\|\s*did:\s*(.*?)\s*\|\s*saw:\s*(.*)$", re.IGNORECASE)
QUOTE_SEPARATOR = re.compile(r"[\"“”»]\s*;\s*[\"“«]")
QUOTE_MARKS = '"“”«» '
SCORE = re.compile(r"(?:Результат|Result):\s*(\d+)\s*/\s*(\d+)")


def _plain(text):
    """Lower case with single spaces, for comparing what an agent quoted with the screen."""
    return re.sub(r"\s+", " ", str(text)).strip().lower()


# ---- 1 vs 2: the agent's report against the driver's record ----


def split_quotes(saw):
    """Split 'SAW: "a"; "b"' into ["a", "b"].

    Splitting on the '"; "' separator (instead of matching quote pairs) keeps a quote that
    itself contains quotes, like '"TYPE INTO: ... = "6""', in one piece.
    """
    pieces = QUOTE_SEPARATOR.split(saw.strip())
    quotes = []
    for piece in pieces:
        piece = piece.strip()
        if piece[:1] in QUOTE_MARKS:
            piece = piece[1:]
        if piece[-1:] in QUOTE_MARKS:
            piece = piece[:-1]
        piece = piece.strip()
        if re.search(r"\w", piece):
            quotes.append(piece)
    return quotes


def parse_agent_report(text):
    """Read the lines 'STEP n | DID: ... | SAW: "quote"; "quote"' from an agent's report."""
    steps = []
    for line in text.splitlines():
        match = STEP_LINE.match(line)
        if match:
            steps.append(
                {
                    "step": int(match.group(1)),
                    "did": match.group(2).strip(),
                    "quotes": split_quotes(match.group(3)),
                }
            )
    return steps


def check_agent_alignment(agent_steps, driver_steps):
    """Compare what the agent says it did and saw with the driver's record of the same step.

    driver_steps: {step number: {"cmd", "arg", "screen"}} for this student.
    A problem here usually means the agent misread or misreported, not an app bug.
    """
    problems = []
    for reported in agent_steps:
        number = reported["step"]
        recorded = driver_steps.get(number)
        if recorded is None:
            problems.append(f"step {number}: the agent reports a step the driver never ran")
            continue
        did = _plain(reported["did"])
        expected = _plain(" ".join(str(part) for part in (recorded["cmd"], recorded.get("arg")) if part is not None))
        if not did.startswith(_plain(recorded["cmd"])) or (
            recorded.get("arg") is not None and _plain(recorded["arg"]) not in did
        ):
            problems.append(f"step {number}: the agent says it did '{reported['did']}', the driver ran '{expected}'")
        screen = _plain(recorded.get("screen", ""))
        for quote in reported["quotes"]:
            if _plain(quote) not in screen:
                problems.append(f'step {number}: the agent says it saw "{quote}", but the screen did not show it')
    return problems


# ---- 2 vs 3: what happened in the browser against what the server stored ----


def check_unique_answers(rows):
    """Each student has at most one stored answer per question."""
    seen = defaultdict(int)
    for item in rows:
        seen[(item["user_id"], item["question"])] += 1
    return [
        f"user {user}: question '{question}' is stored {count} times"
        for (user, question), count in seen.items()
        if count > 1
    ]


def check_timeout_rows(rows):
    """An empty answer means time ran out, so it must be failed."""
    return [
        f"user {item['user_id']}: question '{item['question']}' has an empty answer marked correct"
        for item in rows
        if item["selected_answer"] == "" and item["is_correct"]
    ]


def check_answer_times(rows, limits, grace, tolerance=1.0):
    """A stored (non-empty) answer must have arrived within the question's limit plus the grace."""
    problems = []
    for item in rows:
        limit = limits.get(item["question"], 0)
        if limit > 0 and item["selected_answer"] != "" and item["time_taken"] > limit + grace + tolerance:
            problems.append(
                f"user {item['user_id']}: question '{item['question']}' was answered after "
                f"{item['time_taken']:.1f} s, limit {limit} s + {grace} s grace, but it counts as an answer"
            )
    return problems


def check_submits_match_rows(submits, rows, allowed_without_submit):
    """Every accepted answer is stored, the stored result matches what the page was told,
    and every stored row comes from a request (or from the server's own timeout check).

    submits: [{"user_id", "question", "status", "response"}] from the driver's request log.
    allowed_without_submit: {(user_id, question)} the server stored by itself (background check,
    whole-quiz end).
    """
    problems = []
    stored = {(item["user_id"], item["question"]): item for item in rows}
    accepted = set()
    for submit in submits:
        if submit.get("status") != 200:
            continue
        key = (submit["user_id"], submit["question"])
        accepted.add(key)
        item = stored.get(key)
        if item is None:
            problems.append(f"user {key[0]}: the answer to '{key[1]}' was accepted (200) but is not stored")
            continue
        response = submit.get("response") or {}
        if response.get("timed_out") and item["selected_answer"] != "":
            problems.append(
                f"user {key[0]}: the page was told 'time is up' for '{key[1]}', "
                f"but the stored answer is '{item['selected_answer']}'"
            )
        if (
            "is_correct" in response
            and not response.get("timed_out")
            and bool(response["is_correct"]) != bool(item["is_correct"])
        ):
            problems.append(
                f"user {key[0]}: the page was told is_correct={response['is_correct']} for '{key[1]}', "
                f"but the stored row says {item['is_correct']}"
            )
    for key in stored:
        if key not in accepted and key not in allowed_without_submit:
            problems.append(
                f"user {key[0]}: '{key[1]}' is stored, but no request sent it and the server did not time it out"
            )
    return problems


def parse_screen_score(text):
    """Read 'Результат: 2/3 (67%)' (or 'Result: ...') from a screen. None when there is no result."""
    match = SCORE.search(text or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def check_screen_scores(final_scores, rows, total_questions):
    """The score a student saw on the results screen equals the stored answers."""
    problems = []
    correct = defaultdict(int)
    for item in rows:
        if item["is_correct"]:
            correct[item["user_id"]] += 1
    for user, (shown_correct, shown_total) in final_scores.items():
        if (shown_correct, shown_total) != (correct[user], total_questions):
            problems.append(
                f"user {user}: the results screen showed {shown_correct}/{shown_total}, "
                f"the stored answers give {correct[user]}/{total_questions}"
            )
    return problems


def check_live_stats(final_states, rows):
    """The last live stats state of each answered question matches the stored answer."""
    problems = []
    for item in rows:
        key = (item["user_id"], item["question"])
        if item["selected_answer"] == "":
            expected = "timeout"
        else:
            expected = "ok" if item["is_correct"] else "fail"
        actual = final_states.get(key)
        if actual != expected:
            problems.append(
                f"user {key[0]}: live stats show '{actual}' for '{key[1]}', the stored answer means '{expected}'"
            )
    return problems


# ---- Loading a run ----


def load_events(run_dir):
    with open(run_dir / "events.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_answer_rows(run_dir):
    files = [
        p for p in (run_dir / "data").glob("*.csv") if not p.name.endswith((".users.csv", ".answers_with_users.csv"))
    ]
    rows = []
    for path in files:
        with open(path, encoding="utf-8") as f:
            for item in csv.DictReader(f):
                rows.append(
                    {
                        "user_id": item["user_id"],
                        "question": item["question"],
                        "selected_answer": item["selected_answer"],
                        "is_correct": item["is_correct"] == "True",
                        "time_taken": float(item["time_taken_seconds"] or 0),
                    }
                )
    return rows


def analyze(run_dir):
    """Run every check on a finished run and write report.md. Returns the number of problems found."""
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    events = load_events(run_dir)
    rows = load_answer_rows(run_dir)
    server_log = (run_dir / "server.log").read_text(encoding="utf-8", errors="replace")
    question_text = {int(k): v for k, v in meta["question_text"].items()}

    # Which user_id belongs to which student, from the register replies
    user_of = {}
    pending_register = {}
    for event in events:
        if event["kind"] == "request" and event["path"] == "/api/register":
            pending_register[event["req_id"]] = event["student"]
        elif event["kind"] == "response" and event.get("req_id") in pending_register:
            body = event.get("body") or {}
            if isinstance(body, dict) and body.get("user_id"):
                user_of[pending_register[event["req_id"]]] = body["user_id"]
    student_of = {user: student for student, user in user_of.items()}

    # Submits with their replies
    requests = {e["req_id"]: e for e in events if e["kind"] == "request"}
    submits = []
    for event in events:
        if event["kind"] == "response" and requests.get(event["req_id"], {}).get("path") == "/api/submit-answer":
            body = requests[event["req_id"]].get("body") or {}
            submits.append(
                {
                    "user_id": body.get("user_id"),
                    "question": question_text.get(body.get("question_id"), f"#{body.get('question_id')}"),
                    "status": event["status"],
                    "response": event.get("body") if isinstance(event.get("body"), dict) else {},
                }
            )

    # Rows the server stored by itself: the background check, and whole-quiz ends
    allowed = set()
    for match in re.finditer(r"Time ran out for user (\d+) on question (\d+)", server_log):
        allowed.add((match.group(1), question_text.get(int(match.group(2)))))
    ended = set(re.findall(r"Whole-quiz time is up for user (\d+)", server_log))
    for item in rows:
        if item["user_id"] in ended and item["selected_answer"] == "":
            allowed.add((item["user_id"], item["question"]))

    # Last screen of each student
    last_screen = {}
    driver_steps = defaultdict(dict)
    for event in events:
        if event["kind"] == "step":
            # The agent may quote anything the tool printed for the step, not only the page text
            driver_steps[event["student"]][event["step"]] = {**event, "screen": format_step(event)}
            last_screen[event["student"]] = event.get("screen", "")
    final_scores = {}
    for student, screen in last_screen.items():
        score = parse_screen_score(screen)
        if score and student in user_of:
            final_scores[user_of[student]] = score

    # Live stats: last state per user and question
    final_states = {}
    for event in events:
        message = event.get("message") if event["kind"] == "live" else None
        if message and message.get("type") in ("state_update", "user_registered"):
            final_states[(message["user_id"], question_text.get(message["question_id"]))] = message["state"]

    sections = {
        "Each question stored once per student": check_unique_answers(rows),
        "Empty (timed-out) answers are failed": check_timeout_rows(rows),
        "Answers arrived within limit + grace": check_answer_times(
            rows, {question_text[int(qid)]: limit for qid, limit in meta["limits"].items()}, meta["grace"]
        ),
        "Requests and stored answers agree": check_submits_match_rows(submits, rows, allowed),
        "Results screen matches stored answers": check_screen_scores(final_scores, rows, len(question_text)),
        "Live stats match stored answers": check_live_stats(final_states, rows),
    }

    agent_sections = {}
    for report_path in sorted((run_dir / "agents").glob("*.md")) if (run_dir / "agents").exists() else []:
        student = report_path.stem
        agent_steps = parse_agent_report(report_path.read_text(encoding="utf-8"))
        problems = check_agent_alignment(agent_steps, driver_steps.get(student, {}))
        if not agent_steps:
            problems.append("the report has no 'STEP n | DID: ... | SAW: ...' lines")
        agent_sections[student] = (len(agent_steps), problems)

    coverage = [
        f"- Results screens read: {len(final_scores)} of {len(user_of)} students",
        f"- Live stats messages recorded: {sum(1 for e in events if e['kind'] == 'live')}",
        f"- Answer requests with a reply: {len(submits)}",
    ]
    write_report(run_dir, meta, sections, agent_sections, rows, user_of, coverage)
    write_timelines(run_dir, events, rows, user_of, question_text)
    return sum(len(p) for p in sections.values())


def write_report(run_dir, meta, sections, agent_sections, rows, user_of, coverage):
    lines = [f"# Harness run: {meta['scenario']}", "", meta.get("description", ""), ""]
    lines.append(f"- Students: {len(user_of)} registered ({', '.join(sorted(user_of))})")
    lines.append(
        f"- Stored answers: {len(rows)}, of them timed out (empty): {sum(1 for r in rows if r['selected_answer'] == '')}"
    )
    lines.append(f"- Settings used: `{json.dumps(meta.get('settings'), ensure_ascii=False)}`")
    lines.extend(coverage)
    lines.append("")
    lines.append("## Checks: browser record vs server data")
    lines.append("")
    for title, problems in sections.items():
        mark = "PASS" if not problems else f"FAIL ({len(problems)})"
        lines.append(f"- **{mark}** {title}")
        for problem in problems:
            lines.append(f"  - {problem}")
    lines.append("")
    lines.append("## Agent reports vs driver record")
    lines.append("")
    if not agent_sections:
        lines.append("No agent reports in this run.")
    for student, (count, problems) in agent_sections.items():
        mark = "aligned" if not problems else f"{len(problems)} difference(s)"
        lines.append(f"- **{student}**: {count} reported steps, {mark}")
        for problem in problems:
            lines.append(f"  - {problem}")
    lines.append("")
    lines.append("Per-student timelines: `timelines/<student>.md`. Screenshots: `shots/`.")
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_timelines(run_dir, events, rows, user_of, question_text):
    """One file per student: driver steps, requests and the stored rows, in time order."""
    out = run_dir / "timelines"
    out.mkdir(exist_ok=True)
    requests = {e["req_id"]: e for e in events if e["kind"] == "request"}
    per_student = defaultdict(list)
    for event in events:
        student = event.get("student")
        if not student:
            continue
        if event["kind"] == "step":
            screen = " / ".join(line for line in event.get("screen", "").splitlines() if line.strip())[:300]
            arg = f" {event['arg']}" if event.get("arg") is not None else ""
            error = f" ERROR: {event['error']}" if event.get("error") else ""
            start = event.get("t_start", event["t"])
            per_student[student].append(
                (
                    start,
                    f"{start:7.1f}s  STEP {event['step']}: {event['cmd']}{arg}{error}  (done at {event['t']:.1f}s)\n          screen: {screen}",
                )
            )
        elif event["kind"] == "response":
            request = requests.get(event["req_id"], {})
            if request.get("path") in ("/api/submit-answer", "/api/question-start", "/api/register"):
                per_student[student].append(
                    (
                        request["t"],
                        f"{request['t']:7.1f}s  {request.get('method')} {request.get('path')} "
                        f"{json.dumps(request.get('body'), ensure_ascii=False)}"
                        f" -> {event['status']} at {event['t']:.1f}s {json.dumps(event.get('body'), ensure_ascii=False)[:200]}",
                    )
                )
        elif event["kind"] in ("request_failed", "network", "note"):
            per_student[student].append(
                (event["t"], f"{event['t']:7.1f}s  {event['kind'].upper()}: {event.get('detail', '')}")
            )
    for student, entries in per_student.items():
        user = user_of.get(student)
        stored = [r for r in rows if r["user_id"] == user]
        ordered = [line for _, line in sorted(entries, key=lambda entry: entry[0])]
        text = [f"# {student} (user_id {user})", "", "```", *ordered, "```", "", "## Stored answers", ""]
        for item in stored:
            text.append(
                f"- {item['question']} → '{item['selected_answer']}', correct={item['is_correct']}, time={item['time_taken']:.1f}s"
            )
        (out / f"{student}.md").write_text("\n".join(text) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m harness.checks <run_dir>")
        sys.exit(2)
    found = analyze(sys.argv[1])
    print(f"{found} problem(s) found. Report: {Path(sys.argv[1]) / 'report.md'}")
