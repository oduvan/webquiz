# CLAUDE.md

This file contains project context and memory for Claude Code sessions.

## ⚠️ CRITICAL: Documentation and Testing Requirements

**EVERY code change MUST include:**

1. **Update CLAUDE.md** - This file must reflect all architectural changes, new features, API endpoints, data flows, and technical decisions
2. **Update README.md** - User-facing documentation must be updated with new features, installation steps, or usage changes
3. **Update docs/** - Both Ukrainian (`docs/uk/`) and English (`docs/en/`) documentation must be updated:
   - Add new sections for new features
   - Update existing sections for modified functionality
   - Keep both language versions synchronized
4. **Create new tests** - All new functionality MUST have automated tests:
   - Integration tests for API endpoints
   - Unit tests for internal logic
   - Update test counts in CLAUDE.md
   - Follow existing test patterns in `tests/` directory
5. **Mobile Support** - All UI changes MUST be mobile-responsive:
   - Test on mobile viewport (max-width: 768px)
   - Input fields must not overflow screen
   - Tables should stack vertically on mobile
   - Use responsive width: `width: 100%; max-width: [desktop-size]`
   - Add mobile-specific CSS in @media queries

**Testing Philosophy:**
- Write tests FIRST or immediately after implementing features
- NEVER rely on manual testing alone
- Tests should be comprehensive and cover edge cases
- All tests must pass before considering work complete

**Documentation is not optional** - It's a core part of every feature implementation.
**Mobile support is not optional** - All UI elements must be responsive and mobile-friendly.

---

## Project Overview
WebQuiz - A modern web-based quiz and testing system built with Python and aiohttp that allows users to take multiple-choice tests with real-time answer submission and statistics tracking. Features multi-quiz management with admin controls.

**Key Features:**
- User registration with unique usernames and UUID-based user IDs
- **Customizable username label**: Configurable `registration.username_label` to customize the username field label (default: Ukrainian "Ім'я користувача")
- **Mobile-responsive UI**: All forms and interfaces adapt to mobile screens (≤768px) with proper input sizing and table stacking
- **Registration approval workflow**: Optional admin approval for new registrations with real-time notifications
- **Multi-quiz system**: Questions loaded from `quizzes/` directory with multiple YAML files
- **Admin interface**: Web-based admin panel with master key authentication for quiz management
- **Config file editor**: Web-based configuration editor with real-time validation in file manager
- **Dynamic quiz switching**: Real-time quiz switching with automatic server state reset
- **Smart file naming**: CSV files prefixed with quiz names, unique suffixes prevent overwrites
- Web interface with auto-generated index.html if not present
- Real-time answer validation via REST API
- **Immediate answer feedback**: Visual confirmation (green/red) after each answer submission
- **Auto-advance functionality**: Seamless question progression when `show_right_answer: false` (no continue button needed)
- **Question randomization**: Configurable per-student question order randomization with `randomize_questions: true` in quiz YAML
- Server-side timing for accurate response measurement (starts on approval if approval required)
- In-memory storage with periodic CSV backup (30s intervals) to configurable file path
- User session persistence with cookie-based user ID storage
- Responsive web interface with dark/light theme
- **Live statistics monitoring**: Real-time WebSocket-powered dashboard showing user progress with timing information
- **Admin approval dashboard**: Real-time pending approvals with WebSocket updates
- Configurable file paths for quizzes, logs, CSV output, and static files
- **Multi-platform binary distribution**: Automated builds for Linux, macOS (Intel + Apple Silicon), and Windows via GitHub Actions
  - PyInstaller 6.15 creates standalone executables with no Python dependency
  - Separate macOS binaries for Intel (x86_64) and Apple Silicon (ARM64) architectures
  - Automatic executable directory defaults for portable operation
  - Binaries automatically attached to GitHub releases as zipped archives
- Comprehensive test suite (integration + unit tests)

## Architecture
- **Backend**: Python aiohttp server with middleware-based error handling, admin authentication, and WebSocket support
- **Frontend**: Vanilla HTML/JS single-page application with embedded questions data + admin interface + live stats dashboard
  - **Mobile-responsive CSS**: @media queries for viewport ≤768px with fluid layouts, input field adaptations, and table stacking
  - **Registration forms**: Responsive width (`width: 100%; max-width: 250px`) with proper box-sizing for mobile devices
  - **Waiting approval forms**: Dynamic JavaScript-generated forms with mobile-responsive styles
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
- **`docs/uk/`** - Ukrainian documentation in Markdown format (compiled to PDF with version number on title page)
- **`docs/en/`** - English documentation in Markdown format (compiled to PDF with version number on title page)
- **`{quiz_name}_user_responses.csv`** - User response storage with quiz name prefix (e.g., `math_quiz_user_responses.csv`)
- **`server_{suffix}.log`** - Server activity logs with unique suffixes (no overwrites)
- `static/` - Static files folder (automatically generated, contains current quiz's index.html)
- **`dist/webquiz`** - Standalone PyInstaller binary executable
- `tests/` - Test suite
  - `test_cli_directory_creation.py` - CLI directory and file creation tests (8 tests)
  - `test_admin_api.py` - Admin API functionality tests (13 tests)
  - `test_config_management.py` - Config editor and validation tests (17 tests)
  - `test_registration_approval.py` - Registration approval workflow tests (23 tests)
  - `test_auto_advance.py` - Auto-advance Selenium tests for show_right_answer behavior (6 tests)
  - `test_username_label.py` - Username label customization tests (10 tests)
  - `test_randomize_questions.py` - Question randomization tests (13 tests)
  - `test_admin_quiz_editor.py` - Admin quiz editor with randomize_questions tests (5 tests)
  - `test_live_stats_websocket.py` - Live stats WebSocket tests with randomization (5 tests)
  - `conftest.py` - Test fixtures and configuration with parallel testing support
- `pyproject.toml` - Poetry configuration and dependencies (includes PyInstaller 6.15)
- `requirements.txt` - Legacy pip dependencies
- `venv/` - Python virtual environment
- `.gitignore` - Git ignore file (excludes generated files, logs, virtual env)
- `.github/workflows/test.yml` - GitHub Actions CI/CD pipeline for automated testing
- `.github/workflows/release.yml` - GitHub Actions release workflow with multi-platform binary builds

## API Endpoints

### Public Endpoints
- `POST /api/register` - Register unique username (returns user_id, requires_approval, approved flags)
- `PUT /api/update-registration` - Update registration data (only if not approved yet)
- `POST /api/submit-answer` - Submit answer (user_id, question_id, selected_answer)
- `GET /api/verify-user/{user_id}` - Verify user session, get progress, and check approval status (includes question_order array when randomization enabled)

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

### Installation Options

#### Option 1: Pre-built Binaries (No Python Required)
Download platform-specific zipped binaries from [GitHub Releases](https://github.com/oduvan/webquiz/releases):
```bash
# Linux
wget https://github.com/oduvan/webquiz/releases/latest/download/webquiz-linux.zip
unzip webquiz-linux.zip
chmod +x webquiz-linux
./webquiz-linux --help

# macOS Intel (x86_64)
wget https://github.com/oduvan/webquiz/releases/latest/download/webquiz-macos-intel.zip
unzip webquiz-macos-intel.zip
chmod +x webquiz-macos-intel
./webquiz-macos-intel --help

# macOS Apple Silicon (ARM64/M1/M2/M3)
wget https://github.com/oduvan/webquiz/releases/latest/download/webquiz-macos-apple-silicon.zip
unzip webquiz-macos-apple-silicon.zip
chmod +x webquiz-macos-apple-silicon
./webquiz-macos-apple-silicon --help

# Windows
# Download webquiz-windows.exe.zip from releases page, extract, then run:
webquiz-windows.exe --help
```

#### Option 2: Python Package Installation
```bash
# Setup with Poetry (recommended)
poetry install

# Setup with pip (alternative)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running the Server
```bash
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
```

### Development Commands
```bash
# Build binary locally (creates binary for current OS only)
poetry run build_binary              # Create standalone executable with PyInstaller

# Run tests (ALWAYS use venv!)
source venv/bin/activate && python -m pytest tests/ -v          # Run all tests with verbose output
source venv/bin/activate && python -m pytest tests/ -v -n 4     # Run tests in parallel with 4 workers (requires pytest-xdist)

# Alternative (without Poetry installation)
python -m webquiz.cli
```

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
- **Periodic CSV flush**: Automatic periodic flush using proper CSV module for escaping
- **Embedded questions data**: Questions injected directly into HTML template (no separate JSON file)
- **In-memory storage**: Fast responses, CSV backup for persistence, resets on quiz switch
- **Session persistence**: Cookie-based user_id storage for seamless user experience
- **Real-time monitoring**: WebSocket-based live statistics with automatic client cleanup and broadcasting
- **Auto-advance behavior**: When `show_right_answer: false`, quiz automatically progresses to next question after answer submission without requiring manual continue button click, creating seamless quiz flow
- **Mobile-first responsive design**: All UI elements use responsive widths with @media queries for ≤768px screens
  - Input fields: `width: 100%; max-width: [desktop-size]` pattern
  - Tables: Stack vertically on mobile with `display: block` for td elements
  - Registration forms: Server-generated HTML includes responsive styles, JavaScript forms match
- **Multi-platform binary distribution**: GitHub Actions workflow builds binaries for all major platforms
  - Matrix strategy builds on ubuntu-latest, macos-13 (Intel), macos-14 (Apple Silicon), and windows-latest simultaneously
  - macOS requires separate builds for Intel (x86_64) and Apple Silicon (ARM64) architectures due to PyInstaller limitations
  - PyInstaller creates self-contained executables with embedded templates and dependencies
  - All binaries are zipped for easier distribution and download
  - Only zipped binaries are attached to GitHub releases (8 total assets: 2 Python packages + 4 zipped binaries + 2 PDF docs)
  - Local `poetry run build_binary` creates binary for current OS/architecture only (PyInstaller limitation)
- **UTF-8 Content-Type header**: Index.html served with `Content-Type: text/html; charset=utf-8` to ensure proper display of Ukrainian/multilingual text (prevents ISO-8859-1 default encoding issues)
- **Customizable username label**: Config option `registration.username_label` allows customization of username field label in both registration and waiting approval forms
- **Server-side question randomization**: Random question order generated server-side during user registration/approval, stored per-user, and sent to client for reordering. Ensures each student gets unique randomized order that persists across sessions. Client-side JavaScript reorders questions array based on server-provided question IDs.
- **Live stats first question tracking**: When randomization enabled, live stats initialization uses user's actual first question ID from `question_order` array instead of hardcoded question 1, preventing duplicate "thinking" indicators in live stats dashboard.
- **Comprehensive testing**: Integration tests for API + unit tests for internal logic + WebSocket integration tests

## Data Flow

### Normal Quiz Flow
1. Server loads quiz files from `quizzes/` directory → selects first available quiz → injects questions into HTML template (without correct answers)
2. User registers → user_id generated, stored by user_id key
   - If `registration.approve: false` (default): timing starts immediately
   - If `registration.approve: true`: timing delayed until admin approval
3. Client stores user_id in cookies for session persistence
4. User submits answers → server calculates time taken → validated against correct answers → stored in memory
5. Automatic periodic flush → responses written to CSV with quiz name prefix using proper CSV module
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

### Question Randomization Flow (when `randomize_questions: true`)
1. Server loads quiz YAML → reads `randomize_questions` setting (default: false)
2. Student registers → server generates random question order using `random.shuffle()` → stores as `question_order` array in user data
   - If approval required: order generated at registration (before approval)
   - If no approval: order generated immediately at registration
3. Student verifies → server returns `question_order` array in API response (e.g., `[3, 1, 4, 2, 5]`)
4. Client receives question order → JavaScript `applyQuestionOrder()` function reorders questions array based on IDs
5. Questions displayed in randomized order → user submits answers using original question IDs
6. Question order persists across page reloads and browser sessions (stored server-side per user)
7. Each student gets unique randomized order (different students, different orders)

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
- **Auto-Advance Selenium Tests (6)**: Test automatic question progression when show_right_answer is false
  - Auto-advance behavior with show_right_answer: false (1 test)
  - Manual continue with show_right_answer: true (1 test)
  - Multi-question auto-advance flow (1 test)
  - Auto-advance without visual feedback (1 test)
  - Last question auto-advance to results (1 test)
  - Button state management during auto-advance (1 test)
- **Username Label Tests (10)**: Test customizable username field label functionality
  - Default Ukrainian label (1 test)
  - Custom English label (1 test)
  - Custom Ukrainian label (1 test)
  - Label in waiting approval form (1 test)
  - Special characters (apostrophes) (1 test)
  - HTML escaping/XSS (1 test)
  - Emoji characters (1 test)
  - Config validation for non-string values (1 test)
  - Label appears in both forms (1 test)
  - Empty string handling (1 test)
- **Question Randomization Tests (13)**: Test question order randomization functionality
  - Randomization disabled by default (1 test)
  - Randomization enabled generates question_order (1 test)
  - Different users get different orders (1 test)
  - Question order persists across verifications (1 test)
  - Randomization with approval workflow (1 test)
  - YAML validation accepts randomize_questions boolean (1 test)
  - YAML validation rejects non-boolean randomize_questions (1 test)
  - randomize_questions: false behaves like disabled (1 test)
  - Question order contains all IDs exactly once (1 test)
  - Randomization with single question (1 test)
  - YAML validation accepts other top-level fields (1 test)
  - Edge cases and data integrity (2 tests)
- **Admin Quiz Editor Tests (5)**: Test admin panel quiz editor with randomize_questions
  - Create quiz with randomize_questions via wizard (1 test)
  - Default behavior when randomize_questions not specified (1 test)
  - Edit quiz to add randomize_questions (1 test)
  - Preserve randomize_questions setting after edit (1 test)
  - Disable randomize_questions via edit (1 test)
- **Live Stats WebSocket Tests (5)**: Test WebSocket live stats with question randomization
  - Correct first question in randomized order (1 test)
  - No duplicate question notifications (1 test)
  - Correct first question with approval workflow (1 test)
  - Question 1 shown without randomization (1 test)
  - Multiple users get different first questions (1 test)
- **Total: 100 tests** with GitHub Actions CI/CD pipeline
- **Parallel Testing**: Tests use predefined ports (8080-8087) with worker-based allocation to prevent conflicts
- **Fast Server Startup**: Port availability checking instead of HTTP requests for efficient fixture startup
- **Test Isolation**: `custom_webquiz_server` fixture automatically cleans up directories and config files after each test to prevent data contamination between sequential test runs
- **Testing Philosophy**: Create new automated tests for newly implemented functionality instead of manual testing
- **Test Organization**: Fixtures separated into `conftest.py` for reusability across test modules

## Notes
- Username must be unique across all users (per quiz session)
- Questions use 0-indexed correct_answer field
- Server validates all answers server-side with automatic timing
- **CSV files**: Two CSV files are generated per quiz session:
  - **User responses CSV** (`{quiz_name}_user_responses.csv`):
    - Headers: `user_id,question,selected_answer,correct_answer,is_correct,time_taken_seconds`
    - Contains individual answer submissions
  - **Users CSV** (`{quiz_name}_user_responses.users.csv`):
    - Headers: `user_id,username,[custom_fields...],registered_at,total_questions_asked,correct_answers`
    - Contains user registration data and statistics
    - `total_questions_asked`: Number of questions the user has answered
    - `correct_answers`: Number of correct answers by the user
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
- **Username label customization** (`registration.username_label`):
  - Customize the label for the username field in registration forms
  - Default: "Ім'я користувача" (Ukrainian for "Username")
  - Appears in both registration form and waiting approval form
  - Supports special characters, emojis, and multilingual text
  - Config validation ensures string type
- **Question randomization** (`randomize_questions: true`):
  - Each student receives unique randomized question order
  - Order generated server-side at registration/approval, persists across sessions
  - Client receives question_order array (e.g., [3, 1, 4, 2, 5]) and reorders questions
  - Default: `false` (questions appear in YAML order)
  - Must be boolean value, validated during quiz validation
  - **Admin panel support**: Wizard mode includes checkbox for enabling/disabling randomization
  - Checkbox state properly loaded when editing existing quizzes
  - Setting persists when saving/editing quizzes through admin interface
- **Mobile responsiveness**:
  - All forms and inputs are mobile-responsive (tested at ≤768px viewport)
  - Registration form fields use `width: 100%; max-width: 250px` pattern
  - Waiting approval form dynamically generated with same responsive styles
  - Tables stack vertically on mobile using `display: block` for cells
  - All new UI features MUST include mobile support from the start
- **Quiz isolation**: Switching quizzes resets all server state for complete isolation
- **File safety**: Unique suffixes prevent overwriting existing log/CSV files
- Middleware handles JSON parsing errors and validation
- HTTP exceptions used for proper status codes (404, 400, 500)
- Generated files (logs, CSV, client JSON, YAML) are git-ignored
- Server automatically creates missing quiz files with sample questions

## Release Process

The release workflow (`.github/workflows/release.yml`) is triggered manually via workflow_dispatch and performs the following:

1. **Multi-Platform Binary Build** (`build-binaries` job):
   - Runs in parallel on Linux, macOS (Intel + Apple Silicon), and Windows runners
   - Each platform builds a standalone binary using PyInstaller
   - macOS builds on two separate runners for architecture support:
     - `macos-13` for Intel (x86_64)
     - `macos-14` for Apple Silicon (ARM64)
   - Binaries are renamed with platform suffix (webquiz-linux, webquiz-macos-intel, webquiz-macos-apple-silicon, webquiz-windows.exe)
   - Each binary is also zipped for easier distribution
   - Uploaded as artifacts for the release job

2. **Release Job** (runs after binaries are built):
   - Validates version format (X, X.Y, or X.Y.Z)
   - Updates version in `pyproject.toml` and `webquiz/__init__.py`
   - Installs dependencies and builds Python packages (wheel + tar.gz)
   - Generates PDF documentation in Ukrainian and English using Pandoc (with version on title page)
   - Publishes to PyPI
   - Downloads all binary artifacts from build job
   - Creates GitHub release with all assets:
     - Python wheel and source distribution
     - Linux, macOS (Intel + Apple Silicon), and Windows binaries (zipped only)
     - Ukrainian and English PDF documentation (with version on title page)
   - Updates webquiz-ansible repository with new version
