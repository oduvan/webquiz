# CLAUDE.md

This file contains project context and memory for Claude Code sessions.

## Project Overview
Testing system built with Python and aiohttp that allows users to take multiple-choice tests with real-time answer submission and statistics tracking.

**Key Features:**
- User registration with unique usernames (no IDs)
- Multiple-choice questions loaded from YAML
- Real-time answer validation via REST API
- In-memory storage with periodic CSV backup (30s intervals)
- User statistics and performance tracking
- Responsive web interface

## Architecture
- **Backend**: Python aiohttp server with middleware-based error handling
- **Frontend**: Vanilla HTML/JS single-page application
- **Data Storage**: 
  - Questions: YAML file with correct answers
  - User responses: In-memory � CSV file
  - Users: In-memory dictionary (username as key)
- **API Design**: RESTful endpoints with JSON responses

## Key Files
- `server.py` - Main aiohttp server with middleware and API endpoints
- `questions.yaml` - Questions database with correct answers (no IDs needed)
- `user_responses.csv` - User response storage (username,question_text,selected_answer_text,correct_answer_text,is_correct,time_taken_seconds)
- `server.log` - Server activity log (resets on startup)
- `static/` - Static files folder
  - `index.html` - Single-page web client with dark/light theme
  - `questions_for_client.json` - Auto-generated questions without correct answers
- `requirements.txt` - Python dependencies (aiohttp, PyYAML, aiofiles)
- `venv/` - Python virtual environment

## API Endpoints
- `POST /api/register` - Register unique username
- `POST /api/submit-answer` - Submit answer (username, question_id, selected_answer)
- `GET /api/questions` - Get questions without correct answers
- `GET /api/user/{username}/stats` - Get user statistics

## Commands
```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run server
python server.py
# Server runs on http://localhost:8080

# Add questions
# Edit questions.yaml, restart server to load changes
```

## Technical Decisions
- **Middleware over try-catch**: Used aiohttp middleware for cleaner error handling
- **Username-based auth**: Users identified by unique usernames, not generated IDs
- **Periodic CSV flush**: Every 30 seconds to prevent data loss
- **Client-side question filtering**: Server generates separate JSON without correct answers
- **In-memory storage**: Fast responses, CSV backup for persistence

## Data Flow
1. Server loads questions.yaml � generates questions_for_client.json
2. User registers � username stored in memory
3. Client fetches questions � displays test interface
4. User submits answers � validated against correct answers � stored in memory
5. Periodic flush � responses written to CSV
6. Stats calculated from in-memory responses

## Notes
- Username must be unique across all users
- Questions use 0-indexed correct_answer field
- Server validates all answers server-side
- CSV headers: username,question_id,selected_answer,is_correct,timestamp
- Middleware handles JSON parsing errors and validation
- HTTP exceptions used for proper status codes (404, 400, 500)