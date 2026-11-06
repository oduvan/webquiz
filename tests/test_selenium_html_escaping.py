"""
Selenium tests: text from quizzes and from students is shown as plain text.

Quiz authors write things like `<vtx_band>` in question text. Students can type
anything into their name. The pages must show this text as it is written. They
must not treat it as HTML, because then the browser hides it (an unknown tag)
or runs it (a script tag or an event handler).
"""

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from conftest import custom_webquiz_server
from selenium_helpers import (
    skip_if_selenium_disabled,
    browser,
    wait_for_element,
    find_register_button,
    find_option_by_index,
)
from test_selenium_quiz_editor import admin_login


TAG_QUESTION = "What does 0 mean for `<vtx_band>` and `<vtx_channel>`?"
TAG_OPTION_A = "Use <default> band"
TAG_OPTION_B = "Turn <b>off</b> the VTX"
# A name that would run code if the page used it as HTML
SCRIPT_USERNAME = "<img src=x onerror=\"window.injected=1\">Bob"

TAG_QUIZ = {
    "default.yaml": {
        "title": "Tags <in> title",
        "questions": [
            {"question": TAG_QUESTION, "options": [TAG_OPTION_A, TAG_OPTION_B], "correct_answer": 0},
        ],
    }
}


def element_html_has_no_tag(browser, element, tag_name):
    """True when the element has no child element with this tag name."""
    return browser.execute_script("return arguments[0].getElementsByTagName(arguments[1]).length === 0;", element, tag_name)


@skip_if_selenium_disabled
def test_live_stats_shows_tags_in_question_text(browser):
    """The live stats header shows `<vtx_band>` instead of hiding it."""
    with custom_webquiz_server(quizzes=TAG_QUIZ) as (proc, port):
        base_url = f"http://localhost:{port}"
        requests.post(f"{base_url}/api/register", json={"username": "student1"})

        browser.get(f"{base_url}/live-stats/")
        header = WebDriverWait(browser, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "th .question-text"))
        )

        assert TAG_QUESTION in header.text, f"Question text lost its tags: {header.text!r}"
        th = header.find_element(By.XPATH, "./ancestor::th")
        assert TAG_QUESTION in th.get_attribute("title"), "Tooltip should keep the tags too"


@skip_if_selenium_disabled
def test_live_stats_shows_username_as_text(browser):
    """A student name with HTML in it is shown as text and never runs."""
    with custom_webquiz_server(quizzes=TAG_QUIZ) as (proc, port):
        base_url = f"http://localhost:{port}"
        response = requests.post(f"{base_url}/api/register", json={"username": SCRIPT_USERNAME})
        assert response.status_code == 200

        browser.get(f"{base_url}/live-stats/")
        name_cell = WebDriverWait(browser, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".username-text"))
        )

        assert name_cell.text == SCRIPT_USERNAME
        assert element_html_has_no_tag(browser, name_cell, "img"), "The name was turned into an <img> element"
        assert browser.execute_script("return window.injected === undefined;"), "Code from the name ran"


@skip_if_selenium_disabled
def test_quiz_page_shows_tags_in_question_options_and_results(browser):
    """The student sees the tags in the question, the options and the results table."""
    with custom_webquiz_server(quizzes=TAG_QUIZ) as (proc, port):
        browser.get(f"http://localhost:{port}/")

        assert "Tags <in> title" in browser.title
        assert browser.find_element(By.TAG_NAME, "h1").text == "Tags <in> title"

        wait_for_element(browser, By.ID, "username").send_keys("student1")
        find_register_button(browser).click()

        question = wait_for_element(browser, By.CSS_SELECTOR, ".question-text")
        assert question.text == TAG_QUESTION

        option_a = find_option_by_index(browser, 0)
        option_b = find_option_by_index(browser, 1)
        assert option_a.text == TAG_OPTION_A
        assert option_b.text == TAG_OPTION_B
        assert element_html_has_no_tag(browser, option_b, "b"), "Option text was turned into a <b> element"

        # Pick the wrong option so the results also show the right one
        option_b.click()
        browser.find_element(By.ID, "submit-answer-btn").click()
        continue_btn = WebDriverWait(browser, 10).until(EC.element_to_be_clickable((By.ID, "continue-btn")))
        continue_btn.click()

        results = WebDriverWait(browser, 10).until(EC.visibility_of_element_located((By.ID, "results-content")))
        WebDriverWait(browser, 10).until(lambda d: TAG_QUESTION in results.text)
        assert TAG_OPTION_B in results.text, f"Selected answer lost its tags: {results.text!r}"
        assert TAG_OPTION_A in results.text, f"Correct answer lost its tags: {results.text!r}"


@skip_if_selenium_disabled
def test_quiz_page_text_question_keeps_tags(browser):
    """A text question shows tags in the starting value and in the correct answer."""
    quiz = {
        "default.yaml": {
            "title": "Text quiz",
            "questions": [
                {
                    "question": "Type the command",
                    "default_value": "vtx <band> </textarea><b>x</b>",
                    "correct_value": "vtx <band> <channel>",
                    "checker": "",
                }
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz) as (proc, port):
        browser.get(f"http://localhost:{port}/")
        wait_for_element(browser, By.ID, "username").send_keys("student1")
        find_register_button(browser).click()

        textarea = wait_for_element(browser, By.ID, "text-answer-input")
        assert textarea.get_attribute("value") == "vtx <band> </textarea><b>x</b>"

        browser.find_element(By.ID, "submit-answer-btn").click()
        feedback = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#checker-feedback .correct-value-display"))
        )
        assert "vtx <band> <channel>" in feedback.text, f"Correct value lost its tags: {feedback.text!r}"


@skip_if_selenium_disabled
def test_waiting_form_keeps_quotes_and_tags_in_name(browser):
    """The waiting-for-approval form shows the full name, quotes and tags included."""
    config = {"registration": {"approve": True}}
    username = 'O"Brien <x>'

    with custom_webquiz_server(config=config, quizzes=TAG_QUIZ) as (proc, port):
        browser.get(f"http://localhost:{port}/")
        wait_for_element(browser, By.ID, "username").send_keys(username)
        find_register_button(browser).click()

        waiting_input = wait_for_element(browser, By.ID, "waiting-username")
        assert waiting_input.get_attribute("value") == username


@skip_if_selenium_disabled
def test_admin_pending_users_show_name_and_fields_as_text(browser):
    """The admin approval list shows a student's name and fields as text."""
    config = {"registration": {"approve": True, "fields": ["Group"]}}
    group_value = "<i>10-A</i>"

    with custom_webquiz_server(config=config, quizzes=TAG_QUIZ) as (proc, port):
        base_url = f"http://localhost:{port}"
        response = requests.post(
            f"{base_url}/api/register", json={"username": SCRIPT_USERNAME, "group": group_value}
        )
        assert response.status_code == 200

        admin_login(browser, port)
        name = WebDriverWait(browser, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".pending-user-name"))
        )
        item = name.find_element(By.XPATH, "./ancestor::div[contains(@class, 'pending-user-item')]")

        assert SCRIPT_USERNAME in name.text
        assert f"Group: {group_value}" in item.text
        assert element_html_has_no_tag(browser, item, "img"), "The name was turned into an <img> element"
        assert element_html_has_no_tag(browser, item, "i"), "The field value was turned into an <i> element"
        assert browser.execute_script("return window.injected === undefined;"), "Code from the name ran"
