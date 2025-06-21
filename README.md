# Testing System

A web-based testing system built with Python and aiohttp that allows users to take multiple-choice tests with real-time answer submission and statistics tracking.

## Features

- User registration on first page visit
- Multiple-choice questions loaded from YAML file
- Real-time answer submission via REST API
- In-memory storage with periodic CSV file backup
- User statistics and scoring
- Responsive web interface

## Setup

1. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Server

```bash
python server.py
```

The server will start on `http://localhost:8080`

## API Endpoints

- `POST /api/register` - Register a new user
- `POST /api/submit-answer` - Submit an answer to a question
- `GET /api/questions` - Get all questions (without correct answers)
- `GET /api/user/{user_id}/stats` - Get user statistics

## Files

- `server.py` - Main server application
- `questions.yaml` - Questions and answers database
- `user_responses.csv` - User response storage
- `questions_for_client.json` - Auto-generated client questions (created on startup)
- `index.html` - Web client interface

## How It Works

1. Questions are stored in `questions.yaml` with correct answers
2. On startup, server generates `questions_for_client.json` without correct answers
3. Users register and receive a unique ID
4. Answers are stored in memory and periodically flushed to CSV
5. Server validates answers and provides immediate feedback
6. User statistics are calculated in real-time

## Adding Questions

Edit `questions.yaml` to add new questions:

```yaml
questions:
  - id: 6
    question: "Your question here?"
    options:
      - "Option 1"
      - "Option 2" 
      - "Option 3"
      - "Option 4"
    correct_answer: 1  # 0-indexed
```

Restart the server to load new questions.