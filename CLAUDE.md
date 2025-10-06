# CLAUDE.md

This file contains project context and memory for Claude Code sessions.

## Project Overview
WebQuiz - A modern web-based quiz and testing system built with Python and aiohttp that allows users to take multiple-choice tests with real-time answer submission and statistics tracking. Features multi-quiz management with admin controls.

**Key Features:**
- User registration with unique usernames and UUID-based user IDs
- **Registration approval workflow**: Optional admin approval for new registrations with real-time notifications
- **Multi-quiz system**: Questions loaded from `quizzes/` directory with multiple YAML files
- **Admin interface**: Web-based admin panel with master key authentication for quiz management
- **Config file editor**: Web-based configuration editor with real-time validation in file manager
- **Dynamic quiz switching**: Real-time quiz switching with automatic server state reset
- **Smart file naming**: CSV files prefixed with quiz names, unique suffixes prevent overwrites
- Web interface with auto-generated index.html if not present
- Real-time answer validation via REST API
- **Immediate answer feedback**: Visual confirmation (green/red) after each answer submission
- Server-side timing for accurate response measurement (starts on approval if approval required)
- In-memory storage with periodic CSV backup (30s intervals) to configurable file path
- User session persistence with cookie-based user ID storage
- Responsive web interface with dark/light theme
- **Live statistics monitoring**: Real-time WebSocket-powered dashboard showing user progress with timing information
- **Admin approval dashboard**: Real-time pending approvals with WebSocket updates
- Configurable file paths for quizzes, logs, CSV output, and static files
- **Binary distribution with PyInstaller 6.15**: Creates standalone executable with automatic executable directory defaults
- Comprehensive test suite (integration + unit tests)

## Architecture
- **Backend**: Python aiohttp server with middleware-based error handling, admin authentication, and WebSocket support
- **Frontend**: Vanilla HTML/JS single-page application with embedded questions data + admin interface + live stats dashboard
- **Data Storage**: 
  - **Questions**: Multiple YAML files in `quizzes/` directory with correct answers (auto-created with defaults)
  - **User responses**: In-memory → CSV files with quiz name prefixes (proper CSV module usage)
  - **Users**: In-memory dictionary (user_id as key, contains username) - resets on quiz switch
  - **Session timing**: Server-side tracking for accurate measurements
  - **Quiz state**: Dynamic loading and switching with complete state reset
  - **Live stats**: Real-time user progress tracking with WebSocket broadcasting and timing information
- **API Design**: RESTful endpoints with JSON responses + admin-protected endpoints
- **Authentication**: Master key-based admin authentication with decorator protection
- **Testing**: Integration tests with real HTTP requests + unit tests for internal logic

## Key Files
- `webquiz/server.py` - Main aiohttp server with middleware, API endpoints, and admin functionality
- `webquiz/cli.py` - CLI interface with daemon support and configurable default paths for binary execution
- `webquiz/build.py` - PyInstaller binary build script
- `webquiz/binary_entry.py` - Entry point for PyInstaller binary with executable directory defaults
- `webquiz/__init__.py` - Package initialization
- **`quizzes/` directory** - Contains multiple YAML quiz files:
  - `default.yaml` - Default questions (auto-created if missing)
  - `math_quiz.yaml` - Mathematics questions
  - `geography_quiz.yaml` - Geography questions  
  - _(additional quiz files as needed)_
- `webquiz/templates/index.html` - Main quiz interface template
- **`webquiz/templates/admin.html`** - Admin interface template for quiz management
- **`webquiz/templates/files.html`** - File manager template with logs, CSV, and config editor tabs
- **`webquiz/templates/live_stats.html`** - Live statistics dashboard template with WebSocket client
- **`{quiz_name}_user_responses.csv`** - User response storage with quiz name prefix (e.g., `math_quiz_user_responses.csv`)
- **`server_{suffix}.log`** - Server activity logs with unique suffixes (no overwrites)
- `static/` - Static files folder (automatically generated, contains current quiz's index.html)
- **`dist/webquiz`** - Standalone PyInstaller binary executable
- `tests/` - Test suite
  - `test_cli_directory_creation.py` - CLI directory and file creation tests (8 tests)
  - `test_admin_api.py` - Admin API functionality tests (13 tests)
  - `test_config_management.py` - Config editor and validation tests (17 tests)
  - `test_registration_approval.py` - Registration approval workflow tests (23 tests)
  - `conftest.py` - Test fixtures and configuration with parallel testing support
- `pyproject.toml` - Poetry configuration and dependencies (includes PyInstaller 6.15)
- `requirements.txt` - Legacy pip dependencies
- `venv/` - Python virtual environment
- `.gitignore` - Git ignore file (excludes generated files, logs, virtual env)
- `.github/workflows/test.yml` - GitHub Actions CI/CD pipeline for automated testing

## API Endpoints

### Public Endpoints
- `POST /api/register` - Register unique username (returns user_id, requires_approval, approved flags)
- `PUT /api/update-registration` - Update registration data (only if not approved yet)
- `POST /api/submit-answer` - Submit answer (user_id, question_id, selected_answer)
- `GET /api/verify-user/{user_id}` - Verify user session, get progress, and check approval status

### Admin Endpoints (require master key authentication)
- **`GET /admin`** - Serve admin interface webpage
- **`POST /api/admin/auth`** - Test admin authentication (master key required)
- **`PUT /api/admin/approve-user`** - Approve a user for testing (starts timing)
- **`GET /api/admin/list-quizzes`** - List available quiz files and current active quiz
- **`POST /api/admin/switch-quiz`** - Switch to different quiz file and reset server state
- **`PUT /api/admin/config`** - Update server configuration file with validation (requires restart)

### Live Stats Endpoints (public access)
- **`GET /live-stats`** - Serve live statistics dashboard webpage
- **`WebSocket /ws/live-stats`** - Real-time WebSocket connection for live progress updates

### Admin WebSocket Endpoint
- **`WebSocket /ws/admin`** - Real-time WebSocket for admin approval notifications (new registrations, updates, approvals)

## Commands
```bash
# Setup with Poetry (recommended)
poetry install

# Setup with pip (alternative)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run server
webquiz                              # Foreground mode
webquiz --master-key secret123       # Enable admin interface with master key
webquiz --quizzes-dir my_quizzes     # Use custom quizzes directory
webquiz --logs-dir /var/log          # Use custom logs directory
webquiz --csv-dir /data              # Use custom CSV directory
webquiz --static /var/www/quiz       # Use custom static directory
WEBQUIZ_MASTER_KEY=secret webquiz    # Set master key via environment variable
webquiz -d                           # Daemon mode
webquiz --stop                       # Stop daemon
webquiz --status                     # Check status

# Build binary
poetry run build_binary              # Create standalone executable with PyInstaller

# Run tests (ALWAYS use venv!)
source venv/bin/activate && python -m pytest tests/ -v          # Run all tests with verbose output
source venv/bin/activate && python -m pytest tests/ -v -n 4     # Run tests in parallel with 4 workers (requires pytest-xdist)

# Alternative (without Poetry installation)
python -m webquiz.cli

## Technical Decisions
- **Middleware over try-catch**: Used aiohttp middleware for cleaner error handling
- **UUID-based user IDs**: Users identified by UUID with username storage, stored by user_id as key
- **Server-side timing**: Question timing tracked server-side for accuracy and security
- **Multi-file quiz system**: `quizzes/` directory with multiple YAML files instead of single config
- **Master key authentication**: Admin endpoints protected with decorator-based authentication
- **Config validation**: All sections optional with defaults, comprehensive structure and type validation before save
- **Smart file naming**: CSV files prefixed with quiz names, unique suffixes prevent overwrites
- **Dynamic quiz switching**: Complete server state reset when switching quizzes for isolation
- **Auto-YAML creation**: Server creates default quiz files if directory is empty
- **Periodic CSV flush**: Every 30 seconds using proper CSV module for escaping
- **Embedded questions data**: Questions injected directly into HTML template (no separate JSON file)
- **In-memory storage**: Fast responses, CSV backup for persistence, resets on quiz switch
- **Session persistence**: Cookie-based user_id storage for seamless user experience
- **Real-time monitoring**: WebSocket-based live statistics with automatic client cleanup and broadcasting
- **Comprehensive testing**: Integration tests for API + unit tests for internal logic

## Data Flow

### Normal Quiz Flow
1. Server loads quiz files from `quizzes/` directory → selects first available quiz → injects questions into HTML template (without correct answers)
2. User registers → user_id generated, stored by user_id key
   - If `registration.approve: false` (default): timing starts immediately
   - If `registration.approve: true`: timing delayed until admin approval
3. Client stores user_id in cookies for session persistence
4. User submits answers → server calculates time taken → validated against correct answers → stored in memory
5. Periodic flush → responses written to CSV with quiz name prefix using proper CSV module
6. Server automatically tracks timing for each question transition

### Admin Quiz Management Flow
1. Admin accesses `/admin` → enters master key → authenticates
2. Admin views available quiz files and current active quiz
3. Admin selects different quiz → clicks switch button
4. Server resets all state (users, progress, responses) → loads new quiz → regenerates HTML → creates new CSV file
5. All existing users lose session (intentional isolation between quizzes)

### Config Editor Flow
1. Admin accesses `/files/` → navigates to Config tab
2. Config content auto-loaded from `webquiz.yaml` and displayed in editor
3. Admin edits config → clicks Save
4. Server validates YAML syntax → validates structure and data types → saves to file
5. Warning displayed: changes require server restart to take effect
6. Validation errors shown if config is invalid (prevents saving bad configs)

### Registration Approval Flow (when `registration.approve: true`)
1. Student registers → server creates user with `approved: false`
2. Student sees "Waiting for approval" page with editable registration form
3. Admin receives WebSocket notification on `/ws/admin`
4. Admin sees pending user in "Pending Approvals" panel (real-time)
5. Student can update registration data (sends update to admin via WebSocket)
6. Student clicks "Check" button → API call to check approval status
7. Admin clicks "Approve" button → server sets `approved: true` and **starts timing**
8. Next time student clicks "Check" → API returns `approved: true`
9. Student UI shows first question → **timing already started server-side**

## Test Strategy
- **CLI Directory Creation Tests (8)**: Test directory and file creation by webquiz CLI command
- **Admin API Tests (13)**: Test admin interface authentication, quiz management, and validation endpoints
- **Config Management Tests (17)**: Test config editor, YAML validation, structure validation, and error handling
- **Registration Approval Tests (23)**: Test approval workflow, timing behavior, and WebSocket notifications
  - POST /api/register modifications (4 tests)
  - GET /api/verify-user/{user_id} modifications (3 tests)
  - PUT /api/update-registration (5 tests)
  - PUT /api/admin/approve-user (6 tests)
  - WebSocket /ws/admin (3 tests - partial)
  - Timing behavior validation (2 tests)
- **Total: 61 tests** with GitHub Actions CI/CD pipeline
- **Parallel Testing**: Tests use predefined ports (8080-8087) with worker-based allocation to prevent conflicts
- **Fast Server Startup**: Port availability checking instead of HTTP requests for efficient fixture startup
- **Testing Philosophy**: Create new automated tests for newly implemented functionality instead of manual testing
- **Test Organization**: Fixtures separated into `conftest.py` for reusability across test modules

## Notes
- Username must be unique across all users (per quiz session)
- Questions use 0-indexed correct_answer field
- Server validates all answers server-side with automatic timing
- **CSV headers**: user_id,username,question_text,selected_answer_text,correct_answer_text,is_correct,time_taken_seconds
- **CSV naming**: `{quiz_name}_user_responses.csv` with unique suffixes (e.g., `math_quiz_user_responses_0001.csv`)
- **Admin access**: Master key required for admin endpoints, can be set via CLI or environment variable
- **Config editor**: Web-based YAML editor with validation in `/files/` (Config tab), changes require server restart
- **Config validation**: All config sections optional (uses defaults), validates YAML syntax and data types before save
- **Registration approval** (`registration.approve: true`):
  - Students wait for admin approval before starting test
  - Timing starts only when admin approves (not at registration)
  - Students can update registration data while waiting
  - Admin receives real-time WebSocket notifications
  - Manual "Check" button for students to check approval status
  - Default: `approve: false` (auto-approve, existing behavior)
- **Quiz isolation**: Switching quizzes resets all server state for complete isolation
- **File safety**: Unique suffixes prevent overwriting existing log/CSV files
- Middleware handles JSON parsing errors and validation
- HTTP exceptions used for proper status codes (404, 400, 500)
- Generated files (logs, CSV, client JSON, YAML) are git-ignored
- Server automatically creates missing quiz files with sample questions