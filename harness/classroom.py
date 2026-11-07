"""The browser driver: one browser, one isolated session per student.

Every command a student (AI agent or script) gives goes through
Classroom.command(). The driver, not the student, records each step:
the command, the screen text after it, a screenshot, and every API request
the page sent with its reply. That record is what the agents' own reports
are compared against.
"""

import asyncio
import json
import re
import time
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

# Reads what a person would see: page text, things to click, places to type
LOOK_JS = r"""() => {
  const visible = el => {
    if (!el.getClientRects().length) return false;
    const style = getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none' && el.closest('.hidden') === null;
  };
  const text = (document.body.innerText || '').replace(/\n{3,}/g, '\n\n').trim();
  const clickable = [];
  document.querySelectorAll('button, .option, a').forEach(el => {
    if (!visible(el)) return;
    const label = (el.innerText || '').trim().replace(/\s+/g, ' ');
    if (!label) return;
    const disabled = !!el.disabled || el.classList.contains('disabled');
    clickable.push({kind: el.classList.contains('option') ? 'option' : el.tagName.toLowerCase(), label, disabled});
  });
  const inputs = [];
  document.querySelectorAll('input[type=text], input:not([type]), textarea').forEach(el => {
    if (!visible(el)) return;
    inputs.push({kind: el.tagName.toLowerCase(), label: el.placeholder || el.id || '', value: el.value, disabled: el.disabled});
  });
  return {text, clickable, inputs};
}"""

# A short state summary for scripted students
STATE_JS = r"""() => {
  const shown = id => { const el = document.getElementById(id); return !!el && !el.classList.contains('hidden') && el.getClientRects().length > 0; };
  const q = document.querySelector('#current-question-container .question-text');
  const timer = document.getElementById('question-timer');
  return {
    question: q ? q.innerText.trim() : null,
    question_timer: timer ? timer.textContent : null,
    quiz_timer: shown('quiz-timer-box') ? document.getElementById('quiz-timer').textContent : null,
    results: shown('results'),
    can_continue: shown('continue-btn') && !document.getElementById('continue-btn').disabled,
    time_up: !!document.querySelector('#current-question-container .time-up-message'),
  };
}"""

COMMANDS = ("open", "look", "click", "type", "wait", "reload", "offline", "close")
MAX_SCREEN = 2500


class Student:
    def __init__(self, name, context, device):
        self.name = name
        self.context = context
        self.device = device
        self.page = None
        self.step = 0
        self.lock = asyncio.Lock()
        self.offline_task = None


class Classroom:
    """Owns the browser, the students and the run record (events.jsonl, shots/)."""

    def __init__(self, base_url, run_dir):
        self.base_url = base_url.rstrip("/")
        self.run_dir = Path(run_dir)
        (self.run_dir / "shots").mkdir(parents=True, exist_ok=True)
        self.events = open(self.run_dir / "events.jsonl", "a", encoding="utf-8")
        self.t0 = time.monotonic()
        self.students = {}
        self._req_counter = 0
        self._playwright = None
        self.browser = None

    def now(self):
        return round(time.monotonic() - self.t0, 2)

    def log(self, kind, **data):
        record = {"t": self.now(), "wall": datetime.now().isoformat(timespec="milliseconds"), "kind": kind, **data}
        self.events.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.events.flush()
        return record

    async def start(self):
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch()

    async def stop(self):
        for student in self.students.values():
            try:
                await student.context.close()
            except Exception:
                pass
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        self.events.close()

    async def add_student(self, name, device="desktop"):
        if device == "phone":
            options = dict(self._playwright.devices["iPhone 13"])
        else:
            options = {"viewport": {"width": 1100, "height": 900}}
        context = await self.browser.new_context(**options)
        student = Student(name, context, device)
        self.students[name] = student
        self.log("note", student=name, detail=f"student added ({device})")
        return student

    def _watch(self, student, page):
        """Record every /api/ request the page sends, with its reply."""

        def on_request(request):
            path = re.sub(r"^https?://[^/]+", "", request.url).split("?")[0]
            if not path.startswith("/api/"):
                return
            self._req_counter += 1
            request._harness_id = self._req_counter
            body = None
            if request.post_data:
                try:
                    body = json.loads(request.post_data)
                except ValueError:
                    body = request.post_data
            self.log(
                "request", student=student.name, req_id=self._req_counter, method=request.method, path=path, body=body
            )

        async def read_response(response, req_id):
            try:
                text = await response.text()
                try:
                    body = json.loads(text)
                except ValueError:
                    body = text[:500]
            except Exception as error:
                body = f"<unreadable: {error}>"
            self.log("response", student=student.name, req_id=req_id, status=response.status, body=body)

        def on_response(response):
            req_id = getattr(response.request, "_harness_id", None)
            if req_id is not None:
                asyncio.ensure_future(read_response(response, req_id))

        def on_failed(request):
            req_id = getattr(request, "_harness_id", None)
            if req_id is not None:
                self.log(
                    "request_failed", student=student.name, req_id=req_id, detail=f"{request.url} {request.failure}"
                )

        page.on("request", on_request)
        page.on("response", on_response)
        page.on("requestfailed", on_failed)

    async def look(self, student):
        if student.page is None or student.page.is_closed():
            return {"text": "(no page open: use 'open')", "clickable": [], "inputs": []}
        try:
            return await student.page.evaluate(LOOK_JS)
        except Exception as error:
            return {"text": f"(page not readable: {error})", "clickable": [], "inputs": []}

    async def state(self, name):
        student = self.students[name]
        if student.page is None or student.page.is_closed():
            return {}
        try:
            return await student.page.evaluate(STATE_JS)
        except Exception:
            return {}

    async def command(self, name, cmd, arg=None, screenshot=True, settle=0.7):
        """Run one command for a student and record it as a step. Returns the step record."""
        if name not in self.students:
            raise KeyError(f"unknown student '{name}'")
        if cmd not in COMMANDS:
            raise ValueError(f"unknown command '{cmd}', use one of: {', '.join(COMMANDS)}")
        student = self.students[name]
        async with student.lock:
            student.step += 1
            number = student.step
            started = self.now()
            error = None
            result = ""
            try:
                result = await self._run(student, cmd, arg)
            except Exception as exc:
                error = str(exc).splitlines()[0][:300]
            if cmd not in ("wait", "look", "close") and settle:
                await asyncio.sleep(settle)
            screen = await self.look(student)
            shot = None
            if screenshot and student.page is not None and not student.page.is_closed():
                shot = f"shots/{name}-{number:03d}.png"
                try:
                    await student.page.screenshot(path=str(self.run_dir / shot))
                except Exception:
                    shot = None
            return self.log(
                "step",
                student=name,
                step=number,
                t_start=started,
                cmd=cmd,
                arg=arg,
                result=result,
                error=error,
                screen=screen["text"][:MAX_SCREEN],
                clickable=screen["clickable"],
                inputs=screen["inputs"],
                screenshot=shot,
            )

    async def _run(self, student, cmd, arg):
        if cmd == "open":
            if student.page is None or student.page.is_closed():
                student.page = await student.context.new_page()
                self._watch(student, student.page)
            await student.page.goto(self.base_url + "/")
            return "opened the quiz page"
        if cmd == "look":
            return "looked at the screen"
        if student.page is None or student.page.is_closed():
            if cmd == "wait":
                await asyncio.sleep(min(float(arg or 1), 90))
                return f"waited {arg} s (no page open)"
            raise RuntimeError("no page open: use 'open' first")
        page = student.page
        if cmd == "click":
            label = str(arg or "").strip()
            pattern = re.compile(r"^\s*" + re.escape(label) + r"\s*$")
            candidates = page.locator("button, .option, a").filter(has_text=pattern).locator("visible=true")
            if await candidates.count() == 0:
                candidates = page.locator("button, .option, a").filter(has_text=label).locator("visible=true")
            if await candidates.count() == 0:
                raise RuntimeError(f"nothing to click with the text '{label}'")
            await candidates.first.click(timeout=3000)
            return f"clicked '{label}'"
        if cmd == "type":
            field = page.locator("textarea:visible:enabled")
            if await field.count() == 0:
                field = page.locator("input[type=text]:visible:enabled, input:not([type]):visible:enabled")
            if await field.count() == 0:
                raise RuntimeError("no place to type on the screen")
            await field.first.fill(str(arg or ""))
            return f"typed '{arg}'"
        if cmd == "wait":
            seconds = min(float(arg or 1), 90)
            await asyncio.sleep(seconds)
            return f"waited {seconds:g} s"
        if cmd == "reload":
            await page.reload()
            return "reloaded the page"
        if cmd == "offline":
            seconds = min(float(arg or 5), 120)
            await student.context.set_offline(True)
            self.log("network", student=student.name, detail=f"offline for {seconds:g} s")

            async def back_online():
                await asyncio.sleep(seconds)
                await student.context.set_offline(False)
                self.log("network", student=student.name, detail="online again")

            student.offline_task = asyncio.ensure_future(back_online())
            return f"Wi-Fi off for {seconds:g} s (the command returns at once)"
        if cmd == "close":
            await page.close()
            return "closed the tab"
        raise ValueError(cmd)

    # Scripted students use exact selectors, but still go through command() for "click"
    async def click_selector(self, name, selector, screenshot=False):
        """Click an element by CSS selector, recorded as a click on its visible text."""
        student = self.students[name]
        label = (await student.page.locator(selector).first.inner_text()).strip()
        return await self.command(name, "click", label, screenshot=screenshot, settle=0.3)
