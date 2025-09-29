# Selenium End-to-End Tests

This directory contains comprehensive end-to-end tests using Selenium WebDriver to test the complete WebQuiz user journey.

## Test Coverage

### Registration & Session Flow (4 tests)
- ✅ `test_user_registration_complete_flow()` - Full registration workflow
- ✅ `test_registration_form_validation()` - Empty username validation
- ✅ `test_session_persistence_on_reload()` - Cookie-based session continuity
- ✅ `test_username_display_after_registration()` - UI state management

### Quiz Taking Experience (6 tests)
- ✅ `test_complete_quiz_journey()` - End-to-end quiz completion
- ✅ `test_question_selection_and_feedback()` - Visual feedback system
- ✅ `test_progress_bar_functionality()` - Progress indication
- ✅ `test_button_state_management()` - Submit/continue button behavior
- ✅ `test_results_display_accuracy()` - Results calculation verification
- ✅ `test_different_question_types()` - Text, image, and mixed questions

### Show Right Answer Configuration (4 tests)
- ✅ `test_show_right_answer_true_visual_feedback()` - Correct answer highlighting when enabled
- ✅ `test_show_right_answer_false_visual_feedback()` - Correct answer hiding when disabled  
- ✅ `test_show_right_answer_false_correct_answer_visual_feedback()` - User correct answer feedback when showing disabled
- ✅ `test_show_right_answer_multi_question_journey()` - Complete quiz with mixed answers and hidden correct answers

### UI Behavior & Interaction (3 tests)
- ✅ `test_theme_toggle_functionality()` - Dark/light theme switching
- ✅ `test_browser_navigation_behavior()` - Back/forward button handling

## Requirements

### System Dependencies
- **Chrome Browser**: Required for running tests
- **Python 3.9+**: For async support and modern features

### Python Dependencies
**Via Poetry (recommended):**
```bash
poetry install  # Includes all dev dependencies including Selenium
```

**Via pip:**
```bash
pip install -r requirements.txt
```

### Installation Instructions

#### macOS
```bash
# Install Chrome via Homebrew
brew install google-chrome

# Or download from: https://www.google.com/chrome/
```

#### Ubuntu/Debian
```bash
# Install Chrome
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
sudo apt update
sudo apt install google-chrome-stable
```

#### GitHub Actions (Automatic)
Chrome is pre-installed on GitHub Actions runners, no additional setup needed.

## Running Tests

### Local Development
```bash
# Run all Selenium tests
pytest tests/test_user_journey_selenium.py -v

# Run specific test
pytest tests/test_user_journey_selenium.py::test_complete_quiz_journey -v

# Generate HTML report
pytest tests/test_user_journey_selenium.py --html=selenium-report.html --self-contained-html
```

### Debug Mode (Visible Browser)
For debugging and development, use the `SHOW_BROWSER` environment variable to display the browser window:

```bash
# Show browser window during tests (for debugging)
SHOW_BROWSER=true pytest tests/test_user_journey_selenium.py -v

# Single test with visible browser
SHOW_BROWSER=1 pytest tests/test_user_journey_selenium.py::test_complete_quiz_journey -v

# Combined with other options
SHOW_BROWSER=yes pytest tests/test_user_journey_selenium.py -v --html=report.html
```

### Environment Variables
Control test behavior with environment variables:

```bash
# Skip Selenium tests entirely (useful for CI environments without browser)
SKIP_SELENIUM=true pytest tests/ -v

# Show browser window during tests (for debugging and development)
SHOW_BROWSER=true pytest tests/test_user_journey_selenium.py -v

# Default behavior: headless mode, run all tests
pytest tests/test_user_journey_selenium.py -v
```

### CI/CD Pipeline
```bash
# Headless mode (default) - no environment variables needed
pytest tests/test_user_journey_selenium.py --tb=short
```

## Test Architecture

### Browser Configuration
- **Headless Mode**: No visible browser window by default (CI/CD friendly)
- **Debug Mode**: Visible browser window via `SHOW_BROWSER=true` (development friendly)
- **Automatic WebDriver Management**: Downloads correct ChromeDriver automatically
- **Cross-platform**: Works on Windows, macOS, Linux
- **GitHub Actions Ready**: Pre-configured for CI/CD

### Test Fixtures
- `browser()`: Chrome WebDriver with headless configuration
- `custom_webquiz_server()`: Server with custom quiz configurations
- Helper functions for waiting and element interaction

### Error Handling
- **Graceful degradation**: Tests skip if Chrome unavailable
- **Detailed logging**: Screenshots and error messages on failures
- **Timeout management**: Explicit waits for dynamic content

## Sample GitHub Actions Workflow

```yaml
name: Selenium Tests
on: [push, pull_request]

jobs:
  selenium-tests:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3

    - name: Set up Python 3.9
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'

    - name: Install dependencies
      run: |
        poetry install --no-interaction --no-ansi

    - name: Run Selenium tests
      run: |
        poetry run pytest tests/test_user_journey_selenium.py -v --html=selenium-report.html --self-contained-html

    - name: Upload test results
      if: always()
      uses: actions/upload-artifact@v3
      with:
        name: selenium-test-results
        path: selenium-report.html
```

## Key Features Tested

### Real User Simulation
- ✅ Actual browser interactions (clicks, typing, navigation)
- ✅ JavaScript execution and DOM manipulation
- ✅ CSS styling and visual feedback
- ✅ Form validation and error handling

### User Experience Validation
- ✅ Registration workflow with validation
- ✅ Quiz taking with progress tracking
- ✅ Visual feedback on answer submission
- ✅ Results calculation and display
- ✅ Session persistence across page reloads
- ✅ Show/hide correct answers configuration testing

### Cross-browser Compatibility
- ✅ Headless Chrome (default)
- ✅ Can be extended to Firefox, Safari, Edge
- ✅ Mobile viewport testing capability

## Troubleshooting

### Chrome Not Found
```bash
# Error: cannot find Chrome binary
# Solution: Install Chrome browser (see installation instructions above)
```

### WebDriver Issues
```bash
# Error: WebDriver version mismatch
# Solution: webdriver-manager automatically handles this
```

### Test Timeouts
```bash
# Error: Timeout waiting for element
# Solution: Increase timeout or check element selectors
```

### GitHub Actions Failures
```bash
# Error: Display not found
# Solution: Ensure --headless flag is enabled
```

## Benefits

### Complete Coverage
- **Real browser testing** vs. unit test mocks
- **JavaScript validation** of client-side functionality
- **User experience testing** of actual workflows
- **Visual regression detection** through screenshots

### CI/CD Integration
- **Automated testing** on every commit
- **Cross-platform validation** (Windows, macOS, Linux)
- **Performance monitoring** of real user interactions
- **Deployment confidence** through E2E validation

### Development Support
- **Debug mode** for visual test development
- **Screenshot capture** on test failures
- **HTML reports** with detailed test results
- **Fast feedback loop** for UI changes