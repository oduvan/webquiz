# AI Testing System

A modern web-based testing system built with Python and aiohttp that allows users to take multiple-choice tests with real-time answer validation and performance tracking.

## ✨ Features

- **User Management**: Unique username registration with UUID-based session tracking
- **Question System**: YAML-based questions with automatic file generation
- **Real-time Validation**: Server-side answer checking and timing
- **Session Persistence**: Cookie-based user sessions for seamless experience
- **Performance Tracking**: Server-side timing for accurate response measurement
- **Data Export**: Automatic CSV export of user responses with proper escaping
- **Responsive UI**: Clean web interface with dark/light theme support
- **Comprehensive Testing**: Full test suite with integration and unit tests

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd aiotests
   ```

2. **Set up virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the server**
   ```bash
   python server.py
   ```

5. **Open your browser**
   ```
   http://localhost:8080
   ```

That's it! The server will automatically create sample questions if none exist.

## 📁 Project Structure

```
aiotests/
├── server.py                 # Main application server
├── requirements.txt          # Python dependencies
├── .gitignore               # Git ignore rules
├── CLAUDE.md                # Project documentation
├── README.md                # This file
├── static/                  # Frontend files
│   └── index.html          # Single-page web application
├── tests/                   # Test suite
│   ├── conftest.py         # Test configuration
│   ├── test_integration.py # Integration tests (11 tests)
│   └── test_server.py      # Unit tests (3 tests)
└── venv/                   # Virtual environment (excluded from git)

# Generated at runtime (excluded from git):
├── questions.yaml          # Question database
├── user_responses.csv      # User response data
├── server.log             # Server logs
└── static/questions_for_client.json  # Client-safe questions
```

## 🔧 API Reference

### Authentication
- User sessions managed via UUID stored in browser cookies
- No passwords required - username-based registration

### Endpoints

#### `POST /api/register`
Register a new user with unique username.

**Request:**
```json
{
  "username": "john_doe"
}
```

**Response:**
```json
{
  "username": "john_doe",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "User registered successfully"
}
```

#### `POST /api/submit-answer`
Submit an answer for a question.

**Request:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "question_id": 1,
  "selected_answer": 2
}
```

**Response:**
```json
{
  "is_correct": true,
  "time_taken": 5.23,
  "message": "Answer submitted successfully"
}
```

#### `GET /api/verify-user/{user_id}`
Verify user session and get progress information.

**Response:**
```json
{
  "valid": true,
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "john_doe",
  "next_question_index": 2,
  "total_questions": 5,
  "last_answered_question_id": 1
}
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run only integration tests
pytest tests/test_integration.py

# Run only unit tests  
pytest tests/test_server.py
```

### Test Coverage
- **11 Integration Tests**: End-to-end API testing with real HTTP requests
- **3 Unit Tests**: Internal functionality testing (CSV, YAML, data structures)
- **Total**: 14 tests covering all critical functionality

## 📋 Question Format

Questions are stored in `questions.yaml` (auto-generated if missing):

```yaml
questions:
  - id: 1
    question: "What is 2 + 2?"
    options:
      - "3"
      - "4"
      - "5"
      - "6"
    correct_answer: 1  # 0-indexed (option "4")
  
  - id: 2
    question: "What is the capital of France?"
    options:
      - "London"
      - "Berlin"
      - "Paris"
      - "Madrid"
    correct_answer: 2  # 0-indexed (option "Paris")
```

## 📊 Data Export

User responses are automatically exported to `user_responses.csv`:

```csv
user_id,username,question_text,selected_answer_text,correct_answer_text,is_correct,time_taken_seconds
550e8400-e29b-41d4-a716-446655440000,john_doe,"What is 2 + 2?","4","4",True,3.45
```

## 🎨 Customization

### Adding Your Own Questions

1. **Edit questions.yaml** (created automatically on first run)
2. **Restart the server** to load new questions
3. **Questions must have unique IDs** and 0-indexed correct answers

### Styling

- Modify `static/index.html` for UI changes
- Built-in dark/light theme toggle
- Responsive design works on mobile and desktop

## 🛠️ Development

### Key Technical Decisions

- **Server-side timing**: All timing calculated server-side for accuracy
- **UUID-based sessions**: Secure user identification without passwords  
- **Middleware error handling**: Clean error management with proper HTTP status codes
- **CSV module usage**: Proper escaping for data with commas/quotes
- **Auto-file generation**: Zero-configuration setup with sensible defaults

### Architecture

- **Backend**: Python 3.8+ with aiohttp async web framework
- **Frontend**: Vanilla HTML/CSS/JavaScript (no frameworks)
- **Storage**: In-memory with periodic CSV backups (30-second intervals)
- **Session Management**: Cookie-based with server-side validation

## 🐛 Troubleshooting

### Common Issues

**Port already in use:**
```bash
# Kill process using port 8080
lsof -ti:8080 | xargs kill -9
```

**Virtual environment issues:**
```bash
# Recreate virtual environment
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Questions not loading:**
- Check that `questions.yaml` has valid YAML syntax
- Restart server after editing questions
- Check server logs for errors

## 📝 License

This project is open source. Feel free to use and modify as needed.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📞 Support

For questions or issues:
- Check the server logs (`server.log`)
- Run the test suite to verify setup
- Review this README and `CLAUDE.md` for detailed documentation