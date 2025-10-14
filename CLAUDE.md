# CLAUDE.md

## ⚠️ CRITICAL: Every Code Change MUST Include

1. **Update CLAUDE.md** - Reflect architectural changes, new features, API endpoints, technical decisions
2. **Update README.md** - User-facing documentation
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
- **Testing**: Integration + unit tests (101 total)

## Key Files
- `webquiz/server.py` - Main aiohttp server
- `webquiz/cli.py` - CLI with daemon support
- `webquiz/build.py` - PyInstaller build script
- `webquiz/templates/` - index.html, admin.html, files.html, live_stats.html
- `tests/` - Test suite (8+13+17+23+6+10+14+5+5 = 101 tests)
- `docs/uk/`, `docs/en/` - Documentation (compiled to PDF with version)

## API Endpoints

**Public:**
- `POST /api/register`, `PUT /api/update-registration`, `POST /api/submit-answer`, `GET /api/verify-user/{user_id}`

**Admin (master key required):**
- `GET /admin`, `POST /api/admin/auth`, `PUT /api/admin/approve-user`, `GET /api/admin/list-quizzes`, `POST /api/admin/switch-quiz`, `PUT /api/admin/config`

**WebSockets:**
- `WS /ws/live-stats` (public), `WS /ws/admin` (admin approval notifications)

## Dev Commands

```bash
# Setup
poetry install

# Run
webquiz --master-key secret123
webquiz -d  # daemon

# Test (ALWAYS use venv!)
source venv/bin/activate && python -m pytest tests/ -v -n 4

# Build binary (current OS only)
poetry run build_binary
```

## Technical Decisions
- **Middleware-based error handling** for aiohttp
- **6 digits user ID** stored by user_id as key
- **Server-side timing** for accuracy (starts on admin approval if required)
- **Multi-file quiz system** in `quizzes/` dir, auto-created if missing
- **Master key decorator** for admin authentication
- **Config validation** with comprehensive structure/type checks before save
- **Smart CSV naming** with quiz prefix + unique suffixes (no overwrites)
- **Quiz state reset** on switch for complete isolation
- **In-memory → CSV** with 30s periodic flush using CSV module
- **Cookie-based session** persistence (user_id)
- **WebSocket live stats** with automatic client cleanup
- **Auto-advance UI** when `show_right_answer: false`
- **Mobile-first** with `width: 100%; max-width: [size]` and @media ≤768px
- **UTF-8 Content-Type** for Ukrainian/multilingual text support
- **Server-side question randomization** generated at registration, stored per-user as `question_order` array, client reorders via JS
- **Test completion detection** uses answer count (`len(user_answers[user_id])`) instead of question ID to support randomization
- **Live stats first question** uses user's actual first from `question_order` (prevents duplicates)
- **Multi-platform binaries** via GitHub Actions (macOS-13 Intel, macOS-14 ARM64, Linux, Windows)

## Key Flows

**Quiz**: Load YAML → inject to HTML → register user → cookie session → submit answers → timing → validate → in-memory → CSV flush
**Approval**: Register → `approved: false` → wait → admin WebSocket notified → approve button → **timing starts** → student checks → quiz begins
**Randomization**: Load YAML → register → `random.shuffle()` → store `question_order` per-user → client receives array → JS reorders → persists across sessions
**Admin**: Switch quiz → reset all state (users, progress, responses) → new CSV → session isolation

## Tests (101 total)
- CLI directory creation (8)
- Admin API (13)
- Config management (17)
- Registration approval (23)
- Auto-advance UI (6)
- Username label (10)
- Question randomization (14)
- Admin quiz editor (5)
- Live stats WebSocket (5)

**Setup**: Parallel testing with ports 8080-8087, `custom_webquiz_server` fixture auto-cleans directories, `conftest.py` for shared fixtures

## Important Notes
- **CSV files** (2 per session): `{quiz_name}_user_responses.csv` (submissions) + `{quiz_name}_user_responses.users.csv` (user stats)
- **Config** (`webquiz.yaml`): All sections optional, editable via `/files/`, requires restart, UTF-8 charset header
- **Config options**:
  - `registration.approve: true` - Admin approval required, timing starts on approval (default: false)
  - `registration.username_label` - Customize username field label (default: "Ім'я користувача")
  - `randomize_questions: true` - Per-student random order, stored as `question_order` array (default: false)
  - `show_right_answer: false` - Auto-advance without continue button (seamless flow)
- Questions use **0-indexed** `correct_answer` field
- Usernames unique per quiz session
- Switching quizzes = full state reset

## Release
**Trigger**: GitHub Actions → "Release and Deploy to PyPI" → Enter version (X.Y.Z)

**Process**: Build binaries (Linux, macOS Intel/ARM64, Windows) → Update versions → Generate PDFs (uk/en) → Publish to PyPI → Create GitHub release with 8 assets (2 Python packages + 4 zipped binaries + 2 PDFs)

**Note**: macOS builds on separate runners (macos-13 Intel, macos-14 ARM64)
