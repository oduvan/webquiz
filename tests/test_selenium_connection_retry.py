"""
Selenium tests for request retry on the quiz page.

A fetch wrapper in the page simulates the connection: with ``__networkDown`` set every
request fails, and ``__dropResponses`` lets the server handle a request but loses the
response, the case where a retry must not record anything twice.
"""

import json
import time

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from conftest import custom_webquiz_server
from selenium_helpers import (
    skip_if_selenium_disabled,
    browser,
    register_user,
    find_options,
    find_register_button,
    wait_for_clickable,
    wait_for_element,
    wait_for_question_containing_text,
)


TWO_QUESTIONS = {
    "default.yaml": {
        "title": "Retry Quiz",
        "questions": [
            {"question": "First question", "options": ["A", "B"], "correct_answer": 0},
            {"question": "Second question", "options": ["C", "D"], "correct_answer": 1},
        ],
    }
}

FETCH_PATCH = """
window.__realFetch = window.__realFetch || window.fetch;
window.__networkDown = %s;
window.__dropResponses = {};
window.fetch = async function(url, options) {
    if (window.__networkDown) {
        throw new TypeError('Failed to fetch');
    }
    for (const part in window.__dropResponses) {
        if (String(url).includes(part) && window.__dropResponses[part] > 0) {
            window.__dropResponses[part]--;
            await window.__realFetch(url, options);
            throw new TypeError('Failed to fetch');
        }
    }
    return window.__realFetch(url, options);
};
"""


def install_fetch_patch(browser, network_down=False):
    browser.execute_script(FETCH_PATCH % json.dumps(network_down))


def install_fetch_patch_on_load(browser, network_down=False):
    """Install the wrapper before page scripts run, for requests sent on page load."""
    browser.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": FETCH_PATCH % json.dumps(network_down)})


def banner_visible(browser):
    banner = browser.find_element(By.ID, "connection-banner")
    return "hidden" not in banner.get_attribute("class")


def final_results(port, browser):
    user_id = browser.get_cookie("user_id")["value"]
    data = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}").json()
    return data.get("final_results")


@skip_if_selenium_disabled
def test_lost_answer_response_is_retried_without_duplicate(browser):
    """The server records the answer but the response is lost: the page retries and the answer counts once."""
    with custom_webquiz_server(quizzes=TWO_QUESTIONS) as (proc, port):
        register_user(browser, port)
        install_fetch_patch(browser)
        browser.execute_script("window.__dropResponses['api/submit-answer'] = 1;")

        find_options(browser)[0].click()
        wait_for_clickable(browser, By.ID, "submit-answer-btn").click()

        # The retry gets the stored result and the page shows feedback as usual
        wait_for_clickable(browser, By.ID, "continue-btn", timeout=10).click()
        wait_for_question_containing_text(browser, "Second question")

        find_options(browser)[1].click()
        wait_for_clickable(browser, By.ID, "submit-answer-btn").click()
        wait_for_clickable(browser, By.ID, "continue-btn").click()
        wait_for_element(browser, By.ID, "results-content")
        WebDriverWait(browser, 10).until(lambda b: not banner_visible(b))

        results = final_results(port, browser)
        assert results is not None, "Quiz should be completed"
        assert results["total_count"] == 2
        assert results["correct_count"] == 2


@skip_if_selenium_disabled
def test_offline_submit_shows_banner_and_keeps_answer(browser):
    """While offline the page shows the banner, keeps the chosen answer and sends it once back online."""
    with custom_webquiz_server(quizzes=TWO_QUESTIONS) as (proc, port):
        register_user(browser, port)
        install_fetch_patch(browser)

        options = find_options(browser)
        options[0].click()
        browser.execute_script("window.__networkDown = true;")
        wait_for_clickable(browser, By.ID, "submit-answer-btn").click()

        WebDriverWait(browser, 5).until(banner_visible)
        assert browser.find_element(By.ID, "submit-answer-btn").get_attribute("disabled") is not None

        # The answer is locked while the page retries
        options[1].click()
        assert "selected" in options[0].get_attribute("class")
        assert "selected" not in options[1].get_attribute("class")

        time.sleep(1.5)
        browser.execute_script("window.__networkDown = false;")
        wait_for_clickable(browser, By.ID, "continue-btn", timeout=10)
        assert not banner_visible(browser)
        assert "feedback-correct" in options[0].get_attribute("class")

        results = requests.get(
            f"http://localhost:{port}/api/verify-user/{browser.get_cookie('user_id')['value']}"
        ).json()
        assert results["next_question_index"] == 1


@skip_if_selenium_disabled
def test_reload_while_offline_waits_for_server(browser):
    """A page loaded while offline keeps waiting instead of showing the registration form."""
    with custom_webquiz_server(quizzes=TWO_QUESTIONS) as (proc, port):
        register_user(browser, port)
        install_fetch_patch_on_load(browser, network_down=True)
        browser.refresh()

        WebDriverWait(browser, 5).until(banner_visible)
        time.sleep(1.5)
        assert "hidden" not in browser.find_element(By.ID, "loading").get_attribute("class")
        assert "hidden" in browser.find_element(By.ID, "registration").get_attribute("class")

        browser.execute_script("window.__networkDown = false;")
        wait_for_question_containing_text(browser, "First question", timeout=10)
        WebDriverWait(browser, 10).until(lambda b: not banner_visible(b))
        assert "hidden" in browser.find_element(By.ID, "registration").get_attribute("class")


@skip_if_selenium_disabled
def test_lost_registration_response_starts_quiz(browser):
    """The server registers the user but the response is lost: the retry returns the same user."""
    with custom_webquiz_server(quizzes=TWO_QUESTIONS) as (proc, port):
        browser.get(f"http://localhost:{port}/")
        wait_for_element(browser, By.ID, "username").send_keys("Anna")
        install_fetch_patch(browser)
        browser.execute_script("window.__dropResponses['api/register'] = 1;")

        find_register_button(browser).click()

        wait_for_question_containing_text(browser, "First question", timeout=10)
        error = browser.find_element(By.ID, "registration-error")
        assert "hidden" in error.get_attribute("class"), f"No registration error expected, got: {error.text}"
        assert browser.find_element(By.ID, "username-display").text == "Anna"
