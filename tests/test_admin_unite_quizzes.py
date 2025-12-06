"""Tests for the admin unite-quizzes API endpoint."""

import os
import requests
import yaml
from conftest import custom_webquiz_server, get_admin_session


def test_unite_two_quizzes_success(temp_dir):
    """Test uniting two quizzes creates combined quiz."""
    quizzes = {
        "quiz1.yaml": {
            "title": "Quiz 1",
            "questions": [
                {"question": "Q1 from quiz1?", "options": ["A", "B"], "correct_answer": 0},
                {"question": "Q2 from quiz1?", "options": ["C", "D"], "correct_answer": 1},
            ],
        },
        "quiz2.yaml": {
            "title": "Quiz 2",
            "questions": [
                {"question": "Q1 from quiz2?", "options": ["E", "F"], "correct_answer": 0},
            ],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)

        response = requests.post(
            f"http://localhost:{port}/api/admin/unite-quizzes",
            cookies=cookies,
            json={"quiz_filenames": ["quiz1.yaml", "quiz2.yaml"], "new_name": "united"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["filename"] == "united.yaml"
        assert data["total_questions"] == 3
        assert data["source_quizzes"] == ["quiz1.yaml", "quiz2.yaml"]
        assert "warning" not in data  # No duplicates


def test_unite_three_quizzes_success(temp_dir):
    """Test uniting three quizzes combines all questions."""
    quizzes = {
        "quiz1.yaml": {
            "title": "Quiz 1",
            "questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": 0}],
        },
        "quiz2.yaml": {
            "title": "Quiz 2",
            "questions": [{"question": "Q2?", "options": ["C", "D"], "correct_answer": 1}],
        },
        "quiz3.yaml": {
            "title": "Quiz 3",
            "questions": [{"question": "Q3?", "options": ["E", "F"], "correct_answer": 0}],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)

        response = requests.post(
            f"http://localhost:{port}/api/admin/unite-quizzes",
            cookies=cookies,
            json={"quiz_filenames": ["quiz1.yaml", "quiz2.yaml", "quiz3.yaml"], "new_name": "all_united"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_questions"] == 3
        assert len(data["source_quizzes"]) == 3


def test_unite_takes_config_from_first_quiz(temp_dir):
    """Test that title, show_right_answer, etc. come from first quiz."""
    quizzes = {
        "quiz1.yaml": {
            "title": "First Quiz Title",
            "description": "First quiz description",
            "show_right_answer": False,
            "randomize_questions": True,
            "questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": 0}],
        },
        "quiz2.yaml": {
            "title": "Second Quiz Title",
            "description": "Second quiz description",
            "show_right_answer": True,
            "randomize_questions": False,
            "questions": [{"question": "Q2?", "options": ["C", "D"], "correct_answer": 1}],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)

        response = requests.post(
            f"http://localhost:{port}/api/admin/unite-quizzes",
            cookies=cookies,
            json={"quiz_filenames": ["quiz1.yaml", "quiz2.yaml"], "new_name": "united_config"},
        )

        assert response.status_code == 200

        # Read the created file and verify config
        quizzes_dir = os.path.join(temp_dir, f"quizzes_{port}")
        united_path = os.path.join(quizzes_dir, "united_config.yaml")
        with open(united_path, "r", encoding="utf-8") as f:
            united_quiz = yaml.safe_load(f)

        assert united_quiz["title"] == "First Quiz Title"
        assert united_quiz["description"] == "First quiz description"
        assert united_quiz["show_right_answer"] is False
        assert united_quiz["randomize_questions"] is True


def test_unite_preserves_question_order(temp_dir):
    """Test questions appear in order: quiz1 questions, then quiz2, etc."""
    quizzes = {
        "quiz1.yaml": {
            "title": "Quiz 1",
            "questions": [
                {"question": "First question", "options": ["A", "B"], "correct_answer": 0},
                {"question": "Second question", "options": ["C", "D"], "correct_answer": 1},
            ],
        },
        "quiz2.yaml": {
            "title": "Quiz 2",
            "questions": [
                {"question": "Third question", "options": ["E", "F"], "correct_answer": 0},
            ],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)

        response = requests.post(
            f"http://localhost:{port}/api/admin/unite-quizzes",
            cookies=cookies,
            json={"quiz_filenames": ["quiz1.yaml", "quiz2.yaml"], "new_name": "order_test"},
        )

        assert response.status_code == 200

        # Read the created file and verify order
        quizzes_dir = os.path.join(temp_dir, f"quizzes_{port}")
        united_path = os.path.join(quizzes_dir, "order_test.yaml")
        with open(united_path, "r", encoding="utf-8") as f:
            united_quiz = yaml.safe_load(f)

        questions = united_quiz["questions"]
        assert questions[0]["question"] == "First question"
        assert questions[1]["question"] == "Second question"
        assert questions[2]["question"] == "Third question"


def test_unite_requires_at_least_two_quizzes(temp_dir):
    """Test error when trying to unite single quiz."""
    quizzes = {
        "quiz1.yaml": {
            "title": "Quiz 1",
            "questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": 0}],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)

        response = requests.post(
            f"http://localhost:{port}/api/admin/unite-quizzes",
            cookies=cookies,
            json={"quiz_filenames": ["quiz1.yaml"], "new_name": "should_fail"},
        )

        assert response.status_code == 400
        assert "принаймні 2" in response.json()["error"]


def test_unite_empty_quiz_list_error(temp_dir):
    """Test error when quiz_filenames is empty."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        response = requests.post(
            f"http://localhost:{port}/api/admin/unite-quizzes",
            cookies=cookies,
            json={"quiz_filenames": [], "new_name": "empty_test"},
        )

        assert response.status_code == 400
        assert "принаймні 2" in response.json()["error"]


def test_unite_missing_new_name_error(temp_dir):
    """Test error when new_name is not provided."""
    quizzes = {
        "quiz1.yaml": {
            "title": "Quiz 1",
            "questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": 0}],
        },
        "quiz2.yaml": {
            "title": "Quiz 2",
            "questions": [{"question": "Q2?", "options": ["C", "D"], "correct_answer": 1}],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)

        response = requests.post(
            f"http://localhost:{port}/api/admin/unite-quizzes",
            cookies=cookies,
            json={"quiz_filenames": ["quiz1.yaml", "quiz2.yaml"], "new_name": ""},
        )

        assert response.status_code == 400
        assert "обов'язкове" in response.json()["error"]


def test_unite_existing_filename_error(temp_dir):
    """Test 409 error when new name already exists."""
    quizzes = {
        "quiz1.yaml": {
            "title": "Quiz 1",
            "questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": 0}],
        },
        "quiz2.yaml": {
            "title": "Quiz 2",
            "questions": [{"question": "Q2?", "options": ["C", "D"], "correct_answer": 1}],
        },
        "existing.yaml": {
            "title": "Existing Quiz",
            "questions": [{"question": "Q?", "options": ["X", "Y"], "correct_answer": 0}],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)

        response = requests.post(
            f"http://localhost:{port}/api/admin/unite-quizzes",
            cookies=cookies,
            json={"quiz_filenames": ["quiz1.yaml", "quiz2.yaml"], "new_name": "existing"},
        )

        assert response.status_code == 409
        assert "вже існує" in response.json()["error"]


def test_unite_nonexistent_quiz_error(temp_dir):
    """Test 404 error when one of the quizzes doesn't exist."""
    quizzes = {
        "quiz1.yaml": {
            "title": "Quiz 1",
            "questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": 0}],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)

        response = requests.post(
            f"http://localhost:{port}/api/admin/unite-quizzes",
            cookies=cookies,
            json={"quiz_filenames": ["quiz1.yaml", "nonexistent.yaml"], "new_name": "united"},
        )

        assert response.status_code == 404
        assert "не знайдено" in response.json()["error"]


def test_unite_without_auth(temp_dir):
    """Test 401 error without authentication."""
    quizzes = {
        "quiz1.yaml": {
            "title": "Quiz 1",
            "questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": 0}],
        },
        "quiz2.yaml": {
            "title": "Quiz 2",
            "questions": [{"question": "Q2?", "options": ["C", "D"], "correct_answer": 1}],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        # No cookies - not authenticated
        response = requests.post(
            f"http://localhost:{port}/api/admin/unite-quizzes",
            json={"quiz_filenames": ["quiz1.yaml", "quiz2.yaml"], "new_name": "united"},
        )

        assert response.status_code == 401


def test_unite_warns_on_duplicate_questions(temp_dir):
    """Test warning is included when duplicate questions detected."""
    quizzes = {
        "quiz1.yaml": {
            "title": "Quiz 1",
            "questions": [
                {"question": "Same question text", "options": ["A", "B"], "correct_answer": 0},
            ],
        },
        "quiz2.yaml": {
            "title": "Quiz 2",
            "questions": [
                {"question": "Same question text", "options": ["C", "D"], "correct_answer": 1},  # Duplicate
                {"question": "Unique question", "options": ["E", "F"], "correct_answer": 0},
            ],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)

        response = requests.post(
            f"http://localhost:{port}/api/admin/unite-quizzes",
            cookies=cookies,
            json={"quiz_filenames": ["quiz1.yaml", "quiz2.yaml"], "new_name": "with_dups"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_questions"] == 3  # All included
        assert "warning" in data
        assert "1" in data["warning"]  # 1 duplicate found


def test_unite_same_text_different_file_not_duplicate(temp_dir):
    """Test that same question text with different file is not counted as duplicate."""
    quizzes = {
        "quiz1.yaml": {
            "title": "Quiz 1",
            "questions": [
                {"question": "Same question text", "options": ["A", "B"], "correct_answer": 0, "file": "file1.xlsx"},
            ],
        },
        "quiz2.yaml": {
            "title": "Quiz 2",
            "questions": [
                {
                    "question": "Same question text",
                    "options": ["C", "D"],
                    "correct_answer": 1,
                    "file": "file2.xlsx",
                },  # Different file
            ],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)

        response = requests.post(
            f"http://localhost:{port}/api/admin/unite-quizzes",
            cookies=cookies,
            json={"quiz_filenames": ["quiz1.yaml", "quiz2.yaml"], "new_name": "no_dups"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_questions"] == 2
        # No warning because different files make them unique
        assert "warning" not in data or data.get("warning") is None


def test_unite_with_yaml_extension_in_name(temp_dir):
    """Test that providing .yaml extension in name works correctly."""
    quizzes = {
        "quiz1.yaml": {
            "title": "Quiz 1",
            "questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": 0}],
        },
        "quiz2.yaml": {
            "title": "Quiz 2",
            "questions": [{"question": "Q2?", "options": ["C", "D"], "correct_answer": 1}],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)

        response = requests.post(
            f"http://localhost:{port}/api/admin/unite-quizzes",
            cookies=cookies,
            json={"quiz_filenames": ["quiz1.yaml", "quiz2.yaml"], "new_name": "united.yaml"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "united.yaml"  # Not united.yaml.yaml


def test_unite_preserves_optional_config_fields(temp_dir):
    """Test description, min_correct, show_answers_on_completion preserved."""
    quizzes = {
        "quiz1.yaml": {
            "title": "Quiz 1",
            "description": "Test description",
            "min_correct": 2,
            "show_answers_on_completion": True,
            "questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": 0}],
        },
        "quiz2.yaml": {
            "title": "Quiz 2",
            "questions": [{"question": "Q2?", "options": ["C", "D"], "correct_answer": 1}],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)

        response = requests.post(
            f"http://localhost:{port}/api/admin/unite-quizzes",
            cookies=cookies,
            json={"quiz_filenames": ["quiz1.yaml", "quiz2.yaml"], "new_name": "with_options"},
        )

        assert response.status_code == 200

        # Read the created file and verify config
        quizzes_dir = os.path.join(temp_dir, f"quizzes_{port}")
        united_path = os.path.join(quizzes_dir, "with_options.yaml")
        with open(united_path, "r", encoding="utf-8") as f:
            united_quiz = yaml.safe_load(f)

        assert united_quiz["description"] == "Test description"
        assert united_quiz["min_correct"] == 2
        assert united_quiz["show_answers_on_completion"] is True


def test_unite_invalid_quiz_structure_error(temp_dir):
    """Test error when one quiz has invalid structure."""
    # Create a quiz with invalid structure manually
    quizzes = {
        "quiz1.yaml": {
            "title": "Valid Quiz",
            "questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": 0}],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        cookies = get_admin_session(port)

        # Create invalid quiz file directly
        quizzes_dir = os.path.join(temp_dir, f"quizzes_{port}")
        invalid_path = os.path.join(quizzes_dir, "invalid.yaml")
        with open(invalid_path, "w", encoding="utf-8") as f:
            yaml.dump({"title": "Invalid Quiz"}, f)  # Missing questions field

        response = requests.post(
            f"http://localhost:{port}/api/admin/unite-quizzes",
            cookies=cookies,
            json={"quiz_filenames": ["quiz1.yaml", "invalid.yaml"], "new_name": "should_fail"},
        )

        assert response.status_code == 400
        assert "неправильну структуру" in response.json()["error"]


# Selenium tests for multi-select UI functionality
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

from selenium_helpers import skip_if_selenium_disabled, browser, wait_for_element


def admin_login(browser, port, master_key="test123"):
    """Helper to log in to admin panel."""
    browser.get(f"http://localhost:{port}/admin/")
    password_input = wait_for_element(browser, By.ID, "master-key")
    password_input.send_keys(master_key)
    login_button = browser.find_element(By.CSS_SELECTOR, "button[onclick='authenticate()']")
    login_button.click()
    WebDriverWait(browser, 10).until(EC.visibility_of_element_located((By.ID, "admin-panel")))
    time.sleep(0.5)


@skip_if_selenium_disabled
def test_single_select_shows_standard_buttons(temp_dir, browser):
    """Test that selecting 1 quiz shows switch/edit/duplicate buttons."""
    quizzes = {
        "quiz1.yaml": {
            "title": "Quiz 1",
            "questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": 0}],
        },
        "quiz2.yaml": {
            "title": "Quiz 2",
            "questions": [{"question": "Q2?", "options": ["C", "D"], "correct_answer": 1}],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        admin_login(browser, port)

        # Wait for quiz select element
        quiz_select = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "quiz-select")))

        # Select one quiz
        options = quiz_select.find_elements(By.TAG_NAME, "option")
        options[0].click()
        time.sleep(0.3)

        # Verify single-quiz-actions is visible
        single_actions = browser.find_element(By.ID, "single-quiz-actions")
        assert single_actions.is_displayed()

        # Verify multi-quiz-actions is hidden
        multi_actions = browser.find_element(By.ID, "multi-quiz-actions")
        assert not multi_actions.is_displayed()

        # Verify buttons are enabled
        edit_btn = browser.find_element(By.ID, "edit-btn")
        assert not edit_btn.get_attribute("disabled")


@skip_if_selenium_disabled
def test_multi_select_shows_unite_button(temp_dir, browser):
    """Test that selecting 2+ quizzes shows unite button."""
    import platform

    quizzes = {
        "quiz1.yaml": {
            "title": "Quiz 1",
            "questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": 0}],
        },
        "quiz2.yaml": {
            "title": "Quiz 2",
            "questions": [{"question": "Q2?", "options": ["C", "D"], "correct_answer": 1}],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        admin_login(browser, port)

        # Wait for quiz select element
        quiz_select = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "quiz-select")))

        # Select multiple quizzes using modifier key (Command on macOS, Ctrl elsewhere)
        options = quiz_select.find_elements(By.TAG_NAME, "option")
        actions = ActionChains(browser)

        # Use Command key on macOS, Ctrl on other platforms
        modifier = Keys.COMMAND if platform.system() == "Darwin" else Keys.CONTROL
        actions.click(options[0]).key_down(modifier).click(options[1]).key_up(modifier).perform()
        time.sleep(0.5)

        # Verify single-quiz-actions is hidden
        single_actions = browser.find_element(By.ID, "single-quiz-actions")
        assert (
            not single_actions.is_displayed()
        ), "Single quiz actions should be hidden when multiple quizzes are selected"

        # Verify multi-quiz-actions is visible
        multi_actions = browser.find_element(By.ID, "multi-quiz-actions")
        assert multi_actions.is_displayed(), "Multi quiz actions should be visible when multiple quizzes are selected"

        # Verify unite button is present
        unite_btn = browser.find_element(By.ID, "unite-btn")
        assert unite_btn.is_displayed()


@skip_if_selenium_disabled
def test_current_quiz_marked_in_select(temp_dir, browser):
    """Test current quiz shows '(поточний)' suffix after switching."""
    quizzes = {
        "quiz1.yaml": {
            "title": "Quiz 1",
            "questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": 0}],
        },
        "quiz2.yaml": {
            "title": "Quiz 2",
            "questions": [{"question": "Q2?", "options": ["C", "D"], "correct_answer": 1}],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        # First switch to a quiz via API so there's a current quiz
        cookies = get_admin_session(port)
        requests.post(
            f"http://localhost:{port}/api/admin/switch-quiz",
            cookies=cookies,
            json={"quiz_filename": "quiz1.yaml"},
        )

        admin_login(browser, port)

        # Wait for quiz select element
        quiz_select = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "quiz-select")))

        # Find option with current quiz marker
        options = quiz_select.find_elements(By.TAG_NAME, "option")
        current_quiz_found = False
        for option in options:
            if "(поточний)" in option.text:
                current_quiz_found = True
                break

        assert current_quiz_found, "Current quiz should be marked with '(поточний)'"


@skip_if_selenium_disabled
def test_delete_button_disabled_for_current_quiz(temp_dir, browser):
    """Test delete button is disabled when current quiz is selected."""
    quizzes = {
        "quiz1.yaml": {
            "title": "Quiz 1",
            "questions": [{"question": "Q1?", "options": ["A", "B"], "correct_answer": 0}],
        },
    }

    with custom_webquiz_server(quizzes=quizzes) as (proc, port):
        # First switch to a quiz via API so there's a current quiz
        cookies = get_admin_session(port)
        requests.post(
            f"http://localhost:{port}/api/admin/switch-quiz",
            cookies=cookies,
            json={"quiz_filename": "quiz1.yaml"},
        )

        admin_login(browser, port)

        # Wait for quiz select element
        quiz_select = WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "quiz-select")))

        # Select the current quiz (only one quiz, which is current)
        options = quiz_select.find_elements(By.TAG_NAME, "option")
        options[0].click()
        time.sleep(0.3)

        # Verify delete button is disabled
        delete_btn = browser.find_element(By.ID, "delete-btn")
        assert delete_btn.get_attribute("disabled")
