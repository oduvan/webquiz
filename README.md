# WebQuiz

A modern web-based quiz and testing system built with Python and aiohttp that allows users to take multiple-choice tests with real-time answer validation and performance tracking.

## ✨ Features

- **User Management**: Unique username registration with UUID-based session tracking
- **Multi-Quiz System**: Questions loaded from `quizzes/` directory with multiple YAML files
- **Admin Interface**: Web-based admin panel with master key authentication for quiz management
- **Registration Approval**: Optional admin approval workflow for new registrations with real-time notifications
- **Dynamic Quiz Switching**: Real-time quiz switching with automatic server state reset
- **Config File Editor**: Web-based configuration editor with real-time validation
- **Live Statistics**: Real-time WebSocket-powered dashboard showing user progress
- **Real-time Validation**: Server-side answer checking with immediate feedback
- **Session Persistence**: Cookie-based user sessions for seamless experience
- **Performance Tracking**: Server-side timing for accurate response measurement
- **Data Export**: Automatic CSV export with quiz-prefixed filenames and unique suffixes
- **Responsive UI**: Clean web interface with dark/light theme support
- **Binary Distribution**: Standalone PyInstaller executable with auto-configuration
- **Comprehensive Testing**: 210+ tests covering all functionality with CI/CD pipeline
- **Flexible File Paths**: Configurable paths for quizzes, logs, CSV, and static files

## 🚀 Quick Start

### Prerequisites

- Python 3.9+ (required by aiohttp)
- Poetry (recommended) or pip
- Git

### Installation with Poetry (Recommended)

1. **Clone the repository**
   ```bash
   git clone git@github.com:oduvan/webquiz.git
   cd webquiz
   ```

2. **Install with Poetry**
   ```bash
   poetry install
   ```

3. **Run the server**
   ```bash
   webquiz           # Foreground mode
   webquiz -d        # Daemon mode
   ```

4. **Open your browser**
   ```
   http://localhost:8080
   ```

The server will automatically create necessary directories and files on first run.

### Alternative Installation with pip

1. **Clone and set up virtual environment**
   ```bash
   git clone git@github.com:oduvan/webquiz.git
   cd webquiz
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the server**
   ```bash
   python -m webquiz.cli
   ```

The server will automatically create necessary directories and files on first run.

## 📁 Project Structure

```
webquiz/
├── pyproject.toml           # Poetry configuration and dependencies
├── requirements.txt         # Legacy pip dependencies  
├── .gitignore              # Git ignore rules
├── CLAUDE.md               # Project documentation
├── README.md               # This file
├── webquiz/                # Main package
│   ├── __init__.py        # Package initialization
│   ├── cli.py             # CLI entry point (webquiz command)
│   ├── server.py          # Main application server
│   ├── build.py           # PyInstaller binary build script
│   ├── binary_entry.py    # Binary executable entry point
│   ├── version_check.py   # Version update checking
│   ├── server_config.yaml.example  # Configuration example
│   └── templates/         # HTML templates
│       ├── index.html                     # Main quiz interface
│       ├── admin.html                     # Admin management panel
│       ├── files.html                     # File manager interface
│       ├── live_stats.html                # Live statistics dashboard
│       ├── quiz_selection_required.html   # Quiz selection prompt
│       └── template_error.html            # Error page template
├── tests/                  # Test suite (14 test files)
│   ├── conftest.py                      # Test fixtures and configuration
│   ├── test_cli_directory_creation.py   # CLI and directory tests
│   ├── test_admin_api.py                # Admin API tests
│   ├── test_admin_quiz_management.py    # Quiz management tests
│   ├── test_config_management.py        # Config editor tests
│   ├── test_registration_approval.py    # Registration approval tests
│   ├── test_registration_fields.py      # Registration fields tests
│   ├── test_index_generation.py         # Template generation tests
│   ├── test_files_management.py         # File manager tests
│   ├── test_integration_multiple_choice.py  # Multiple choice integration tests
│   ├── test_multiple_answers.py         # Multiple answer tests
│   ├── test_show_right_answer.py        # Show answer tests
│   ├── test_selenium_multiple_choice.py # Selenium multiple choice tests
│   ├── test_selenium_registration_fields.py # Selenium registration tests
│   └── test_user_journey_selenium.py    # Selenium user journey tests
└── .github/
    └── workflows/
        └── test.yml       # CI/CD pipeline

# Generated at runtime (excluded from git):
└── quizzes/               # Quiz files directory
    ├── default.yaml      # Default quiz (auto-created)
    └── *.yaml            # Additional quiz files
```

## 🖥️ CLI Commands

The `webquiz` command provides several options:

```bash
# Start server in foreground (default)
webquiz

# Start server with admin interface (requires master key)
webquiz --master-key secret123

# Start server with custom directories
webquiz --quizzes-dir my_quizzes
webquiz --logs-dir /var/log
webquiz --csv-dir /data
webquiz --static /var/www/quiz

# Combine multiple options
webquiz --master-key secret123 --quizzes-dir quizzes --logs-dir logs

# Set master key via environment variable
export WEBQUIZ_MASTER_KEY=secret123
webquiz

# Start server as daemon (background)
webquiz -d
webquiz --daemon

# Stop daemon server
webquiz --stop

# Check daemon status
webquiz --status

# Show help
webquiz --help

# Show version
webquiz --version
```

### Key Options

- `--master-key`: Enable admin interface with authentication
- `--quizzes-dir`: Directory containing quiz YAML files (default: `./quizzes`)
- `--logs-dir`: Directory for server logs (default: current directory)
- `--csv-dir`: Directory for CSV exports (default: current directory)
- `--static`: Directory for static files (default: `./static`)
- `-d, --daemon`: Run server in background
- `--stop`: Stop daemon server
- `--status`: Check daemon status

### Daemon Mode Features

- **Background execution**: Server runs independently in background
- **PID file management**: Automatic process tracking via `webquiz.pid`
- **Graceful shutdown**: Proper cleanup on stop
- **Status monitoring**: Check if daemon is running
- **Log preservation**: All output still goes to `server.log`

## 🚀 Release Management

This project uses GitHub Actions for automated versioning, PyPI deployment, and GitHub Release creation.

### Creating a New Release

1. **Go to GitHub Actions** in the repository
2. **Select "Release and Deploy to PyPI" workflow**
3. **Click "Run workflow"**
4. **Enter the new version** (e.g., `1.0.6`, `2.0.0`)
5. **Click "Run workflow"**

The action will automatically:
- ✅ Update version in `pyproject.toml` and `webquiz/__init__.py`
- ✅ Run tests to ensure everything works
- ✅ Commit the version changes
- ✅ Create a git tag with the version
- ✅ Build the package using Poetry
- ✅ Publish to PyPI
- 🆕 **Create a GitHub Release** with built artifacts

### What's included in GitHub Releases

Each release automatically includes:
- 📦 **Python wheel package** (`.whl` file)
- 📋 **Source distribution** (`.tar.gz` file)  
- 📝 **Formatted release notes** with installation instructions
- 🔗 **Links to commit history** for detailed changelog
- 📋 **Installation commands** for the specific version

### Prerequisites for Release Deployment

Repository maintainers need to set up:
- `PYPI_API_TOKEN` secret in GitHub repository settings
- PyPI account with publish permissions for the `webquiz` package
- `GITHUB_TOKEN` is automatically provided by GitHub Actions

## 🧪 Testing

Run the comprehensive test suite:

```bash
# With Poetry
poetry run pytest

# Or directly
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run in parallel with 4 workers
pytest tests/ -v -n 4

# Run specific test file
pytest tests/test_admin_api.py
pytest tests/test_registration_approval.py
```

### Test Coverage

The project has **210+ tests** across **14 test files** covering:

- **CLI and Directory Creation** (7 tests): Directory and file creation
- **Admin API** (14 tests): Admin interface and authentication
- **Admin Quiz Management** (18 tests): Quiz switching and management
- **Config Management** (16 tests): Config editor and validation
- **Registration Approval** (20 tests): Approval workflow and timing
- **Files Management** (32 tests): File manager interface
- **Index Generation** (13 tests): Template generation tests
- **Registration Fields** (12 tests): Custom registration fields
- **Show Right Answer** (5 tests): Answer display functionality
- **Integration Tests** (6 tests): Multiple choice, multiple answers
- **Selenium Tests** (56 tests): End-to-end browser testing

The test suite uses GitHub Actions CI/CD for automated testing on every commit.

## 📋 Configuration Format

### Quiz Files

Questions are stored in YAML files in the `quizzes/` directory. The server automatically creates a `default.yaml` file if the directory is empty.

**Example quiz file** (`quizzes/math_quiz.yaml`):

```yaml
title: "Mathematics Quiz"
questions:
  - question: "What is 2 + 2?"
    options:
      - "3"
      - "4"
      - "5"
      - "6"
    correct_answer: 1  # 0-indexed (option "4")
  
  - question: "What is 5 × 3?"
    options:
      - "10"
      - "15"
      - "20"
      - "25"
    correct_answer: 1  # 0-indexed (option "15")
```

### Server Configuration

Optional server configuration file (`webquiz.yaml`):

```yaml
server:
  host: "0.0.0.0"
  port: 8080

registration:
  approve: false  # Set to true to require admin approval
  fields:
    - name: "full_name"
      label: "Full Name"
      required: true

quiz:
  show_right_answer: false  # Show correct answer after submission
```

All configuration sections are optional and have sensible defaults.

## 📊 Data Export

User responses are automatically exported to CSV files with quiz-prefixed filenames and unique suffixes to prevent overwrites:

**Example:** `math_quiz_user_responses_0001.csv`

```csv
user_id,question,selected_answer,correct_answer,is_correct,time_taken_seconds
123456,"What is 2 + 2?","4","4",True,3.45
123456,"What is 5 × 3?","15","15",True,2.87
```

CSV files are created with proper escaping and include all user response data. Files are flushed periodically (every 30 seconds) to ensure data persistence.

## 🎨 Customization

### Adding Your Own Quizzes

1. **Create a YAML file** in the `quizzes/` directory
   ```bash
   # Example: quizzes/science_quiz.yaml
   ```

2. **Add your questions** following the format:
   ```yaml
   title: "Science Quiz"
   questions:
     - question: "What is H2O?"
       options: ["Water", "Hydrogen", "Oxygen", "Salt"]
       correct_answer: 0
   ```

3. **Switch to your quiz** via the admin interface
   - Access `/admin` with your master key
   - Select your quiz from the dropdown
   - Click "Switch Quiz"

### Admin Interface

Enable admin features with a master key:

```bash
webquiz --master-key secret123
```

Access admin panels:
- `/admin` - Quiz management and user approval
- `/files` - View logs, CSV files, and edit configuration
- `/live-stats` - Real-time user progress dashboard

### Styling

- Templates are located in `webquiz/templates/`
- Built-in dark/light theme toggle
- Responsive design works on mobile and desktop
- Generated `static/index.html` can be customized (regenerates on quiz switch)

## 🛠️ Development

### Building Binary Executable

Create a standalone executable with PyInstaller:

```bash
# Build binary
poetry run build_binary

# Or directly
python -m webquiz.build

# The binary will be created at:
./dist/webquiz

# Run the binary
./dist/webquiz
./dist/webquiz --master-key secret123
```

The binary includes all templates and configuration examples, with automatic directory creation on first run.

### Key Technical Decisions

- **Multi-quiz system**: Questions loaded from `quizzes/` directory with YAML files
- **Master key authentication**: Admin endpoints protected with decorator-based authentication
- **Server-side timing**: All timing calculated server-side for accuracy
- **UUID-based sessions**: Secure user identification without passwords  
- **Middleware error handling**: Clean error management with proper HTTP status codes
- **CSV module usage**: Proper escaping for data with commas/quotes
- **Smart file naming**: CSV files prefixed with quiz names, unique suffixes prevent overwrites
- **Dynamic quiz switching**: Complete server state reset when switching quizzes
- **WebSocket support**: Real-time updates for admin and live statistics
- **Binary distribution**: PyInstaller for standalone executable with auto-configuration

### Architecture

- **Backend**: Python 3.9+ with aiohttp async web framework
- **Frontend**: Vanilla HTML/CSS/JavaScript (no frameworks)
- **Storage**: In-memory with periodic CSV backups (30-second intervals)
- **Session Management**: Cookie-based with server-side validation
- **Real-time Features**: WebSocket for live stats and admin notifications

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

**Quiz not loading:**
- Check that quiz YAML files have valid syntax
- Verify `quizzes/` directory exists and contains `.yaml` files
- Check server logs for errors
- Restart server after adding new quiz files

**Admin interface not accessible:**
- Ensure you started server with `--master-key` option
- Or set `WEBQUIZ_MASTER_KEY` environment variable
- Check that you're using the correct master key

**Tests failing:**
- Always run tests in virtual environment: `source venv/bin/activate`
- Install test dependencies: `poetry install` or `pip install -r requirements.txt`
- Use parallel testing: `pytest tests/ -v -n 4`

**Daemon not stopping:**
```bash
# Check status
webquiz --status

# Force kill if needed
cat webquiz.pid | xargs kill -9
rm webquiz.pid
```

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