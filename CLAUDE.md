# CLAUDE.md

## ⚠️ CRITICAL: Every Code Change MUST Include

1. **Update CLAUDE.md** - Reflect architectural changes, new features, API endpoints, technical decisions. Keep this file MINIMAL - detailed user-facing info belongs in README.md
2. **Update README.md** - User-facing documentation with detailed usage instructions. Only for new or changed features: a bug fix does not need a README change, except for the test counts
3. **Update docs/** - Both Ukrainian (`docs/uk/`) and English (`docs/en/`) in sync. Only for new or changed features: a bug fix does not need a docs change
4. **Write tests FIRST** - All functionality requires automated tests (update test counts below)
5. **Mobile support** - All UI must be responsive (≤768px viewport, `width: 100%; max-width: [size]`)

---

## Project Overview
WebQuiz - Python/aiohttp quiz system with multi-quiz management, real-time WebSocket stats, admin approval workflow, and question randomization.

## Architecture
- **Backend**: aiohttp + middleware + WebSocket
- **Frontend**: Vanilla HTML/JS (mobile-responsive @media ≤768px)
- **Storage**: In-memory → CSV (5s flush), YAML configs, quiz state resets on switch
- **Auth**: Session cookies for admin (master key at login), automatic local network restriction
- **Testing**: Integration + unit test

## Key Files
- `webquiz/server.py` - Main aiohttp server
- `webquiz/config.py` - Configuration dataclasses and loading functions
- `webquiz/translations.py` - UI and error message translations (uk/en)
- `webquiz/tunnel.py` - SSH tunnel manager for public access
- `webquiz/time_limits.py` - Quiz time limit rules (read, check, effective seconds per question)
- `webquiz/explanations.py` - Question explanations: Markdown → safe HTML (mistune), image references, checks
- `webquiz/transfer.py` - File transfer between servers on the same tunnel server
- `webquiz/cli.py` - CLI with daemon support
- `webquiz/build.py` - PyInstaller build script
- `installer/webquiz.iss` - Inno Setup script for Windows installer
- `webquiz/templates/` - index.html, admin.html, files.html, csv_table.html, live_stats.html
- `tests/` - Test suite
- `harness/` - Classroom test harness: real browsers, scripted teacher and students, AI agent students; not run by pytest (see `harness/README.md`)
- `docs/uk/`, `docs/en/` - Documentation (compiled to PDF with version)
- `gh-pages/index.html` - GitHub Pages download page template (version placeholder: `{{VERSION}}`)
- `gh-pages/docs/` - Docsify config files for online documentation (en/, uk/)

## API Endpoints

**Public:**
- `POST /api/register` (optional `registration_token`: a repeat with the same token returns the existing user), `PUT /api/update-registration`, `POST /api/submit-answer` (repeat with the same answer returns the stored result; a different answer to an answered question → 409; after a timeout any answer to that question returns the stored timeout; response has `test_completed` and, for a timeout, `timed_out: true`; `explanation_html` when the running quiz has `show_right_answer` and `show_explanation` on and the question has an explanation, never on a whole-quiz timeout), `POST /api/question-start` (ignored for an answered question; response adds `remaining_seconds` / `quiz_remaining_seconds` when a time limit applies), `GET /api/verify-user/{user_id}`
- `GET /attach/{filename}` - Download quiz file attachment (Content-Disposition: attachment)

**Admin (session cookie required, local network only):**
- `POST /api/admin/auth` - Authenticate with master key in request body (`{"master_key": "..."}`)
- `GET /api/admin/check-session`, `GET /api/admin/version-check`, `PUT /api/admin/approve-user`, `POST /api/admin/force-show-answers`, `GET /api/admin/list-quizzes`, `POST /api/admin/switch-quiz` (optional `settings`: start settings for this run, see below; 400 with `errors` and no switch when invalid; response has the running `settings`), `PUT /api/admin/config` (accepts `{content: yaml}` or `{data: {section: {...}}}` for JSON partial update; response includes `config_content` and `config_data`)
- `POST /api/admin/preview-explanation` - Render explanation Markdown for the editor preview (`{"markdown": "..."}` → `{"html": "..."}`, same renderer as for students)
- Quiz management: `GET /api/admin/quiz/{filename}`, `POST /api/admin/create-quiz`, `PUT /api/admin/quiz/{filename}`, `DELETE /api/admin/quiz/{filename}`, `POST /api/admin/download-quiz`, `POST /api/admin/unite-quizzes`
- Quiz file attachments: `GET /api/admin/list-files` (list files in quizzes/attach/)
- Checker templates: `GET /api/admin/list-checker-templates` (list configured checker templates for text questions)
- File management: `GET /api/files/list`, `GET /api/files/{type}/view/{filename}`, `GET /api/files/{type}/download/{filename}`, `PUT /api/files/quizzes/save/{filename}`
- Tunnel management: `POST /api/admin/tunnel/connect`, `POST /api/admin/tunnel/disconnect`
- File transfer: `GET /api/admin/transfer` (state: own name, sent offers, incoming requests), `POST /api/admin/transfer/send` (`{to, files: [{type, name}]}`), `POST /api/admin/transfer/{request_id}/accept` (optional `{files: [{type, name, action: save|replace|rename|skip, new_name}]}`; 400 keeps the request open), `POST /api/admin/transfer/{request_id}/reject`

**Server-to-server (through the tunnel, protected by the offer token, not by IP):**
- `POST /api/transfer/offer`, `GET /api/transfer/download/{token}/{type}/{filename}`, `POST /api/transfer/result`

**Admin Pages (local network only):**
- `GET /admin/` - Admin interface page
- `GET /live-stats/` - Live stats page
- `GET /files/` - File manager page
- `GET /files/csv/{filename}` - CSV table viewer page (`?question=`, `?user=`, `?embedded=1`)

**WebSockets:**
- `WS /ws/live-stats` (local network only), `WS /ws/admin` (local network only, admin approval + tunnel status + file transfer notifications: `transfer_request`, `transfer_request_removed`, `transfer_result`)

## Dev Commands

⚠️ **ALWAYS use venv**: All Python commands and poetry operations must run inside virtual environment (`source venv/bin/activate` or `poetry shell`)

```bash
# Environment Setup (from scratch)
python3 -m venv venv           # Create virtual environment
source venv/bin/activate       # Activate venv
pip install poetry             # Install poetry inside venv
poetry install                 # Install project dependencies

# Quick Setup (if venv already exists)
source venv/bin/activate && poetry install

# Run
source venv/bin/activate && webquiz --master-key secret123
source venv/bin/activate && webquiz -d  # daemon

# Test
source venv/bin/activate && python -m pytest tests/ -v -n 4

# Test with coverage (subprocess tracking enabled, use pytest-cov)
source venv/bin/activate && python -m pytest tests/ -v --cov=webquiz --cov-report=html --cov-report=term-missing

# Note: Use pytest-cov (--cov) not "coverage run" for subprocess tracking

# Build binary (current OS only)
source venv/bin/activate && poetry run build_binary
```

### Environment Requirements
- **Python**: 3.10+ (tested with 3.10-3.14)
- **Poetry**: Installed inside venv (not globally) to avoid conflicts
- **Test ports**: Tests use ports 8080-8087 for parallel execution (-n 4 uses 4 workers). CLI tests that launch a real server use 8090-8097 via `--port` so they never collide with fixture workers

## Stress Testing

**Note**: Stress testing moved to separate project: [webquiz-stress-test](https://github.com/oduvan/webquiz-stress-test)

```bash
# Install stress test tool
pip install webquiz-stress-test

# Run stress test
webquiz-stress-test -c 50
```

## Technical Decisions
- **Middleware-based error handling** for aiohttp
- **Configuration module separation** - config.py contains dataclasses for configuration (using standard dataclasses module with field(default_factory=...))
- **6 digits user ID** stored by user_id as key
- **Server-side timing** for accuracy. A question's clock starts at `POST /api/question-start` (when the page shows it), also for the first question; registration and approval do not start it. A repeated question-start does not restart it. `current_question_ids[user_id]` names the question whose clock runs; `quiz_start_times[user_id]` (first question-start) is the whole-quiz clock. question-start returns 404 for an unknown question and starts clocks only for the student's next unanswered question; an answer stops only its own question's clock. `question_ready_times[user_id]` (registration/approval, then each stored answer) is the fallback start for the time limit check when an answer arrives without question-start (a request sent by hand)
- **Multi-file quiz system** in `quizzes/` dir, auto-created if missing
- **Session-based admin auth** - Master key sent in request body to `/api/admin/auth`, returns session cookie for subsequent requests (no header-based auth)
- **Config validation** with comprehensive structure/type checks before save. Quiz-wide on/off settings (`show_right_answer`, `randomize_questions`, `show_answers_on_completion`, `show_final_list`) must be real booleans; loading a quiz does not validate, only saving does
- **Smart CSV naming** with quiz prefix + unique suffixes (no overwrites)
- **Quiz state reset** on switch for complete isolation
- **In-memory → CSV** with 5s periodic flush using CSV module (no test-specific flush endpoint)
- **Cookie-based session** persistence (user_id for quiz users, admin_session for admin authentication)
- **Admin session cookies** - Secure httponly cookies set on successful master key authentication, persisted across page refreshes and navigation between admin/files pages
- **WebSocket live stats** with automatic client cleanup and **two-group display** (in-progress/completed)
- **Auto-advance UI** when `show_right_answer: false`
- **Mobile-first** with `width: 100%; max-width: [size]` and @media ≤768px
- **UTF-8 Content-Type** for Ukrainian/multilingual text support
- **Server-side question randomization** generated at registration, stored per-user as `question_order` array, client reorders via JS
- **Sticky question groups** - Questions with `stick_to_the_previous: true` stay adjacent during randomization. Groups are formed by consecutive sticky flags and shuffled as units. First question cannot be sticky (no previous to stick to). UI shows 🔗 indicator on collapsed questions.
- **Test completion detection** uses answer count (`len(user_answers[user_id])`) instead of question ID to support randomization
- **Live stats first question** uses user's actual first from `question_order` (prevents duplicates)
- **Two-group live stats** - Users split into "In Progress" and "Completed" groups, automatically move on completion
- **Multi-platform binaries** via GitHub Actions (macOS-13 Intel, macOS-14 ARM64, Linux, Windows)
- **Windows installer** - Inno Setup script (`installer/webquiz.iss`) builds `webquiz-windows-setup.exe` with Start Menu shortcut and Add/Remove Programs uninstaller. Built in CI alongside portable ZIP. Version injected via `/DMyAppVersion` flag.
- **Coverage excludes build tools**: build.py and binary_entry.py omitted from coverage (not runtime code)
- **Wizard-only quiz editor** - Admin panel uses wizard mode only; YAML editing available in file manager with validation
- **CSV table viewer** - `csv_table.html` at `/files/csv/{filename}` (`@local_network_only`; data comes from `/api/files/csv/view/`, so it needs the admin session like the rest). One page for both places: the file manager pop-up shows it in an iframe with `?embedded=1` (hides its own header, shows "Open in new window"), and the CSV list has a "↗ New window" link to it. Filters by `question` column and by user (`user_id`, labelled with `username`; for a plain answers CSV the names come from the matching `.users.csv`). Filters live in the address (`?question=&user=`, updated with `history.replaceState`). `parseCSV()` reads quoted fields with commas, `""` and line breaks. Table cells wrap (`white-space: pre-line`) instead of growing sideways. Theme follows localStorage and the `storage` event.
- **File manager quiz editing** - Direct YAML editing with validation button, automatic backup, and active quiz reload
- **Dynamic answer visibility** - `show_answers_on_completion: true` reveals correct answers only after all approved students complete, with automatic re-hiding when new students register
- **SSH Tunnel for public access** - Optional feature to expose local server via SSH reverse tunnel with Unix domain sockets
- **ED25519 SSH keys** - Auto-generated if missing, stored with binary-relative paths for PyInstaller compatibility
- **Tunnel auto-reconnect** - Exponential backoff (5s → 300s max), connection monitoring via asyncssh
- **asyncssh forward_remote_path_to_port** - Used for forwarding remote Unix socket to local TCP port (not forward_remote_path)
- **WebSocket tunnel status** - Real-time updates broadcast to admin clients, no polling needed
- **Admin-triggered connection** - No auto-connect on startup, admin clicks button to establish tunnel
- **Tunnel URL in access list** - Public tunnel URL automatically added to "URL для доступу з інших пристроїв:" list with green background when connected
- **IP address detection** - Automatically uses HTTP for IP addresses (IPv4/IPv6) and HTTPS for domain names when fetching tunnel_config.yaml
- **Client IP behind proxies** - `get_client_ip()` trusts `X-Forwarded-For` / `X-Real-IP` only when the TCP peer is loopback (local reverse proxy or the SSH tunnel, which forwards to 127.0.0.1) and takes the **last** `X-Forwarded-For` entry (the tunnel server's nginx uses `$proxy_add_x_forwarded_for`, so earlier entries come from the client). Direct LAN clients cannot spoof their IP with headers.
- **File transfer between servers** - "Ask first, then send" over the public tunnel URLs (`{base_url}/{socket_name}/...`); direct SSH stream-local connections are blocked by the tunnel server (`AllowTcpForwarding remote`). Sender keeps an offer with a random token (30 min lifetime) and POSTs the file list; receiver admin accepts; receiver downloads from `{its own base_url}/{sender}/` with the token and reports the result. Only `.yaml/.yml` quizzes, `.log` logs, `.csv` files, plus images (`quizzes/imgs/`) and attachments (`quizzes/attach/`) referenced by offered quizzes (`image`, image `options`, `file`), added automatically by the sender; names without path or Windows-invalid characters; offer entries carry a SHA-256. Receiver shows per file a case (`new`, `same`, `different`, `in_use` = current log/CSV/active quiz from `get_files_in_use`) with allowed actions (save/replace/rename/skip) and a default (save/skip/rename/rename); target name is the original name, `{sender}_` prefix for logs/CSV; rename suggests the first free `{sender}_name`, `_2`, `_3`. `_build_plan()` validates all choices before any download (400 keeps the request). Receiver downloads media first and rewrites references in received quizzes with ruamel round-trip when media got a new name. Files page send panel is hidden until `GET /api/admin/transfer` reports `available`. State is in memory (`TransferManager`). `TunnelManager.get_public_endpoint()` returns `(base_url, socket_id)` while connected.
- **Local network restriction** - All admin functionality (API endpoints via @admin_auth_required, HTML pages, WebSockets) automatically restricted to private networks (RFC 1918: 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16) with no configuration needed
- **Quiz download folder validation** - Path traversal protection: blocks "..", absolute paths (Unix/Windows), normalizes paths, ensures extraction stays within quizzes directory; allows subfolder paths like "folder/subfolder/"
- **Private quiz archives** - A `quizzes` entry may carry `auth_header_token`, the only way to supply a token (no environment variable support by design). When an entry has it, `admin_download_quiz` looks the entry up with `find_downloadable_quiz(name)` and uses the **config's** `download_path` and `folder`, ignoring the request's, so a token can never be sent to an address supplied by the client. The token goes out as `Authorization: Bearer`, and only to an https URL (or http on localhost) — `can_send_token_to()` otherwise returns 400. Without the field the download is unauthenticated, as before. The token is not part of the `DOWNLOADABLE_QUIZZES` injected into admin.html. For GitHub use `https://api.github.com/repos/OWNER/REPO/zipball/REF`: the plain `github.com/.../archive/....zip` URL redirects cross-host to codeload and httpx strips `Authorization` there, giving a 404.
- **Archive root folder resolution** - GitHub archives wrap everything in `owner-repo-<sha>/`, whose name changes per commit. If `folder` is not found at the archive top level and exactly one directory was extracted, the folder is retried inside it, so `folder: data` works. Existing configs that spell out the root folder keep working.
- **Clipboard API fallback** - Copy public key button uses modern navigator.clipboard API for HTTPS/localhost, falls back to document.execCommand() for non-secure contexts (HTTP over IP)
- **Package version check** - Admin panel periodically checks if package was updated while server is running by comparing in-memory version with file version; shows "Restart Required" banner when mismatch detected
- **Quiz file attachments** - Questions can have downloadable files via `file` field (e.g., `file: "data.xlsx"`). Files stored in `quizzes/attach/`, served at `/attach/{filename}` with `Content-Disposition: attachment` header for forced download. Server auto-prepends `/attach/` when serving to client. Admin panel has file picker modal for selecting files.
- **Startup environment logging** - On server start, logs comprehensive environment info for troubleshooting: WebQuiz version, Python version/executable, OS/platform info, aiohttp version, working directory, config file path, binary mode status, server/path/admin/registration/tunnel configuration, and network interfaces. Master key value is never logged (only True/False).
- **SD card/slow storage reliability** - All file writes (config, quizzes, CSV) use `flush()` + `os.fsync()` to ensure data is physically written to storage before returning success. Prevents data loss on Raspberry Pi and systems with SD cards or exFAT partitions when powered off shortly after save.
- **Config hot-reload** - When admin saves config via web form (`PUT /api/admin/config`), changes are applied immediately without server restart. Hot-reloadable: registration settings (approve, fields, username_label), admin.trusted_ips, downloadable quizzes list, tunnel config. Requires restart (security/stability): server host/port, paths, master_key - shows "restart required" message with specific config paths. Quiz always restarted (users/state cleared) on config save. Templates are reloaded on each config save. If applying changes fails, config file is automatically rolled back to previous state.
- **Multi-quiz selection** - Admin panel uses `<select multiple>` for quiz list instead of clickable divs. Single selection shows standard buttons (Switch, Edit, Duplicate, Delete). Multiple selection (Ctrl+click/Cmd+click) shows Unite button and Delete. Delete button disabled when current quiz is in selection.
- **Quiz list with titles** - `GET /api/admin/list-quizzes` returns array of objects with `filename` and `title` fields (title is null if quiz has no title). Admin panel displays quiz titles alongside filenames in selection list.
- **Quiz unite** - `POST /api/admin/unite-quizzes` combines multiple quizzes into one. Takes config (title, description, show_right_answer, randomize_questions, show_answers_on_completion, show_final_list) from first quiz, combines all questions in order. `min_correct` is per-question only and is never copied to the top level. Accepts `{quiz_filenames: [...], new_name: "..."}`, validates all quizzes exist and have valid structure, warns about duplicate questions, creates new quiz file with fsync.
- **Question points** - Each question can have a `points` field (default: 1). Points are tracked per-answer, accumulated in user stats, and displayed in live stats (earned/total format), final results, and users CSV. Questions worth anything other than 1 point show a trophy indicator in UI.
- **Decimal points** - `points` may be a decimal with at most 2 places (e.g. `0.5`, `1.25`); must be > 0. Validation applies to all question types (it used to run only for text questions). Server normalizes every points value and sum through `normalize_points()`/`sum_points()` in `server.py`, which round to 2 decimals and return an int when whole, so sums like 0.1+0.2 report as 0.3 and not 0.30000000000000004. Templates mirror this with `roundPoints()`/`formatPoints()` JS helpers; the admin editor's points input uses `step="0.01" min="0.01"`, and `validateWizardPoints()` blocks a save with an inline error naming the question when a value is not a number, is <= 0, or has more than 2 decimals.
- **Text input questions** - Questions with `checker` field are automatically detected as text input questions (no `type` field needed). Fields: `default_value` (initial textarea value), `correct_value` (shown when wrong), `checker` (Python code for validation). Checker code is validated for Python syntax on quiz save. Checker code runs in sandboxed environment with limited builtins (math functions, basic types) plus helper functions: `to_int(str)` - convert to integer, `distance(str)` - parse distance (supports "2km", "2000m", "2км"), `direction_angle(str)` - parse direction angle ("20-30" = 2030). If checker is empty, exact match with `correct_value` is used. Returns `checker_error` message on failure.
- **Checker templates** - Admin-configurable code templates for text question validation. Defined in config as `checker_templates: [{name: "...", code: "..."}]`. Templates available in admin quiz editor for quick insertion.
- **Dark/Light theme switcher** - All pages (quiz, admin, live stats, file manager) support dark/light theme toggle via button in top-right corner. Theme preference persisted in localStorage (`theme` key), shared across all pages. CSS uses CSS variables (`:root` for light, `[data-theme="dark"]` for dark) with smooth 0.3s transitions.
- **Manual answer revelation** - Admin can click "Show Answers" button to force `all_students_completed()` to return true, triggering existing answer visibility logic. Button only visible when quiz has `show_answers_on_completion: true`. Affects all students who complete after button click (including new registrations). One-way action (cannot be undone until quiz switch). Endpoint: `POST /api/admin/force-show-answers` (admin-auth required). Flag `force_all_completed` resets on quiz switch.
- **Quiz renaming** - Admin can rename quizzes via editor modal. Backend renames physical file with validation. **Active quiz cannot be renamed** (must switch to different quiz first, returns 409 error). CSV files retain old quiz name prefix (historical data preservation). Prevents filename conflicts with 409 status code.
- **Student request retry** - Quiz page sends requests through `fetchWithRetry()` (index.html): network error, 15s timeout (AbortController) or 502/503/504 → retry after 1s, 2s, 4s, then every 5s, forever, with a `#connection-banner` (`T.connection_lost`). Other HTTP errors are returned to the caller as before. The answer is locked (`answerLocked`, textarea disabled) while it is sent, and submit awaits the pending `questionStartRequest` so the server gets question-start before the answer. Page-load verification retries instead of falling back to the registration form. Server makes repeats safe: `answer_results[user_id][question_id]` stores `{selected_answer, response}` **before** the live-stats broadcast `await`, so a concurrent retry also gets the stored result; `registration_tokens[token] -> user_id` (client sends a random `registration_token`, built with `crypto.getRandomValues` because `randomUUID` needs a secure context). Both dicts are cleared in `reset_server_state()`.
- **Plain text, never HTML** - Quiz text (question, options, title, `default_value`, `correct_value`, checker errors) and student input (username, registration fields) are shown as plain text on every page, so `<vtx_band>` stays visible and student names cannot inject HTML/JS. JS templates wrap every such value in `escapeHtml()` before `innerHTML` (index.html, live_stats.html, admin.html, files.html each define it). Server-side: `html.escape()` for `{{QUIZ_TITLE}}`, `{{USERNAME_LABEL}}`, registration labels and the quiz-selection list; `json_for_script()` (writes `<` as `\u003c`) for JSON put inside `<script>` (`{{QUESTIONS_DATA}}`, `CONFIG_CONTENT`, `CONFIG_DATA`, `DOWNLOADABLE_QUIZZES`) so a `</script>` in quiz text cannot end the script. Values inside `onclick="fn(...)"` use `escapeHtml(JSON.stringify(value))`.
- **Question text copy prevention** - Quiz questions have `user-select: none` CSS and a `copy` event handler on the question container to prevent students from copying question text. Text input fields for text questions remain selectable.
- **Quiz time limits** - `webquiz/time_limits.py` holds pure functions: `validate_time_limits()` (called from `_validate_quiz_data`), `parse_time_limit()` (malformed value on load = no limits + log warning), `question_limits()` (effective seconds per question id). Unite copies `time_limit` from the first quiz. Submit order: stored timeout → repeat/order/409 checks → whole quiz (empty answer or past `W + grace` → `_end_whole_quiz` stores every unanswered question as timed out) → empty answer (400 unless the question is limited, else timeout) → per-question late answer past `L + grace` → timeout → normal. `_record_answer()` stores normal answers and timeouts alike; a timeout is `selected_answer` "" in CSV, `is_correct` False, no checker, 0 points, `timed_out: True` in `user_answers` (not CSV), live stats state `"timeout"`. Grace 5 s (`WEBQUIZ_TIME_LIMIT_GRACE_SECONDS`, tests only). Design: `docs/superpowers/specs/2026-11-04-quiz-time-limits-design.md`
- **Classroom test harness** - `python -m harness.run <scenario>` starts a WebQuiz server on port 8199, a Playwright browser (one context per student), a scripted teacher (start pop-up) and scripted students; AI agents drive their own students with `python -m harness.student <name> <cmd>` via an API on port 8198. The driver records every step (screen text, screenshot, `/api/` requests and replies) and live stats messages in `events.jsonl`; `harness/checks.py` checks them against the stored CSV and against the agents' `STEP n | DID | SAW` reports. Only `tests/test_harness_checks.py` runs with pytest
- **Question explanations** - Per-question `explanation` (Markdown) shown as its own step after the answer feedback ("Продовжити" → `#explanation-step` → "Далі" → next question), only when the running quiz has `show_right_answer` and `show_explanation` (default false). `webquiz/explanations.py` renders with mistune 3 (`HTMLRenderer(escape=True)`: raw HTML as text; harmful links as plain text; other links `target="_blank" rel="noopener"`; `/imgs/` → `imgs/` for the quiz page, `../imgs/` for the admin preview; plugins table + strikethrough imported as functions for PyInstaller). Rendered once per quiz load into `explanations_html[question_id]`; sent only in the answer reply (`_record_answer(..., with_explanation=False)` from `_end_whole_quiz`), never in `QUESTIONS_DATA`. The step is outside `#current-question-container` (copy blocker) and keeps `currentQuestionIndex` on the answered question, so whole-quiz time-up behaves as on the "Продовжити" screen. "Далі" (`#explanation-next-btn`) sits on the right like "Продовжити"; it stays disabled on screen 400 ms before the next question opens (double-click guard). Editor: `.explanation-group` folded (`.folded`) while empty, `.explanation-toggle-btn` unfolds; `.question-explanation` textarea, image insert (`![](</imgs/name>)` for names with spaces/brackets), `.explanation-preview-btn` swaps the textarea for the server-rendered preview (`POST /api/admin/preview-explanation`) and back; `#show-explanation-group` shown only while some explanation exists. Transfer finds/rewrites images inside explanation text (`explanation_image_names`, `rewrite_explanation_images`), keeping the YAML scalar style. Design: `docs/superpowers/specs/2026-11-07-question-explanations-design.md`
- **Start settings** - The admin panel's switch button opens `#start-quiz-modal` with the quiz-wide settings (`START_SETTING_KEYS` in `server.py`: show_right_answer, randomize_questions, show_answers_on_completion, show_final_list, show_explanation, time_limit), filled from the quiz file via `GET /api/admin/quiz/{filename}`. `switch-quiz` sends them as `settings`; `_validate_start_settings()` checks them; `switch_quiz(filename, settings)` stores them in `start_settings` for that file and `_apply_start_settings()` puts them over the file values after `load_questions_from_file`. Never written to the file. A restart of the same file without `settings` (config save, editor save) keeps them; another file without `settings` drops them. A missing key keeps the file value; `time_limit: null` = no limit
- **Show final list** - `show_final_list` quiz option (default: true) controls whether the question-by-question results table is displayed on the final screen. When false, only the score summary (e.g., "3/5 (60%)") is shown. Setting is loaded from YAML, injected as `showFinalList` JS variable, validated as boolean, and editable in admin quiz editor.
- **Image preloading** - All quiz images (question images and image options) are preloaded immediately on page load. Uses `new Image()` to cache images in browser while user fills registration form. Images from options starting with `/` are detected as image paths. Ensures instant image display during quiz.
- **Config form editor** - File manager Config tab has Form/YAML toggle. Form view provides structured editing for language (uk/en dropdown) and registration config (approve, username_label, fields). Form sends JSON partial updates via `PUT /api/admin/config` with `{data: {language: "...", section: {...}}}` format — backend merges into existing YAML config (top-level scalars like `language` and per-section dicts are both supported). YAML view remains for direct editing. Both views sync after save (response includes `config_content` and `config_data`). Switching views with unsaved changes triggers confirm dialog. No external JS dependencies — server injects `CONFIG_DATA` as parsed JSON alongside `CONFIG_CONTENT`.
- **Disabled registration fields** - `registration.disabled_fields` (list of strings, default: empty) keeps field names in the config without showing them on the registration form. Admin form view renders `fields` + `disabled_fields` as a single unified list with per-row checkboxes — toggling a checkbox moves the field between the two lists on save (no add/delete needed). Server-side registration ignores anything in `disabled_fields`; only `fields` is iterated when rendering the form, validating required fields, and writing CSV headers. Hot-reloadable.
- **Comment-preserving config save** - Partial JSON updates via `PUT /api/admin/config` use `ruamel.yaml` in round-trip mode to load and re-dump the config file, so user comments and blank lines between sections survive form-driven edits. PyYAML is still used for validation and for the `{content}` full-replacement path (which writes the user-supplied text verbatim).
- **Quiz interface language** - `language` config option (`"uk"` or `"en"`, default `"uk"`) controls all user-facing strings in quiz interface and API error messages. Translations stored in `webquiz/translations.py`. HTML static text uses server-side `{{PLACEHOLDER}}` replacement. JS dynamic strings use injected `T` object (`const T = {{TRANSLATIONS_JSON}}`). CSS `content:` properties use server-side placeholders. Server-side error messages use `self.translations["key"]`. Hot-reloadable — applied on config save (quiz restart regenerates template).

## Key Flows

**Quiz**: Load YAML → inject to HTML → register user → cookie session → submit answers → timing → validate → in-memory → CSV flush
**Approval**: Register → `approved: false` → wait → admin WebSocket notified → approve button → student checks → quiz begins → **timing starts** at question-start
**Randomization**: Load YAML → register → `random.shuffle()` → store `question_order` per-user → client receives array → JS reorders → persists across sessions
**Admin**: Switch quiz → reset all state (users, progress, responses) → new CSV → session isolation
**Live Stats Groups**: Users display in "In Progress" group → answer questions → complete final question → automatically move to "Completed" group with `completed: true` flag in WebSocket
**Tunnel**: Initialize → check/generate keys → admin clicks connect → fetch server config → create SSH connection → forward remote Unix socket to local port (forward_remote_path_to_port) → broadcast public URL via WebSocket → auto-reconnect on disconnect
**File Transfer**: Sender admin ticks files in `/files/` → `POST /api/admin/transfer/send` → offer + token stored → `POST {base_url}/{target}/api/transfer/offer` → receiver broadcasts `transfer_request` to admin WebSocket → admin accepts → receiver GETs each file from `{base_url}/{sender}/api/transfer/download/{token}/...` into a temp file, renames to a free name → `POST .../api/transfer/result` → sender marks offer accepted/rejected/failed (files page polls `GET /api/admin/transfer`)
**Startup**: Load config → create TestingServer → initialize log file → configure logging → **log environment info** (version, Python, OS, config, paths, network) → initialize tunnel → load questions → start periodic flush and time limit watcher → register routes
**Config Hot-Reload**: Admin saves config → validate YAML → backup original config → write to file → reload config from file → detect restart-required changes (server, paths, master_key) → apply safe changes (registration, trusted_ips, quizzes, tunnel) → reload templates → disconnect tunnel if connected (admin can reconnect) → restart current quiz (reset users/state) → return message (either "saved and applied" or "restart required for: ..."). On failure: rollback config file to backup → return error
**Time limits**: question-start starts the question clock (and the whole-quiz clock once) → page counts down from `remaining_seconds` / `quiz_remaining_seconds` → at zero the page submits an empty answer → server stores a timeout. `time_limit_watcher()` runs `check_time_limits()` every second (`WEBQUIZ_TIME_LIMIT_CHECK_INTERVAL`, tests only) for pages that went quiet: a running question clock past `L + grace` → timeout; whole quiz past `W + grace` → `_end_whole_quiz`. It never starts a clock, so a student who leaves mid-quiz in per-question mode stays unfinished (teacher uses "Show answers")
**Text Question Validation**: Submit text answer → check question type → if text: execute checker code in sandboxed env (restricted builtins + math + helper functions: to_int, distance, direction_angle) → if exception: answer incorrect + return error message → if no exception: answer correct. No checker: exact match with `correct_value`

**Setup**: Parallel testing with ports 8080-8087, `custom_webquiz_server` fixture auto-cleans directories, `conftest.py` for shared fixtures. `test_cli_directory_creation.py` spawns the CLI with `sys.executable` and a worker-specific port from 8090-8097 (`cli_test_port()`)

## Important Notes
- **CSV files** (2 per session, 3 with `extra_answers_with_users_csv: true`): `{quiz_name}_{NNNN}.csv` (per-answer submissions) + `{quiz_name}_{NNNN}.users.csv` (one row per user with stats: total_time in MM:SS format, earned_points, total_points) + optional `{quiz_name}_{NNNN}.answers_with_users.csv` (per-answer rows with `user_id`, `username`, and registration fields prepended). All three share the same `{NNNN}` suffix; `generate_csv_path` advances the suffix only when all candidate files for that number are free.
- **Config** (`webquiz.yaml`): All sections optional, editable via `/files/` or admin panel, hot-reloaded on save (returns `restart_required` list if server/paths/master_key changed), UTF-8 charset header
- **Config options**:
  - `language: en` - Quiz interface and error message language, `"uk"` (Ukrainian, default) or `"en"` (English). Hot-reloadable.
  - `extra_answers_with_users_csv: true` - Generate an additional **third** CSV (`{quiz}_{NNNN}.answers_with_users.csv`) with one row per submitted answer, prefixed by `user_id`, `username`, and registration field columns (default: false). The `extra_` prefix highlights that it is generated alongside the standard answers + users CSVs; the `answers_with_users` part names exactly what is combined. Useful for downstream analysis where you want answers and user attributes joined. Hot-reloadable (takes effect on next quiz switch / quiz restart).
  - `server.port` - Port the server listens on (default: 8080). CLI `--port` overrides it
  - `server.include_ipv6: true` - Include IPv6 addresses in network interfaces list (default: false)
  - `server.url_format` - URL format for admin panel network access URLs (default: `http://{IP}:{PORT}/`). Placeholders: `{IP}`, `{PORT}`. Example for reverse proxy: `http://{IP}/webquiz/`
  - `registration.approve: true` - Admin approval required; time does not run while a student waits, the clock starts when the first question is shown (default: false)
  - `registration.username_label` - Customize username field label (default: empty = falls back to language translation, "Ім'я користувача" for uk / "Username" for en)
  - `registration.fields` - List of additional registration fields shown to users (default: empty)
  - `registration.disabled_fields` - List of additional registration fields preserved in the config but hidden from the registration form (default: empty). Admin form view toggles fields between `fields` and `disabled_fields` via per-row checkboxes — useful when admins frequently switch fields on/off without losing their names.
  - `randomize_questions: true` - Per-student random order, stored as `question_order` array (default: false)
  - `show_right_answer: false` - Auto-advance without continue button (seamless flow)
  - `show_answers_on_completion: true` - Reveal correct answers dynamically after all approved students complete, with waiting message and reload prompt (default: false)
  - `show_explanation: true` - Show each question's `explanation` (Markdown) as a step after the answer; needs `show_right_answer` (default: false)
  - `show_final_list: false` - Hide the list of questions with answers on the results screen, showing only the score summary (default: true)
  - `time_limit: {per_question: N}` or `time_limit: {whole_quiz: N}` - Quiz time limit in whole seconds (0 = no limit). Questions may set `time_limit: N` (used only in `per_question` mode). Rules in `webquiz/time_limits.py`
  - `quizzes[].auth_header_token` - Access token for a private archive, sent in the `Authorization` header (default: none = unauthenticated download)
  - `tunnel.server` - SSH tunnel server hostname (e.g., "tunnel.example.com")
  - `tunnel.public_key` - Path to SSH public key file (auto-generated if missing)
  - `tunnel.private_key` - Path to SSH private key file (auto-generated if missing)
  - `tunnel.socket_name` - Optional fixed socket name instead of random generation (default: random 6-8 hex chars). Needed for file transfer (other servers address this one by it). After a disconnect the name can stay busy up to 5 min (stale socket file until the tunnel server's cleanup cron)
  - `tunnel.config` - Optional nested config subsection (username, socket_directory, base_url) - bypasses server fetch when provided
- Questions use **0-indexed** `correct_answer` field and optional `points` field (default: 1)
- Text questions are detected by `checker` field (no `type` field needed, no `options` or `correct_answer`)
- `checker_templates` - List of `{name, code}` objects for admin panel template dropdown
- Usernames unique per quiz session
- Switching quizzes = full state reset

## Release
**Trigger**: GitHub Actions → "Release and Deploy to PyPI" → Enter version (X.Y.Z)

**Process**: Build binaries (Linux, macOS Intel/ARM64, Windows) → Build Windows installer (Inno Setup) → Update versions → Generate PDFs (uk/en) → Publish to PyPI → Create GitHub release with 9 assets (2 Python packages + 4 zipped binaries + 1 Windows installer + 2 PDFs) → Deploy GitHub Pages

**Release notes**: if `.github/release-notes/vX.Y.md` exists at the release tag, the workflow puts it at the top of the GitHub release notes (screenshots go in `.github/release-notes/images/vX.Y/`, linked by `raw.githubusercontent.com/oduvan/webquiz/vX.Y/...` URLs)

**Note**: macOS builds on separate runners (macos-15-intel Intel, macos-15 ARM64)

**GitHub Pages**: https://oduvan.github.io/webquiz/ - Static site with download page and online documentation
- `deploy-pages.yml` - Manual trigger or called by release.yml (no auto-deploy on commit)
- Documentation uses Docsify (no build step, renders markdown on-the-fly)
- Docsify config in `gh-pages/docs/` with `_sidebar.md` for navigation
