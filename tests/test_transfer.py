"""Unit tests for file transfer between WebQuiz servers (webquiz/transfer.py).

Two TransferManager instances act as two servers. A small aiohttp app plays
the tunnel server: it routes "/start/{name}/api/transfer/..." to the manager
with that socket name, and answers 502 for unknown names like nginx does when
the socket file is missing.
"""

import hashlib
import os
from datetime import datetime, timedelta

import httpx
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from webquiz import transfer as transfer_module
from webquiz.transfer import (
    TransferError,
    TransferManager,
    is_allowed_file,
    is_valid_server_name,
    quiz_media_files,
    rewrite_quiz_media,
)


class Machine:
    """One WebQuiz server with its own directories"""

    def __init__(self, root, name, tunnel):
        self.name = name
        self.tunnel = tunnel
        self.online = True
        self.dirs = {kind: str(root / name / kind) for kind in ("quizzes", "logs", "csv", "images", "attachments")}
        for path in self.dirs.values():
            os.makedirs(path)
        self.messages = []
        self.files_in_use = []
        self.manager = TransferManager(
            get_directories=lambda: self.dirs,
            get_endpoint=lambda: (self.tunnel.base_url, self.name) if self.online else None,
            notify=self._notify,
            get_files_in_use=lambda: self.files_in_use,
        )

    async def _notify(self, message):
        self.messages.append(message)

    def write(self, kind, filename, content):
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(os.path.join(self.dirs[kind], filename), mode) as f:
            f.write(content)

    def read(self, kind, filename):
        with open(os.path.join(self.dirs[kind], filename)) as f:
            return f.read()

    def files(self, kind):
        return sorted(os.listdir(self.dirs[kind]))


class FakeTunnelServer:
    def __init__(self):
        self.machines = {}
        self.base_url = None

    def _manager(self, request):
        machine = self.machines.get(request.match_info["name"])
        if machine is None or not machine.online:
            raise web.HTTPBadGateway()
        return machine.manager

    async def offer(self, request):
        return await self._manager(request).handle_offer(request)

    async def download(self, request):
        return await self._manager(request).handle_download(request)

    async def result(self, request):
        return await self._manager(request).handle_result(request)

    def app(self):
        app = web.Application()
        app.router.add_post("/start/{name}/api/transfer/offer", self.offer)
        app.router.add_get("/start/{name}/api/transfer/download/{token}/{type}/{filename}", self.download)
        app.router.add_post("/start/{name}/api/transfer/result", self.result)
        return app


@pytest.fixture
async def tunnel(tmp_path):
    fake = FakeTunnelServer()
    server = TestServer(fake.app())
    await server.start_server()
    fake.base_url = str(server.make_url("/start"))
    fake.add = lambda name: fake.machines.setdefault(name, Machine(tmp_path, name, fake))
    yield fake
    await server.close()


@pytest.fixture
def machines(tunnel):
    return tunnel.add("room-a"), tunnel.add("room-b")


async def send(sender, receiver, files):
    await sender.manager.send_offer(receiver.name, files)
    requests = receiver.manager.list_incoming()
    assert len(requests) == 1
    return requests[0]


# ----- Name and file validation -----


def test_server_name_validation():
    assert is_valid_server_name("room-12")
    assert is_valid_server_name("Teacher_PC.2")
    assert not is_valid_server_name("")
    assert not is_valid_server_name("../x")
    assert not is_valid_server_name("a/b")
    assert not is_valid_server_name(".hidden")
    assert not is_valid_server_name("a..b")
    assert not is_valid_server_name("x" * 65)
    assert not is_valid_server_name(None)


def test_allowed_files():
    assert is_allowed_file("quizzes", "math.yaml")
    assert is_allowed_file("quizzes", "math.YML")
    assert is_allowed_file("logs", "0001.log")
    assert is_allowed_file("csv", "results.csv")
    assert not is_allowed_file("quizzes", "math.yaml.backup")
    assert not is_allowed_file("logs", "0001.csv")
    assert not is_allowed_file("static", "index.html")
    assert not is_allowed_file("quizzes", "../math.yaml")
    assert not is_allowed_file("quizzes", "sub\\math.yaml")
    assert not is_allowed_file("quizzes", ".math.yaml")
    assert not is_allowed_file("quizzes", "<img src=x onerror=alert(1)>.yaml")
    assert not is_allowed_file("quizzes", "a:b.yaml")
    assert not is_allowed_file("quizzes", "a\nb.yaml")
    assert not is_allowed_file("quizzes", None)
    assert is_allowed_file("quizzes", "Математика 5 клас.yaml")
    assert is_allowed_file("images", "map.PNG")
    assert not is_allowed_file("images", "map.html")
    assert is_allowed_file("attachments", "data.xlsx")
    assert is_allowed_file("attachments", "README")
    assert not is_allowed_file("attachments", "../data.xlsx")


# ----- Full flow -----


async def test_accept_downloads_all_files(machines):
    a, b = machines
    a.write("quizzes", "math.yaml", "title: Math\n")
    a.write("logs", "0001.log", "log line\n")
    a.write("csv", "results.csv", "a,b\n1,2\n")

    request = await send(
        a,
        b,
        [
            {"type": "quizzes", "name": "math.yaml"},
            {"type": "logs", "name": "0001.log"},
            {"type": "csv", "name": "results.csv"},
        ],
    )
    assert request["from"] == "room-a"
    assert [f["size"] for f in request["files"]] == [12, 9, 8]
    stored = next(iter(b.manager.incoming.values()))
    assert stored["files"][0]["sha256"] == hashlib.sha256(b"title: Math\n").hexdigest()
    assert [f["case"] for f in request["files"]] == ["new", "new", "new"]
    # Logs and CSV files are saved with the sender name
    assert [f["target"] for f in request["files"]] == ["math.yaml", "room-a_0001.log", "room-a_results.csv"]
    assert "token" not in request
    assert b.messages[-1]["type"] == "transfer_request"

    result = await b.manager.accept(request["id"])

    assert result["failed"] == []
    assert [f["saved_as"] for f in result["saved"]] == ["math.yaml", "room-a_0001.log", "room-a_results.csv"]
    assert b.read("quizzes", "math.yaml") == "title: Math\n"
    assert b.read("logs", "room-a_0001.log") == "log line\n"
    assert b.read("csv", "room-a_results.csv") == "a,b\n1,2\n"
    assert b.manager.list_incoming() == []
    assert b.messages[-1] == {"type": "transfer_request_removed", "id": request["id"]}

    # The sender learns the result and stops serving the files
    offer = a.manager.get_state()["outgoing"][0]
    assert offer["status"] == "accepted"
    assert a.messages[-1]["type"] == "transfer_result"
    token = next(iter(a.manager.outgoing))
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{a.tunnel.base_url}/room-a/api/transfer/download/{token}/quizzes/math.yaml")
    assert response.status_code == 404


def plan_of(request, name):
    return next(f for f in request["files"] if f["name"] == name)


async def test_cases_and_default_actions(machines):
    """Every incoming file gets a case and a safe default action."""
    a, b = machines
    for name, content in (("same.yaml", "x"), ("diff.yaml", "new"), ("active.yaml", "a"), ("fresh.yaml", "f")):
        a.write("quizzes", name, content)
    b.write("quizzes", "same.yaml", "x")
    b.write("quizzes", "diff.yaml", "old")
    b.write("quizzes", "active.yaml", "b")
    b.files_in_use = [None, os.path.join(b.dirs["quizzes"], "active.yaml")]

    files = [{"type": "quizzes", "name": n} for n in ("same.yaml", "diff.yaml", "active.yaml", "fresh.yaml")]
    request = await send(a, b, files)

    expected = {
        "same.yaml": ("same", ["replace", "rename", "skip"], "skip"),
        "diff.yaml": ("different", ["replace", "rename", "skip"], "rename"),
        "active.yaml": ("in_use", ["rename", "skip"], "rename"),
        "fresh.yaml": ("new", ["save", "rename", "skip"], "save"),
    }
    for name, (case, actions, default) in expected.items():
        plan = plan_of(request, name)
        assert (plan["case"], plan["actions"], plan["default_action"]) == (case, actions, default), name
        assert plan["suggested_name"] == f"room-a_{name}"

    result = await b.manager.accept(request["id"])

    assert {f["name"]: f["saved_as"] for f in result["saved"]} == {
        "diff.yaml": "room-a_diff.yaml",
        "active.yaml": "room-a_active.yaml",
        "fresh.yaml": "fresh.yaml",
    }
    assert [f["name"] for f in result["skipped"]] == ["same.yaml"]
    assert b.read("quizzes", "diff.yaml") == "old"
    assert b.read("quizzes", "active.yaml") == "b"
    assert b.files("quizzes") == ["active.yaml", "diff.yaml", "fresh.yaml", "room-a_active.yaml", "room-a_diff.yaml", "same.yaml"]


async def test_suggested_names_never_overwrite(machines):
    a, b = machines
    a.write("quizzes", "math.yaml", "new")
    a.write("logs", "0001.log", "new log")
    b.write("quizzes", "math.yaml", "old")
    b.write("quizzes", "room-a_math.yaml", "older")
    b.write("logs", "room-a_0001.log", "old log")

    files = [{"type": "quizzes", "name": "math.yaml"}, {"type": "logs", "name": "0001.log"}]
    request = await send(a, b, files)
    assert plan_of(request, "math.yaml")["suggested_name"] == "room-a_math_2.yaml"
    assert plan_of(request, "0001.log")["suggested_name"] == "room-a_0001_2.log"

    result = await b.manager.accept(request["id"])
    assert [f["saved_as"] for f in result["saved"]] == ["room-a_math_2.yaml", "room-a_0001_2.log"]
    assert b.read("quizzes", "math.yaml") == "old"
    assert b.read("quizzes", "room-a_math.yaml") == "older"
    assert b.read("logs", "room-a_0001.log") == "old log"


async def test_admin_chooses_replace_rename_skip(machines):
    a, b = machines
    a.write("quizzes", "math.yaml", "new math")
    a.write("quizzes", "geo.yaml", "new geo")
    a.write("logs", "0001.log", "log")
    a.write("csv", "results.csv", "a,b")
    b.write("quizzes", "math.yaml", "old math")

    request = await send(
        a,
        b,
        [
            {"type": "quizzes", "name": "math.yaml"},
            {"type": "quizzes", "name": "geo.yaml"},
            {"type": "logs", "name": "0001.log"},
            {"type": "csv", "name": "results.csv"},
        ],
    )
    result = await b.manager.accept(
        request["id"],
        [
            {"type": "quizzes", "name": "math.yaml", "action": "replace"},
            {"type": "quizzes", "name": "geo.yaml", "action": "rename", "new_name": "Географія 7.yaml"},
            {"type": "logs", "name": "0001.log", "action": "skip"},
            # results.csv: no choice, default (save as room-a_results.csv)
        ],
    )

    assert result["failed"] == []
    assert [(f["name"], f["action"], f["saved_as"]) for f in result["saved"]] == [
        ("math.yaml", "replace", "math.yaml"),
        ("geo.yaml", "rename", "Географія 7.yaml"),
        ("results.csv", "save", "room-a_results.csv"),
    ]
    assert [(f["name"], f["action"]) for f in result["skipped"]] == [("0001.log", "skip")]
    assert b.read("quizzes", "math.yaml") == "new math"
    assert b.read("quizzes", "Географія 7.yaml") == "new geo"
    assert b.files("logs") == []
    assert a.manager.get_state()["outgoing"][0]["status"] == "accepted"


@pytest.mark.parametrize(
    "choice, message",
    [
        ({"name": "active.yaml", "action": "replace"}, "not possible"),
        ({"name": "fresh.yaml", "action": "replace"}, "not possible"),
        ({"name": "diff.yaml", "action": "save"}, "not possible"),
        ({"name": "diff.yaml", "action": "delete"}, "not possible"),
        ({"name": "fresh.yaml", "action": "rename", "new_name": "diff.yaml"}, "already exists"),
        ({"name": "fresh.yaml", "action": "rename", "new_name": "fresh.txt"}, "not a valid name"),
        ({"name": "fresh.yaml", "action": "rename", "new_name": "../x.yaml"}, "not a valid name"),
        ({"name": "diff.yaml", "action": "rename", "new_name": "fresh.yaml"}, "chosen for two files"),
    ],
)
async def test_invalid_choices_keep_request_open(machines, choice, message):
    a, b = machines
    for name in ("diff.yaml", "active.yaml", "fresh.yaml"):
        a.write("quizzes", name, "from a")
    b.write("quizzes", "diff.yaml", "b")
    b.write("quizzes", "active.yaml", "b")
    b.files_in_use = [os.path.join(b.dirs["quizzes"], "active.yaml")]
    files = [{"type": "quizzes", "name": n} for n in ("diff.yaml", "active.yaml", "fresh.yaml")]
    request = await send(a, b, files)

    with pytest.raises(TransferError) as error:
        await b.manager.accept(request["id"], [{"type": "quizzes", **choice}])

    assert error.value.status == 400
    assert message in error.value.message
    assert b.files("quizzes") == ["active.yaml", "diff.yaml"]  # nothing downloaded
    assert [r["id"] for r in b.manager.list_incoming()] == [request["id"]]  # admin can choose again
    assert a.manager.get_state()["outgoing"][0]["status"] == "waiting"


async def test_file_used_by_server_cannot_be_replaced_during_download(machines):
    """Choices are checked again right before a file is saved."""
    a, b = machines
    a.write("quizzes", "diff.yaml", "from a")
    b.write("quizzes", "diff.yaml", "b")
    request = await send(a, b, [{"type": "quizzes", "name": "diff.yaml"}])
    original_build_plan = b.manager._build_plan

    def build_plan_then_start_using(request, choices):
        plan = original_build_plan(request, choices)
        b.files_in_use = [os.path.join(b.dirs["quizzes"], "diff.yaml")]
        return plan

    b.manager._build_plan = build_plan_then_start_using
    result = await b.manager.accept(request["id"], [{"type": "quizzes", "name": "diff.yaml", "action": "replace"}])

    assert "used by the running server" in result["failed"][0]["error"]
    assert b.read("quizzes", "diff.yaml") == "b"


QUIZ_WITH_MEDIA = """# Geography quiz
title: Geography
questions:
- question: Where is Kyiv?
  image: "/imgs/map.png"  # main map
  options: ["/imgs/a.png", "/imgs/b.png", "Lviv"]
  correct_answer: 0
- question: Open the table
  file: data.xlsx
  options: ["1", "2"]
  correct_answer: 1
- question: Read the notes
  file: /attach/notes.pdf
  image: /imgs/missing.png
  options: ["yes", "no"]
  correct_answer: 0
"""


def write_quiz_with_media(machine):
    machine.write("quizzes", "geo.yaml", QUIZ_WITH_MEDIA)
    for name in ("map.png", "a.png", "b.png"):
        machine.write("images", name, f"image {name}".encode())
    machine.write("attachments", "data.xlsx", b"table")
    machine.write("attachments", "notes.pdf", b"notes")


def test_quiz_media_files(tmp_path):
    path = tmp_path / "geo.yaml"
    path.write_text(QUIZ_WITH_MEDIA)
    assert quiz_media_files(str(path)) == [
        ("images", "map.png"),
        ("images", "a.png"),
        ("images", "b.png"),
        ("attachments", "data.xlsx"),
        ("images", "missing.png"),
        ("attachments", "notes.pdf"),
    ]

    path.write_text("questions:\n- image: /imgs/sub/x.png\n  file: ../secret.txt\n  options: [/imgs/ok.png]\n")
    assert quiz_media_files(str(path)) == [("images", "ok.png")]

    path.write_text("questions: [unclosed")
    assert quiz_media_files(str(path)) == []
    assert quiz_media_files(str(tmp_path / "missing.yaml")) == []


def test_rewrite_quiz_media_keeps_comments(tmp_path):
    path = tmp_path / "geo.yaml"
    path.write_text(QUIZ_WITH_MEDIA)

    changed = rewrite_quiz_media(
        str(path),
        {("images", "map.png"): "room-a_map.png", ("attachments", "notes.pdf"): "room-a_notes.pdf"},
    )

    text = path.read_text()
    assert changed
    assert '"/imgs/room-a_map.png"' in text
    assert "# main map" in text
    assert "/attach/room-a_notes.pdf" in text
    assert "# Geography quiz" in text
    assert '"/imgs/a.png"' in text
    assert "file: data.xlsx" in text
    assert not rewrite_quiz_media(str(path), {("images", "other.png"): "x.png"})


async def test_quiz_is_sent_with_its_images_and_attachments(machines):
    a, b = machines
    write_quiz_with_media(a)

    request = await send(a, b, [{"type": "quizzes", "name": "geo.yaml"}])

    # missing.png does not exist on the sender, so it is not offered
    assert [(f["type"], f["name"]) for f in request["files"]] == [
        ("quizzes", "geo.yaml"),
        ("images", "map.png"),
        ("images", "a.png"),
        ("images", "b.png"),
        ("attachments", "data.xlsx"),
        ("attachments", "notes.pdf"),
    ]

    result = await b.manager.accept(request["id"])

    assert result["failed"] == []
    assert b.read("quizzes", "geo.yaml") == QUIZ_WITH_MEDIA  # no renames, quiz unchanged
    assert b.files("images") == ["a.png", "b.png", "map.png"]
    assert b.files("attachments") == ["data.xlsx", "notes.pdf"]
    assert b.read("images", "map.png") == "image map.png"


async def test_identical_images_are_skipped_by_default(machines):
    a, b = machines
    write_quiz_with_media(a)
    b.write("images", "map.png", b"image map.png")

    request = await send(a, b, [{"type": "quizzes", "name": "geo.yaml"}])
    assert plan_of(request, "map.png")["case"] == "same"
    result = await b.manager.accept(request["id"])

    assert [f["name"] for f in result["skipped"]] == ["map.png"]
    assert sorted(f["saved_as"] for f in result["saved"]) == ["a.png", "b.png", "data.xlsx", "geo.yaml", "notes.pdf"]
    assert b.files("images") == ["a.png", "b.png", "map.png"]
    assert b.read("quizzes", "geo.yaml") == QUIZ_WITH_MEDIA


async def test_renamed_image_by_choice_updates_quiz(machines):
    a, b = machines
    write_quiz_with_media(a)
    request = await send(a, b, [{"type": "quizzes", "name": "geo.yaml"}])

    await b.manager.accept(request["id"], [{"type": "images", "name": "a.png", "action": "rename", "new_name": "circle.png"}])

    quiz = b.read("quizzes", "geo.yaml")
    assert '"/imgs/circle.png"' in quiz
    assert '"/imgs/b.png"' in quiz
    assert b.files("images") == ["b.png", "circle.png", "map.png"]


async def test_skipped_image_keeps_quiz_reference(machines):
    a, b = machines
    write_quiz_with_media(a)
    b.write("images", "map.png", b"receiver map")
    request = await send(a, b, [{"type": "quizzes", "name": "geo.yaml"}])

    await b.manager.accept(request["id"], [{"type": "images", "name": "map.png", "action": "skip"}])

    assert '"/imgs/map.png"' in b.read("quizzes", "geo.yaml")
    assert b.read("images", "map.png") == "receiver map"


async def test_different_images_get_new_names_and_quiz_points_to_them(machines):
    a, b = machines
    write_quiz_with_media(a)
    b.write("images", "map.png", b"another map")
    b.write("attachments", "notes.pdf", b"other notes")
    b.write("quizzes", "geo.yaml", "title: Old geography\n")

    result = await b.manager.accept((await send(a, b, [{"type": "quizzes", "name": "geo.yaml"}]))["id"])

    saved = {f["name"]: f["saved_as"] for f in result["saved"]}
    assert saved == {
        "geo.yaml": "room-a_geo.yaml",
        "map.png": "room-a_map.png",
        "a.png": "a.png",
        "b.png": "b.png",
        "data.xlsx": "data.xlsx",
        "notes.pdf": "room-a_notes.pdf",
    }
    # Files of the receiver are untouched
    assert b.read("images", "map.png") == "another map"
    assert b.read("attachments", "notes.pdf") == "other notes"
    assert b.read("quizzes", "geo.yaml") == "title: Old geography\n"
    # The received quiz points to the received files
    quiz = b.read("quizzes", "room-a_geo.yaml")
    assert '"/imgs/room-a_map.png"' in quiz
    assert "file: /attach/room-a_notes.pdf" in quiz
    assert '"/imgs/a.png"' in quiz
    assert b.read("images", "room-a_map.png") == "image map.png"


async def test_media_limit_counts_images(machines, monkeypatch):
    a, b = machines
    write_quiz_with_media(a)
    monkeypatch.setattr(transfer_module, "MAX_FILES_PER_OFFER", 3)
    with pytest.raises(TransferError) as error:
        await a.manager.send_offer("room-b", [{"type": "quizzes", "name": "geo.yaml"}])
    assert "images and attachments" in error.value.message


async def test_reject_tells_sender_and_saves_nothing(machines):
    a, b = machines
    a.write("quizzes", "math.yaml", "x")
    request = await send(a, b, [{"type": "quizzes", "name": "math.yaml"}])

    await b.manager.reject(request["id"])

    assert b.files("quizzes") == []
    assert b.manager.list_incoming() == []
    assert a.manager.get_state()["outgoing"][0]["status"] == "rejected"
    with pytest.raises(TransferError) as error:
        await b.manager.accept(request["id"])
    assert error.value.status == 404


async def test_sender_offline_after_offer(machines):
    a, b = machines
    a.write("quizzes", "math.yaml", "x")
    request = await send(a, b, [{"type": "quizzes", "name": "math.yaml"}])

    a.online = False
    result = await b.manager.accept(request["id"])

    assert result["saved"] == []
    assert "not online" in result["failed"][0]["error"]
    assert b.files("quizzes") == []  # no temporary files left


async def test_fake_offer_cannot_deliver_files(machines, tunnel):
    """A stranger can post an offer, but B downloads only from the named server with its token."""
    a, b = machines
    a.write("quizzes", "math.yaml", "x")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{tunnel.base_url}/room-b/api/transfer/offer",
            json={"from": "room-a", "token": "f" * 43, "files": [{"type": "quizzes", "name": "math.yaml"}]},
        )
    assert response.status_code == 202

    result = await b.manager.accept(b.manager.list_incoming()[0]["id"])

    assert result["saved"] == []
    assert result["failed"][0]["error"] == "The sender does not offer this file anymore"
    assert b.files("quizzes") == []


async def test_download_only_offered_files_with_token(machines, tunnel):
    a, b = machines
    a.write("quizzes", "math.yaml", "x")
    a.write("quizzes", "secret.yaml", "y")
    await send(a, b, [{"type": "quizzes", "name": "math.yaml"}])
    token = next(iter(a.manager.outgoing))
    url = f"{tunnel.base_url}/room-a/api/transfer/download"

    async with httpx.AsyncClient() as client:
        assert (await client.get(f"{url}/{token}/quizzes/math.yaml")).status_code == 200
        assert (await client.get(f"{url}/{token}/quizzes/secret.yaml")).status_code == 404
        assert (await client.get(f"{url}/{'x' * 43}/quizzes/math.yaml")).status_code == 404
        assert (await client.get(f"{url}/{token}/logs/math.yaml")).status_code == 404


async def test_expired_offer(machines):
    a, b = machines
    a.write("quizzes", "math.yaml", "x")
    request = await send(a, b, [{"type": "quizzes", "name": "math.yaml"}])
    offer = next(iter(a.manager.outgoing.values()))
    offer["created"] -= transfer_module.OFFER_LIFETIME + timedelta(seconds=1)

    result = await b.manager.accept(request["id"])

    assert result["saved"] == []
    assert a.manager.get_state()["outgoing"][0]["status"] == "expired"


async def test_old_incoming_requests_are_removed(machines):
    a, b = machines
    a.write("quizzes", "math.yaml", "x")
    await send(a, b, [{"type": "quizzes", "name": "math.yaml"}])
    request = next(iter(b.manager.incoming.values()))
    request["received"] = datetime.now() - transfer_module.OFFER_LIFETIME - timedelta(seconds=1)

    assert b.manager.list_incoming() == []


async def test_file_size_limit(machines, monkeypatch):
    a, b = machines
    a.write("logs", "0001.log", "x" * 100)
    request = await send(a, b, [{"type": "logs", "name": "0001.log"}])
    monkeypatch.setattr(transfer_module, "MAX_FILE_SIZE", 10)

    result = await b.manager.accept(request["id"])

    assert result["saved"] == []
    assert "larger" in result["failed"][0]["error"]
    assert b.files("logs") == []


# ----- Sender errors -----


async def test_send_requires_tunnel(machines):
    a, b = machines
    a.online = False
    with pytest.raises(TransferError) as error:
        await a.manager.send_offer("room-b", [{"type": "quizzes", "name": "math.yaml"}])
    assert error.value.status == 409


async def test_send_to_unknown_server(machines):
    a, b = machines
    a.write("quizzes", "math.yaml", "x")
    with pytest.raises(TransferError) as error:
        await a.manager.send_offer("room-x", [{"type": "quizzes", "name": "math.yaml"}])
    assert "not online" in error.value.message
    assert a.manager.outgoing == {}


@pytest.mark.parametrize(
    "target, files, message",
    [
        ("../x", [{"type": "quizzes", "name": "math.yaml"}], "Invalid server name"),
        ("room-a", [{"type": "quizzes", "name": "math.yaml"}], "name of this server"),
        ("room-b", [], "No files selected"),
        ("room-b", "math.yaml", "No files selected"),
        ("room-b", [{"type": "static", "name": "math.yaml"}], "cannot be transferred"),
        ("room-b", [{"type": "quizzes", "name": "../math.yaml"}], "cannot be transferred"),
        ("room-b", [{"type": "quizzes", "name": "missing.yaml"}], "File not found"),
    ],
)
async def test_send_validation(machines, target, files, message):
    a, b = machines
    a.write("quizzes", "math.yaml", "x")
    with pytest.raises(TransferError) as error:
        await a.manager.send_offer(target, files)
    assert message in error.value.message
    assert b.manager.list_incoming() == []


async def test_send_skips_duplicate_files(machines):
    a, b = machines
    a.write("quizzes", "math.yaml", "x")
    file = {"type": "quizzes", "name": "math.yaml"}
    request = await send(a, b, [file, file])
    assert len(request["files"]) == 1


# ----- Receiver validation -----


@pytest.mark.parametrize(
    "data, message",
    [
        ("not a dict", "Invalid request"),
        ({"from": "../x", "token": "t" * 43, "files": [{"type": "logs", "name": "a.log"}]}, "Invalid sender"),
        ({"from": "room-b", "token": "t" * 43, "files": [{"type": "logs", "name": "a.log"}]}, "Invalid sender"),
        ({"from": "room-a", "token": "short", "files": [{"type": "logs", "name": "a.log"}]}, "Invalid token"),
        ({"from": "room-a", "token": "t" * 43, "files": [{"type": "logs", "name": "../a.log"}]}, "cannot be"),
        ({"from": "room-a", "token": "t" * 43, "files": []}, "No files"),
    ],
)
def test_incoming_validation(machines, data, message):
    a, b = machines
    with pytest.raises(TransferError) as error:
        b.manager.add_incoming(data)
    assert message in error.value.message


def test_incoming_ignores_invalid_checksum(machines):
    a, b = machines
    files = [{"type": "logs", "name": "a.log", "size": 1, "sha256": "not-a-checksum"}]
    request = b.manager.add_incoming({"from": "room-a", "token": "t" * 43, "files": files})
    assert request["files"][0]["sha256"] is None


def test_incoming_requires_tunnel(machines):
    a, b = machines
    b.online = False
    with pytest.raises(TransferError) as error:
        b.manager.add_incoming({"from": "room-a", "token": "t" * 43, "files": [{"type": "logs", "name": "a.log"}]})
    assert error.value.status == 409


def test_incoming_request_limit(machines):
    a, b = machines
    data = {"from": "room-a", "token": "t" * 43, "files": [{"type": "logs", "name": "a.log", "size": True}]}
    for _ in range(transfer_module.MAX_INCOMING_REQUESTS):
        request = b.manager.add_incoming(data)
    assert request["files"][0]["size"] == 0  # invalid size is ignored
    with pytest.raises(TransferError) as error:
        b.manager.add_incoming(data)
    assert error.value.status == 429


async def test_result_endpoint_validation(machines, tunnel):
    a, b = machines
    url = f"{tunnel.base_url}/room-a/api/transfer/result"
    async with httpx.AsyncClient() as client:
        assert (await client.post(url, content=b"not json")).status_code == 400
        assert (await client.post(url, json={"token": "x" * 43, "status": "hacked"})).status_code == 400
        assert (await client.post(url, json={"token": "x" * 43, "status": "accepted"})).status_code == 404


async def test_state(machines):
    a, b = machines
    a.write("quizzes", "math.yaml", "x")
    await send(a, b, [{"type": "quizzes", "name": "math.yaml"}])

    state = a.manager.get_state()
    assert state["available"] is True
    assert state["name"] == "room-a"
    assert state["outgoing"][0]["to"] == "room-b"
    assert state["outgoing"][0]["status"] == "waiting"
    assert "token" not in state["outgoing"][0]

    b.online = False
    assert b.manager.get_state()["available"] is False
    assert b.manager.get_state()["name"] is None
