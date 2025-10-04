"""
Shared helper functions and fixtures for Selenium tests.

This module contains common utilities used across all Selenium test files
to reduce code duplication and improve maintainability.
"""
import pytest
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from conftest import get_worker_port


# ============================================================================
# PYTEST MARKERS AND FIXTURES
# ============================================================================

skip_if_selenium_disabled = pytest.mark.skipif(
    os.getenv('SKIP_SELENIUM', '').lower() in ('true', '1', 'yes'),
    reason="Selenium tests skipped (SKIP_SELENIUM environment variable is set)"
)


@pytest.fixture
def browser():
    """Set up Chrome/Chromium browser in headless mode for testing."""
    # Get worker-specific port for parallel testing
    worker_port = get_worker_port()
    # Calculate debugging port based on worker port (9222 + offset)
    debug_port = 9222 + (worker_port - 8080)

    options = Options()

    # Check SHOW_BROWSER environment variable for debugging
    show_browser = os.getenv('SHOW_BROWSER', '').lower() in ('true', '1', 'yes')
    if not show_browser:
        options.add_argument('--headless')  # Headless mode unless SHOW_BROWSER is set

    options.add_argument('--no-sandbox')  # Required for GitHub Actions
    options.add_argument('--disable-dev-shm-usage')  # Overcome limited resource problems
    options.add_argument('--disable-gpu')  # Disable GPU acceleration
    options.add_argument('--disable-extensions')  # Disable extensions
    options.add_argument('--disable-web-security')  # Disable web security for testing
    options.add_argument('--disable-features=VizDisplayCompositor')  # Fix rendering issues
    options.add_argument(f'--remote-debugging-port={debug_port}')  # Worker-specific debugging port
    options.add_argument('--window-size=1920,1080')  # Set consistent window size

    try:
        # Use webdriver-manager for cross-platform compatibility
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.implicitly_wait(10)

        yield driver

        # Cleanup
        driver.quit()
    except Exception as e:
        pytest.skip(f"Chrome/Chromium browser not available: {e}")


# ============================================================================
# WAIT HELPERS
# ============================================================================

def wait_for_element(browser, by, selector, timeout=10):
    """Helper function to wait for element with better error handling."""
    try:
        return WebDriverWait(browser, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
    except TimeoutException:
        print(f"Timeout waiting for element: {by}={selector}")
        print(f"Current page source: {browser.page_source[:500]}...")
        raise


def wait_for_clickable(browser, by, selector, timeout=10):
    """Helper function to wait for clickable element."""
    return WebDriverWait(browser, timeout).until(
        EC.element_to_be_clickable((by, selector))
    )


# ============================================================================
# ELEMENT FINDERS
# ============================================================================

def find_register_button(browser):
    """Find the registration button using CSS class."""
    return browser.find_element(By.CSS_SELECTOR, '.register-btn')


def find_option_by_index(browser, index):
    """Find an option by its index using data attribute."""
    return browser.find_element(By.CSS_SELECTOR, f'[data-option-index="{index}"]')


def find_option_by_text(browser, text):
    """Find an option by its text content (fallback method)."""
    options = browser.find_elements(By.CSS_SELECTOR, '.quiz-option')
    for option in options:
        if text in option.text:
            return option
    raise NoSuchElementException(f"Option with text '{text}' not found")


def find_options(browser):
    """Find all option div elements (works for both single and multiple choice)."""
    return browser.find_elements(By.CSS_SELECTOR, '.quiz-option')


def find_question_text(browser):
    """Find the current question text element."""
    return browser.find_element(By.CSS_SELECTOR, '.question-text')


def wait_for_question_text(browser, timeout=10):
    """Wait for question text to be present."""
    return wait_for_element(browser, By.CSS_SELECTOR, '.question-text', timeout)


# ============================================================================
# OPTION STATE HELPERS
# ============================================================================

def is_option_selected(option_element):
    """Check if an option is selected by checking for 'selected' class."""
    return 'selected' in option_element.get_attribute('class')


def get_selected_options(browser):
    """Get all currently selected options."""
    options = find_options(browser)
    return [opt for opt in options if is_option_selected(opt)]


# ============================================================================
# QUESTION TYPE HELPERS
# ============================================================================

def is_multiple_choice_question(browser):
    """Check if current question is multiple choice by looking for the hint element."""
    try:
        # Check if the multiple-choice-hint element exists and is displayed
        hint = browser.find_element(By.CSS_SELECTOR, '.multiple-choice-hint')
        return hint.is_displayed()
    except:
        return False


# ============================================================================
# USER REGISTRATION HELPERS
# ============================================================================

def get_registration_fields(browser):
    """
    Get all additional registration fields (excluding username).

    Returns:
        List of WebElement objects with class 'registration-field'
    """
    return browser.find_elements(By.CLASS_NAME, 'registration-field')


def fill_registration_field(browser, field_label, value):
    """
    Fill a registration field by its label text (from table row).

    Args:
        browser: Selenium WebDriver instance
        field_label: The label text of the field (e.g., 'Grade', 'Клас')
        value: The value to fill in the field

    Raises:
        NoSuchElementException: If field with given label is not found
    """
    # Find the table row containing the label
    from selenium.webdriver.common.by import By
    try:
        # Look for TD containing the label text with colon
        label_td = browser.find_element(By.XPATH, f"//td[contains(text(), '{field_label}:')]")
        # Find the input field in the next sibling TD
        parent_tr = label_td.find_element(By.XPATH, "..")
        input_field = parent_tr.find_element(By.CSS_SELECTOR, "input.registration-field")
        input_field.clear()
        input_field.send_keys(value)
    except:
        raise NoSuchElementException(f"Registration field with label '{field_label}' not found")


def fill_registration_field_by_name(browser, field_name, value):
    """
    Fill a registration field by its data-field-name attribute.

    Args:
        browser: Selenium WebDriver instance
        field_name: The field name attribute (e.g., 'grade', 'school')
        value: The value to fill in the field

    Raises:
        NoSuchElementException: If field with given name is not found
    """
    try:
        field = browser.find_element(By.CSS_SELECTOR, f'[data-field-name="{field_name}"]')
        field.clear()
        field.send_keys(value)
    except NoSuchElementException:
        raise NoSuchElementException(f"Registration field with name '{field_name}' not found")


def register_user(browser, port, username='TestStudent', **additional_fields):
    """
    Helper to register a user and start quiz.

    Args:
        browser: Selenium WebDriver instance
        port: Server port number
        username: Username to register with
        **additional_fields: Additional registration fields as keyword arguments
                           (e.g., grade='10', school='Central HS')

    Example:
        register_user(browser, port, 'Student1', grade='10', school='North HS')
    """
    browser.get(f'http://localhost:{port}/')
    username_input = wait_for_element(browser, By.ID, 'username')
    username_input.send_keys(username)

    # Fill additional registration fields if provided
    for field_name, value in additional_fields.items():
        fill_registration_field_by_name(browser, field_name, value)

    register_button = find_register_button(browser)
    register_button.click()
    wait_for_element(browser, By.ID, 'current-question-container')
