import asyncio
import json
import csv
import uuid
import yaml
from datetime import datetime
from typing import Dict, List, Any
from aiohttp import web
import aiofiles
import logging
from io import StringIO

# Logger will be configured in create_app() with custom log file
logger = logging.getLogger(__name__)

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
    def __init__(self, config_file: str = 'config.yaml', log_file: str = 'server.log', csv_file: str = 'user_responses.csv', static_dir: str = 'static'):
        self.config_file = config_file
        self.log_file = log_file
        self.csv_file = csv_file
        self.static_dir = static_dir
        self.users: Dict[str, Dict[str, Any]] = {}  # user_id -> user data
        self.questions: List[Dict[str, Any]] = []
        self.user_responses: List[Dict[str, Any]] = []
        self.questions_for_client: List[Dict[str, Any]] = []
        self.user_progress: Dict[str, int] = {}  # user_id -> last_answered_question_id
        self.question_start_times: Dict[str, datetime] = {}  # user_id -> question_start_time
        
    async def initialize_log_file(self):
        """Initialize/recreate log file"""
        try:
            # Clear the log file by opening in write mode
            with open(self.log_file, 'w') as f:
                f.write('')
            logger.info(f"=== Server Started - Log File Reset: {self.log_file} ===")
        except Exception as e:
            print(f"Error initializing log file {self.log_file}: {e}")

    async def initialize_csv(self):
        """Initialize/recreate CSV file with headers"""
        try:
            async with aiofiles.open(self.csv_file, 'w') as f:
                await f.write('user_id,username,question_text,selected_answer_text,correct_answer_text,is_correct,time_taken_seconds\n')
            logger.info(f"Initialized CSV file with headers: {self.csv_file}")
        except Exception as e:
            logger.error(f"Error initializing CSV file {self.csv_file}: {e}")
    
    async def create_default_config_yaml(self):
        """Create default config.yaml file"""
        default_questions = {
            'questions': [
                {
                    'id': 1,
                    'question': 'What is 2 + 2?',
                    'options': ['3', '4', '5', '6'],
                    'correct_answer': 1
                },
                {
                    'id': 2,
                    'question': 'What is the capital of France?',
                    'options': ['London', 'Berlin', 'Paris', 'Madrid'],
                    'correct_answer': 2
                },
                {
                    'id': 3,
                    'question': 'Which programming language is this server written in?',
                    'options': ['JavaScript', 'Python', 'Java', 'C++'],
                    'correct_answer': 1
                }
            ]
        }
        
        try:
            async with aiofiles.open(self.config_file, 'w') as f:
                await f.write(yaml.dump(default_questions, default_flow_style=False))
            logger.info(f"Created default config file: {self.config_file}")
        except Exception as e:
            logger.error(f"Error creating default config file {self.config_file}: {e}")

    async def load_questions(self):
        """Load questions from config file"""
        try:
            async with aiofiles.open(self.config_file, 'r') as f:
                content = await f.read()
                data = yaml.safe_load(content)
                self.questions = data['questions']
                
                # Add automatic IDs if not present
                for i, question in enumerate(self.questions):
                    if 'id' not in question:
                        question['id'] = i + 1
                        
                logger.info(f"Loaded {len(self.questions)} questions from {self.config_file}")
        except FileNotFoundError:
            logger.info(f"{self.config_file} not found, creating default file")
            await self.create_default_config_yaml()
            # Retry loading after creating default file
            await self.load_questions()
        except Exception as e:
            logger.error(f"Error loading questions from {self.config_file}: {e}")
            
    async def generate_client_questions(self):
        """Generate JSON file with questions without correct answers"""
        self.questions_for_client = []
        for q in self.questions:
            client_question = {
                'id': q['id'],
                'question': q['question'],
                'options': q['options']
            }
            self.questions_for_client.append(client_question)
            
        try:
            # Ensure static directory exists
            import os
            os.makedirs(self.static_dir, exist_ok=True)
            
            client_questions_path = f"{self.static_dir}/questions_for_client.json"
            async with aiofiles.open(client_questions_path, 'w') as f:
                await f.write(json.dumps(self.questions_for_client, indent=2))
                logger.info(f"Generated client questions JSON file: {client_questions_path}")
        except Exception as e:
            logger.error(f"Error generating client questions: {e}")
            
    async def create_default_index_html(self):
        """Create default index.html file if it doesn't exist"""
        index_path = f"{self.static_dir}/index.html"
        
        # Copy template from package
        try:
            try:
                # Try modern importlib.resources first (Python 3.9+)
                import importlib.resources as pkg_resources
                template_content = (pkg_resources.files('webquiz') / 'templates' / 'index.html').read_text()
            except (ImportError, AttributeError):
                # Fallback to pkg_resources for older Python versions
                import pkg_resources
                template_path = pkg_resources.resource_filename('webquiz', 'templates/index.html')
                async with aiofiles.open(template_path, 'r') as template_file:
                    template_content = await template_file.read()
            
            # Write to destination
            async with aiofiles.open(index_path, 'w') as f:
                await f.write(template_content)
                
            logger.info(f"Created default index.html file: {index_path}")
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
            async with aiofiles.open(index_path, 'w') as f:
                await f.write(fallback_html)
            logger.warning(f"Created fallback index.html file: {index_path}")
        except Exception as e:
            logger.error(f"Error creating fallback index.html: {e}")
            
    async def flush_responses_to_csv(self):
        """Flush in-memory responses to CSV file"""
        if not self.user_responses:
            return
            
        try:
            # Use StringIO buffer to write CSV data
            csv_buffer = StringIO()
            csv_writer = csv.writer(csv_buffer)
            
            # Write all responses to buffer
            for response in self.user_responses:
                csv_writer.writerow([
                    response['user_id'],
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
            
            async with aiofiles.open(self.csv_file, 'a') as f:
                await f.write(csv_content)
                    
            logger.info(f"Flushed {total_responses} responses to CSV: {self.csv_file}")
        except Exception as e:
            logger.error(f"Error flushing responses to CSV: {e}")
            
    async def periodic_flush(self):
        """Periodically flush responses to CSV"""
        while True:
            await asyncio.sleep(30)  # Flush every 30 seconds
            await self.flush_responses_to_csv()
            
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
        
        # Update user progress
        self.user_progress[user_id] = question_id
        
        # Start timing for next question if not the last question
        if question_id < len(self.questions):
            self.question_start_times[user_id] = datetime.now()
        
        logger.info(f"Answer submitted by {username} (ID: {user_id}) for question {question_id}: {'Correct' if is_correct else 'Incorrect'} (took {time_taken:.2f}s)")
        logger.info(f"Updated progress for user {user_id}: last answered question = {question_id}")
        
        return web.json_response({
            'is_correct': is_correct,
            'time_taken': time_taken,
            'message': 'Answer submitted successfully'
        })
            
        

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
            
            # Start timing for current question if user has questions left
            if next_question_index < len(self.questions):
                self.question_start_times[user_id] = datetime.now()
            
            logger.info(f"User {user_id} verification: last_answered={last_answered_question_id}, next_index={next_question_index}")
                
            return web.json_response({
                'valid': True,
                'user_id': user_id,
                'username': username,
                'next_question_index': next_question_index,
                'total_questions': len(self.questions),
                'last_answered_question_id': last_answered_question_id
            })
        else:
            return web.json_response({
                'valid': False,
                'message': 'User ID not found'
            })

async def create_app(config_file: str = 'config.yaml', log_file: str = 'server.log', csv_file: str = 'user_responses.csv', static_dir: str = 'static'):
    """Create and configure the application"""
    # Configure logging with custom log file
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  # Also log to console
        ],
        force=True  # Override any existing configuration
    )
    
    server = TestingServer(config_file, log_file, csv_file, static_dir)
    
    # Clean/recreate log file and CSV file on startup
    await server.initialize_log_file()
    await server.initialize_csv()
    
    # Load questions and generate client JSON
    await server.load_questions()
    await server.generate_client_questions()
    
    # Create default index.html if it doesn't exist
    await server.create_default_index_html()
    
    # Start periodic flush task
    asyncio.create_task(server.periodic_flush())
    
    # Create app with middleware
    app = web.Application(middlewares=[error_middleware])
    
    # Routes
    app.router.add_post('/api/register', server.register_user)
    app.router.add_post('/api/submit-answer', server.submit_answer)
    app.router.add_get('/api/verify-user/{user_id}', server.verify_user_id)
    
    # Serve static files from configured static directory
    app.router.add_static('/', path=static_dir, name='static')
    
    return app

# Server is now started via CLI (aiotests.cli:main)