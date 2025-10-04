import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from conftest import custom_webquiz_server
from selenium_helpers import (
    skip_if_selenium_disabled,
    browser,
    wait_for_element,
    wait_for_clickable,
    find_register_button
)


@skip_if_selenium_disabled
def test_registration_form_renders_extra_fields(temp_dir, browser):
    """Test that registration form renders additional fields from config"""
    config = {
        'registration': {
            'fields': ['Grade', 'School']
        }
    }

    quiz_data = {
        'default.yaml': {
            'title': 'Registration Fields Test',
            'questions': [
                {
                    'question': 'Test question?',
                    'options': ['A', 'B'],
                    'correct_answer': 0
                }
            ]
        }
    }

    with custom_webquiz_server(config=config, quizzes=quiz_data) as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Wait for registration form
        username_input = wait_for_element(browser, By.ID, 'username')
        assert username_input.is_displayed()

        # Find additional registration fields
        additional_fields = browser.find_elements(By.CLASS_NAME, 'registration-field')
        assert len(additional_fields) == 2, "Should have 2 additional fields"

        # Check field labels in table format
        # Find the table rows containing labels
        grade_label = browser.find_element(By.XPATH, "//td[contains(text(), 'Grade:')]")
        school_label = browser.find_element(By.XPATH, "//td[contains(text(), 'School:')]")
        assert grade_label.is_displayed()
        assert school_label.is_displayed()


@skip_if_selenium_disabled
def test_registration_with_all_fields_filled(temp_dir, browser):
    """Test successful registration with all fields filled"""
    config = {
        'registration': {
            'fields': ['Grade', 'School']
        }
    }

    quiz_data = {
        'default.yaml': {
            'title': 'Registration Success Test',
            'questions': [
                {
                    'question': 'Test question?',
                    'options': ['A', 'B'],
                    'correct_answer': 0
                }
            ]
        }
    }

    with custom_webquiz_server(config=config, quizzes=quiz_data) as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Fill registration form
        username_input = wait_for_element(browser, By.ID, 'username')
        username_input.send_keys('TestStudent')

        # Fill additional fields
        additional_fields = browser.find_elements(By.CLASS_NAME, 'registration-field')
        additional_fields[0].send_keys('10')  # Grade
        additional_fields[1].send_keys('Central High School')  # School

        # Submit registration
        register_button = find_register_button(browser)
        register_button.click()

        # Wait for test section to appear (registration successful)
        test_section = WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, 'test-section'))
        )
        assert test_section.is_displayed()

        # Verify user info is displayed
        user_info = wait_for_element(browser, By.ID, 'user-info')
        assert 'TestStudent' in user_info.text


@skip_if_selenium_disabled
def test_registration_missing_required_field(temp_dir, browser):
    """Test validation when required field is missing"""
    config = {
        'registration': {
            'fields': ['Grade']
        }
    }

    quiz_data = {
        'default.yaml': {
            'title': 'Validation Test',
            'questions': [
                {
                    'question': 'Test question?',
                    'options': ['A', 'B'],
                    'correct_answer': 0
                }
            ]
        }
    }

    with custom_webquiz_server(config=config, quizzes=quiz_data) as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Fill only username, leave grade field empty
        username_input = wait_for_element(browser, By.ID, 'username')
        username_input.send_keys('IncompleteStudent')

        # Submit without filling grade
        register_button = find_register_button(browser)
        register_button.click()

        # Wait a moment for error to appear
        time.sleep(0.5)

        # Should still be on registration page
        registration_section = browser.find_element(By.ID, 'registration')
        assert 'hidden' not in registration_section.get_attribute('class')

        # Error message should be visible
        error_element = browser.find_element(By.ID, 'registration-error')
        assert 'hidden' not in error_element.get_attribute('class')


@skip_if_selenium_disabled
def test_multiple_users_with_registration_fields(temp_dir, browser):
    """Test multiple users can register with additional fields"""
    config = {
        'registration': {
            'fields': ['Grade']
        }
    }

    quiz_data = {
        'default.yaml': {
            'title': 'Multiple Users Test',
            'questions': [
                {
                    'question': 'Test question?',
                    'options': ['A', 'B'],
                    'correct_answer': 0
                }
            ]
        }
    }

    with custom_webquiz_server(config=config, quizzes=quiz_data) as (proc, port):
        # Register first user
        browser.get(f'http://localhost:{port}/')

        username_input = wait_for_element(browser, By.ID, 'username')
        username_input.send_keys('Student1')

        grade_field = browser.find_element(By.CLASS_NAME, 'registration-field')
        grade_field.send_keys('9')

        register_button = find_register_button(browser)
        register_button.click()

        # Wait for test to load
        WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, 'test-section'))
        )

        # Clear cookies to simulate new user
        browser.delete_all_cookies()

        # Register second user
        browser.get(f'http://localhost:{port}/')

        username_input = wait_for_element(browser, By.ID, 'username')
        username_input.send_keys('Student2')

        grade_field = browser.find_element(By.CLASS_NAME, 'registration-field')
        grade_field.send_keys('10')

        register_button = find_register_button(browser)
        register_button.click()

        # Should succeed
        test_section = WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, 'test-section'))
        )
        assert test_section.is_displayed()


@skip_if_selenium_disabled
def test_quiz_flow_with_registration_fields(temp_dir, browser):
    """Test complete quiz flow with registration fields"""
    config = {
        'registration': {
            'fields': ['Grade', 'School']
        }
    }

    quiz_data = {
        'default.yaml': {
            'title': 'Full Flow Test',
            'questions': [
                {
                    'question': 'What is 1+1?',
                    'options': ['1', '2', '3'],
                    'correct_answer': 1
                },
                {
                    'question': 'What is 2+2?',
                    'options': ['3', '4', '5'],
                    'correct_answer': 1
                }
            ]
        }
    }

    with custom_webquiz_server(config=config, quizzes=quiz_data) as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Register
        username_input = wait_for_element(browser, By.ID, 'username')
        username_input.send_keys('QuizTaker')

        fields = browser.find_elements(By.CLASS_NAME, 'registration-field')
        fields[0].send_keys('11')
        fields[1].send_keys('North High')

        register_button = find_register_button(browser)
        register_button.click()

        # Wait for quiz to load
        WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, 'test-section'))
        )

        # Answer first question
        option = wait_for_element(browser, By.ID, 'option_1')
        option.click()

        submit_btn = browser.find_element(By.ID, 'submit-answer-btn')
        submit_btn.click()

        # Wait for continue button
        continue_btn = WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, 'continue-btn'))
        )
        continue_btn.click()

        # Answer second question
        time.sleep(0.5)
        option = browser.find_element(By.ID, 'option_1')
        option.click()

        submit_btn = browser.find_element(By.ID, 'submit-answer-btn')
        submit_btn.click()

        # Wait for continue button
        continue_btn = WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, 'continue-btn'))
        )
        continue_btn.click()

        # Should show results
        results_section = WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, 'results'))
        )
        assert results_section.is_displayed()


@skip_if_selenium_disabled
def test_registration_with_cyrillic_labels_selenium(temp_dir, browser):
    """Test that Cyrillic field labels render correctly in browser"""
    config = {
        'registration': {
            'fields': ['Клас', 'Школа']
        }
    }

    quiz_data = {
        'default.yaml': {
            'title': 'Cyrillic Test',
            'questions': [
                {
                    'question': 'Test?',
                    'options': ['A', 'B'],
                    'correct_answer': 0
                }
            ]
        }
    }

    with custom_webquiz_server(config=config, quizzes=quiz_data) as (proc, port):
        browser.get(f'http://localhost:{port}/')

        # Wait for registration form
        username_input = wait_for_element(browser, By.ID, 'username')
        username_input.send_keys('УкраїнськийУчень')

        # Find and fill Cyrillic fields
        additional_fields = browser.find_elements(By.CLASS_NAME, 'registration-field')
        assert len(additional_fields) == 2

        # Check labels are in Cyrillic
        klas_label = browser.find_element(By.XPATH, "//td[contains(text(), 'Клас:')]")
        shkola_label = browser.find_element(By.XPATH, "//td[contains(text(), 'Школа:')]")
        assert klas_label.is_displayed()
        assert shkola_label.is_displayed()

        # Fill fields
        additional_fields[0].send_keys('8')
        additional_fields[1].send_keys('Гімназія №7')

        # Submit
        register_button = find_register_button(browser)
        register_button.click()

        # Should succeed
        test_section = WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.ID, 'test-section'))
        )
        assert test_section.is_displayed()


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
