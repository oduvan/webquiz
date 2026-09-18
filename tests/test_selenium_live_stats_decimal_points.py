"""
Selenium tests for decimal question points on the live stats page.

Verifies the per-user score and the question header show clean decimals
instead of binary floating point noise.
"""

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from conftest import custom_webquiz_server
from selenium_helpers import skip_if_selenium_disabled, browser


@skip_if_selenium_disabled
def test_live_stats_shows_clean_decimal_score(browser):
    """A 0.1 + 0.2 score reads 0.3 on the live stats page."""
    quiz = {
        "default.yaml": {
            "title": "Live Decimal Quiz",
            "questions": [
                {"question": "Q1", "options": ["A", "B"], "correct_answer": 0, "points": 0.1},
                {"question": "Q2", "options": ["A", "B"], "correct_answer": 0, "points": 0.2},
                {"question": "Q3", "options": ["A", "B"], "correct_answer": 0, "points": 0.7},
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz) as (proc, port):
        base_url = f"http://localhost:{port}"

        user_id = requests.post(f"{base_url}/api/register", json={"username": "livedecimal"}).json()["user_id"]
        # Two correct (0.1 + 0.2), one wrong
        for question_id, answer in [(1, 0), (2, 0), (3, 1)]:
            requests.post(
                f"{base_url}/api/submit-answer",
                json={"user_id": user_id, "question_id": question_id, "selected_answer": answer},
            )

        browser.get(f"{base_url}/live-stats/")
        WebDriverWait(browser, 15).until(lambda d: "livedecimal" in d.page_source)

        body = browser.find_element(By.TAG_NAME, "body").text

        assert "0.30000000000000004" not in body, f"Float noise on the live stats page: {body}"
        assert "0.3/1" in body, f"Expected a 0.3/1 score on the live stats page, got: {body}"


@skip_if_selenium_disabled
def test_live_stats_shows_decimal_question_points(browser):
    """A question worth 0.5 shows a trophy indicator with 0.5 in the header."""
    quiz = {
        "default.yaml": {
            "title": "Live Indicator Quiz",
            "questions": [
                {"question": "Half point question", "options": ["A", "B"], "correct_answer": 0, "points": 0.5}
            ],
        }
    }

    with custom_webquiz_server(quizzes=quiz) as (proc, port):
        base_url = f"http://localhost:{port}"
        requests.post(f"{base_url}/api/register", json={"username": "indicatoruser"})

        browser.get(f"{base_url}/live-stats/")
        WebDriverWait(browser, 15).until(lambda d: d.find_elements(By.CSS_SELECTOR, ".points-indicator"))

        indicator = browser.find_element(By.CSS_SELECTOR, ".points-indicator")
        assert "0.5" in indicator.get_attribute("innerHTML"), f"Expected 0.5 in the indicator: {indicator.text}"
