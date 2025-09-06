import asyncio
import json
import csv
import uuid
import yaml
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from aiohttp import web, WSMsgType
import aiofiles
import logging
from io import StringIO
from dataclasses import dataclass, asdict

# Logger will be configured in create_app() with custom log file
logger = logging.getLogger(__name__)

def resolve_path_relative_to_binary(path_str: str) -> str:
    """Resolve relative paths relative to binary directory when running as binary."""
    if not path_str or os.path.isabs(path_str):
        return path_str
    
    binary_dir = os.environ.get('WEBQUIZ_BINARY_DIR')
    if binary_dir:
        # Running as binary - resolve relative to binary directory
        resolved = Path(binary_dir) / path_str
        return str(resolved)
    else:
        # Running normally - return as-is (relative to cwd)
        return path_str

@dataclass
class ServerConfig:
    """Server configuration data class"""
    host: str = "0.0.0.0"
    port: int = 8080

@dataclass  
class PathsConfig:
    """Paths configuration data class"""
    quizzes_dir: str = None
    logs_dir: str = None
    csv_dir: str = None
    static_dir: str = None
    
    def __post_init__(self):
        if self.quizzes_dir is None:
            self.quizzes_dir = resolve_path_relative_to_binary("quizzes")
        if self.logs_dir is None:
            self.logs_dir = resolve_path_relative_to_binary("logs")
        if self.csv_dir is None:
            self.csv_dir = resolve_path_relative_to_binary("data")
        if self.static_dir is None:
            self.static_dir = resolve_path_relative_to_binary("static")

@dataclass
class AdminConfig:
    """Admin configuration data class"""
    master_key: Optional[str] = None

@dataclass
class OptionsConfig:
    """Options configuration data class"""
    flush_interval: int = 30

@dataclass
class WebQuizConfig:
    """Main configuration data class"""
    server: ServerConfig = None
    paths: PathsConfig = None
    admin: AdminConfig = None
    options: OptionsConfig = None
    
    def __post_init__(self):
        if self.server is None:
            self.server = ServerConfig()
        if self.paths is None:
            self.paths = PathsConfig()
        if self.admin is None:
            self.admin = AdminConfig()
        if self.options is None:
            self.options = OptionsConfig()

def ensure_directory_exists(path: str) -> str:
    """Create directory if it doesn't exist and return the path"""
    os.makedirs(path, exist_ok=True)
    return path

def load_config_from_yaml(config_path: str) -> WebQuizConfig:
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        if not config_data:
            return WebQuizConfig()
            
        # Create config objects from YAML data
        server_config = ServerConfig(**(config_data.get('server', {})))
        paths_config = PathsConfig(**(config_data.get('paths', {})))
        admin_config = AdminConfig(**(config_data.get('admin', {})))
        options_config = OptionsConfig(**(config_data.get('options', {})))
        
        return WebQuizConfig(
            server=server_config,
            paths=paths_config,
            admin=admin_config,
            options=options_config
        )
    except FileNotFoundError:
        logger.warning(f"Config file not found: {config_path}, using defaults")
        return WebQuizConfig()
    except Exception as e:
        logger.error(f"Error loading config from {config_path}: {e}")
        return WebQuizConfig()

def get_default_config_path() -> Optional[str]:
    """Get default config file path, creating one if it doesn't exist."""
    # Determine where to look for/create config file
    binary_dir = os.environ.get('WEBQUIZ_BINARY_DIR')
    if binary_dir:
        config_path = Path(binary_dir) / "webquiz.yaml"
    else:
        config_path = Path.cwd() / "webquiz.yaml"
    
    # If config file exists, return it
    if config_path.exists():
        return str(config_path)
    
    # Create default config file
    try:
        create_default_config_file(config_path)
        return str(config_path)
    except Exception as e:
        logger.warning(f"Could not create default config file at {config_path}: {e}")
        return None

def create_default_config_file(config_path: Path):
    """Create a default config file with example content."""
    try:
        # Try modern importlib.resources first (Python 3.9+)
        import importlib.resources as pkg_resources
        example_content = (pkg_resources.files('webquiz') / 'server_config.yaml.example').read_text()
    except (ImportError, AttributeError):
        # Fallback to pkg_resources for older Python versions
        import pkg_resources
        example_content = pkg_resources.resource_string('webquiz', 'server_config.yaml.example').decode('utf-8')
    
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(example_content)
    logger.info(f"Created default config file: {config_path}")

def load_config_with_overrides(config_path: Optional[str] = None, **cli_overrides) -> WebQuizConfig:
    """Load configuration with CLI parameter overrides
    
    Priority: CLI parameters > config file > defaults
    """
    # Use default config file if none provided
    if not config_path:
        config_path = get_default_config_path()
    
    # Start with config file or defaults
    if config_path:
        if os.path.exists(config_path):
            config = load_config_from_yaml(config_path)
            logger.info(f"Loaded configuration from: {config_path}")
        else:
            # Config file specified but doesn't exist - create from example
            create_default_config_file(Path(config_path))
            config = load_config_from_yaml(config_path)
            logger.info(f"Loaded configuration from newly created: {config_path}")
    else:
        config = WebQuizConfig()
        logger.info("Using default configuration")
    
    # Apply CLI overrides
    for key, value in cli_overrides.items():
        if value is not None:  # Only override if CLI parameter was provided
            if key in ['host', 'port']:
                setattr(config.server, key, value)
            elif key in ['quizzes_dir', 'logs_dir', 'csv_dir', 'static_dir']:
                setattr(config.paths, key, value)
            elif key in ['master_key']:
                setattr(config.admin, key, value)
            elif key in ['flush_interval']:
                setattr(config.options, key, value)
    
    # Environment variable override for master key
    env_master_key = os.environ.get('WEBQUIZ_MASTER_KEY')
    if env_master_key and not cli_overrides.get('master_key'):
        config.admin.master_key = env_master_key
        logger.info("Master key loaded from environment variable")
    
    return config

def generate_unique_filename(base_path: str) -> str:
    """Generate a unique filename with suffix (0001, 0002, etc.) if file exists"""
    if not os.path.exists(base_path):
        return base_path
    
    # Split the path into name and extension
    name, ext = os.path.splitext(base_path)
    
    # Find the next available suffix
    suffix = 1
    while True:
        new_path = f"{name}_{suffix:04d}{ext}"
        if not os.path.exists(new_path):
            return new_path
        suffix += 1

def admin_auth_required(func):
    """Decorator to require master key authentication for admin endpoints"""
    async def wrapper(self, request):
        # Check if master key is provided
        if not self.master_key:
            return web.json_response({'error': 'Admin functionality disabled - no master key set'}, status=403)
        
        # Get master key from request (header or body)
        provided_key = request.headers.get('X-Master-Key')
        if not provided_key:
            try:
                data = await request.json()
                provided_key = data.get('master_key')
            except:
                pass
        
        if not provided_key or provided_key != self.master_key:
            return web.json_response({'error': 'Invalid or missing master key'}, status=401)
        
        return await func(self, request)
    return wrapper

@web.middleware
async def error_middleware(request, handler):
    """Global error handling middleware"""
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return web.json_response({'error': str(e)}, status=400)
    except KeyError as e:
        logger.error(f"Missing field: {e}")
        return web.json_response({'error': f'Missing required field: {e}'}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return web.json_response({'error': 'Internal server error'}, status=500)


class TestingServer:
    def __init__(self, config: WebQuizConfig):
        self.config = config
        self.quizzes_dir = config.paths.quizzes_dir
        self.master_key = config.admin.master_key
        self.current_quiz_file = None  # Will be set when quiz is selected
        self.logs_dir = config.paths.logs_dir
        self.csv_dir = config.paths.csv_dir
        self.static_dir = config.paths.static_dir
        self.log_file = None  # Will be set during initialization
        self.csv_file = None  # Will be set when quiz is selected
        self.quiz_title = 'Система Тестування'  # Default title, updated when quiz is loaded
        self.users: Dict[str, Dict[str, Any]] = {}  # user_id -> user data
        self.questions: List[Dict[str, Any]] = []
        self.user_responses: List[Dict[str, Any]] = []
        self.user_progress: Dict[str, int] = {}  # user_id -> last_answered_question_id
        self.question_start_times: Dict[str, datetime] = {}  # user_id -> question_start_time
        self.user_stats: Dict[str, Dict[str, Any]] = {}  # user_id -> final stats for completed users
        self.user_answers: Dict[str, List[Dict[str, Any]]] = {}  # user_id -> list of answers for stats calculation
        
        # Live stats WebSocket infrastructure
        self.websocket_clients: List[web.WebSocketResponse] = []  # Connected WebSocket clients
        self.live_stats: Dict[str, Dict[int, str]] = {}  # user_id -> {question_id: state}
        
    def generate_log_path(self) -> str:
        """Generate log file path in logs directory with simple numeric naming"""
        ensure_directory_exists(self.logs_dir)
        
        # Find the next available number
        suffix = 1
        while True:
            log_path = os.path.join(self.logs_dir, f"{suffix:04d}.log")
            if not os.path.exists(log_path):
                return log_path
            suffix += 1
        
    def generate_csv_path(self, quiz_name: str) -> str:
        """Generate CSV file path in CSV directory with quiz name and numeric naming"""
        ensure_directory_exists(self.csv_dir)
        
        # Clean quiz name (remove extension)
        quiz_prefix = quiz_name.replace('.yaml', '').replace('.yml', '')
        
        # Find the next available number for this quiz
        suffix = 1
        while True:
            csv_path = os.path.join(self.csv_dir, f"{quiz_prefix}_{suffix:04d}.csv")
            if not os.path.exists(csv_path):
                return csv_path
            suffix += 1
        
    def reset_server_state(self):
        """Reset all server state for new quiz"""
        self.users.clear()
        self.user_responses.clear()
        self.user_progress.clear()
        self.question_start_times.clear()
        self.user_stats.clear()
        self.user_answers.clear()
        self.live_stats.clear()
        logger.info("Server state reset for new quiz")
        
    async def list_available_quizzes(self):
        """List all available quiz files in quizzes directory"""
        try:
            quiz_files = []
            if os.path.exists(self.quizzes_dir):
                for filename in os.listdir(self.quizzes_dir):
                    if filename.endswith(('.yaml', '.yml')):
                        quiz_files.append(filename)
            return sorted(quiz_files)
        except Exception as e:
            logger.error(f"Error listing quiz files: {e}")
            return []
            
    async def switch_quiz(self, quiz_filename: str):
        """Switch to a different quiz file and reset server state"""
        quiz_path = os.path.join(self.quizzes_dir, quiz_filename)
        if not os.path.exists(quiz_path):
            raise ValueError(f"Quiz file not found: {quiz_filename}")
            
        # Reset server state
        self.reset_server_state()
        
        # Update current quiz and CSV filename
        self.current_quiz_file = quiz_path
        self.csv_file = self.generate_csv_path(quiz_filename)
        
        # Load new questions
        await self.load_questions_from_file(quiz_path)
        
        # Regenerate index.html with new questions
        await self.create_default_index_html()
        
        # Notify WebSocket clients about quiz switch
        await self.broadcast_to_websockets({
            'type': 'quiz_switched',
            'current_quiz': quiz_filename,
            'questions': self.questions,
            'total_questions': len(self.questions),
            'message': f'Quiz switched to: {quiz_filename}'
        })
        
        logger.info(f"Switched to quiz: {quiz_filename}, CSV: {self.csv_file}")
        
    async def create_admin_selection_page(self):
        """Create a page informing admin to select a quiz first"""
        ensure_directory_exists(self.static_dir)
        index_path = f"{self.static_dir}/index.html"
        
        # Get list of available quizzes for display
        available_quizzes = await self.list_available_quizzes()
        quiz_list_html = ""
        for quiz in available_quizzes:
            quiz_list_html += f"<li>{quiz}</li>"
        
        admin_url = f"/admin" if self.master_key else "#"
        admin_message = "Access admin panel" if self.master_key else "Admin panel disabled (no master key set)"
        
        selection_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WebQuiz - Admin Selection Required</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
            color: #333;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .quiz-list {{
            text-align: left;
            background: #f8f9fa;
            padding: 20px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .admin-button {{
            display: inline-block;
            background: #007bff;
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 5px;
            margin: 10px;
        }}
        .admin-button:hover {{
            background: #0056b3;
        }}
        .disabled {{
            background: #6c757d;
            cursor: not-allowed;
        }}
        .warning {{
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            color: #856404;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 WebQuiz System</h1>
        
        <div class="warning">
            <h3>⚠️ Quiz Selection Required</h3>
            <p>Multiple quiz files are available, but no default quiz is set. An administrator must select which quiz to use.</p>
        </div>
        
        <h3>📋 Available Quiz Files:</h3>
        <div class="quiz-list">
            <ul>
                {quiz_list_html}
            </ul>
        </div>
        
        <p>To set a default quiz, rename one of the files to <code>default.yaml</code> or use the admin panel to select a quiz.</p>
        
        <a href="{admin_url}" class="admin-button {'disabled' if not self.master_key else ''}">{admin_message}</a>
        
        <div style="margin-top: 30px; font-size: 0.9em; color: #666;">
            <p>💡 <strong>Tip:</strong> Rename your preferred quiz file to <code>default.yaml</code> to make it load automatically.</p>
        </div>
    </div>
</body>
</html>'''
        
        try:
            async with aiofiles.open(index_path, 'w', encoding='utf-8') as f:
                await f.write(selection_html)
            logger.info(f"Created admin selection page: {index_path}")
        except Exception as e:
            logger.error(f"Error creating admin selection page: {e}")
        
    
    async def initialize_log_file(self):
        """Initialize new log file with unique suffix in logs directory"""
        try:
            # Generate log file path
            self.log_file = self.generate_log_path()
            # Create the new log file
            with open(self.log_file, 'w') as f:
                f.write('')
            logger.info(f"=== Server Started - New Log File Created: {self.log_file} ===")
        except Exception as e:
            print(f"Error initializing log file {self.log_file}: {e}")

    async def create_default_config_yaml(self, file_path: str = None):
        """Create default config.yaml file"""
        if file_path is None:
            file_path = self.config_file if hasattr(self, 'config_file') else 'config.yaml'
        default_questions = {
            'questions': [
                {
                    'question': 'What is 2 + 2?',
                    'options': ['3', '4', '5', '6'],
                    'correct_answer': 1
                },
                {
                    'question': 'What is the capital of France?',
                    'options': ['London', 'Berlin', 'Paris', 'Madrid'],
                    'correct_answer': 2
                },
                {
                    'question': 'Which programming language is this server written in?',
                    'options': ['JavaScript', 'Python', 'Java', 'C++'],
                    'correct_answer': 1
                }
            ]
        }
        
        try:
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(yaml.dump(default_questions, default_flow_style=False, allow_unicode=True))
            logger.info(f"Created default config file: {file_path}")
        except Exception as e:
            logger.error(f"Error creating default config file {file_path}: {e}")

    async def load_questions_from_file(self, quiz_file_path: str):
        """Load questions from specific quiz file"""
        try:
            async with aiofiles.open(quiz_file_path, 'r') as f:
                content = await f.read()
                data = yaml.safe_load(content)
                self.questions = data['questions']
                
                # Store quiz title or use default
                self.quiz_title = data.get('title', 'Система Тестування')
                
                # Add automatic IDs based on array index
                for i, question in enumerate(self.questions):
                    question['id'] = i + 1
                        
                logger.info(f"Loaded {len(self.questions)} questions from {quiz_file_path}")
        except Exception as e:
            logger.error(f"Error loading questions from {quiz_file_path}: {e}")
            raise
            
    async def load_questions(self):
        """Load questions based on available quiz files"""
        try:
            # Check if quizzes directory exists
            if not os.path.exists(self.quizzes_dir):
                os.makedirs(self.quizzes_dir)
                logger.info(f"Created quizzes directory: {self.quizzes_dir}")
            
            # Get available quiz files
            available_quizzes = await self.list_available_quizzes()
            
            if not available_quizzes:
                # No quiz files found, create default
                default_path = os.path.join(self.quizzes_dir, 'default.yaml')
                await self.create_default_config_yaml(default_path)
                available_quizzes = ['default.yaml']
                await self.switch_quiz('default.yaml')
            elif len(available_quizzes) == 1:
                # Only one quiz file - use it as default
                await self.switch_quiz(available_quizzes[0])
                logger.info(f"Using single quiz file as default: {available_quizzes[0]}")
            elif 'default.yaml' in available_quizzes or 'default.yml' in available_quizzes:
                # Multiple files but default.yaml exists - use it
                default_file = 'default.yaml' if 'default.yaml' in available_quizzes else 'default.yml'
                await self.switch_quiz(default_file)
                logger.info(f"Using explicit default file: {default_file}")
            else:
                # Multiple files but no default.yaml - don't load any quiz
                logger.info(f"Multiple quiz files found but no default.yaml - admin must select quiz first")
                await self.create_admin_selection_page()
            
        except Exception as e:
            logger.error(f"Error in load_questions: {e}")
            raise
            
            
    async def create_default_index_html(self):
        """Create default index.html file with embedded questions data"""
        ensure_directory_exists(self.static_dir)
        index_path = f"{self.static_dir}/index.html"
        
        # Prepare questions data for client (without correct answers)
        questions_for_client = []
        for q in self.questions:
            client_question = {
                'id': q['id'],
                'options': q['options']
            }
            # Include question text if present
            if 'question' in q and q['question']:
                client_question['question'] = q['question']
            # Include optional image attribute if present
            if 'image' in q and q['image']:
                client_question['image'] = q['image']
            questions_for_client.append(client_question)
        
        # Convert questions to JSON string for embedding
        questions_json = json.dumps(questions_for_client, indent=2)
        
        # Copy template from package
        try:
            try:
                # Try modern importlib.resources first (Python 3.9+)
                import importlib.resources as pkg_resources
                template_content = (pkg_resources.files('webquiz') / 'templates' / 'index.html').read_text(encoding='utf-8')
            except (ImportError, AttributeError):
                # Fallback to pkg_resources for older Python versions
                import pkg_resources
                template_path = pkg_resources.resource_filename('webquiz', 'templates/index.html')
                async with aiofiles.open(template_path, 'r', encoding='utf-8') as template_file:
                    template_content = await template_file.read()
            
            # Inject questions data and title into template
            html_content = template_content.replace('{{QUESTIONS_DATA}}', questions_json)
            html_content = html_content.replace('{{QUIZ_TITLE}}', self.quiz_title)
            
            # Write to destination
            async with aiofiles.open(index_path, 'w', encoding='utf-8') as f:
                await f.write(html_content)
                
            logger.info(f"Created index.html file with embedded questions data: {index_path}")
            return
        except Exception as e:
            logger.error(f"Error copying template index.html: {e}")
            # Continue to fallback
            
        # Fallback: create minimal HTML if template is not available
        fallback_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WebQuiz Testing System</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
        input { padding: 10px; width: 300px; margin: 10px 0; border: 1px solid #ddd; border-radius: 3px; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>WebQuiz Testing System</h1>
        <div id="error">
            <h2>Template Error</h2>
            <p>Unable to load the full interface template. Please ensure the WebQuiz package is properly installed.</p>
            <p>You can manually create an index.html file in the static directory with your custom interface.</p>
        </div>
    </div>
</body>
</html>'''
        
        try:
            async with aiofiles.open(index_path, 'w', encoding='utf-8') as f:
                await f.write(fallback_html)
            logger.warning(f"Created fallback index.html file: {index_path}")
        except Exception as e:
            logger.error(f"Error creating fallback index.html: {e}")
            
    async def flush_responses_to_csv(self):
        """Flush in-memory responses to CSV file"""
        if not self.user_responses:
            return
            
        try:
            # Check if CSV file exists, if not create it with headers
            file_exists = os.path.exists(self.csv_file)
            
            # Use StringIO buffer to write CSV data
            csv_buffer = StringIO()
            csv_writer = csv.writer(csv_buffer)
            
            # Write headers if file doesn't exist
            if not file_exists:
                csv_writer.writerow(['username', 'question_text', 'selected_answer_text', 'correct_answer_text', 'is_correct', 'time_taken_seconds'])
            
            # Write all responses to buffer
            for response in self.user_responses:
                csv_writer.writerow([
                    response['username'],
                    response['question_text'],
                    response['selected_answer_text'],
                    response['correct_answer_text'],
                    response['is_correct'],
                    response['time_taken_seconds']
                ])
            
            # Write buffer content to file
            csv_content = csv_buffer.getvalue()
            csv_buffer.close()
            total_responses = len(self.user_responses)
            self.user_responses.clear()
            
            mode = 'w' if not file_exists else 'a'
            async with aiofiles.open(self.csv_file, mode) as f:
                await f.write(csv_content)
                    
            action = "Created" if not file_exists else "Updated"
            logger.info(f"{action} CSV file with {total_responses} responses: {self.csv_file}")
        except Exception as e:
            logger.error(f"Error flushing responses to CSV: {e}")
            
    async def periodic_flush(self):
        """Periodically flush responses to CSV"""
        while True:
            await asyncio.sleep(30)  # Flush every 30 seconds
            await self.flush_responses_to_csv()
    
    async def broadcast_to_websockets(self, message: dict):
        """Broadcast message to all connected WebSocket clients"""
        if not self.websocket_clients:
            return
            
        # Clean up closed connections
        active_clients = []
        for ws in self.websocket_clients:
            if not ws.closed:
                try:
                    await ws.send_str(json.dumps(message))
                    active_clients.append(ws)
                except Exception as e:
                    logger.warning(f"Failed to send message to WebSocket client: {e}")
        
        self.websocket_clients = active_clients
    
    def update_live_stats(self, user_id: str, question_id: int, state: str, time_taken: float = None):
        """Update live stats for a user and question"""
        if user_id not in self.live_stats:
            self.live_stats[user_id] = {}
        
        # Store both state and time_taken
        self.live_stats[user_id][question_id] = {
            'state': state,
            'time_taken': time_taken
        }
            
    async def register_user(self, request):
        """Register a new user"""
        data = await request.json()
        username = data['username'].strip()
        
        if not username:
            raise ValueError('Username cannot be empty')
            
        # Check if username already exists
        for existing_user in self.users.values():
            if existing_user['username'] == username:
                raise ValueError('Username already exists')
        
        # Generate unique user ID
        user_id = str(uuid.uuid4())
        
        self.users[user_id] = {
            'user_id': user_id,
            'username': username,
            'registered_at': datetime.now().isoformat()
        }
        
        # Start timing for first question
        self.question_start_times[user_id] = datetime.now()
        
        # Initialize live stats: set first question to "think"
        if len(self.questions) > 0:
            self.update_live_stats(user_id, 1, "think")
            
            # Broadcast new user registration
            await self.broadcast_to_websockets({
                'type': 'user_registered',
                'user_id': user_id,
                'username': username,
                'question_id': 1,
                'state': 'think',
                'time_taken': None,
                'total_questions': len(self.questions)
            })
        
        logger.info(f"Registered user: {username} with ID: {user_id}")
        return web.json_response({
            'username': username,
            'user_id': user_id,
            'message': 'User registered successfully'
        })
            
    async def submit_answer(self, request):
        """Submit test answer"""
        data = await request.json()
        user_id = data['user_id']
        question_id = data['question_id']
        selected_answer = data['selected_answer']
        
        # Find user by user_id
        if user_id not in self.users:
            return web.json_response({'error': 'User not found'}, status=404)
        
        username = self.users[user_id]['username']
            
        # Find the question
        question = next((q for q in self.questions if q['id'] == question_id), None)
        if not question:
            return web.json_response({'error': 'Question not found'}, status=404)
            
        # Calculate time taken server-side
        time_taken = 0
        if user_id in self.question_start_times:
            time_taken = (datetime.now() - self.question_start_times[user_id]).total_seconds()
            # Clean up the start time
            del self.question_start_times[user_id]
        
        # Check if answer is correct
        is_correct = selected_answer == question['correct_answer']
        
        # Store response in memory
        response_data = {
            'user_id': user_id,
            'username': username,
            'question_id': question_id,
            'question_text': question['question'],
            'selected_answer_text': question['options'][selected_answer],
            'correct_answer_text': question['options'][question['correct_answer']],
            'is_correct': is_correct,
            'time_taken_seconds': time_taken,
            'timestamp': datetime.now().isoformat()
        }
        
        self.user_responses.append(response_data)
        
        # Track answer separately for stats calculation (independent of CSV flushing)
        if user_id not in self.user_answers:
            self.user_answers[user_id] = []
        
        answer_data = {
            'question': question['question'],
            'selected_answer': question['options'][selected_answer],
            'correct_answer': question['options'][question['correct_answer']],
            'is_correct': is_correct,
            'time_taken': time_taken
        }
        self.user_answers[user_id].append(answer_data)
        
        # Update user progress
        self.user_progress[user_id] = question_id
        
        # Update live stats: set current question state based on correctness
        state = "ok" if is_correct else "fail"
        self.update_live_stats(user_id, question_id, state, time_taken)
        
        # Broadcast current question result
        await self.broadcast_to_websockets({
            'type': 'state_update',
            'user_id': user_id,
            'username': username,
            'question_id': question_id,
            'state': state,
            'time_taken': time_taken,
            'total_questions': len(self.questions)
        })
        
        # Check if this was the last question and calculate final stats
        if question_id == len(self.questions):
            # Test completed - calculate and store final stats
            self.calculate_and_store_user_stats(user_id)
            logger.info(f"Test completed for user {user_id} - final stats calculated")
        else:
            # Start timing for next question and update live stats
            next_question_id = question_id + 1
            self.question_start_times[user_id] = datetime.now()
            self.update_live_stats(user_id, next_question_id, "think")
            
            # Broadcast next question thinking state
            await self.broadcast_to_websockets({
                'type': 'state_update',
                'user_id': user_id,
                'username': username,
                'question_id': next_question_id,
                'state': 'think',
                'time_taken': None,
                'total_questions': len(self.questions)
            })
        
        logger.info(f"Answer submitted by {username} (ID: {user_id}) for question {question_id}: {'Correct' if is_correct else 'Incorrect'} (took {time_taken:.2f}s)")
        logger.info(f"Updated progress for user {user_id}: last answered question = {question_id}")
        
        return web.json_response({
            'is_correct': is_correct,
            'correct_answer': question['correct_answer'],
            'time_taken': time_taken,
            'message': 'Answer submitted successfully'
        })
            
        

    def calculate_and_store_user_stats(self, user_id):
        """Calculate and store final stats for a completed user using user_answers (not user_responses)"""
        # Get answers from dedicated user_answers tracking (independent of CSV flushing)
        if user_id not in self.user_answers or not self.user_answers[user_id]:
            logger.warning(f"No answers found for user {user_id} during stats calculation")
            return
        
        user_answer_list = self.user_answers[user_id]
        
        # Calculate stats from user_answers
        correct_count = 0
        total_time = 0
        
        for answer in user_answer_list:
            if answer['is_correct']:
                correct_count += 1
            total_time += answer['time_taken']
        
        total_count = len(user_answer_list)
        percentage = round((correct_count / total_count) * 100) if total_count > 0 else 0
        
        # Store final stats (copy the answer data to avoid reference issues)
        self.user_stats[user_id] = {
            'test_results': [answer.copy() for answer in user_answer_list],
            'correct_count': correct_count,
            'total_count': total_count,
            'percentage': percentage,
            'total_time': total_time,
            'completed_at': datetime.now().isoformat()
        }
        
        logger.info(f"Stored final stats for user {user_id}: {correct_count}/{total_count} ({percentage}%) using user_answers")
    
    def get_user_final_results(self, user_id):
        """Get final results for a completed user from persistent user_stats"""
        if user_id in self.user_stats:
            # Return stored stats (without the completed_at timestamp for the frontend)
            stats = self.user_stats[user_id].copy()
            stats.pop('completed_at', None)  # Remove timestamp from response
            return stats
        
        # Fallback - should not happen if calculate_and_store_user_stats was called
        return {
            'test_results': [],
            'correct_count': 0,
            'total_count': 0,
            'percentage': 0,
            'total_time': 0
        }
    
    async def verify_user_id(self, request):
        """Verify if user_id exists and return user data"""
        user_id = request.match_info['user_id']
        
        # Find user by user_id
        if user_id in self.users:
            user_data = self.users[user_id]
            username = user_data['username']
            # Get last answered question ID from progress tracking
            last_answered_question_id = self.user_progress.get(user_id, 0)
            
            # Find the index of next question to answer
            next_question_index = 0
            if last_answered_question_id > 0:
                # Find the index of last answered question, then add 1
                for i, question in enumerate(self.questions):
                    if question['id'] == last_answered_question_id:
                        next_question_index = i + 1
                        break
            
            # Ensure we don't go beyond available questions
            if next_question_index >= len(self.questions):
                next_question_index = len(self.questions)
            
            # Check if test is completed
            test_completed = next_question_index >= len(self.questions)
            
            response_data = {
                'valid': True,
                'user_id': user_id,
                'username': username,
                'next_question_index': next_question_index,
                'total_questions': len(self.questions),
                'last_answered_question_id': last_answered_question_id,
                'test_completed': test_completed
            }
            
            if test_completed:
                # Get final results for completed test
                final_results = self.get_user_final_results(user_id)
                response_data['final_results'] = final_results
                logger.info(f"User {user_id} verification: test completed, returning final results")
            else:
                # Start timing for current question if user has questions left
                self.question_start_times[user_id] = datetime.now()
                logger.info(f"User {user_id} verification: last_answered={last_answered_question_id}, next_index={next_question_index}")
                
            return web.json_response(response_data)
        else:
            return web.json_response({
                'valid': False,
                'message': 'User ID not found'
            })
    
    # Admin API endpoints
    @admin_auth_required
    async def admin_list_quizzes(self, request):
        """List available quiz files"""
        quizzes = await self.list_available_quizzes()
        return web.json_response({
            'quizzes': quizzes,
            'current_quiz': os.path.basename(self.current_quiz_file) if self.current_quiz_file else None
        })
    
    @admin_auth_required  
    async def admin_switch_quiz(self, request):
        """Switch to a different quiz"""
        try:
            data = await request.json()
            quiz_filename = data['quiz_filename']
            
            await self.switch_quiz(quiz_filename)
            
            return web.json_response({
                'success': True,
                'message': f'Switched to quiz: {quiz_filename}',
                'current_quiz': quiz_filename,
                'csv_file': os.path.basename(self.csv_file)
            })
        except Exception as e:
            logger.error(f"Error switching quiz: {e}")
            return web.json_response({'error': str(e)}, status=400)
    
    @admin_auth_required
    async def admin_auth_test(self, request):
        """Test admin authentication"""
        return web.json_response({
            'authenticated': True,
            'message': 'Admin authentication successful'
        })
    
    @admin_auth_required
    async def admin_get_quiz(self, request):
        """Get quiz content for editing"""
        try:
            filename = request.match_info['filename']
            quiz_path = os.path.join(self.quizzes_dir, filename)
            
            if not os.path.exists(quiz_path):
                return web.json_response({'error': 'Quiz file not found'}, status=404)
            
            with open(quiz_path, 'r', encoding='utf-8') as f:
                quiz_content = f.read()
            
            # Also return parsed YAML for wizard mode
            try:
                import yaml
                parsed_quiz = yaml.safe_load(quiz_content)
                return web.json_response({
                    'filename': filename,
                    'content': quiz_content,
                    'parsed': parsed_quiz
                })
            except yaml.YAMLError as e:
                return web.json_response({
                    'filename': filename,
                    'content': quiz_content,
                    'parsed': None,
                    'yaml_error': str(e)
                })
        except Exception as e:
            logger.error(f"Error getting quiz: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    @admin_auth_required
    async def admin_create_quiz(self, request):
        """Create new quiz from wizard or text input"""
        try:
            data = await request.json()
            filename = data.get('filename', '').strip()
            mode = data.get('mode', 'wizard')  # 'wizard' or 'text'
            
            if not filename:
                return web.json_response({'error': 'Filename is required'}, status=400)
            
            if not filename.endswith('.yaml'):
                filename += '.yaml'
            
            quiz_path = os.path.join(self.quizzes_dir, filename)
            
            # Check if file already exists
            if os.path.exists(quiz_path):
                return web.json_response({'error': 'Quiz file already exists'}, status=409)
            
            # Validate and create quiz content
            if mode == 'wizard':
                quiz_data = data.get('quiz_data', {})
                if not self._validate_quiz_data(quiz_data):
                    return web.json_response({'error': 'Invalid quiz data structure'}, status=400)
                
                import yaml
                quiz_content = yaml.dump(quiz_data, default_flow_style=False, allow_unicode=True)
            else:  # text mode
                quiz_content = data.get('content', '').strip()
                if not quiz_content:
                    return web.json_response({'error': 'Quiz content is required'}, status=400)
                
                # Validate YAML
                try:
                    import yaml
                    parsed = yaml.safe_load(quiz_content)
                    if not self._validate_quiz_data(parsed):
                        return web.json_response({'error': 'Invalid quiz data structure'}, status=400)
                except yaml.YAMLError as e:
                    return web.json_response({'error': f'Invalid YAML: {str(e)}'}, status=400)
            
            # Write the quiz file
            with open(quiz_path, 'w', encoding='utf-8') as f:
                f.write(quiz_content)
            
            logger.info(f"Created new quiz: {filename}")
            return web.json_response({
                'success': True,
                'message': f'Quiz "{filename}" created successfully',
                'filename': filename
            })
        except Exception as e:
            logger.error(f"Error creating quiz: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    @admin_auth_required
    async def admin_update_quiz(self, request):
        """Update existing quiz"""
        try:
            filename = request.match_info['filename']
            data = await request.json()
            mode = data.get('mode', 'wizard')
            
            quiz_path = os.path.join(self.quizzes_dir, filename)
            
            if not os.path.exists(quiz_path):
                return web.json_response({'error': 'Quiz file not found'}, status=404)
            
            # Create backup
            backup_path = quiz_path + '.backup'
            import shutil
            shutil.copy2(quiz_path, backup_path)
            
            # Prepare new content
            if mode == 'wizard':
                quiz_data = data.get('quiz_data', {})
                if not self._validate_quiz_data(quiz_data):
                    return web.json_response({'error': 'Invalid quiz data structure'}, status=400)
                
                import yaml
                quiz_content = yaml.dump(quiz_data, default_flow_style=False, allow_unicode=True)
            else:  # text mode
                quiz_content = data.get('content', '').strip()
                if not quiz_content:
                    return web.json_response({'error': 'Quiz content is required'}, status=400)
                
                # Validate YAML
                try:
                    import yaml
                    parsed = yaml.safe_load(quiz_content)
                    if not self._validate_quiz_data(parsed):
                        return web.json_response({'error': 'Invalid quiz data structure'}, status=400)
                except yaml.YAMLError as e:
                    return web.json_response({'error': f'Invalid YAML: {str(e)}'}, status=400)
            
            # Write updated content
            with open(quiz_path, 'w', encoding='utf-8') as f:
                f.write(quiz_content)
            
            # If this is the current quiz, reload it
            if self.current_quiz_file and os.path.basename(self.current_quiz_file) == filename:
                await self.switch_quiz(filename)
            
            logger.info(f"Updated quiz: {filename}")
            return web.json_response({
                'success': True,
                'message': f'Quiz "{filename}" updated successfully',
                'backup_created': os.path.basename(backup_path)
            })
        except Exception as e:
            logger.error(f"Error updating quiz: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    @admin_auth_required
    async def admin_delete_quiz(self, request):
        """Delete quiz file"""
        try:
            filename = request.match_info['filename']
            quiz_path = os.path.join(self.quizzes_dir, filename)
            
            if not os.path.exists(quiz_path):
                return web.json_response({'error': 'Quiz file not found'}, status=404)
            
            # Don't allow deleting the current quiz
            if self.current_quiz_file and os.path.basename(self.current_quiz_file) == filename:
                return web.json_response({'error': 'Cannot delete the currently active quiz'}, status=400)
            
            # Create backup before deletion
            backup_path = quiz_path + '.deleted_backup'
            import shutil
            shutil.copy2(quiz_path, backup_path)
            
            # Delete the file
            os.remove(quiz_path)
            
            logger.info(f"Deleted quiz: {filename} (backup: {backup_path})")
            return web.json_response({
                'success': True,
                'message': f'Quiz "{filename}" deleted successfully',
                'backup_created': os.path.basename(backup_path)
            })
        except Exception as e:
            logger.error(f"Error deleting quiz: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    @admin_auth_required
    async def admin_validate_quiz(self, request):
        """Validate quiz YAML structure"""
        try:
            data = await request.json()
            content = data.get('content', '').strip()
            
            if not content:
                return web.json_response({'valid': False, 'errors': ['Content is empty']})
            
            try:
                import yaml
                parsed = yaml.safe_load(content)
                
                # Validate structure
                errors = []
                if not self._validate_quiz_data(parsed, errors):
                    return web.json_response({'valid': False, 'errors': errors})
                
                return web.json_response({
                    'valid': True,
                    'parsed': parsed,
                    'question_count': len(parsed.get('questions', []))
                })
            except yaml.YAMLError as e:
                return web.json_response({'valid': False, 'errors': [f'YAML syntax error: {str(e)}']})
        except Exception as e:
            logger.error(f"Error validating quiz: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    def _validate_quiz_data(self, data, errors=None):
        """Validate quiz data structure"""
        if errors is None:
            errors = []
        
        if not isinstance(data, dict):
            errors.append("Quiz data must be a dictionary")
            return False
        
        if 'questions' not in data:
            errors.append("Quiz must contain 'questions' field")
            return False
        
        questions = data['questions']
        if not isinstance(questions, list):
            errors.append("'questions' must be a list")
            return False
        
        if len(questions) == 0:
            errors.append("Quiz must contain at least one question")
            return False
        
        for i, question in enumerate(questions):
            if not isinstance(question, dict):
                errors.append(f"Question {i+1} must be a dictionary")
                continue
            
            # Validate required fields (except 'question' which is optional if image provided)
            required_fields = ['options', 'correct_answer']
            for field in required_fields:
                if field not in question:
                    errors.append(f"Question {i+1} missing required field: {field}")
            
            # Either question text OR image must be provided
            has_question = 'question' in question and question['question']
            has_image = 'image' in question and question['image']
            if not has_question and not has_image:
                errors.append(f"Question {i+1} must have either question text or image")
            
            # Validate options
            if 'options' in question:
                options = question['options']
                if not isinstance(options, list):
                    errors.append(f"Question {i+1} options must be a list")
                elif len(options) < 2:
                    errors.append(f"Question {i+1} must have at least 2 options")
                elif not all(isinstance(opt, str) for opt in options):
                    errors.append(f"Question {i+1} all options must be strings")
            
            # Validate correct_answer
            if 'correct_answer' in question and 'options' in question:
                correct_answer = question['correct_answer']
                if not isinstance(correct_answer, int):
                    errors.append(f"Question {i+1} correct_answer must be an integer")
                elif correct_answer < 0 or correct_answer >= len(question['options']):
                    errors.append(f"Question {i+1} correct_answer index out of range")
        
        return len(errors) == 0
        
    async def serve_admin_page(self, request):
        """Serve the admin interface page"""
        try:
            try:
                # Try modern importlib.resources first (Python 3.9+)
                import importlib.resources as pkg_resources
                template_content = (pkg_resources.files('webquiz') / 'templates' / 'admin.html').read_text()
            except (ImportError, AttributeError):
                # Fallback to pkg_resources for older Python versions
                import pkg_resources
                template_path = pkg_resources.resource_filename('webquiz', 'templates/admin.html')
                async with aiofiles.open(template_path, 'r') as template_file:
                    template_content = await template_file.read()
            
            return web.Response(text=template_content, content_type='text/html')
        except Exception as e:
            logger.error(f"Error serving admin page: {e}")
            return web.Response(text='<h1>Admin page not found</h1>', content_type='text/html', status=404)
    
    async def serve_live_stats_page(self, request):
        """Serve the live stats page"""
        try:
            try:
                # Try modern importlib.resources first (Python 3.9+)
                import importlib.resources as pkg_resources
                template_content = (pkg_resources.files('webquiz') / 'templates' / 'live_stats.html').read_text()
            except (ImportError, AttributeError):
                # Fallback to pkg_resources for older Python versions
                import pkg_resources
                template_path = pkg_resources.resource_filename('webquiz', 'templates/live_stats.html')
                async with aiofiles.open(template_path, 'r') as template_file:
                    template_content = await template_file.read()
            
            return web.Response(text=template_content, content_type='text/html')
        except Exception as e:
            logger.error(f"Error serving live stats page: {e}")
            return web.Response(text='<h1>Live stats page not found</h1>', content_type='text/html', status=404)
    
    async def websocket_live_stats(self, request):
        """WebSocket endpoint for live stats updates"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        # Add to connected clients
        self.websocket_clients.append(ws)
        logger.info(f"New WebSocket client connected. Total clients: {len(self.websocket_clients)}")
        
        # Send initial state
        try:
            initial_data = {
                'type': 'initial_state',
                'live_stats': self.live_stats,
                'users': {user_id: user_data['username'] for user_id, user_data in self.users.items()},
                'questions': self.questions,
                'total_questions': len(self.questions),
                'current_quiz': os.path.basename(self.current_quiz_file) if self.current_quiz_file else None
            }
            await ws.send_str(json.dumps(initial_data))
        except Exception as e:
            logger.error(f"Error sending initial state to WebSocket client: {e}")
        
        # Listen for messages (mainly for connection keep-alive)
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    if data.get('type') == 'ping':
                        await ws.send_str(json.dumps({'type': 'pong'}))
                except Exception as e:
                    logger.warning(f"Error processing WebSocket message: {e}")
            elif msg.type == WSMsgType.ERROR:
                logger.error(f'WebSocket error: {ws.exception()}')
                break
        
        # Remove from connected clients when connection closes
        if ws in self.websocket_clients:
            self.websocket_clients.remove(ws)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.websocket_clients)}")
        
        return ws

async def create_app(config: WebQuizConfig):
    """Create and configure the application"""
    
    server = TestingServer(config)
    
    # Initialize log file first (this will set server.log_file)
    await server.initialize_log_file()
    
    # Configure logging with the actual log file path
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(server.log_file),
            logging.StreamHandler()  # Also log to console
        ],
        force=True  # Override any existing configuration
    )
    
    # Load questions and create HTML with embedded data (CSV will be initialized in switch_quiz)
    await server.load_questions()
    
    # Start periodic flush task
    asyncio.create_task(server.periodic_flush())
    
    # Create app with middleware
    app = web.Application(middlewares=[error_middleware])
    
    # Routes
    app.router.add_post('/api/register', server.register_user)
    app.router.add_post('/api/submit-answer', server.submit_answer)
    app.router.add_get('/api/verify-user/{user_id}', server.verify_user_id)
    
    # Admin routes
    app.router.add_get('/admin/', server.serve_admin_page)
    app.router.add_post('/api/admin/auth', server.admin_auth_test)
    app.router.add_get('/api/admin/list-quizzes', server.admin_list_quizzes)
    app.router.add_post('/api/admin/switch-quiz', server.admin_switch_quiz)
    app.router.add_get('/api/admin/quiz/{filename}', server.admin_get_quiz)
    app.router.add_post('/api/admin/create-quiz', server.admin_create_quiz)
    app.router.add_put('/api/admin/quiz/{filename}', server.admin_update_quiz)
    app.router.add_delete('/api/admin/quiz/{filename}', server.admin_delete_quiz)
    app.router.add_post('/api/admin/validate-quiz', server.admin_validate_quiz)
    
    # Live stats routes (public access)
    app.router.add_get('/live-stats/', server.serve_live_stats_page)
    app.router.add_get('/ws/live-stats', server.websocket_live_stats)
    
    # Serve static files from configured static directory
    app.router.add_static('/', path=config.paths.static_dir, name='static')
    
    return app

# Server is now started via CLI (aiotests.cli:main)