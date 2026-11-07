"""Selenium tests for explanations in the admin quiz editor and the start pop-up."""

import base64
import os
import time

import requests
import yaml
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from conftest import custom_webquiz_server, get_admin_session, register_student
from selenium_helpers import browser, skip_if_selenium_disabled
from test_selenium_admin_decimal_points import expand_question, save_quiz
from test_selenium_admin_start_settings import open_start_popup
from test_selenium_quiz_editor import admin_login, select_and_edit_quiz

# A 1x1 PNG image
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def quiz(explanation=None, **settings):
    first = {"question": "Q1", "options": ["A", "B"], "correct_answer": 0}
    if explanation is not None:
        first["explanation"] = explanation
    data = {
        "title": "Editor Explanations",
        "questions": [first, {"question": "Q2", "options": ["A", "B"], "correct_answer": 1}],
        **settings,
    }
    return {"default.yaml": data}


def saved_quiz(port):
    cookies = get_admin_session(port)
    response = requests.get(f"http://localhost:{port}/api/admin/quiz/default.yaml", cookies=cookies)
    return yaml.safe_load(response.json()["content"])


def explanation_field(item):
    return item.find_element(By.CSS_SELECTOR, "textarea.question-explanation")


def preview_box(item):
    return item.find_element(By.CSS_SELECTOR, ".explanation-preview")


def js_click(browser, element):
    browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    # Click via JS: the editor's sticky action bar can sit over the button
    browser.execute_script("arguments[0].click();", element)


def unfold_explanation(browser, item):
    js_click(browser, item.find_element(By.CSS_SELECTOR, ".explanation-toggle-btn"))
    WebDriverWait(browser, 3).until(lambda d: explanation_field(item).is_displayed())


def toggle_preview(browser, item):
    js_click(browser, item.find_element(By.CSS_SELECTOR, ".explanation-preview-btn"))


def open_first_question(browser, port):
    admin_login(browser, port)
    select_and_edit_quiz(browser)
    return expand_question(browser, 0)


@skip_if_selenium_disabled
def test_empty_explanation_is_folded(temp_dir, browser):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        item = open_first_question(browser, port)
        toggle = item.find_element(By.CSS_SELECTOR, ".explanation-toggle-btn")
        assert toggle.is_displayed()
        assert "Додати пояснення" in toggle.text
        assert not explanation_field(item).is_displayed()
        unfold_explanation(browser, item)
        assert item.find_element(By.CSS_SELECTOR, ".explanation-preview-btn").is_displayed()


@skip_if_selenium_disabled
def test_existing_explanation_is_unfolded(temp_dir, browser):
    with custom_webquiz_server(quizzes=quiz("Loaded *text*", show_explanation=True)) as (proc, port):
        item = open_first_question(browser, port)
        assert explanation_field(item).is_displayed()
        assert explanation_field(item).get_attribute("value") == "Loaded *text*"
        assert not preview_box(item).is_displayed()
        assert browser.find_element(By.ID, "show-explanation-group").is_displayed()
        assert browser.find_element(By.ID, "show-explanation").is_selected()
        second = expand_question(browser, 1)
        assert not explanation_field(second).is_displayed()


@skip_if_selenium_disabled
def test_preview_button_replaces_the_field(temp_dir, browser):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        item = open_first_question(browser, port)
        unfold_explanation(browser, item)
        explanation_field(item).send_keys("**Bold** text")
        time.sleep(0.6)
        assert not preview_box(item).is_displayed()  # no preview until the button is pressed

        toggle_preview(browser, item)
        WebDriverWait(browser, 3).until(lambda d: preview_box(item).find_elements(By.TAG_NAME, "strong"))
        assert preview_box(item).find_element(By.TAG_NAME, "strong").text == "Bold"
        assert preview_box(item).is_displayed()
        assert not explanation_field(item).is_displayed()
        assert not item.find_element(By.CSS_SELECTOR, ".explanation-image-btn").is_displayed()

        toggle_preview(browser, item)
        WebDriverWait(browser, 3).until(lambda d: explanation_field(item).is_displayed())
        assert not preview_box(item).is_displayed()
        assert explanation_field(item).get_attribute("value") == "**Bold** text"


@skip_if_selenium_disabled
def test_editor_show_explanation_appears_with_text(temp_dir, browser):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        item = open_first_question(browser, port)
        group = browser.find_element(By.ID, "show-explanation-group")
        assert not group.is_displayed()
        unfold_explanation(browser, item)
        explanation_field(item).send_keys("Because")
        WebDriverWait(browser, 3).until(lambda d: group.is_displayed())
        explanation_field(item).clear()
        explanation_field(item).send_keys(" ")
        WebDriverWait(browser, 3).until(lambda d: not group.is_displayed())


@skip_if_selenium_disabled
def test_editor_saves_explanation_and_option(temp_dir, browser):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        item = open_first_question(browser, port)
        unfold_explanation(browser, item)
        explanation_field(item).send_keys("Because **A**")
        checkbox = WebDriverWait(browser, 3).until(EC.visibility_of_element_located((By.ID, "show-explanation")))
        if not checkbox.is_selected():
            checkbox.click()
        save_quiz(browser)
        saved = saved_quiz(port)
        assert saved["questions"][0]["explanation"] == "Because **A**"
        assert "explanation" not in saved["questions"][1]
        assert saved["show_explanation"] is True


@skip_if_selenium_disabled
def test_editor_inserts_image_markdown(temp_dir, browser):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        with open(os.path.join(temp_dir, f"quizzes_{port}", "imgs", "pic.png"), "wb") as f:
            f.write(PNG)
        item = open_first_question(browser, port)
        unfold_explanation(browser, item)
        js_click(browser, item.find_element(By.CSS_SELECTOR, ".explanation-image-btn"))
        image = WebDriverWait(browser, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#image-grid .image-item"))
        )
        image.click()
        WebDriverWait(browser, 3).until(
            lambda d: "![](/imgs/pic.png)" in explanation_field(item).get_attribute("value")
        )
        toggle_preview(browser, item)
        preview_image = WebDriverWait(browser, 3).until(lambda d: preview_box(item).find_element(By.TAG_NAME, "img"))
        WebDriverWait(browser, 5).until(
            lambda d: d.execute_script("return arguments[0].naturalWidth", preview_image) > 0
        )


@skip_if_selenium_disabled
def test_start_popup_explanation_checkbox(temp_dir, browser):
    with custom_webquiz_server(quizzes=quiz("Why", show_explanation=True)) as (proc, port):
        open_start_popup(browser, port)
        checkbox = WebDriverWait(browser, 5).until(EC.visibility_of_element_located((By.ID, "start-show-explanation")))
        WebDriverWait(browser, 5).until(lambda d: checkbox.is_selected())
        assert checkbox.is_enabled()
        browser.find_element(By.ID, "start-show-right-answer").click()  # untick "show correct answers"
        assert not checkbox.is_enabled()
        assert browser.find_element(By.ID, "start-show-explanation-note").is_displayed()


@skip_if_selenium_disabled
def test_start_popup_hides_explanation_checkbox_without_explanations(temp_dir, browser):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        open_start_popup(browser, port)
        WebDriverWait(browser, 5).until(lambda d: d.find_element(By.ID, "start-time-limit-mode").is_displayed())
        assert not browser.find_element(By.ID, "start-show-explanation-group").is_displayed()


@skip_if_selenium_disabled
def test_start_popup_sends_show_explanation(temp_dir, browser):
    with custom_webquiz_server(quizzes=quiz("Why", show_explanation=True, show_right_answer=True)) as (proc, port):
        open_start_popup(browser, port)
        checkbox = WebDriverWait(browser, 5).until(EC.visibility_of_element_located((By.ID, "start-show-explanation")))
        WebDriverWait(browser, 5).until(lambda d: checkbox.is_selected())
        checkbox.click()
        browser.find_element(By.ID, "start-quiz-confirm").click()
        WebDriverWait(browser, 10).until(EC.invisibility_of_element_located((By.ID, "start-quiz-modal")))
        user_id = register_student(port)
        reply = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": 1, "selected_answer": 0},
        ).json()
        assert "explanation_html" not in reply


@skip_if_selenium_disabled
def test_editor_uses_angle_brackets_for_unusual_image_names(temp_dir, browser):
    with custom_webquiz_server(quizzes=quiz()) as (proc, port):
        item = open_first_question(browser, port)
        field = explanation_field(item)
        for path in ("/imgs/pic(1).png", "/imgs/my pic.png", "/imgs/plain.png"):
            browser.execute_script("insertExplanationImage(arguments[0], arguments[1])", field, path)
        assert field.get_attribute("value") == "![](</imgs/pic(1).png>)![](</imgs/my pic.png>)![](/imgs/plain.png)"
