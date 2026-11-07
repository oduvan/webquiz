"""Scripted students (no AI) and the scripted teacher.

Scripted students act at exact times, so they cover the timing edges that
an AI agent cannot hit on purpose. They use the same driver commands as the
agents, so their steps are recorded the same way.
"""

import asyncio
import time

POLL = 0.3


def resolve_answer(spec, question_number, answers):
    """Turn an answer spec into ("options", [labels]) or ("text", value)."""
    if spec is None:
        spec = answers[question_number]
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


async def scripted_student(classroom, name, plan, answers, deadline):
    """Register, then follow the plan question by question until the results or the deadline."""
    await classroom.command(name, "open", screenshot=False)
    await classroom.command(name, "type", name, screenshot=False, settle=0.2)
    await classroom.click_selector(name, ".register-btn", screenshot=True)

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
            if not await handle_question(classroom, name, action, number, answers, shown_at, quiz_start):
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
    await page.close()
    return reply.get("settings")
