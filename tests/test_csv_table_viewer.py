"""
Tests for the CSV table viewer page (/files/csv/{filename}).

The page shows one CSV file as a table with filters by question and by user.
The file manager shows the same page inside its pop-up (in an iframe) and can
open it in a new window.
"""

import requests

from conftest import custom_webquiz_server


def test_csv_table_page_is_served():
    """The viewer page is an HTML page with the question and user filters."""
    with custom_webquiz_server() as (proc, port):
        response = requests.get(f"http://localhost:{port}/files/csv/results_0001.csv")

        assert response.status_code == 200
        assert response.headers["Content-Type"].startswith("text/html")
        assert 'id="question-filter"' in response.text
        assert 'id="user-filter"' in response.text
        assert 'id="row-count"' in response.text
        assert 'id="open-new-window"' in response.text


def test_csv_table_page_reads_file_through_admin_api():
    """The page loads the file through the protected view API, not directly."""
    with custom_webquiz_server() as (proc, port):
        response = requests.get(f"http://localhost:{port}/files/csv/results_0001.csv")

        assert response.status_code == 200
        assert "/api/files/csv/view/" in response.text
        assert "function parseCSV" in response.text
        assert "function renderCsvTable" in response.text


def test_csv_table_page_blocked_from_public_ip():
    """Like the other admin pages, the viewer page is for the local network only."""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Forwarded-For": "8.8.8.8"}
        response = requests.get(f"http://localhost:{port}/files/csv/results_0001.csv", headers=headers)

        assert response.status_code == 403


def test_files_page_shows_table_in_iframe():
    """The file manager pop-up shows the viewer page in an iframe."""
    with custom_webquiz_server() as (proc, port):
        response = requests.get(f"http://localhost:{port}/files/")

        assert response.status_code == 200
        assert 'id="csv-table-frame"' in response.text
        assert "/files/csv/" in response.text


def test_files_page_has_new_window_link_for_csv():
    """Every CSV file in the list gets a link that opens the table in a new window."""
    with custom_webquiz_server() as (proc, port):
        response = requests.get(f"http://localhost:{port}/files/")

        assert response.status_code == 200
        assert "↗ New window" in response.text
        assert 'target="_blank"' in response.text
