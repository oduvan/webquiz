# CLAUDE.md

## ⚠️ CRITICAL: Every Code Change MUST Include

1. **Update CLAUDE.md** - Reflect architectural changes, new features, API endpoints, technical decisions. Keep this file MINIMAL - detailed user-facing info belongs in README.md
2. **Update README.md** - User-facing documentation with detailed usage instructions
3. **Update docs/** - Both Ukrainian (`docs/uk/`) and English (`docs/en/`) in sync
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
- `webquiz/tunnel.py` - SSH tunnel manager for public access
- `webquiz/cli.py` - CLI with daemon support
- `webquiz/build.py` - PyInstaller build script
- `webquiz/templates/` - index.html, admin.html, files.html, live_stats.html
- `tests/` - Test suite
- `docs/uk/`, `docs/en/` - Documentation (compiled to PDF with version)

## API Endpoints

**Public:**
- `POST /api/register`, `PUT /api/update-registration`, `POST /api/submit-answer`, `GET /api/verify-user/{user_id}`
- `GET /attach/{filename}` - Download quiz file attachment (Content-Disposition: attachment)

**Admin (session cookie required, local network only):**
- `POST /api/admin/auth` - Authenticate with master key in request body (`{"master_key": "..."}`)
- `GET /api/admin/check-session`, `GET /api/admin/version-check`, `PUT /api/admin/approve-user`, `GET /api/admin/list-quizzes`, `POST /api/admin/switch-quiz`, `PUT /api/admin/config`
- Quiz management: `GET /api/admin/quiz/{filename}`, `POST /api/admin/create-quiz`, `PUT /api/admin/quiz/{filename}`, `DELETE /api/admin/quiz/{filename}`, `POST /api/admin/download-quiz`, `POST /api/admin/unite-quizzes`
- Quiz file attachments: `GET /api/admin/list-files` (list files in quizzes/attach/)
- Checker templates: `GET /api/admin/list-checker-templates` (list configured checker templates for text questions)
- File management: `GET /api/files/list`, `GET /api/files/{type}/view/{filename}`, `GET /api/files/{type}/download/{filename}`, `PUT /api/files/quizzes/save/{filename}`
- Tunnel management: `POST /api/admin/tunnel/connect`, `POST /api/admin/tunnel/disconnect`, `GET /api/admin/tunnel/public-key`

**Admin Pages (local network only):**
- `GET /admin/` - Admin interface page
- `GET /live-stats/` - Live stats page
- `GET /files/` - File manager page

**WebSockets:**
- `WS /ws/live-stats` (local network only), `WS /ws/admin` (local network only, admin approval + tunnel status notifications)

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
- **Python**: 3.9+ (tested with 3.9-3.14)
- **Poetry**: Installed inside venv (not globally) to avoid conflicts
- **Test ports**: Tests use ports 8080-8087 for parallel execution (-n 4 uses 4 workers)

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
- **Server-side timing** for accuracy (starts on admin approval if required)
- **Multi-file quiz system** in `quizzes/` dir, auto-created if missing
- **Session-based admin auth** - Master key sent in request body to `/api/admin/auth`, returns session cookie for subsequent requests (no header-based auth)
- **Config validation** with comprehensive structure/type checks before save
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
- **Test completion detection** uses answer count (`len(user_answers[user_id])`) instead of question ID to support randomization
- **Live stats first question** uses user's actual first from `question_order` (prevents duplicates)
- **Two-group live stats** - Users split into "In Progress" and "Completed" groups, automatically move on completion
- **Multi-platform binaries** via GitHub Actions (macOS-13 Intel, macOS-14 ARM64, Linux, Windows)
- **Coverage excludes build tools**: build.py and binary_entry.py omitted from coverage (not runtime code)
- **Wizard-only quiz editor** - Admin panel uses wizard mode only; YAML editing available in file manager with validation
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
- **Local network restriction** - All admin functionality (API endpoints via @admin_auth_required, HTML pages, WebSockets) automatically restricted to private networks (RFC 1918: 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16) with no configuration needed
- **Quiz download folder validation** - Path traversal protection: blocks "..", absolute paths (Unix/Windows), normalizes paths, ensures extraction stays within quizzes directory; allows subfolder paths like "folder/subfolder/"
- **Clipboard API fallback** - Copy public key button uses modern navigator.clipboard API for HTTPS/localhost, falls back to document.execCommand() for non-secure contexts (HTTP over IP)
- **Package version check** - Admin panel periodically checks if package was updated while server is running by comparing in-memory version with file version; shows "Restart Required" banner when mismatch detected
- **Quiz file attachments** - Questions can have downloadable files via `file` field (e.g., `file: "data.xlsx"`). Files stored in `quizzes/attach/`, served at `/attach/{filename}` with `Content-Disposition: attachment` header for forced download. Server auto-prepends `/attach/` when serving to client. Admin panel has file picker modal for selecting files.
- **Startup environment logging** - On server start, logs comprehensive environment info for troubleshooting: WebQuiz version, Python version/executable, OS/platform info, aiohttp version, working directory, config file path, binary mode status, server/path/admin/registration/tunnel configuration, and network interfaces. Master key value is never logged (only True/False).
- **SD card/slow storage reliability** - All file writes (config, quizzes, CSV) use `flush()` + `os.fsync()` to ensure data is physically written to storage before returning success. Prevents data loss on Raspberry Pi and systems with SD cards or exFAT partitions when powered off shortly after save.
- **Config hot-reload** - When admin saves config via web form (`PUT /api/admin/config`), changes are applied immediately without server restart. Hot-reloadable: registration settings (approve, fields, username_label), admin.trusted_ips, downloadable quizzes list, tunnel config. Requires restart (security/stability): server host/port, paths, master_key - shows "restart required" message with specific config paths. Quiz always restarted (users/state cleared) on config save. Templates are reloaded on each config save. If applying changes fails, config file is automatically rolled back to previous state.
- **Multi-quiz selection** - Admin panel uses `<select multiple>` for quiz list instead of clickable divs. Single selection shows standard buttons (Switch, Edit, Duplicate, Delete). Multiple selection (Ctrl+click/Cmd+click) shows Unite button and Delete. Delete button disabled when current quiz is in selection.
- **Quiz list with titles** - `GET /api/admin/list-quizzes` returns array of objects with `filename` and `title` fields (title is null if quiz has no title). Admin panel displays quiz titles alongside filenames in selection list.
- **Quiz unite** - `POST /api/admin/unite-quizzes` combines multiple quizzes into one. Takes config (title, settings) from first quiz, combines all questions in order. Accepts `{quiz_filenames: [...], new_name: "..."}`, validates all quizzes exist and have valid structure, warns about duplicate questions, creates new quiz file with fsync.
- **Question points** - Each question can have a `points` field (default: 1). Points are tracked per-answer, accumulated in user stats, and displayed in live stats (earned/total format), final results, and users CSV. Questions with >1 point show a trophy indicator in UI.
- **Text input questions** - Questions with `checker` field are automatically detected as text input questions (no `type` field needed). Fields: `default_value` (initial textarea value), `correct_value` (shown when wrong), `checker` (Python code for validation). Checker code is validated for Python syntax on quiz save. Checker code runs in sandboxed environment with limited builtins (math functions, basic types) plus helper functions: `to_int(str)` - convert to integer, `distance(str)` - parse distance (supports "2km", "2000m", "2км"), `direction_angle(str)` - parse direction angle ("20-30" = 2030). If checker is empty, exact match with `correct_value` is used. Returns `checker_error` message on failure.
- **Checker templates** - Admin-configurable code templates for text question validation. Defined in config as `checker_templates: [{name: "...", code: "..."}]`. Templates available in admin quiz editor for quick insertion.
- **Dark/Light theme switcher** - All pages (quiz, admin, live stats, file manager) support dark/light theme toggle via button in top-right corner. Theme preference persisted in localStorage (`theme` key), shared across all pages. CSS uses CSS variables (`:root` for light, `[data-theme="dark"]` for dark) with smooth 0.3s transitions.

## Key Flows

**Quiz**: Load YAML → inject to HTML → register user → cookie session → submit answers → timing → validate → in-memory → CSV flush
**Approval**: Register → `approved: false` → wait → admin WebSocket notified → approve button → **timing starts** → student checks → quiz begins
**Randomization**: Load YAML → register → `random.shuffle()` → store `question_order` per-user → client receives array → JS reorders → persists across sessions
**Admin**: Switch quiz → reset all state (users, progress, responses) → new CSV → session isolation
**Live Stats Groups**: Users display in "In Progress" group → answer questions → complete final question → automatically move to "Completed" group with `completed: true` flag in WebSocket
**Tunnel**: Initialize → check/generate keys → admin clicks connect → fetch server config → create SSH connection → forward remote Unix socket to local port (forward_remote_path_to_port) → broadcast public URL via WebSocket → auto-reconnect on disconnect
**Startup**: Load config → create TestingServer → initialize log file → configure logging → **log environment info** (version, Python, OS, config, paths, network) → initialize tunnel → load questions → start periodic flush → register routes
**Config Hot-Reload**: Admin saves config → validate YAML → backup original config → write to file → reload config from file → detect restart-required changes (server, paths, master_key) → apply safe changes (registration, trusted_ips, quizzes, tunnel) → reload templates → disconnect tunnel if connected (admin can reconnect) → restart current quiz (reset users/state) → return message (either "saved and applied" or "restart required for: ..."). On failure: rollback config file to backup → return error
**Text Question Validation**: Submit text answer → check question type → if text: execute checker code in sandboxed env (restricted builtins + math + helper functions: to_int, distance, direction_angle) → if exception: answer incorrect + return error message → if no exception: answer correct. No checker: exact match with `correct_value`

**Setup**: Parallel testing with ports 8080-8087, `custom_webquiz_server` fixture auto-cleans directories, `conftest.py` for shared fixtures

## Important Notes
- **CSV files** (2 per session): `{quiz_name}_user_responses.csv` (submissions) + `{quiz_name}_user_responses.users.csv` (user stats with total_time in MM:SS format, earned_points, total_points)
- **Config** (`webquiz.yaml`): All sections optional, editable via `/files/` or admin panel, hot-reloaded on save (returns `restart_required` list if server/paths/master_key changed), UTF-8 charset header
- **Config options**:
  - `server.include_ipv6: true` - Include IPv6 addresses in network interfaces list (default: false)
  - `server.url_format` - URL format for admin panel network access URLs (default: `http://{IP}:{PORT}/`). Placeholders: `{IP}`, `{PORT}`. Example for reverse proxy: `http://{IP}/webquiz/`
  - `registration.approve: true` - Admin approval required, timing starts on approval (default: false)
  - `registration.username_label` - Customize username field label (default: "Ім'я користувача")
  - `randomize_questions: true` - Per-student random order, stored as `question_order` array (default: false)
  - `show_right_answer: false` - Auto-advance without continue button (seamless flow)
  - `show_answers_on_completion: true` - Reveal correct answers dynamically after all approved students complete, with waiting message and reload prompt (default: false)
  - `tunnel.server` - SSH tunnel server hostname (e.g., "tunnel.example.com")
  - `tunnel.public_key` - Path to SSH public key file (auto-generated if missing)
  - `tunnel.private_key` - Path to SSH private key file (auto-generated if missing)
  - `tunnel.socket_name` - Optional fixed socket name instead of random generation (default: random 6-8 hex chars)
  - `tunnel.config` - Optional nested config subsection (username, socket_directory, base_url) - bypasses server fetch when provided
- Questions use **0-indexed** `correct_answer` field and optional `points` field (default: 1)
- Text questions are detected by `checker` field (no `type` field needed, no `options` or `correct_answer`)
- `checker_templates` - List of `{name, code}` objects for admin panel template dropdown
- Usernames unique per quiz session
- Switching quizzes = full state reset

## Release
**Trigger**: GitHub Actions → "Release and Deploy to PyPI" → Enter version (X.Y.Z)

**Process**: Build binaries (Linux, macOS Intel/ARM64, Windows) → Update versions → Generate PDFs (uk/en) → Publish to PyPI → Create GitHub release with 8 assets (2 Python packages + 4 zipped binaries + 2 PDFs)

**Note**: macOS builds on separate runners (macos-15-intel Intel, macos-15 ARM64)
