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

### UI Behavior & Interaction (3 tests)
- ✅ `test_theme_toggle_functionality()` - Dark/light theme switching
- ✅ `test_browser_navigation_behavior()` - Back/forward button handling

## Requirements

### System Dependencies
- **Chrome Browser**: Required for running tests
- **Python 3.9+**: For async support and modern features

### Python Dependencies
```bash
pip install selenium webdriver-manager pytest-html
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

### Debug Mode (Headed Browser)
For debugging, you can modify the browser fixture to remove `--headless`:

```python
# In test_user_journey_selenium.py, comment out this line:
# options.add_argument('--headless')
```

### CI/CD Pipeline
```bash
# Headless mode (default)
pytest tests/test_user_journey_selenium.py --tb=short
```

## Test Architecture

### Browser Configuration
- **Headless Mode**: No visible browser window (CI/CD friendly)
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
        pip install -r requirements.txt
        pip install selenium webdriver-manager pytest-html

    - name: Run Selenium tests
      run: |
        pytest tests/test_user_journey_selenium.py -v --html=selenium-report.html --self-contained-html

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