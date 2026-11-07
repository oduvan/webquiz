# First-Launch Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the first launch of a new install, `/admin/` sends the teacher to a `/setup/` page. There they type a tunnel server and a setup name to download and apply ready-made settings, and then set an admin password.

**Architecture:** The download, checks and config edits are pure functions in a new module, `webquiz/first_setup.py`. Three admin endpoints in `webquiz/server.py` call them, and the config is saved through a save-and-apply helper split out of `admin_update_config`. A new template, `webquiz/templates/setup.html`, drives the two steps. The tunnel server repository publishes `ansible/files/setup/<name>/webquiz.yaml` at `/setup/<name>/webquiz.yaml` on every subdomain.

**Tech Stack:** Python 3.9+, aiohttp, httpx, PyYAML, ruamel.yaml (round-trip), vanilla HTML/JS, pytest + pytest-xdist + Selenium; Ansible + nginx on the tunnel server.

**Spec:** `docs/superpowers/specs/2026-11-06-first-launch-setup-design.md`

## Global Constraints

- All Python commands run inside the venv: `source venv/bin/activate` (create with `python3 -m venv venv && source venv/bin/activate && pip install poetry && poetry install`).
- Tests are written first. Every change updates `CLAUDE.md`, `README.md`, `docs/uk/` and `docs/en/` (done in Task 7).
- UI works on phones: ≤768px, `width: 100%; max-width: …`.
- The setup page uses Ukrainian text and has dark/light theme support like the other pages (CSS variables on `:root` / `[data-theme="dark"]`, `localStorage` key `theme`).
- Every file write uses `flush()` + `os.fsync()`.
- The marker is the top-level key `setup_pending: true`.
- Allowed keys in the downloaded file are exactly `language`, `extra_answers_with_users_csv`, `registration`, `quizzes`, `checker_templates`. Everything else is ignored, including the whole `tunnel` section.
- Key paths written by the setup: `keys/id_ed25519.pub` and `keys/id_ed25519`, only when not set already.
- Setup name: only `a-z`, digits, `-` and `_`, 1 to 64 characters, lowercased.
- Server: a host name or an IPv4 address, lowercased. HTTPS for host names, HTTP for IP addresses.
- Download URL: `<protocol>://<server>/setup/<name>/webquiz.yaml`.
- Code style: black, line length 120 (project config).
- Test ports 8080-8087 come from `get_worker_port()`. Do not hard-code ports.
- Work on branch `claude/first-launch-setup-design` in `webquiz`, and on a new branch `claude/first-launch-setup` (from `master`) in `webquiz-tunnel-server`.

## Review Focus

- The teacher pastes the server as a link (`https://demo.webquiz.xyz/`). Expected: it works, because the leading `http://`/`https://` and a trailing `/` are stripped before the checks (Task 1 test `test_normalize_server_strips_scheme_and_slash`).
- The setup name has spaces around it or capital letters (` School1 `). Expected: it is trimmed and lowercased (Task 1 test `test_normalize_name_trims_and_lowercases`).
- The file is valid YAML but has bad values (`language: de`, `registration: "x"`). Expected: 422 `broken_file` with the validator's messages, and nothing is written (Task 5 test `test_setup_check_rejects_invalid_values`).
- Apply is clicked twice, or the browser retries it. Expected: both calls succeed, the config is the same after each, and the tunnel manager is replaced without errors (Task 5 test `test_setup_apply_twice_is_safe`).
- Finish is sent with an empty or whitespace-only password. Expected: 400, and the marker stays (Task 5 test `test_setup_finish_rejects_blank_password`).

---

### Task 1: Pure setup logic (`first_setup.py`) and round-trip config helpers

**Files:**
- Create: `webquiz/first_setup.py`
- Modify: `webquiz/config.py` (add the round-trip helpers at the end)
- Modify: `webquiz/tunnel.py:183-194` (extract the protocol rule)
- Test: `tests/test_first_setup.py`

**Interfaces:**
- Produces, in `webquiz/tunnel.py`: `get_server_protocol(server: str) -> str`. Returns `"http"` for an IP address and `"https"` otherwise. `TunnelManager` uses it in place of the inline code.
- Produces, in `webquiz/config.py`:
  - `load_config_document(content: str) -> CommentedMap`: round-trip load. Empty, invalid or non-mapping content gives an empty `CommentedMap`.
  - `dump_config_document(doc) -> str`: uses the same ruamel settings as `admin_update_config` today (`preserve_quotes=True`, `allow_unicode=True`, `indent(mapping=2, sequence=4, offset=2)`).
- Produces, in `webquiz/first_setup.py`:
  - Constants: `SETUP_MARKER_KEY = "setup_pending"`, `ALLOWED_SETUP_KEYS = ("language", "extra_answers_with_users_csv", "registration", "quizzes", "checker_templates")`, `DEFAULT_TUNNEL_PUBLIC_KEY = "keys/id_ed25519.pub"`, `DEFAULT_TUNNEL_PRIVATE_KEY = "keys/id_ed25519"`, `SETUP_BASE_URL_ENV = "WEBQUIZ_SETUP_BASE_URL"`.
  - `class SetupError(Exception)` with `__init__(self, kind: str, message: str, details: Optional[List[str]] = None)` and the attributes `kind`, `message`, `details`. Kinds: `invalid_server`, `invalid_name`, `not_found`, `connection`, `broken_file`.
  - `SETUP_ERROR_STATUS = {"invalid_server": 400, "invalid_name": 400, "not_found": 404, "connection": 502, "broken_file": 422}`.
  - `normalize_setup_server(server: str) -> str`: raises `SetupError("invalid_server", …)`.
  - `normalize_setup_name(name: str) -> str`: raises `SetupError("invalid_name", …)`.
  - `build_setup_url(server: str, name: str) -> str`.
  - `filter_setup_settings(data: Any) -> Tuple[Dict[str, Any], List[str]]`: returns `(allowed, ignored_keys_sorted)`.
  - `describe_setup_changes(allowed: Dict[str, Any], current: Dict[str, Any], server: str) -> List[Dict[str, Any]]`: returns one item `{"key", "value", "replaces"}` per allowed key, in `ALLOWED_SETUP_KEYS` order, then one for `"tunnel.server"`.
  - `apply_setup_to_document(doc, allowed: Dict[str, Any], server: str) -> None`.
  - `add_setup_marker(content: str) -> str`.
  - `remove_setup_marker(doc) -> None`.

- [ ] **Step 1: Write the failing tests** in `tests/test_first_setup.py`. These are plain unit tests with no server.

```python
import pytest
from webquiz.first_setup import (
    SetupError, normalize_setup_server, normalize_setup_name, build_setup_url,
    filter_setup_settings, describe_setup_changes, apply_setup_to_document,
    add_setup_marker, remove_setup_marker,
)
from webquiz.config import load_config_document, dump_config_document
from webquiz.tunnel import get_server_protocol

def test_get_server_protocol():
    assert get_server_protocol("192.168.1.5") == "http"
    assert get_server_protocol("demo.webquiz.xyz") == "https"

@pytest.mark.parametrize("raw,expected", [
    ("Demo.WebQuiz.xyz", "demo.webquiz.xyz"), ("192.168.1.5", "192.168.1.5"), ("localhost", "localhost")])
def test_normalize_server_valid(raw, expected):
    assert normalize_setup_server(raw) == expected

def test_normalize_server_strips_scheme_and_slash():
    assert normalize_setup_server(" https://demo.webquiz.xyz/ ") == "demo.webquiz.xyz"
    assert normalize_setup_server("http://192.168.1.5") == "192.168.1.5"

@pytest.mark.parametrize("raw", ["", "a/b", "a b", "user@host", "host:8080", "demo.webquiz.xyz/setup", "-bad.com", "::1"])
def test_normalize_server_invalid(raw):
    with pytest.raises(SetupError) as e:
        normalize_setup_server(raw)
    assert e.value.kind == "invalid_server"

def test_normalize_name_trims_and_lowercases():
    assert normalize_setup_name(" School1 ") == "school1"
    assert normalize_setup_name("a_b-c") == "a_b-c"

@pytest.mark.parametrize("raw", ["", "../x", "a/b", "a b", ".", "..", "x" * 65])
def test_normalize_name_invalid(raw):
    with pytest.raises(SetupError) as e:
        normalize_setup_name(raw)
    assert e.value.kind == "invalid_name"

def test_build_setup_url(monkeypatch):
    monkeypatch.delenv("WEBQUIZ_SETUP_BASE_URL", raising=False)
    assert build_setup_url("demo.webquiz.xyz", "school1") == "https://demo.webquiz.xyz/setup/school1/webquiz.yaml"
    assert build_setup_url("192.168.1.5", "school1") == "http://192.168.1.5/setup/school1/webquiz.yaml"
    monkeypatch.setenv("WEBQUIZ_SETUP_BASE_URL", "http://127.0.0.1:9999/base/")
    assert build_setup_url("demo.webquiz.xyz", "school1") == "http://127.0.0.1:9999/base/setup/school1/webquiz.yaml"

def test_filter_keeps_allowed_and_lists_ignored():
    allowed, ignored = filter_setup_settings({
        "language": "en", "registration": {"fields": ["Class"]}, "admin": {"master_key": "x"},
        "paths": {}, "tunnel": {"server": "evil"}, "something": 1})
    assert allowed == {"language": "en", "registration": {"fields": ["Class"]}}
    assert ignored == ["admin", "paths", "something", "tunnel"]

@pytest.mark.parametrize("data", ["User subdomain: demo\n", None, [1, 2], {"admin": {"master_key": "x"}}])
def test_filter_broken_file(data):
    with pytest.raises(SetupError) as e:
        filter_setup_settings(data)
    assert e.value.kind == "broken_file"

def test_describe_marks_replaced_keys():
    items = describe_setup_changes(
        {"language": "en", "registration": {"fields": ["Class"]}},
        {"registration": {"approve": True}, "language": None},
        "demo.webquiz.xyz")
    assert items == [
        {"key": "language", "value": "en", "replaces": False},
        {"key": "registration", "value": {"fields": ["Class"]}, "replaces": True},
        {"key": "tunnel.server", "value": "demo.webquiz.xyz", "replaces": False},
    ]

CONFIG_WITH_COMMENTS = """# my comment
registration:
  approve: true
  fields:
    - Old
tunnel:
  server: old.webquiz.xyz
  public_key: my.pub
  private_key: my
  socket_name: s1
  config:
    username: old
    socket_directory: /x
    base_url: https://old/
"""

def test_apply_replaces_keys_whole_and_edits_tunnel():
    doc = load_config_document(CONFIG_WITH_COMMENTS)
    apply_setup_to_document(doc, {"registration": {"fields": ["Class"]}}, "demo.webquiz.xyz")
    text = dump_config_document(doc)
    assert "# my comment" in text
    assert dict(doc["registration"]) == {"fields": ["Class"]}
    assert doc["tunnel"]["server"] == "demo.webquiz.xyz"
    assert doc["tunnel"]["public_key"] == "my.pub" and doc["tunnel"]["private_key"] == "my"
    assert doc["tunnel"]["socket_name"] == "s1"
    assert "config" not in doc["tunnel"]

def test_apply_sets_default_key_paths_when_missing():
    doc = load_config_document("language: uk\n")
    apply_setup_to_document(doc, {"language": "en"}, "demo.webquiz.xyz")
    assert doc["language"] == "en"
    assert dict(doc["tunnel"]) == {"server": "demo.webquiz.xyz",
                                   "public_key": "keys/id_ed25519.pub", "private_key": "keys/id_ed25519"}

def test_marker_add_and_remove():
    content = add_setup_marker("server:\n  port: 8080\n")
    assert "setup_pending: true" in content
    assert add_setup_marker(content) == content  # not added twice
    doc = load_config_document(content)
    remove_setup_marker(doc)
    assert "setup_pending" not in dump_config_document(doc)

def test_load_config_document_handles_bad_content():
    assert dict(load_config_document("")) == {}
    assert dict(load_config_document("just a string")) == {}
```

- [ ] **Step 2: Run the tests and check that they fail**

Run: `source venv/bin/activate && python -m pytest tests/test_first_setup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webquiz.first_setup'`.

- [ ] **Step 3: Implement `get_server_protocol` in `webquiz/tunnel.py`, and use it in the tunnel config download** (it replaces the `try: ipaddress.ip_address(...)` block at lines 183-192).

- [ ] **Step 4: Implement `load_config_document` / `dump_config_document` in `webquiz/config.py`**

- [ ] **Step 5: Implement `webquiz/first_setup.py`.** The pinned details:
  - `normalize_setup_server`:
    - Strip spaces, then strip one leading `http://` or `https://` and one trailing `/`, then lowercase.
    - Accept an IPv4 address (`ipaddress.IPv4Address`), or a host name matching `^(?=.{1,253}$)[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$`.
    - Anything else (IPv6 included) is `invalid_server`.
  - `normalize_setup_name`: strip, lowercase, then match `^[a-z0-9_-]{1,64}$`. `.` and `..` therefore fail.
  - `build_setup_url`: if the `WEBQUIZ_SETUP_BASE_URL` environment variable is set, use it with its trailing `/` removed as the base. Otherwise use `f"{get_server_protocol(server)}://{server}"`. Then add `/setup/{name}/webquiz.yaml`. The variable exists only so tests can point to a local fake server.
  - `filter_setup_settings`: anything other than a `dict` is `broken_file` ("The settings file is not a YAML mapping"). A dict with no allowed keys is `broken_file` ("The settings file has no settings the setup can apply"), and `details` lists the ignored keys.
  - `describe_setup_changes`: `replaces` is `True` when `current` has the key with a value that is not `None`. For `tunnel.server`, it is `True` when the current `tunnel.server` is set and is different from the new one.
  - `apply_setup_to_document`:
    - Each allowed key replaces `doc[key]` whole.
    - `doc["tunnel"]` is created as a `CommentedMap` if missing.
    - `tunnel.server = server`.
    - `public_key` / `private_key` are set to the defaults only when missing or empty.
    - `tunnel.config` is deleted. `socket_name` is not touched.
  - `add_setup_marker`: if the content already has a line starting with `setup_pending:`, return it unchanged. Otherwise add this block at the end:

```yaml

# Added by WebQuiz when it created this file. While it is true, /admin/ opens the
# first-launch setup page. The setup removes it when it is finished.
# Delete this line to skip the setup.
setup_pending: true
```

- [ ] **Step 6: Run the tests and check that they pass**

Run: `source venv/bin/activate && python -m pytest tests/test_first_setup.py tests/test_tunnel.py -v`
Expected: all PASS (`test_tunnel.py` shows that the protocol change broke nothing).

- [ ] **Step 7: Commit**

```bash
git add webquiz/first_setup.py webquiz/config.py webquiz/tunnel.py tests/test_first_setup.py
git commit -m "Add first-launch setup helpers: input checks, URL, filtering, config edits"
```

---

### Task 2: Download the settings file, and a fake settings server for tests

**Files:**
- Modify: `webquiz/first_setup.py`
- Modify: `tests/conftest.py` (add the `fake_setup_server` context manager, and add an `env` parameter to `custom_webquiz_server`)
- Test: `tests/test_first_setup.py`

**Interfaces:**
- Consumes: `build_setup_url`, `SetupError` (Task 1).
- Produces:
  - `async def fetch_setup_settings(server: str, name: str, timeout: float = 15.0) -> Dict[str, Any]` in `first_setup.py`. It returns the parsed YAML mapping before filtering. It raises:
    - `not_found` for 404;
    - `connection` for network errors, timeouts and any other status that is not 200 (redirects are not followed);
    - `broken_file` for bad YAML, a non-mapping, or a body larger than `MAX_SETUP_FILE_BYTES = 1_000_000`.
  - In `tests/conftest.py`:
    - `fake_setup_server(files: Dict[str, Union[str, bytes]]) -> ContextManager[str]` yields a base URL like `http://127.0.0.1:<free port>`. It serves `GET /setup/<name>/webquiz.yaml` with status 200 and the given body. Any other path gets 404. It is a `http.server.ThreadingHTTPServer` on port 0, in a daemon thread.
    - `custom_webquiz_server(config=None, quizzes=None, env=None)`: `env` is merged into the subprocess environment.

- [ ] **Step 1: Write the failing tests** (add to `tests/test_first_setup.py`; run the coroutines with `asyncio.run`).

```python
import asyncio
from conftest import fake_setup_server

def test_fetch_ok(monkeypatch):
    with fake_setup_server({"school1": "language: en\n"}) as base:
        monkeypatch.setenv("WEBQUIZ_SETUP_BASE_URL", base)
        assert asyncio.run(fetch_setup_settings("demo.webquiz.xyz", "school1")) == {"language": "en"}

@pytest.mark.parametrize("files,name,kind", [
    ({}, "missing", "not_found"),
    ({"bad": "a: [unclosed\n"}, "bad", "broken_file"),
    ({"big": "a: " + "x" * 1_000_001}, "big", "broken_file"),
])
def test_fetch_errors(monkeypatch, files, name, kind):
    with fake_setup_server(files) as base:
        monkeypatch.setenv("WEBQUIZ_SETUP_BASE_URL", base)
        with pytest.raises(SetupError) as e:
            asyncio.run(fetch_setup_settings("demo.webquiz.xyz", name))
        assert e.value.kind == kind

def test_fetch_connection_error(monkeypatch):
    with fake_setup_server({}) as base:
        pass  # server is closed now
    monkeypatch.setenv("WEBQUIZ_SETUP_BASE_URL", base)
    with pytest.raises(SetupError) as e:
        asyncio.run(fetch_setup_settings("demo.webquiz.xyz", "school1", timeout=2))
    assert e.value.kind == "connection"
```

- [ ] **Step 2: Run the tests and check that they fail**

Run: `source venv/bin/activate && python -m pytest tests/test_first_setup.py -k fetch -v`
Expected: FAIL with `ImportError: cannot import name 'fake_setup_server'`.

- [ ] **Step 3: Implement `fake_setup_server`, the `env` parameter, and `fetch_setup_settings`.** Use `httpx.AsyncClient(timeout=timeout, follow_redirects=False)`, as `tunnel.py` does. Parse the body with `yaml.safe_load`.

- [ ] **Step 4: Run the tests and check that they pass**

Run: `source venv/bin/activate && python -m pytest tests/test_first_setup.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add webquiz/first_setup.py tests/conftest.py tests/test_first_setup.py
git commit -m "Download the setup settings file; add a fake settings server for tests"
```

---

### Task 3: Marker on config creation, `setup_pending` in the config, no default password

**Files:**
- Modify: `webquiz/server.py:180-193` (`create_default_config_file`)
- Modify: `webquiz/server.py` (`_validate_config_data` near line 3233, and `apply_config_changes` near line 797)
- Modify: `webquiz/config.py` (`WebQuizConfig`, `load_config_from_yaml`)
- Modify: `webquiz/server_config.yaml.example` (comment out `master_key: a1`)
- Test: `tests/test_first_setup_marker.py`

**Interfaces:**
- Consumes: `add_setup_marker` (Task 1).
- Produces:
  - `WebQuizConfig.setup_pending: bool = False`. `load_config_from_yaml` sets it to `config_data.get("setup_pending") is True`.
  - `apply_config_changes` copies `new_config.setup_pending` into `self.config`.
  - The validator adds the error `"'setup_pending' must be a boolean"`.

- [ ] **Step 1: Write the failing tests**

```python
from pathlib import Path
from webquiz.server import create_default_config_file, TestingServer
from webquiz.config import load_config_from_yaml, WebQuizConfig

def test_created_config_has_marker_and_no_master_key(tmp_path):
    path = tmp_path / "webquiz.yaml"
    create_default_config_file(path)
    assert "setup_pending: true" in path.read_text(encoding="utf-8")
    config = load_config_from_yaml(str(path))
    assert config.setup_pending is True
    assert config.admin.master_key is None

def test_config_without_marker_is_not_pending(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("server:\n  port: 8080\n", encoding="utf-8")
    assert load_config_from_yaml(str(path)).setup_pending is False

def test_marker_string_is_not_pending(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("setup_pending: 'no'\n", encoding="utf-8")
    assert load_config_from_yaml(str(path)).setup_pending is False

def test_validator_checks_marker_type():
    server = TestingServer(WebQuizConfig())
    errors = []
    assert server._validate_config_data({"setup_pending": True}, errors) is True
    assert server._validate_config_data({"setup_pending": "yes"}, errors) is False
    assert "'setup_pending' must be a boolean" in errors
```

- [ ] **Step 2: Run the tests and check that they fail**

Run: `source venv/bin/activate && python -m pytest tests/test_first_setup_marker.py -v`
Expected: FAIL (`AttributeError: 'WebQuizConfig' object has no attribute 'setup_pending'`).

- [ ] **Step 3: Implement.** `create_default_config_file` writes `add_setup_marker(example_content)` with `flush()` + `os.fsync()`. In the example file, the line becomes `  # master_key: "your-secret-key"  # Set to allow admin login from other computers`.

- [ ] **Step 4: Run the new tests plus the config and CLI suites**

Run: `source venv/bin/activate && python -m pytest tests/test_first_setup_marker.py tests/test_config_loading.py tests/test_cli_directory_creation.py tests/test_config_management.py -v -n 4`
Expected: all PASS. If a CLI test expected `master_key: a1` or the exact example content, update that test to the new example.

- [ ] **Step 5: Commit**

```bash
git add webquiz/server.py webquiz/config.py webquiz/server_config.yaml.example tests/test_first_setup_marker.py tests/
git commit -m "Mark newly created configs for the first-launch setup; drop the default password"
```

---

### Task 4: Split the save-and-apply logic out of `admin_update_config`

This is a refactor with no change in behaviour. The existing config tests guard it.

**Files:**
- Modify: `webquiz/server.py:3556-3725` (`admin_update_config`)

**Interfaces:**
- Consumes: `load_config_document`, `dump_config_document` (Task 1).
- Produces, in `webquiz/server.py`:
  - `class ConfigSaveError(Exception)` with `__init__(self, status: int, payload: dict)`.
  - `async def TestingServer._save_and_apply_config(self, content: str) -> List[str]`. It does everything `admin_update_config` does today after the content is built:
    - parse with `yaml.safe_load` (failure: `ConfigSaveError(400, {"error": "Invalid YAML syntax: …"})`);
    - run `_validate_config_data` (failure: `ConfigSaveError(400, {"error": "Configuration validation failed", "errors": [...]})`);
    - keep the original file for rollback, then write with fsync;
    - reload, get `_config_requires_restart`, `apply_config_changes`, `restart_current_quiz`;
    - on failure, roll back and raise `ConfigSaveError(500, {"success": False, "error": "Failed to apply configuration: …. Changes rolled back.", "config_path": …})`.
  
  It returns `restart_reasons`.
  - `admin_update_config` keeps its request parsing and response building. The `{data}` merge loads and dumps with the Task 1 helpers, and keeps its per-key merge loop as it is.

- [ ] **Step 1: Run the guarding suites before the change**

Run: `source venv/bin/activate && python -m pytest tests/test_config_management.py tests/test_config_hot_reload.py tests/test_language.py tests/test_registration_disabled_fields.py -v -n 4`
Expected: all PASS (this is the baseline).

- [ ] **Step 2: Refactor** as described in Interfaces.

- [ ] **Step 3: Run the same suites again**

Expected: all PASS with the same count as Step 1.

- [ ] **Step 4: Commit**

```bash
git add webquiz/server.py
git commit -m "Split config save-and-apply out of the config endpoint for reuse"
```

---

### Task 5: Setup API, redirects and tunnel set-up

**Files:**
- Modify: `webquiz/server.py` (new methods on `TestingServer`, `serve_admin_page` near line 4131, routes near line 4384, `_load_templates` list near line 644)
- Create: `webquiz/templates/setup.html`. In this task it is a placeholder, so the route works; Task 6 fills it in.
- Test: `tests/test_setup_api.py`

**Interfaces:**
- Consumes: `normalize_setup_server`, `normalize_setup_name`, `build_setup_url`, `fetch_setup_settings`, `filter_setup_settings`, `describe_setup_changes`, `apply_setup_to_document`, `remove_setup_marker`, `SetupError`, `SETUP_ERROR_STATUS`, `load_config_document`, `dump_config_document`, `_save_and_apply_config`, `ConfigSaveError`.
- Produces:
  - `TestingServer._get_student_urls(self) -> List[str]`, taken from the URL loop in `serve_admin_page`, which then uses it.
  - `async def TestingServer._reinitialize_tunnel(self) -> None`: if a tunnel manager exists, disconnect it when connected and set it to `None`. Then `await self.initialize_tunnel()`.
  - `serve_admin_page`: first line raises `web.HTTPFound("/setup/")` when `self.config.setup_pending`.
  - `@local_network_only serve_setup_page`: raises `web.HTTPFound("/admin/")` when not pending. Otherwise it serves `setup.html` with `<script>` injected values `IS_TRUSTED_IP` (bool) and `MASTER_KEY_SET` (bool, `bool(self.master_key)`), the same way `serve_files_page` does.
  - `@admin_auth_required` endpoints. Each one returns `409 {"error": "Setup is already finished", "kind": "not_pending"}` when not pending.
    - `POST /api/admin/setup/check` `{server, name}` → `200 {"url", "settings", "ignored", "preview"}`.
    - `POST /api/admin/setup/apply` `{server, name}` → `200 {"success": true, "preview"}`.
    - `POST /api/admin/setup/finish` `{master_key?}` → `200 {"success": true, "student_urls": [...]}`.
  - Errors: a `SetupError` becomes `SETUP_ERROR_STATUS[kind]` with `{"error": message, "kind": kind, "details": details}`. When the validator rejects the filtered settings, the result is 422 `broken_file` with `details` = the validator errors.
  - Apply order:
    1. normalize the input;
    2. fetch and filter;
    3. validate the filtered dict (`_validate_config_data`);
    4. read the config file, `load_config_document`, `apply_setup_to_document`, dump;
    5. `_save_and_apply_config`;
    6. `_reinitialize_tunnel`.
  - Finish:
    - If `master_key` is present, it must be a string that is not empty after `strip()`; otherwise 400 `{"kind": "invalid_password"}`, and the marker stays.
    - If `self.master_key` is already set, the given key is ignored.
    - Otherwise, write `admin.master_key` into the document.
    - Remove the marker, call `_save_and_apply_config`, and set `self.master_key` to the new key (if one was set).
- Routes: `app.router.add_get("/setup/", server.serve_setup_page)`, plus `add_post` for the three endpoints. Add `"setup.html"` to the `_load_templates` list.

Shared test configs (put them at the top of `tests/test_setup_api.py`):

```python
PENDING = {"setup_pending": True}  # fixture default: master_key "test123", trusted_ips []
FRESH = {"setup_pending": True, "admin": {"master_key": None, "trusted_ips": ["127.0.0.1"]}}
LAN = {"X-Forwarded-For": "192.168.1.50"}  # the peer is loopback, so this header sets the client IP
SCHOOL1 = "language: en\nregistration:\n  fields:\n    - Class\nadmin:\n  master_key: hacked\ntunnel:\n  server: evil\n"
```

- [ ] **Step 1: Write the failing tests** in `tests/test_setup_api.py`. Use `custom_webquiz_server(config=…, env={"WEBQUIZ_SETUP_BASE_URL": base})`, `fake_setup_server`, `get_admin_session`, `requests`, and the `temp_dir` fixture (generated keys go to `keys/` in the working directory).

| Test | Setup | Assertions |
|------|-------|------------|
| `test_admin_redirects_to_setup_while_pending` | `PENDING` | `GET /admin/` with `allow_redirects=False` → 302, `Location` ends with `/setup/` |
| `test_admin_page_served_when_not_pending` | default | `GET /admin/` → 200 |
| `test_setup_page_redirects_to_admin_when_not_pending` | default | `GET /setup/` with `allow_redirects=False` → 302 to `/admin/` |
| `test_setup_page_served_while_pending` | `PENDING` | `GET /setup/` → 200, body contains `MASTER_KEY_SET = true` |
| `test_setup_api_409_when_not_pending` | default | check, apply and finish each → 409, `kind == "not_pending"` |
| `test_setup_check_preview` | `PENDING`, `SCHOOL1` | 200; `settings == {"language": "en", "registration": {"fields": ["Class"]}}`; `"admin"` and `"tunnel"` in `ignored`; `preview[-1] == {"key": "tunnel.server", "value": "demo.webquiz.xyz", "replaces": False}`; config file unchanged |
| `test_setup_check_unknown_name` | `PENDING`, no files | 404, `kind == "not_found"` |
| `test_setup_check_info_page_is_broken` | `PENDING`, `{"school1": "User subdomain: demo\n"}` | 422, `kind == "broken_file"` |
| `test_setup_check_rejects_invalid_values` | `PENDING`, `{"school1": "language: de\nregistration: x\n"}` | 422, `kind == "broken_file"`, `details` mentions `language` and `registration`; config file unchanged |
| `test_setup_check_invalid_input` | `PENDING` | `{"server": "a/b", "name": "x"}` → 400 `invalid_server`; `{"server": "demo.webquiz.xyz", "name": "../x"}` → 400 `invalid_name` |
| `test_setup_apply_writes_and_applies` | `PENDING`, `SCHOOL1`, `temp_dir` | 200; `GET /` contains `Class`; config file: `language: en`, `tunnel.server == "demo.webquiz.xyz"`, `public_key == "keys/id_ed25519.pub"`, no `hacked`, `setup_pending` still true; files `keys/id_ed25519` and `keys/id_ed25519.pub` exist |
| `test_setup_apply_twice_is_safe` | as above | two applies → both 200; the config file text is the same after each |
| `test_setup_finish_sets_password` | `FRESH` | finish `{"master_key": "newpass"}` → 200, `student_urls` is a list; `GET /admin/` → 200; config has `master_key: newpass` and no `setup_pending`; `POST /api/admin/auth {"master_key": "newpass"}` with `LAN` headers → 200 |
| `test_setup_finish_skip_leaves_no_password` | `FRESH` | finish `{}` → 200; `GET /api/admin/list-quizzes` with `LAN` headers → 403 |
| `test_setup_finish_keeps_existing_key` | `PENDING` | finish `{"master_key": "other"}` → 200; auth with `test123` → 200; config still has `test123` |
| `test_setup_finish_rejects_blank_password` | `FRESH` | finish `{"master_key": "   "}` → 400, `kind == "invalid_password"`; `GET /admin/` still redirects |
| `test_setup_api_denied_for_lan_without_master_key` | `FRESH` | check with `LAN` headers → 403 |

- [ ] **Step 2: Run the tests and check that they fail**

Run: `source venv/bin/activate && python -m pytest tests/test_setup_api.py -v -n 4`
Expected: FAIL. The redirect tests get 200, and the API tests get 404 (no route).

- [ ] **Step 3: Implement** the methods, routes, template list entry and placeholder template from Interfaces.

- [ ] **Step 4: Run the tests and check that they pass, then run the admin suites**

Run: `source venv/bin/activate && python -m pytest tests/test_setup_api.py tests/test_admin_api.py tests/test_admin_session_auth.py tests/test_network_access.py tests/test_tunnel.py -v -n 4`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add webquiz/server.py webquiz/templates/setup.html tests/test_setup_api.py
git commit -m "Add the first-launch setup API and redirect /admin/ while setup is pending"
```

---

### Task 6: The setup page

**Files:**
- Modify: `webquiz/templates/setup.html` (the full page)
- Test: `tests/test_selenium_first_setup.py`

**Interfaces:**
- Consumes: `/api/admin/check-session`, `/api/admin/auth` (existing), the three setup endpoints (Task 5), and the injected `IS_TRUSTED_IP` and `MASTER_KEY_SET`.
- Page states. Only one is visible at a time; the element IDs are fixed for the tests:
  - `#setup-login`: shown when there is no session, the IP is not trusted, and `MASTER_KEY_SET` is true. It has `#setup-login-key` and `#setup-login-btn`. It works like the login in `files.html`.
  - `#setup-local-only`: shown when there is no session, the IP is not trusted, and no master key is set. It says to open the page on the computer where WebQuiz runs.
  - `#setup-step1`: has `#setup-server`, `#setup-name`, `#setup-check-btn`, `#setup-skip-btn`, and an error area `#setup-error`. **Check** needs both fields filled. **Skip** goes to step 2 without calling the server (or straight to finish, when step 2 is skipped).
  - `#setup-preview`: lists the preview items in plain Ukrainian. It shows "замінить" ("will replace") when `replaces` is true, and lists ignored keys as not applied. It has `#setup-back-btn` and `#setup-apply-btn`.
  - `#setup-step2`: has `#setup-password`, `#setup-finish-btn`, `#setup-password-skip-btn`. When `MASTER_KEY_SET` is true, this step is skipped: the page calls finish with `{}` right away.
  - `#setup-done`: has `#setup-student-urls` (one line per URL) and `#setup-open-admin` (a link to `/admin/`).
- The error text depends on `kind`: `not_found`, `connection`, `broken_file` (also shows `details`), `invalid_server`, `invalid_name`, `invalid_password`. All text is in Ukrainian. Apply/Check buttons are disabled while a request runs.
- Layout: a centred card, `width: 100%; max-width: 560px`, with a 16px side padding at ≤768px. A theme toggle in the top-right corner, using the same CSS variables and `localStorage` `theme` key as `files.html`.

- [ ] **Step 1: Write the failing Selenium tests** using `browser`, `temp_dir`, `custom_webquiz_server`, `fake_setup_server`, and the `selenium_helpers` waits. Config: `FRESH` from Task 5. Files: `{"school1": "registration:\n  fields:\n    - Class\n"}`.

```python
@skip_if_selenium_disabled
def test_first_setup_full_flow(temp_dir, browser):
    # open /admin/ → current_url ends with /setup/
    # type " https://demo.webquiz.xyz/ " into #setup-server and "School1" into #setup-name, click #setup-check-btn
    # #setup-preview visible and contains "Class" and "demo.webquiz.xyz"; click #setup-apply-btn
    # #setup-step2 visible; type "newpass" into #setup-password; click #setup-finish-btn
    # #setup-done visible; #setup-student-urls text contains "http://"
    # click #setup-open-admin → current_url ends with /admin/

@skip_if_selenium_disabled
def test_first_setup_wrong_name_shows_error(temp_dir, browser):
    # name "nope" → #setup-error visible and not empty; #setup-preview not visible

@skip_if_selenium_disabled
def test_first_setup_fits_phone_width(temp_dir, browser):
    # browser.set_window_size(375, 812); open /setup/
    # browser.execute_script("return document.documentElement.scrollWidth <= window.innerWidth") is True
    # #setup-check-btn is displayed
```

- [ ] **Step 2: Run the tests and check that they fail**

Run: `source venv/bin/activate && python -m pytest tests/test_selenium_first_setup.py -v`
Expected: FAIL with `TimeoutException` / `NoSuchElementException` (the page is still the placeholder).

- [ ] **Step 3: Build the page** as described in Interfaces.

- [ ] **Step 4: Run the tests and check that they pass**

Run: `source venv/bin/activate && python -m pytest tests/test_selenium_first_setup.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add webquiz/templates/setup.html tests/test_selenium_first_setup.py
git commit -m "Add the first-launch setup page"
```

---

### Task 7: Documentation and the full test run (webquiz)

**Files:**
- Modify: `docs/en/020_first.md`, `docs/uk/020_first.md`
- Modify: `docs/en/040_config.md`, `docs/uk/040_config.md`
- Modify: `README.md`, `CLAUDE.md`

- [ ] **Step 1: `020_first.md` (en and uk, kept in sync).**
  - Add a "First-launch setup" section after the launch steps. It describes the two steps, says the server is the teacher's subdomain (for example `demo.webquiz.xyz`), says Skip keeps the standard settings, and says skipping the password means the admin panel opens only on this computer.
  - Fix the "Files and Folders Created" table: `webquiz.yaml` (not `config.yaml`) and `data/` (not `results/`).

- [ ] **Step 2: `040_config.md` (en and uk).**
  - Document `setup_pending`.
  - Say that new installs have no default admin password.
  - Change the example's `master_key: a1` line to a commented `# master_key: "your-secret-key"`.

- [ ] **Step 3: `README.md`.**
  - Add a feature bullet, and add the setup endpoints to the API section.
  - In the test list, add `- **First-Launch Setup** (N tests): setup helpers, download, API and page (test_first_setup.py, test_first_setup_marker.py, test_setup_api.py, test_selenium_first_setup.py)`, with N set to the real count.

- [ ] **Step 4: `CLAUDE.md`.**
  - Key Files: add `webquiz/first_setup.py`, and add `setup.html` to the templates list.
  - API Endpoints: add `GET /setup/` (admin page) and the three `/api/admin/setup/*` endpoints.
  - Add a one-paragraph **First-launch setup** Technical Decision covering: the marker, allowed keys, the URL, replace-whole semantics, the tunnel edits, `initialize_tunnel()` after Apply, the `WEBQUIZ_SETUP_BASE_URL` override for tests, and no default password.
  - Config options: `setup_pending`.
  - Key Flows: a **First-launch setup** line.

- [ ] **Step 5: Run the whole suite**

Run: `source venv/bin/activate && python -m pytest tests/ -v -n 4`
Expected: all PASS (Selenium included, unless `SKIP_SELENIUM` is set).

- [ ] **Step 6: Commit and push**

```bash
git add docs/ README.md CLAUDE.md
git commit -m "Document the first-launch setup"
git push -u origin claude/first-launch-setup-design
```

---

### Task 8: Publish setup folders on the tunnel server (`webquiz-tunnel-server`)

**Files** (in `/home/user/webquiz-tunnel-server`, on new branch `claude/first-launch-setup` from `master`):
- Create: `ansible/files/setup/README.md`
- Create: `ansible/files/setup/example/webquiz.yaml`
- Modify: `ansible/playbook.yml:96-104` (add `rsync` to "Install required packages")
- Modify: `ansible/playbook.yml` (new task after "Create user-specific tunnel configuration files", near line 256)
- Modify: `ansible/templates/nginx-user-subdomain.conf.j2` (both server blocks)
- Modify: `README.md`

- [ ] **Step 1: Create the setup folder.**
  - `example/webquiz.yaml` has a comment line explaining it, plus `language: uk` and `registration: {fields: [Клас]}`.
  - `README.md` explains three things:
    - Each folder name is a setup name, holding `webquiz.yaml` in the WebQuiz config format. Only `language`, `extra_answers_with_users_csv`, `registration`, `quizzes` and `checker_templates` are used.
    - Teachers type their user subdomain as the server, and the folder name as the setup name.
    - Everything here is public: never put passwords or private keys here.

- [ ] **Step 2: Add the publish task** to `ansible/playbook.yml`:

```yaml
    - name: Publish setup folders for the WebQuiz first-launch setup
      command: >-
        rsync -a --delete --itemize-changes
        --chown=www-data:www-data --chmod=D755,F644
        {{ playbook_dir }}/files/setup/ {{ www_root }}/setup/
      register: setup_rsync
      changed_when: setup_rsync.stdout | length > 0
```

- [ ] **Step 3: Add the nginx location** in both server blocks of `nginx-user-subdomain.conf.j2`, right before `# Default location - return info page`:

```nginx
    # WebQuiz first-launch setup files (shared by all subdomains)
    location /setup/ {
        root {{ www_root }};
        try_files $uri =404;
    }
```

- [ ] **Step 4: Add a "WebQuiz first-launch setup" section to `README.md`.** It covers how to add a setup name (add a folder, push to `main`) and the URL `https://<user>.webquiz.xyz/setup/<name>/webquiz.yaml`.

- [ ] **Step 5: Verify**

Run: `bash validate.sh`
Expected: no new failures compared with `master`.

Run: `python3 -m venv /tmp/claude-0/-home-user/c0ab70c2-ab3f-5bd3-ae96-0de47e35bf4a/scratchpad/ansible-venv && /tmp/claude-0/-home-user/c0ab70c2-ab3f-5bd3-ae96-0de47e35bf4a/scratchpad/ansible-venv/bin/pip install -q ansible-core && /tmp/claude-0/-home-user/c0ab70c2-ab3f-5bd3-ae96-0de47e35bf4a/scratchpad/ansible-venv/bin/ansible-playbook --syntax-check -i localhost, ansible/playbook.yml`
Expected: `playbook: ansible/playbook.yml`. If it fails only because a module collection is missing, report that, and do not change the playbook to work around it.

- [ ] **Step 6: Commit and push** (deployment happens only after a merge to `main`, which Oleksandr does)

```bash
git add ansible/files/setup ansible/playbook.yml ansible/templates/nginx-user-subdomain.conf.j2 README.md
git commit -m "Publish WebQuiz first-launch setup folders on every subdomain"
git push -u origin claude/first-launch-setup
```

- [ ] **Step 7: After Oleksandr merges and the deploy runs** (manual check, not part of the build):
  - `curl -sS -o /dev/null -w "%{http_code}" https://demo.webquiz.xyz/setup/example/webquiz.yaml` → `200`
  - `curl -sS -o /dev/null -w "%{http_code}" https://demo.webquiz.xyz/setup/nope/webquiz.yaml` → `404`
