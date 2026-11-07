"""Scripted students (no AI) and the scripted teacher.

Scripted students act at exact times, so they cover the timing edges that
an AI agent cannot hit on purpose. They use the same driver commands as the
agents, so their steps are recorded the same way.
"""

import asyncio
import time

POLL = 0.3


def resolve_answer(spec, question_id, answers):
    """Turn an answer spec into ("options", [labels]) or ("text", value).

    None means the scenario's correct answer for this question id (so it also
    works when every student gets the questions in a different order).
    """
    if spec is None:
        spec = answers[question_id]
    if isinstance(spec, tuple) and spec and spec[0] == "text":
        return "text", spec[1]
    if isinstance(spec, str):
        return "options", [spec]
    return "options", list(spec)


async def give_answer(classroom, name, spec, question_number, answers, submit=True):
    kind, value = resolve_answer(spec, question_number, answers)
    if kind == "text":
        await classroom.command(name, "type", value, screenshot=False, settle=0.2)
    else:
        for label in value:
            await classroom.command(name, "click", label, screenshot=False, settle=0.2)
    if submit:
        await classroom.click_selector(name, "#submit-answer-btn", screenshot=True)


async def until(start, seconds):
    delay = start + seconds - time.monotonic()
    if delay > 0:
        await asyncio.sleep(delay)


async def handle_question(classroom, name, action, number, answers, shown_at, quiz_start):
    """Run one plan action. Returns False when the student stops (left the quiz)."""
    kind = action[0]
    if kind == "answer":
        await until(shown_at, action[2])
        await give_answer(classroom, name, action[1], number, answers)
    elif kind == "text":
        await until(shown_at, action[2])
        await give_answer(classroom, name, ("text", action[1]), number, answers)
    elif kind == "pick":
        await until(shown_at, action[2])
        await give_answer(classroom, name, action[1], number, answers, submit=False)
    elif kind == "idle":
        pass
    elif kind == "leave":
        await until(shown_at, action[1])
        await classroom.command(name, "close", screenshot=False)
        return False
    elif kind == "reload":
        await until(shown_at, action[1])
        await classroom.command(name, "reload", screenshot=True, settle=1.0)
        await until(shown_at, action[3])
        await give_answer(classroom, name, action[2], number, answers)
    elif kind == "offline_answer":
        _, label, off_at, off_for, delay = action
        await until(shown_at, off_at)
        await classroom.command(name, "offline", off_for, screenshot=False, settle=0)
        await until(shown_at, delay)
        await give_answer(classroom, name, label, number, answers)
    elif kind == "offline_at_quiz_time":
        await until(quiz_start, action[1])
        await classroom.command(name, "offline", action[2], screenshot=False, settle=0)
    else:
        raise ValueError(f"unknown action {action}")
    return True


async def wait_for_approval(classroom, name, checks):
    """Press "Check" at the planned times (seconds since registration) until the quiz starts.

    After the planned checks the student keeps checking every 5 s for 20 s more, then gives up.
    Returns True when the quiz started.
    """
    registered_at = time.monotonic()
    check_button = "button[onclick='checkApprovalStatus()']"
    times = list(checks) + [checks[-1] + 5 * n for n in range(1, 5)]
    for at in times:
        await until(registered_at, at)
        await classroom.click_selector(name, check_button, screenshot=True)
        await asyncio.sleep(0.5)
        if (await classroom.state(name)).get("question"):
            return True
    return False


async def scripted_student(classroom, name, plan, answers, question_ids, deadline):
    """Register, then follow the plan question by question until the results or the deadline.

    plan: {position: action}; position 1 is the first question this student sees.
    plan["check"]: when approval is on, the times (seconds after registering) to press "Check".
    question_ids: {question text: question id}, to find the correct answer in a random order.
    """
    await classroom.command(name, "open", screenshot=False)
    await classroom.command(name, "type", name, screenshot=False, settle=0.2)
    await classroom.click_selector(name, ".register-btn", screenshot=True)

    if "check" in plan and not await wait_for_approval(classroom, name, plan["check"]):
        await classroom.command(name, "look", screenshot=True)
        return

    seen = set()
    number = 0
    quiz_start = None
    while time.monotonic() < deadline:
        state = await classroom.state(name)
        if state.get("results"):
            await asyncio.sleep(1.0)  # the results come from the server; give them a moment
            await classroom.command(name, "look", screenshot=True)
            return
        question = state.get("question")
        if question and question not in seen and not state.get("time_up"):
            seen.add(question)
            number += 1
            shown_at = time.monotonic()
            quiz_start = quiz_start or shown_at
            action = plan.get(number, ("answer", None, 3))
            question_id = question_ids.get(question, number)
            if not await handle_question(classroom, name, action, question_id, answers, shown_at, quiz_start):
                return
            continue
        if state.get("can_continue"):
            await classroom.click_selector(name, "#continue-btn", screenshot=False)
            continue
        await asyncio.sleep(POLL)
    await classroom.command(name, "look", screenshot=True)


async def teacher_start(classroom, quiz_file, settings, master_key):
    """Log in to the admin panel and start the quiz through the start pop-up.

    Returns the settings the running quiz uses (from the switch-quiz reply).
    """
    teacher = await classroom.add_student("teacher")
    page = await teacher.context.new_page()
    shots = classroom.run_dir / "shots"
    await page.goto(classroom.base_url + "/admin/")
    # 127.0.0.1 is a trusted address by default, so the login form may not show
    await page.wait_for_function(
        """() => ['admin-panel', 'master-key'].some(id => {
            const el = document.getElementById(id);
            return el && el.getClientRects().length > 0;
        })"""
    )
    if await page.locator("#master-key").is_visible():
        await page.fill("#master-key", master_key)
        await page.click("button[onclick='authenticate()']")
    await page.wait_for_selector("#admin-panel", state="visible")
    await page.wait_for_timeout(800)
    await page.select_option("#quiz-select", quiz_file)
    await page.click("#switch-btn")
    await page.wait_for_selector("#start-quiz-modal", state="visible")
    await page.wait_for_timeout(600)
    await page.locator("#start-quiz-modal .modal-content").screenshot(path=str(shots / "teacher-1-file-values.png"))

    checkboxes = {
        "show_right_answer": "#start-show-right-answer",
        "show_answers_on_completion": "#start-show-answers-on-completion",
        "randomize_questions": "#start-randomize-questions",
        "show_final_list": "#start-show-final-list",
    }
    for key, selector in checkboxes.items():
        if key in settings:
            await page.set_checked(selector, settings[key], force=True)
            await page.dispatch_event(selector, "change")
    if "time_limit" in settings:
        limit = settings["time_limit"]
        mode = "none" if not limit else next(iter(limit))
        await page.select_option("#start-time-limit-mode", mode)
        if limit:
            await page.fill("#start-time-limit-seconds", str(limit[mode]))
    await page.locator("#start-quiz-modal .modal-content").screenshot(path=str(shots / "teacher-2-chosen.png"))

    async with page.expect_response("**/api/admin/switch-quiz") as response_info:
        await page.click("#start-quiz-confirm")
    reply = await (await response_info.value).json()
    classroom.log("note", student="teacher", detail=f"started the quiz: {reply}")
    teacher.page = page  # stays open: the teacher may approve students later
    return reply.get("settings")


async def teacher_approves(classroom, approvals, agent_names, agent_delay, started, deadline):
    """Click "approve" in the admin panel for each student at the planned time.

    approvals: {student: seconds after the start, or None = never}.
    Agents are approved `agent_delay` seconds after they first show up in the waiting list.
    """
    page = classroom.students["teacher"].page
    planned = {name: at for name, at in approvals.items() if at is not None}
    agents_seen = {}
    agents_left = set(agent_names)
    while (planned or agents_left) and time.monotonic() < deadline:
        now = time.monotonic() - started
        due = [name for name, at in planned.items() if now >= at]
        for name in agents_left:
            if await page.locator(".pending-user-item", has_text=f"👤 {name}").count():
                agents_seen.setdefault(name, now)
                if now - agents_seen[name] >= agent_delay:
                    due.append(name)
        for name in due:
            item = page.locator(".pending-user-item", has_text=f"👤 {name}")
            if await item.count() == 0:
                continue  # not registered yet: try again on the next round
            await item.first.locator(".approve-btn").click()
            classroom.log("note", student="teacher", detail=f"approved {name} at {now:.1f} s")
            planned.pop(name, None)
            agents_left.discard(name)
        await asyncio.sleep(0.5)
