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
- **Storage**: In-memory → CSV (30s flush), YAML configs, quiz state resets on switch
- **Auth**: Master key decorator for admin endpoints
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

**Admin (master key required):**
- `GET /admin`, `POST /api/admin/auth`, `PUT /api/admin/approve-user`, `GET /api/admin/list-quizzes`, `POST /api/admin/switch-quiz`, `PUT /api/admin/config`
- Quiz management: `GET /api/admin/quiz/{filename}`, `POST /api/admin/create-quiz`, `PUT /api/admin/quiz/{filename}`, `DELETE /api/admin/quiz/{filename}`
- File management: `GET /api/files/list`, `GET /api/files/{type}/view/{filename}`, `GET /api/files/{type}/download/{filename}`, `PUT /api/files/quizzes/save/{filename}`
- Tunnel management: `POST /api/admin/tunnel/connect`, `POST /api/admin/tunnel/disconnect`

**WebSockets:**
- `WS /ws/live-stats` (public), `WS /ws/admin` (admin approval + tunnel status notifications)

## Dev Commands

⚠️ **ALWAYS use venv**: All Python commands and poetry operations must run inside virtual environment (`source venv/bin/activate` or `poetry shell`)

```bash
# Setup
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
- **Master key decorator** for admin authentication
- **Config validation** with comprehensive structure/type checks before save
- **Smart CSV naming** with quiz prefix + unique suffixes (no overwrites)
- **Quiz state reset** on switch for complete isolation
- **In-memory → CSV** with 30s periodic flush using CSV module
- **Cookie-based session** persistence (user_id)
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

## Key Flows

**Quiz**: Load YAML → inject to HTML → register user → cookie session → submit answers → timing → validate → in-memory → CSV flush
**Approval**: Register → `approved: false` → wait → admin WebSocket notified → approve button → **timing starts** → student checks → quiz begins
**Randomization**: Load YAML → register → `random.shuffle()` → store `question_order` per-user → client receives array → JS reorders → persists across sessions
**Admin**: Switch quiz → reset all state (users, progress, responses) → new CSV → session isolation
**Live Stats Groups**: Users display in "In Progress" group → answer questions → complete final question → automatically move to "Completed" group with `completed: true` flag in WebSocket
**Tunnel**: Initialize → check/generate keys → admin clicks connect → fetch server config → create SSH connection → forward remote Unix socket to local port (forward_remote_path_to_port) → broadcast public URL via WebSocket → auto-reconnect on disconnect

**Setup**: Parallel testing with ports 8080-8087, `custom_webquiz_server` fixture auto-cleans directories, `conftest.py` for shared fixtures

## Important Notes
- **CSV files** (2 per session): `{quiz_name}_user_responses.csv` (submissions) + `{quiz_name}_user_responses.users.csv` (user stats)
- **Config** (`webquiz.yaml`): All sections optional, editable via `/files/`, requires restart, UTF-8 charset header
- **Config options**:
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
- Questions use **0-indexed** `correct_answer` field
- Usernames unique per quiz session
- Switching quizzes = full state reset

## Release
**Trigger**: GitHub Actions → "Release and Deploy to PyPI" → Enter version (X.Y.Z)

**Process**: Build binaries (Linux, macOS Intel/ARM64, Windows) → Update versions → Generate PDFs (uk/en) → Publish to PyPI → Create GitHub release with 8 assets (2 Python packages + 4 zipped binaries + 2 PDFs)

**Note**: macOS builds on separate runners (macos-13 Intel, macos-14 ARM64)
