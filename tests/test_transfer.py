"""Unit tests for file transfer between WebQuiz servers (webquiz/transfer.py).

Two TransferManager instances act as two servers. A small aiohttp app plays
the tunnel server: it routes "/start/{name}/api/transfer/..." to the manager
with that socket name, and answers 502 for unknown names like nginx does when
the socket file is missing.
"""

import os
from datetime import datetime, timedelta

import httpx
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from webquiz import transfer as transfer_module
from webquiz.transfer import TransferError, TransferManager, is_allowed_file, is_valid_server_name


class Machine:
    """One WebQuiz server with its own directories"""

    def __init__(self, root, name, tunnel):
        self.name = name
        self.tunnel = tunnel
        self.online = True
        self.dirs = {kind: str(root / name / kind) for kind in ("quizzes", "logs", "csv")}
        for path in self.dirs.values():
            os.makedirs(path)
        self.messages = []
        self.manager = TransferManager(
            get_directories=lambda: self.dirs,
            get_endpoint=lambda: (self.tunnel.base_url, self.name) if self.online else None,
            notify=self._notify,
        )

    async def _notify(self, message):
        self.messages.append(message)

    def write(self, kind, filename, content):
        with open(os.path.join(self.dirs[kind], filename), "w") as f:
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


async def test_existing_files_are_never_overwritten(machines):
    a, b = machines
    a.write("quizzes", "math.yaml", "new\n")
    a.write("logs", "0001.log", "new log\n")
    b.write("quizzes", "math.yaml", "old\n")
    b.write("logs", "room-a_0001.log", "old log\n")

    files = [{"type": "quizzes", "name": "math.yaml"}, {"type": "logs", "name": "0001.log"}]
    result = await b.manager.accept((await send(a, b, files))["id"])
    assert [f["saved_as"] for f in result["saved"]] == ["room-a_math.yaml", "room-a_0001_2.log"]

    result = await b.manager.accept((await send(a, b, files))["id"])
    assert [f["saved_as"] for f in result["saved"]] == ["room-a_math_2.yaml", "room-a_0001_3.log"]

    assert b.read("quizzes", "math.yaml") == "old\n"
    assert b.read("logs", "room-a_0001.log") == "old log\n"
    assert b.read("quizzes", "room-a_math_2.yaml") == "new\n"


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
