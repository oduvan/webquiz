"""Run one scenario: server, browser, teacher, scripted students, and the API the AI agents use.

    python -m harness.run normal-lesson [--no-agents]

It prints "READY <run_dir>" once the teacher has started the quiz. The AI
agent students (started by the Claude session) then use
`python -m harness.student <name> <command>`. When they are done, save each
agent's report as <run_dir>/agents/<name>.md and create <run_dir>/agents_done.
The run then waits for the server to finish its own time checks, stops
everything and writes <run_dir>/report.md.
"""

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import aiohttp
import yaml
from aiohttp import web

from harness import checks
from harness.classroom import Classroom, format_step
from harness.scenarios import SCENARIOS
from harness.scripted import scripted_student, teacher_start
from webquiz import time_limits

ROOT = Path(__file__).resolve().parent.parent
SERVER_PORT = 8199
API_PORT = 8198
MASTER_KEY = "harness"


def wait_for_port(port, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    raise RuntimeError(f"nothing listens on port {port}")


def start_server(run_dir, scenario):
    (run_dir / "quizzes").mkdir(parents=True)
    with open(run_dir / "quizzes" / scenario["quiz_file"], "w", encoding="utf-8") as f:
        yaml.safe_dump(scenario["quiz"], f, allow_unicode=True, sort_keys=False)
    config = {
        "server": {"port": SERVER_PORT},
        "paths": {
            "quizzes_dir": str(run_dir / "quizzes"),
            "logs_dir": str(run_dir / "logs"),
            "csv_dir": str(run_dir / "data"),
            "static_dir": str(run_dir / "static"),
        },
        "admin": {"master_key": MASTER_KEY},
    }
    with open(run_dir / "config.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True)
    log = open(run_dir / "server.log", "w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "webquiz.cli", "--config", str(run_dir / "config.yaml")],
        cwd=ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    wait_for_port(SERVER_PORT)
    return process


async def record_live_stats(classroom, stop):
    """Save every live stats message the teacher's screen would get."""
    url = f"ws://127.0.0.1:{SERVER_PORT}/ws/live-stats"
    try:
        await _record(classroom, stop, url)
    except Exception as error:
        classroom.log("note", detail=f"live stats recorder stopped: {error}")


async def _record(classroom, stop, url):
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(url) as ws:
            while not stop.is_set():
                try:
                    message = await asyncio.wait_for(ws.receive(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                if message.type != aiohttp.WSMsgType.TEXT:
                    break
                classroom.log("live", message=json.loads(message.data))


async def start_api(classroom):
    """The HTTP API behind `python -m harness.student`."""

    async def handle(request):
        data = await request.json()
        try:
            record = await classroom.command(data["student"], data["cmd"], data.get("arg"))
        except (KeyError, ValueError) as error:
            return web.Response(text=f"ERROR: {error}", status=400)
        return web.Response(text=format_step(record))

    app = web.Application()
    app.router.add_post("/cmd", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", API_PORT).start()
    return runner


def effective_limits(scenario, settings):
    """Per-question limits the running quiz uses (question id -> seconds), for the checks."""
    settings = settings or {}
    time_limit = settings.get("time_limit")
    parsed, _ = time_limits.parse_time_limit({"time_limit": time_limit} if time_limit else {})
    questions = [dict(q, id=i + 1) for i, q in enumerate(scenario["quiz"]["questions"])]
    return time_limits.question_limits(parsed, questions)


async def run(scenario, with_agents):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = ROOT / "harness" / "runs" / f"{stamp}-{scenario['name']}"
    run_dir.mkdir(parents=True)
    (run_dir / "agents").mkdir()
    server = start_server(run_dir, scenario)
    classroom = Classroom(f"http://127.0.0.1:{SERVER_PORT}", run_dir)
    stop = asyncio.Event()
    api = None
    try:
        await classroom.start()
        recorder = asyncio.ensure_future(record_live_stats(classroom, stop))
        settings = await teacher_start(classroom, scenario["quiz_file"], scenario["start_settings"], MASTER_KEY)

        agents = scenario["agents"] if with_agents else {}
        for name, agent in agents.items():
            await classroom.add_student(name, agent["device"])
        api = await start_api(classroom)

        meta = {
            "scenario": scenario["name"],
            "description": scenario["description"],
            "settings": settings,
            "limits": effective_limits(scenario, settings),
            "grace": time_limits.grace_seconds(),
            "question_text": {i + 1: q["question"] for i, q in enumerate(scenario["quiz"]["questions"])},
            "scripted": {
                name: {str(k): list(v) for k, v in plan.items()} for name, plan in scenario["scripted"].items()
            },
            "agents": agents,
        }
        (run_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        (run_dir / "READY").write_text("ready\n")
        print(f"READY {run_dir}", flush=True)

        started = time.monotonic()
        deadline = started + scenario["max_seconds"]
        for name in scenario["scripted"]:
            await classroom.add_student(name)
        students = [
            scripted_student(classroom, name, plan, scenario["answers"], deadline)
            for name, plan in scenario["scripted"].items()
        ]
        await asyncio.gather(*students)
        print("Scripted students finished.", flush=True)

        while agents and not (run_dir / "agents_done").exists() and time.monotonic() < deadline:
            await asyncio.sleep(2)
        while time.monotonic() < started + scenario["finish_after"]:
            await asyncio.sleep(1)
        await asyncio.sleep(time_limits.grace_seconds() + 7)  # server time checks and the 5 s CSV flush
    finally:
        stop.set()
        if api:
            await api.cleanup()
        await classroom.stop()
        server.terminate()
        server.wait(timeout=10)
    found = checks.analyze(run_dir)
    print(f"DONE {run_dir} — {found} problem(s) in the data checks. See report.md and timelines/.", flush=True)
    return run_dir


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenario", choices=sorted(SCENARIOS))
    parser.add_argument("--no-agents", action="store_true", help="run only the scripted students")
    args = parser.parse_args()
    if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ and Path("/opt/pw-browsers").exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/opt/pw-browsers"  # a shared browser install, if there is one
    asyncio.run(run(SCENARIOS[args.scenario], with_agents=not args.no_agents))


if __name__ == "__main__":
    main()
