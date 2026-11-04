"""
Selenium tests for the CSV table viewer.

The viewer shows one CSV file as a table and lets the admin filter rows by
question and by user. It opens inside the file manager pop-up and can also be
opened in a new window, where the filters are kept in the page address.
"""

import csv
import os
from urllib.parse import quote

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait

from conftest import custom_webquiz_server
from selenium_helpers import skip_if_selenium_disabled, browser


# Requests from the browser come from 127.0.0.1, so a trusted IP skips the login
TRUSTED = {"admin": {"master_key": "test123", "trusted_ips": ["127.0.0.1"]}}

MULTILINE_QUESTION = "Name the capital,\nof France"

ANSWERS_WITH_USERS = [
    ["user_id", "username", "group", "question", "selected_answer", "correct_answer", "is_correct", "time_taken_seconds"],
    ["100001", "Alice", "A1", "What is 2 + 2?", "4", "4", "True", "3.1"],
    ["100001", "Alice", "A1", MULTILINE_QUESTION, "Paris", "Paris", "True", "2.0"],
    ["100002", "Bob", "B2", "What is 2 + 2?", "5", "4", "False", "4.2"],
    ["100002", "Bob", "B2", MULTILINE_QUESTION, "Rome", "Paris", "False", "6.0"],
    ["100003", "Carol", "A1", "What is 2 + 2?", "4", "4", "True", "1.0"],
]

ANSWERS = [
    ["user_id", "question", "selected_answer", "correct_answer", "is_correct", "time_taken_seconds"],
    ["100001", "What is 2 + 2?", "4", "4", "True", "3.1"],
    ["100002", "What is 2 + 2?", "5", "4", "False", "4.2"],
]

USERS = [
    ["user_id", "username", "registered_at", "total_questions_asked", "correct_answers", "earned_points",
     "total_points", "total_time"],
    ["100001", "Alice", "2026-11-04T10:00:00", "1", "1", "1", "1", "0:03"],
    ["100002", "Bob", "2026-11-04T10:00:05", "1", "0", "0", "1", "0:04"],
]

WITH_USERS_NAME = "math_0003.answers_with_users.csv"


def write_csv(port, name, rows):
    """Write a CSV file the same way the server does (csv module, CRLF line ends)."""
    csv_dir = f"data_{port}"
    os.makedirs(csv_dir, exist_ok=True)
    with open(os.path.join(csv_dir, name), "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)


def base_url(port):
    return f"http://127.0.0.1:{port}"


def open_table(browser, port, name, query=""):
    """Open the viewer page for a CSV file and wait until the table is drawn."""
    browser.get(f"{base_url(port)}/files/csv/{quote(name)}{query}")
    wait_for_table(browser)


def wait_for_table(browser):
    WebDriverWait(browser, 10).until(lambda d: d.find_elements(By.CSS_SELECTOR, "#table-container tbody tr"))


def table_rows(browser):
    """Return the table body as a list of rows, each a list of cell texts."""
    rows = []
    for tr in browser.find_elements(By.CSS_SELECTOR, "#table-container tbody tr"):
        rows.append([td.get_attribute("textContent") for td in tr.find_elements(By.TAG_NAME, "td")])
    return rows


def option_texts(browser, select_id):
    return [option.text for option in Select(browser.find_element(By.ID, select_id)).options]


@skip_if_selenium_disabled
def test_filter_by_question(browser):
    """Choosing a question leaves only the answers to that question."""
    with custom_webquiz_server(config=TRUSTED) as (proc, port):
        write_csv(port, WITH_USERS_NAME, ANSWERS_WITH_USERS)
        open_table(browser, port, WITH_USERS_NAME)

        Select(browser.find_element(By.ID, "question-filter")).select_by_visible_text("What is 2 + 2?")

        rows = table_rows(browser)
        assert len(rows) == 3, rows
        assert all(row[3] == "What is 2 + 2?" for row in rows), rows
        assert browser.find_element(By.ID, "row-count").text == "Showing 3 of 5 rows"


@skip_if_selenium_disabled
def test_filter_by_user(browser):
    """Choosing a user leaves only that user's answers; the list shows name and ID."""
    with custom_webquiz_server(config=TRUSTED) as (proc, port):
        write_csv(port, WITH_USERS_NAME, ANSWERS_WITH_USERS)
        open_table(browser, port, WITH_USERS_NAME)

        assert option_texts(browser, "user-filter") == [
            "All users (3)",
            "Alice (100001)",
            "Bob (100002)",
            "Carol (100003)",
        ]

        Select(browser.find_element(By.ID, "user-filter")).select_by_visible_text("Bob (100002)")

        rows = table_rows(browser)
        assert len(rows) == 2, rows
        assert all(row[1] == "Bob" for row in rows), rows
        assert browser.find_element(By.ID, "row-count").text == "Showing 2 of 5 rows"


@skip_if_selenium_disabled
def test_filters_combine(browser):
    """Question and user filters work together."""
    with custom_webquiz_server(config=TRUSTED) as (proc, port):
        write_csv(port, WITH_USERS_NAME, ANSWERS_WITH_USERS)
        open_table(browser, port, WITH_USERS_NAME)

        Select(browser.find_element(By.ID, "question-filter")).select_by_visible_text("What is 2 + 2?")
        Select(browser.find_element(By.ID, "user-filter")).select_by_visible_text("Bob (100002)")

        rows = table_rows(browser)
        assert len(rows) == 1, rows
        assert rows[0][1] == "Bob" and rows[0][4] == "5", rows


@skip_if_selenium_disabled
def test_filters_are_kept_in_page_address(browser):
    """Filters come from the address, and changing them updates the address."""
    with custom_webquiz_server(config=TRUSTED) as (proc, port):
        write_csv(port, WITH_USERS_NAME, ANSWERS_WITH_USERS)
        open_table(browser, port, WITH_USERS_NAME, "?question=" + quote("What is 2 + 2?") + "&user=100002")

        assert browser.find_element(By.ID, "question-filter").get_attribute("value") == "What is 2 + 2?"
        assert browser.find_element(By.ID, "user-filter").get_attribute("value") == "100002"
        assert len(table_rows(browser)) == 1

        Select(browser.find_element(By.ID, "user-filter")).select_by_visible_text("Alice (100001)")

        WebDriverWait(browser, 5).until(lambda d: "user=100001" in d.current_url)
        assert "question=" in browser.current_url


@skip_if_selenium_disabled
def test_quoted_field_with_line_break_stays_one_cell(browser):
    """A question with a line break inside quotes is one cell, not a broken row."""
    with custom_webquiz_server(config=TRUSTED) as (proc, port):
        write_csv(port, WITH_USERS_NAME, ANSWERS_WITH_USERS)
        open_table(browser, port, WITH_USERS_NAME)

        rows = table_rows(browser)
        assert len(rows) == 5, rows
        assert all(len(row) == 8 for row in rows), rows
        assert rows[1][3] == MULTILINE_QUESTION
        assert "What is 2 + 2?" in option_texts(browser, "question-filter")


@skip_if_selenium_disabled
def test_answers_csv_takes_user_names_from_users_csv(browser):
    """The answers CSV has only user IDs; names come from the matching users CSV."""
    with custom_webquiz_server(config=TRUSTED) as (proc, port):
        write_csv(port, "math_0001.csv", ANSWERS)
        write_csv(port, "math_0001.users.csv", USERS)
        open_table(browser, port, "math_0001.csv")

        WebDriverWait(browser, 5).until(lambda d: "Alice (100001)" in option_texts(d, "user-filter"))
        assert "Bob (100002)" in option_texts(browser, "user-filter")


@skip_if_selenium_disabled
def test_answers_csv_without_users_csv_shows_user_ids(browser):
    """Without a users CSV the user list falls back to the IDs."""
    with custom_webquiz_server(config=TRUSTED) as (proc, port):
        write_csv(port, "math_0001.csv", ANSWERS)
        open_table(browser, port, "math_0001.csv")

        assert option_texts(browser, "user-filter") == ["All users (2)", "100001", "100002"]


@skip_if_selenium_disabled
def test_users_csv_has_no_question_filter(browser):
    """The users CSV has no question column, so the question filter is hidden."""
    with custom_webquiz_server(config=TRUSTED) as (proc, port):
        write_csv(port, "math_0001.users.csv", USERS)
        open_table(browser, port, "math_0001.users.csv")

        assert not browser.find_element(By.ID, "question-filter-group").is_displayed()
        assert browser.find_element(By.ID, "user-filter-group").is_displayed()


@skip_if_selenium_disabled
def test_page_asks_to_log_in_without_session(browser):
    """Without an admin session the page explains how to log in."""
    with custom_webquiz_server() as (proc, port):
        write_csv(port, WITH_USERS_NAME, ANSWERS_WITH_USERS)
        browser.get(f"{base_url(port)}/files/csv/{quote(WITH_USERS_NAME)}")

        message = WebDriverWait(browser, 10).until(lambda d: d.find_element(By.ID, "csv-message"))
        WebDriverWait(browser, 10).until(lambda d: "log in" in message.text.lower())
        link = message.find_element(By.TAG_NAME, "a")
        assert link.get_attribute("href").endswith("/files/")
        assert not table_rows(browser)


@skip_if_selenium_disabled
def test_popup_table_opens_in_new_window_with_same_filters(browser):
    """The pop-up shows the table with filters; its button opens it in a new window."""
    with custom_webquiz_server(config=TRUSTED) as (proc, port):
        write_csv(port, WITH_USERS_NAME, ANSWERS_WITH_USERS)
        browser.get(f"{base_url(port)}/files/")

        item = WebDriverWait(browser, 10).until(
            lambda d: d.find_element(By.CSS_SELECTOR, f'#csv-files .file-item[data-name="{WITH_USERS_NAME}"]')
        )
        item.find_element(By.XPATH, ".//button[contains(., 'Table')]").click()

        frame = WebDriverWait(browser, 10).until(lambda d: d.find_element(By.ID, "csv-table-frame"))
        assert frame.is_displayed()
        browser.switch_to.frame(frame)
        wait_for_table(browser)
        assert len(table_rows(browser)) == 5

        Select(browser.find_element(By.ID, "user-filter")).select_by_visible_text("Bob (100002)")
        assert len(table_rows(browser)) == 2

        first_window = browser.current_window_handle
        browser.find_element(By.ID, "open-new-window").click()
        browser.switch_to.default_content()

        WebDriverWait(browser, 10).until(lambda d: len(d.window_handles) == 2)
        new_window = [handle for handle in browser.window_handles if handle != first_window][0]
        browser.switch_to.window(new_window)

        WebDriverWait(browser, 10).until(lambda d: "/files/csv/" in d.current_url)
        assert "user=100002" in browser.current_url
        wait_for_table(browser)
        rows = table_rows(browser)
        assert len(rows) == 2 and all(row[1] == "Bob" for row in rows), rows
        # In its own window the page has no "open in new window" button
        assert not browser.find_element(By.ID, "open-new-window").is_displayed()


@skip_if_selenium_disabled
def test_file_list_link_opens_table_in_new_window(browser):
    """Each CSV file in the list has a link that opens the table in a new window."""
    with custom_webquiz_server(config=TRUSTED) as (proc, port):
        write_csv(port, WITH_USERS_NAME, ANSWERS_WITH_USERS)
        browser.get(f"{base_url(port)}/files/")

        item = WebDriverWait(browser, 10).until(
            lambda d: d.find_element(By.CSS_SELECTOR, f'#csv-files .file-item[data-name="{WITH_USERS_NAME}"]')
        )
        link = item.find_element(By.CSS_SELECTOR, "a.btn-new-window")
        assert link.get_attribute("target") == "_blank"
        assert link.get_attribute("href") == f"{base_url(port)}/files/csv/{quote(WITH_USERS_NAME)}"

        first_window = browser.current_window_handle
        link.click()
        WebDriverWait(browser, 10).until(lambda d: len(d.window_handles) == 2)
        browser.switch_to.window([h for h in browser.window_handles if h != first_window][0])
        wait_for_table(browser)
        assert len(table_rows(browser)) == 5


@skip_if_selenium_disabled
def test_page_fits_phone_screen(browser):
    """On a phone-sized window the page does not scroll sideways; only the table box does."""
    with custom_webquiz_server(config=TRUSTED) as (proc, port):
        write_csv(port, WITH_USERS_NAME, ANSWERS_WITH_USERS)
        browser.set_window_size(375, 800)
        open_table(browser, port, WITH_USERS_NAME)

        page_width = browser.execute_script("return document.documentElement.scrollWidth")
        view_width = browser.execute_script("return document.documentElement.clientWidth")
        assert page_width <= view_width, f"Page is {page_width}px wide in a {view_width}px window"
