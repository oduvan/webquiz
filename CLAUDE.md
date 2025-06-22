# CLAUDE.md

This file contains project context and memory for Claude Code sessions.

## Project Overview
WebQuiz - A modern web-based quiz and testing system built with Python and aiohttp that allows users to take multiple-choice tests with real-time answer submission and statistics tracking.

**Key Features:**
- User registration with unique usernames and UUID-based user IDs
- Multiple-choice questions loaded from config YAML (auto-generated if missing)
- Web interface with auto-generated index.html if not present
- Real-time answer validation via REST API
- Server-side timing for accurate response measurement
- In-memory storage with periodic CSV backup (30s intervals) to configurable file path
- User session persistence with cookie-based user ID storage
- Responsive web interface with dark/light theme
- Configurable file paths for config, logs, CSV output, and static files
- Comprehensive test suite (integration + unit tests)

## Architecture
- **Backend**: Python aiohttp server with middleware-based error handling
- **Frontend**: Vanilla HTML/JS single-page application
- **Data Storage**: 
  - Questions: config.yaml file with correct answers (auto-created with defaults)
  - User responses: In-memory → CSV file (proper CSV module usage)
  - Users: In-memory dictionary (user_id as key, contains username)
  - Session timing: Server-side tracking for accurate measurements
- **API Design**: RESTful endpoints with JSON responses
- **Testing**: Integration tests with real HTTP requests + unit tests for internal logic

## Key Files
- `webquiz/server.py` - Main aiohttp server with middleware and API endpoints
- `webquiz/cli.py` - CLI interface with daemon support
- `webquiz/__init__.py` - Package initialization
- `config.yaml` - Configuration and questions database with correct answers (auto-created with sample questions)
- `static/index.html` - Web interface (auto-generated if missing, never overwrites existing)
- `user_responses.csv` - User response storage (user_id,username,question_text,selected_answer_text,correct_answer_text,is_correct,time_taken_seconds)
- `server.log` - Server activity log (resets on startup)
- `static/` - Static files folder
  - `index.html` - Single-page web client with dark/light theme
  - `index.html` - Web interface (auto-created if missing)
  - `questions_for_client.json` - Auto-generated questions without correct answers
- `tests/` - Test suite
  - `test_integration.py` - Integration tests with real HTTP requests (11 tests)
  - `test_server.py` - Unit tests for internal functionality (3 tests)
  - `conftest.py` - Test fixtures and configuration
- `pyproject.toml` - Poetry configuration and dependencies
- `requirements.txt` - Legacy pip dependencies
- `venv/` - Python virtual environment
- `.gitignore` - Git ignore file (excludes generated files, logs, virtual env)

## API Endpoints
- `POST /api/register` - Register unique username (returns user_id)
- `POST /api/submit-answer` - Submit answer (user_id, question_id, selected_answer)
- `GET /api/verify-user/{user_id}` - Verify user session and get progress

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
webquiz --config custom.yaml         # Use custom config file
webquiz --log-file /var/log/quiz.log # Use custom log file
webquiz --csv-file /data/responses.csv # Use custom CSV file
webquiz --static /var/www/quiz       # Use custom static directory
webquiz --config quiz.yaml --log-file quiz.log --csv-file quiz.csv --static web/
webquiz -d                           # Daemon mode
webquiz --stop                       # Stop daemon
webquiz --status                     # Check status

# Alternative (without Poetry installation)
python -m webquiz.cli

# Add questions
# Edit config.yaml, restart server to load changes

# Run tests
poetry run pytest   # With Poetry
pytest tests/       # Direct
pytest tests/ -v    # Verbose
```

## Technical Decisions
- **Middleware over try-catch**: Used aiohttp middleware for cleaner error handling
- **UUID-based user IDs**: Users identified by UUID with username storage, stored by user_id as key
- **Server-side timing**: Question timing tracked server-side for accuracy and security
- **Auto-YAML creation**: Server creates default questions.yaml if missing
- **Periodic CSV flush**: Every 30 seconds using proper CSV module for escaping
- **Client-side question filtering**: Server generates separate JSON without correct answers
- **In-memory storage**: Fast responses, CSV backup for persistence
- **Session persistence**: Cookie-based user_id storage for seamless user experience
- **Comprehensive testing**: Integration tests for API + unit tests for internal logic

## Data Flow
1. Server loads questions.yaml (or creates default) → generates questions_for_client.json
2. User registers → user_id generated, stored by user_id key, timing starts
3. Client stores user_id in cookies for session persistence
4. User submits answers → server calculates time taken → validated against correct answers → stored in memory
5. Periodic flush → responses written to CSV using proper CSV module
6. Server automatically tracks timing for each question transition

## Test Strategy
- **Integration Tests (11)**: Real HTTP requests testing full API functionality
- **Unit Tests (3)**: Internal functionality not exposed via HTTP
  - CSV writing with proper escaping
  - Default YAML file creation
  - User data structure validation
- **No duplicate tests**: Removed 9 redundant unit tests covered by integration tests

## Notes
- Username must be unique across all users
- Questions use 0-indexed correct_answer field
- Server validates all answers server-side with automatic timing
- CSV headers: user_id,username,question_text,selected_answer_text,correct_answer_text,is_correct,time_taken_seconds
- Middleware handles JSON parsing errors and validation
- HTTP exceptions used for proper status codes (404, 400, 500)
- Generated files (logs, CSV, client JSON, YAML) are git-ignored
- Server automatically creates missing questions.yaml with 3 sample questions