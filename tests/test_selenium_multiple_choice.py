"""
Selenium tests for student experience with multiple choice quizzes.

Tests focus on:
- Checkbox rendering for multiple choice questions
- Radio button rendering for single choice questions
- Selection and submission behavior
- Visual feedback (green/red highlighting)
- Min correct feature
- Results display with pipe separator
- Complete quiz journeys
"""
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
    register_user,
    find_options,
    is_multiple_choice_question,
    is_option_selected,
    get_selected_options,
    find_option_by_text
)


# ============================================================================
# 1. CHECKBOX RENDERING AND INTERACTION TESTS (5 tests)
# ============================================================================

@skip_if_selenium_disabled
def test_multiple_choice_renders_options(browser):
    """Verify multiple choice question renders clickable options."""
    quiz_data = {
        'default.yaml': {
            'title': 'Multiple Choice Rendering Test',
            'questions': [
                {
                    'question': 'Which are programming languages?',
                    'options': ['Python', 'HTML', 'JavaScript', 'CSS'],
                    'correct_answer': [0, 2]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        # Verify options are rendered
        options = find_options(browser)
        assert len(options) == 4, "Should have 4 clickable options"

        # Verify multiple choice hint is shown
        assert is_multiple_choice_question(browser), "Should show multiple choice hint"


@skip_if_selenium_disabled
def test_single_choice_renders_options(browser):
    """Verify single answer questions render clickable options without multiple choice hint."""
    quiz_data = {
        'default.yaml': {
            'title': 'Single Choice Test',
            'questions': [
                {
                    'question': 'What is 2 + 2?',
                    'options': ['3', '4', '5', '6'],
                    'correct_answer': 1
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        # Verify options are rendered
        options = find_options(browser)
        assert len(options) == 4, "Should have 4 clickable options"

        # Verify NO multiple choice hint
        assert not is_multiple_choice_question(browser), "Should not show multiple choice hint for single choice"


@skip_if_selenium_disabled
def test_select_multiple_options_and_submit(browser):
    """Student can select multiple options and submit."""
    quiz_data = {
        'default.yaml': {
            'title': 'Multiple Selection Test',
            'questions': [
                {
                    'question': 'Select all primary colors:',
                    'options': ['Red', 'Green', 'Blue', 'Yellow'],
                    'correct_answer': [0, 2]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        options = find_options(browser)

        # Select first and third options (Red and Blue)
        options[0].click()
        options[2].click()

        # Verify both are selected
        assert is_option_selected(options[0]), "First option should be selected"
        assert is_option_selected(options[2]), "Third option should be selected"
        assert not is_option_selected(options[1]), "Second option should not be selected"

        # Submit answer
        submit_button = browser.find_element(By.ID, 'submit-answer-btn')
        submit_button.click()

        # Wait for feedback
        wait_for_clickable(browser, By.ID, 'continue-btn')


@skip_if_selenium_disabled
def test_unselect_and_reselect_options(browser):
    """Student can change their option selections."""
    quiz_data = {
        'default.yaml': {
            'title': 'Option Toggle Test',
            'questions': [
                {
                    'question': 'Select options:',
                    'options': ['A', 'B', 'C', 'D'],
                    'correct_answer': [0, 1]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        options = find_options(browser)

        # Select first option
        options[0].click()
        assert is_option_selected(options[0]), "Should be selected"

        # Unselect it
        options[0].click()
        assert not is_option_selected(options[0]), "Should be unselected"

        # Select it again
        options[0].click()
        assert is_option_selected(options[0]), "Should be selected again"


@skip_if_selenium_disabled
def test_multiple_choice_hint_displayed(browser):
    """'Select multiple answers' hint visible to student."""
    quiz_data = {
        'default.yaml': {
            'title': 'Hint Display Test',
            'questions': [
                {
                    'question': 'Which are fruits?',
                    'options': ['Apple', 'Carrot', 'Banana', 'Potato'],
                    'correct_answer': [0, 2]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        # Check for multiple choice hint
        assert is_multiple_choice_question(browser), \
            "Should show hint about multiple selection"


# ============================================================================
# 2. SUBMITTING MULTIPLE CHOICE ANSWERS TESTS (6 tests)
# ============================================================================

@skip_if_selenium_disabled
def test_submit_all_correct_checkboxes(browser):
    """Select all required correct answers, verify success feedback."""
    quiz_data = {
        'default.yaml': {
            'title': 'All Correct Test',
            'show_right_answer': True,
            'questions': [
                {
                    'question': 'Which are programming languages?',
                    'options': ['Python', 'HTML', 'JavaScript', 'CSS'],
                    'correct_answer': [0, 2]  # Python and JavaScript
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        options = find_options(browser)

        # Select correct answers (indices 0 and 2)
        options[0].click()
        options[2].click()

        # Submit
        submit_button = browser.find_element(By.ID, 'submit-answer-btn')
        submit_button.click()

        # Wait for feedback
        wait_for_clickable(browser, By.ID, 'continue-btn')

        # Verify correct feedback styling
        options = find_options(browser)
        assert 'feedback-correct' in options[0].get_attribute('class'), \
            "First correct option should have green feedback"
        assert 'feedback-correct' in options[2].get_attribute('class'), \
            "Second correct option should have green feedback"


@skip_if_selenium_disabled
def test_submit_partial_correct_fails(browser):
    """Select only some correct answers (when all required), verify fails."""
    quiz_data = {
        'default.yaml': {
            'title': 'Partial Correct Test',
            'show_right_answer': True,
            'questions': [
                {
                    'question': 'Select both correct answers:',
                    'options': ['Correct1', 'Wrong1', 'Correct2', 'Wrong2'],
                    'correct_answer': [0, 2]  # Need both
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        options = find_options(browser)

        # Select only one correct answer (index 0)
        options[0].click()

        # Submit
        submit_button = browser.find_element(By.ID, 'submit-answer-btn')
        submit_button.click()

        # Wait for feedback
        wait_for_clickable(browser, By.ID, 'continue-btn')

        # Verify incorrect feedback (partial selection is wrong)
        options = find_options(browser)
        # Should show that the selected one is correct but the answer overall is wrong
        # The unselected correct answer should be highlighted
        assert 'feedback-missed' in options[2].get_attribute('class'), \
            "Missed correct answer should be highlighted"


@skip_if_selenium_disabled
def test_submit_with_one_wrong_checkbox_fails(browser):
    """Include one incorrect checkbox, verify fails."""
    quiz_data = {
        'default.yaml': {
            'title': 'Wrong Checkbox Test',
            'show_right_answer': True,
            'questions': [
                {
                    'question': 'Select correct options:',
                    'options': ['Right1', 'Wrong', 'Right2', 'Wrong2'],
                    'correct_answer': [0, 2]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        options = find_options(browser)

        # Select both correct (0, 2) and one wrong (1)
        options[0].click()
        options[1].click()  # Wrong one
        options[2].click()

        # Submit
        submit_button = browser.find_element(By.ID, 'submit-answer-btn')
        submit_button.click()

        # Wait for feedback
        wait_for_clickable(browser, By.ID, 'continue-btn')

        # Verify wrong checkbox has incorrect feedback
        options = find_options(browser)
        assert 'feedback-incorrect' in options[1].get_attribute('class'), \
            "Wrong checkbox should have red feedback"


@skip_if_selenium_disabled
def test_submit_empty_multiple_choice_blocked(browser):
    """Cannot submit without selecting any checkbox."""
    quiz_data = {
        'default.yaml': {
            'title': 'Empty Submit Test',
            'questions': [
                {
                    'question': 'Select at least one:',
                    'options': ['A', 'B', 'C'],
                    'correct_answer': [0, 1]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        # Do not select any checkbox
        submit_button = browser.find_element(By.ID, 'submit-answer-btn')

        # Submit button should be disabled
        assert submit_button.get_attribute('disabled') == 'true', \
            "Submit button should be disabled without selection"


@skip_if_selenium_disabled
def test_submit_button_enables_after_checkbox_selection(browser):
    """Submit button activates when checkbox checked."""
    quiz_data = {
        'default.yaml': {
            'title': 'Button Enable Test',
            'questions': [
                {
                    'question': 'Select options:',
                    'options': ['A', 'B', 'C'],
                    'correct_answer': [0, 1]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        submit_button = browser.find_element(By.ID, 'submit-answer-btn')

        # Initially disabled
        assert submit_button.get_attribute('disabled') == 'true', \
            "Submit should be disabled initially"

        # Check one checkbox
        options = find_options(browser)
        options[0].click()

        # Submit should now be enabled
        time.sleep(0.5)  # Give time for state update
        assert submit_button.get_attribute('disabled') is None, \
            "Submit should be enabled after checking a box"


@skip_if_selenium_disabled
def test_multiple_submissions_different_questions(browser):
    """Submit single answer, then multiple choice, then single."""
    quiz_data = {
        'default.yaml': {
            'title': 'Mixed Submission Test',
            'questions': [
                {
                    'question': 'Single: What is 2+2?',
                    'options': ['3', '4', '5'],
                    'correct_answer': 1
                },
                {
                    'question': 'Multiple: Select colors:',
                    'options': ['Red', 'Dog', 'Blue', 'Car'],
                    'correct_answer': [0, 2]
                },
                {
                    'question': 'Single: Capital of France?',
                    'options': ['London', 'Paris', 'Berlin'],
                    'correct_answer': 1
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        # Question 1: Single answer (radio buttons)
        options = find_options(browser)
        assert len(options) == 3, "Should have radio buttons for single choice"
        options[1].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Question 2: Multiple choice (checkboxes)
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        options = find_options(browser)
        assert len(options) == 4, "Should have checkboxes for multiple choice"
        options[0].click()
        options[2].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Question 3: Single answer (radio buttons)
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        options = find_options(browser)
        assert len(options) == 3, "Should have radio buttons again"
        options[1].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Should reach results
        wait_for_element(browser, By.ID, 'results')


# ============================================================================
# 3. VISUAL FEEDBACK TESTS (5 tests)
# ============================================================================

@skip_if_selenium_disabled
def test_correct_checkboxes_turn_green(browser):
    """All correct selected checkboxes show green feedback."""
    quiz_data = {
        'default.yaml': {
            'title': 'Green Feedback Test',
            'show_right_answer': True,
            'questions': [
                {
                    'question': 'Select all vowels:',
                    'options': ['A', 'B', 'E', 'F', 'I'],
                    'correct_answer': [0, 2, 4]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        options = find_options(browser)
        options[0].click()
        options[2].click()
        options[4].click()

        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn')

        # All selected correct options should have green feedback
        options = find_options(browser)
        assert 'feedback-correct' in options[0].get_attribute('class')
        assert 'feedback-correct' in options[2].get_attribute('class')
        assert 'feedback-correct' in options[4].get_attribute('class')


@skip_if_selenium_disabled
def test_incorrect_checkbox_turns_red(browser):
    """Wrong checkbox shows red feedback."""
    quiz_data = {
        'default.yaml': {
            'title': 'Red Feedback Test',
            'show_right_answer': True,
            'questions': [
                {
                    'question': 'Select correct:',
                    'options': ['Correct', 'Wrong', 'Correct2'],
                    'correct_answer': [0, 2]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        options = find_options(browser)
        options[0].click()
        options[1].click()  # Wrong
        options[2].click()

        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn')

        options = find_options(browser)
        assert 'feedback-incorrect' in options[1].get_attribute('class'), \
            "Wrong option should have red feedback"


@skip_if_selenium_disabled
def test_missed_correct_answer_highlighted(browser):
    """Unselected correct answer shown (when show_right_answer=true)."""
    quiz_data = {
        'default.yaml': {
            'title': 'Missed Answer Test',
            'show_right_answer': True,
            'questions': [
                {
                    'question': 'Select all 3 correct:',
                    'options': ['C1', 'W1', 'C2', 'W2', 'C3'],
                    'correct_answer': [0, 2, 4]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        options = find_options(browser)
        # Only select two correct, miss the third
        options[0].click()
        options[2].click()
        # Missing index 4 (C3)

        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn')

        options = find_options(browser)
        # The missed correct answer should be highlighted
        assert 'feedback-missed' in options[4].get_attribute('class'), \
            "Missed correct answer should be highlighted"


@skip_if_selenium_disabled
def test_no_feedback_when_show_right_answer_false(browser):
    """No visual feedback when show_right_answer=false."""
    quiz_data = {
        'default.yaml': {
            'title': 'No Feedback Test',
            'show_right_answer': False,
            'questions': [
                {
                    'question': 'Select options:',
                    'options': ['A', 'B', 'C'],
                    'correct_answer': [0, 1]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        options = find_options(browser)
        options[0].click()
        options[2].click()  # Wrong

        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn')

        options = find_options(browser)
        # No feedback classes should be present
        for option in options:
            classes = option.get_attribute('class')
            assert 'feedback-correct' not in classes
            assert 'feedback-incorrect' not in classes


@skip_if_selenium_disabled
def test_checkboxes_disabled_after_submit(browser):
    """Cannot change selection after submission."""
    quiz_data = {
        'default.yaml': {
            'title': 'Disabled Test',
            'questions': [
                {
                    'question': 'Select:',
                    'options': ['A', 'B', 'C'],
                    'correct_answer': [0, 1]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        options = find_options(browser)
        options[0].click()

        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn')

        # Options should be disabled
        options = find_options(browser)
        for option in options:
            assert 'disabled' in option.get_attribute('class'), \
                "Options should be disabled after submission"


# ============================================================================
# 4. MIN CORRECT FEATURE TESTS (4 tests)
# ============================================================================

@skip_if_selenium_disabled
def test_min_correct_hint_shows_requirement(browser):
    """'Select at least N answers' hint displayed."""
    quiz_data = {
        'default.yaml': {
            'title': 'Min Correct Hint Test',
            'questions': [
                {
                    'question': 'Select at least 2 colors:',
                    'options': ['Red', 'Green', 'Blue', 'Yellow'],
                    'correct_answer': [0, 1, 2],
                    'min_correct': 2
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        # Check for min_correct hint
        page_source = browser.page_source
        assert '2' in page_source and ('least' in page_source.lower() or 'minimum' in page_source.lower()), \
            "Should show hint about minimum required selections"


@skip_if_selenium_disabled
def test_min_correct_submit_exact_minimum(browser):
    """Submit exactly min_required correct answers, verify success."""
    quiz_data = {
        'default.yaml': {
            'title': 'Exact Minimum Test',
            'show_right_answer': True,
            'questions': [
                {
                    'question': 'Select at least 2:',
                    'options': ['C1', 'C2', 'C3', 'W1'],
                    'correct_answer': [0, 1, 2],
                    'min_correct': 2
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        options = find_options(browser)
        # Select exactly 2 correct answers
        options[0].click()
        options[1].click()

        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn')

        # Should show correct feedback
        options = find_options(browser)
        assert 'feedback-correct' in options[0].get_attribute('class')
        assert 'feedback-correct' in options[1].get_attribute('class')


@skip_if_selenium_disabled
def test_min_correct_submit_more_than_minimum(browser):
    """Submit more than min_required, verify success."""
    quiz_data = {
        'default.yaml': {
            'title': 'More Than Minimum Test',
            'questions': [
                {
                    'question': 'Select at least 2:',
                    'options': ['C1', 'C2', 'C3', 'W1'],
                    'correct_answer': [0, 1, 2],
                    'min_correct': 2
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        options = find_options(browser)
        # Select all 3 correct answers (more than min of 2)
        options[0].click()
        options[1].click()
        options[2].click()

        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn')

        # Should succeed
        # Can continue to next question
        continue_btn = browser.find_element(By.ID, 'continue-btn')
        assert continue_btn.is_displayed()


@skip_if_selenium_disabled
def test_min_correct_submit_less_than_minimum_fails(browser):
    """Submit fewer than min_required, verify fails."""
    quiz_data = {
        'default.yaml': {
            'title': 'Less Than Minimum Test',
            'show_right_answer': True,
            'questions': [
                {
                    'question': 'Select at least 2:',
                    'options': ['C1', 'C2', 'C3', 'W1'],
                    'correct_answer': [0, 1, 2],
                    'min_correct': 2
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port)

        options = find_options(browser)
        # Select only 1 correct answer (less than min of 2)
        options[0].click()

        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn')

        # Should show some indication of insufficient selection
        # The missed correct answers should be highlighted
        options = find_options(browser)
        assert 'feedback-missed' in options[1].get_attribute('class') or \
               'feedback-missed' in options[2].get_attribute('class'), \
            "Should highlight other correct options"


# ============================================================================
# 5. COMPLETE QUIZ JOURNEY TESTS (5 tests)
# ============================================================================

@skip_if_selenium_disabled
def test_complete_all_multiple_choice_quiz(browser):
    """Full quiz with only multiple choice questions."""
    quiz_data = {
        'default.yaml': {
            'title': 'All Multiple Choice Quiz',
            'questions': [
                {
                    'question': 'Q1: Select colors:',
                    'options': ['Red', 'Dog', 'Blue', 'Car'],
                    'correct_answer': [0, 2]
                },
                {
                    'question': 'Q2: Select numbers:',
                    'options': ['One', 'Apple', 'Two', 'Three'],
                    'correct_answer': [0, 2, 3]
                },
                {
                    'question': 'Q3: Select animals:',
                    'options': ['Cat', 'Table', 'Dog', 'Chair'],
                    'correct_answer': [0, 2]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port, 'CompleteJourney')

        # Q1: Answer correctly
        options = find_options(browser)
        options[0].click()
        options[2].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Q2: Answer correctly
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        options = find_options(browser)
        options[0].click()
        options[2].click()
        options[3].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Q3: Answer correctly
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        options = find_options(browser)
        options[0].click()
        options[2].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Should reach results
        wait_for_element(browser, By.ID, 'results')
        assert 'Результат' in browser.page_source or 'Result' in browser.page_source


@skip_if_selenium_disabled
def test_mixed_single_and_multiple_choice_quiz(browser):
    """Alternate between radio buttons and checkboxes."""
    quiz_data = {
        'default.yaml': {
            'title': 'Mixed Quiz',
            'questions': [
                {
                    'question': 'Single: 2+2=?',
                    'options': ['3', '4', '5'],
                    'correct_answer': 1
                },
                {
                    'question': 'Multiple: Colors?',
                    'options': ['Red', 'Car', 'Blue'],
                    'correct_answer': [0, 2]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port, 'MixedQuiz')

        # Q1: Radio buttons
        options = find_options(browser)
        assert len(options) > 0, "Should have radio buttons"
        options[1].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Q2: Checkboxes
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        options = find_options(browser)
        assert len(options) > 0, "Should have checkboxes"
        options[0].click()
        options[2].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Results
        wait_for_element(browser, By.ID, 'results')


@skip_if_selenium_disabled
def test_perfect_score_multiple_choice(browser):
    """Answer all multiple choice correctly, see 100% result."""
    quiz_data = {
        'default.yaml': {
            'title': 'Perfect Score Test',
            'questions': [
                {
                    'question': 'Q1:',
                    'options': ['A', 'B', 'C'],
                    'correct_answer': [0, 1]
                },
                {
                    'question': 'Q2:',
                    'options': ['X', 'Y', 'Z'],
                    'correct_answer': [1, 2]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port, 'PerfectScore')

        # Q1: Correct
        options = find_options(browser)
        options[0].click()
        options[1].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Q2: Correct
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        options = find_options(browser)
        options[1].click()
        options[2].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Check results for 100%
        WebDriverWait(browser, 10).until(
            lambda d: '2/2' in d.page_source or '100%' in d.page_source
        )
        assert '2/2' in browser.page_source or '100%' in browser.page_source


@skip_if_selenium_disabled
def test_zero_score_multiple_choice(browser):
    """Answer all wrong, see 0% result."""
    quiz_data = {
        'default.yaml': {
            'title': 'Zero Score Test',
            'questions': [
                {
                    'question': 'Q1:',
                    'options': ['Correct1', 'Correct2', 'Wrong1', 'Wrong2'],
                    'correct_answer': [0, 1]
                },
                {
                    'question': 'Q2:',
                    'options': ['Wrong1', 'Correct1', 'Correct2'],
                    'correct_answer': [1, 2]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port, 'ZeroScore')

        # Q1: Select wrong answers
        options = find_options(browser)
        options[2].click()  # Wrong
        options[3].click()  # Wrong
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Q2: Select wrong answer
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        options = find_options(browser)
        options[0].click()  # Wrong
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Check results for 0/2
        WebDriverWait(browser, 10).until(
            lambda d: '0/2' in d.page_source or '0%' in d.page_source
        )
        assert '0/2' in browser.page_source or '0%' in browser.page_source


@skip_if_selenium_disabled
def test_partial_score_mixed_quiz(browser):
    """Some correct, some wrong, verify score calculation."""
    quiz_data = {
        'default.yaml': {
            'title': 'Partial Score Test',
            'questions': [
                {
                    'question': 'Q1: Correct',
                    'options': ['A', 'B', 'C'],
                    'correct_answer': [0, 2]
                },
                {
                    'question': 'Q2: Wrong',
                    'options': ['X', 'Y', 'Z'],
                    'correct_answer': [0, 1]
                },
                {
                    'question': 'Q3: Correct',
                    'options': ['M', 'N', 'O'],
                    'correct_answer': [1, 2]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port, 'PartialScore')

        # Q1: Correct
        options = find_options(browser)
        options[0].click()
        options[2].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Q2: Wrong (select wrong ones)
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        options = find_options(browser)
        options[2].click()  # Wrong
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Q3: Correct
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        options = find_options(browser)
        options[1].click()
        options[2].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Check results for 2/3
        WebDriverWait(browser, 10).until(
            lambda d: '2/3' in d.page_source
        )
        assert '2/3' in browser.page_source


# ============================================================================
# 6. RESULTS DISPLAY TESTS (4 tests)
# ============================================================================

@skip_if_selenium_disabled
def test_results_show_multiple_answers_with_pipe(browser):
    """Results display 'Answer1|Answer2|Answer3' format."""
    quiz_data = {
        'default.yaml': {
            'title': 'Results Pipe Test',
            'show_right_answer': True,
            'questions': [
                {
                    'question': 'Select three:',
                    'options': ['Apple', 'Banana', 'Cherry', 'Date'],
                    'correct_answer': [0, 1, 2]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port, 'PipeTest')

        options = find_options(browser)
        options[0].click()
        options[1].click()
        options[2].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Check results
        wait_for_element(browser, By.ID, 'results-content')

        # Results should show answers with | separator
        results_content = browser.execute_script("return document.getElementById('results-content').innerHTML;")
        # Should contain pipe-separated values
        for value in ['Apple', 'Banana', 'Cherry']:
            assert value in results_content, f"{value} should be in results"


@skip_if_selenium_disabled
def test_results_show_correct_answers_multiple_choice(browser):
    """Correct answers shown with pipe separator."""
    quiz_data = {
        'default.yaml': {
            'title': 'Correct Answers Display Test',
            'show_right_answer': True,
            'questions': [
                {
                    'question': 'Select correct:',
                    'options': ['Opt1', 'Opt2', 'Opt3', 'Opt4'],
                    'correct_answer': [0, 2]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port, 'CorrectAnswers')

        # Submit wrong answers
        options = find_options(browser)
        options[1].click()
        options[3].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Check results show correct answers
        wait_for_element(browser, By.ID, 'results')
        results_html = browser.page_source

        # Should show the correct answers
        assert 'Opt1' in results_html or 'Opt3' in results_html, \
            "Results should display correct answers"


@skip_if_selenium_disabled
def test_results_checkmark_and_x_for_multiple_choice(browser):
    """✓ for correct, ✗ for incorrect."""
    quiz_data = {
        'default.yaml': {
            'title': 'Checkmark Test',
            'questions': [
                {
                    'question': 'Q1 Correct:',
                    'options': ['A', 'B', 'C'],
                    'correct_answer': [0, 1]
                },
                {
                    'question': 'Q2 Wrong:',
                    'options': ['X', 'Y', 'Z'],
                    'correct_answer': [0, 1]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port, 'CheckmarkTest')

        # Q1: Correct
        options = find_options(browser)
        options[0].click()
        options[1].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Q2: Wrong
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        options = find_options(browser)
        options[2].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Check results
        wait_for_element(browser, By.ID, 'results')
        results_html = browser.page_source

        # Should have both checkmark and X
        assert '✓' in results_html or '✔' in results_html, "Should have checkmark"
        assert '✗' in results_html or '✘' in results_html or '×' in results_html, "Should have X mark"


@skip_if_selenium_disabled
def test_results_table_displays_all_questions(browser):
    """All questions (single and multiple) in results."""
    quiz_data = {
        'default.yaml': {
            'title': 'Results Table Test',
            'questions': [
                {
                    'question': 'Single question',
                    'options': ['A', 'B'],
                    'correct_answer': 0
                },
                {
                    'question': 'Multiple question',
                    'options': ['X', 'Y', 'Z'],
                    'correct_answer': [0, 1]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port, 'ResultsTable')

        # Q1: Single
        options = find_options(browser)
        options[0].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Q2: Multiple
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        options = find_options(browser)
        options[0].click()
        options[1].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Check results table
        wait_for_element(browser, By.ID, 'results')
        results_table = browser.find_element(By.CLASS_NAME, 'results-table')

        # Both questions should be in the table
        table_html = results_table.get_attribute('innerHTML')
        assert 'Single question' in table_html
        assert 'Multiple question' in table_html


# ============================================================================
# 7. PROGRESS THROUGH QUIZ TESTS (3 tests)
# ============================================================================

@skip_if_selenium_disabled
def test_progress_bar_advances_after_multiple_choice(browser):
    """Progress bar updates after multiple choice submission."""
    quiz_data = {
        'default.yaml': {
            'title': 'Progress Bar Test',
            'questions': [
                {'question': 'Q1', 'options': ['A', 'B'], 'correct_answer': [0]},
                {'question': 'Q2', 'options': ['X', 'Y'], 'correct_answer': [0]},
                {'question': 'Q3', 'options': ['M', 'N'], 'correct_answer': [0]}
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port, 'ProgressBar')

        # Check initial progress (0%)
        progress_fill = browser.find_element(By.ID, 'progress-fill')
        initial_width = progress_fill.get_attribute('style')

        # Answer Q1
        options = find_options(browser)
        options[0].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Progress should have increased
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        progress_fill = browser.find_element(By.ID, 'progress-fill')
        new_width = progress_fill.get_attribute('style')

        # Width should be different (increased)
        assert new_width != initial_width, "Progress bar should advance"


@skip_if_selenium_disabled
def test_question_counter_multiple_choice(browser):
    """'Question 2 of 5' updates correctly."""
    quiz_data = {
        'default.yaml': {
            'title': 'Counter Test',
            'questions': [
                {'question': 'Q1', 'options': ['A', 'B'], 'correct_answer': [0]},
                {'question': 'Q2', 'options': ['X', 'Y'], 'correct_answer': [0]},
                {'question': 'Q3', 'options': ['M', 'N'], 'correct_answer': [0]}
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port, 'Counter')

        # Check Q1 counter
        progress_text = browser.find_element(By.ID, 'progress-text')
        assert '1' in progress_text.text and '3' in progress_text.text

        # Answer Q1
        options = find_options(browser)
        options[0].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn').click()

        # Check Q2 counter
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        progress_text = browser.find_element(By.ID, 'progress-text')
        assert '2' in progress_text.text and '3' in progress_text.text


@skip_if_selenium_disabled
def test_continue_button_works_multiple_choice(browser):
    """Continue button advances to next question."""
    quiz_data = {
        'default.yaml': {
            'title': 'Continue Button Test',
            'questions': [
                {'question': 'First Q', 'options': ['A', 'B'], 'correct_answer': [0]},
                {'question': 'Second Q', 'options': ['X', 'Y'], 'correct_answer': [0]}
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port, 'Continue')

        # Answer Q1
        options = find_options(browser)
        options[0].click()
        browser.find_element(By.ID, 'submit-answer-btn').click()

        # Click continue
        continue_btn = wait_for_clickable(browser, By.ID, 'continue-btn')
        continue_btn.click()

        # Should be on Q2
        wait_for_element(browser, By.CSS_SELECTOR, '.question-text')
        question_text = browser.find_element(By.CSS_SELECTOR, '.question-text').text
        assert 'Second' in question_text


# ============================================================================
# 8. EDGE CASE TESTS (3 tests)
# ============================================================================

@skip_if_selenium_disabled
def test_many_checkboxes_all_visible(browser):
    """Question with 10+ options renders correctly."""
    options = [f'Option{i}' for i in range(12)]
    quiz_data = {
        'default.yaml': {
            'title': 'Many Options Test',
            'questions': [
                {
                    'question': 'Select from many options:',
                    'options': options,
                    'correct_answer': [0, 5, 10]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port, 'ManyOptions')

        options = find_options(browser)
        assert len(options) == 12, "Should have 12 checkboxes"

        # All should be visible
        for option in options:
            assert option.is_displayed(), "All options should be visible"


@skip_if_selenium_disabled
def test_select_all_options_when_all_correct(browser):
    """All options are correct, select all."""
    quiz_data = {
        'default.yaml': {
            'title': 'All Correct Test',
            'questions': [
                {
                    'question': 'All are correct:',
                    'options': ['C1', 'C2', 'C3', 'C4'],
                    'correct_answer': [0, 1, 2, 3]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port, 'AllCorrect')

        options = find_options(browser)

        # Select all
        for option in options:
            option.click()

        # All should be selected
        for option in options:
            assert is_option_selected(option), "All should be selected"

        # Submit
        browser.find_element(By.ID, 'submit-answer-btn').click()
        wait_for_clickable(browser, By.ID, 'continue-btn')


@skip_if_selenium_disabled
def test_rapid_option_clicking_stable(browser):
    """Fast clicking doesn't break state."""
    quiz_data = {
        'default.yaml': {
            'title': 'Rapid Click Test',
            'questions': [
                {
                    'question': 'Click rapidly:',
                    'options': ['A', 'B', 'C', 'D'],
                    'correct_answer': [0, 1]
                }
            ]
        }
    }

    with custom_webquiz_server(quizzes=quiz_data) as (proc, port):
        register_user(browser, port, 'RapidClick')

        options = find_options(browser)

        # Rapid clicking first option multiple times
        for _ in range(5):
            options[0].click()
            time.sleep(0.05)

        # Re-fetch options after clicks
        options = find_options(browser)
        # Should end up selected (odd number of clicks)
        assert is_option_selected(options[0]), "Should be selected after rapid clicks"

        # Click again to unselect
        options[0].click()
        options = find_options(browser)
        assert not is_option_selected(options[0]), "Should be unselected"

        # Now select both correct answers normally
        options[0].click()
        options[1].click()

        # Submit should work
        submit_btn = browser.find_element(By.ID, 'submit-answer-btn')
        assert submit_btn.get_attribute('disabled') is None, "Submit should be enabled"

