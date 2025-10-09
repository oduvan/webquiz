import requests
import time
from conftest import custom_webquiz_server


def test_default_username_label():
    """Test that default username label is Ukrainian 'Ім'я користувача'."""
    with custom_webquiz_server() as (proc, port):
        time.sleep(1)  # Wait for static files to be generated
        response = requests.get(f"http://localhost:{port}/")

        assert response.status_code == 200
        assert "Ім'я користувача:" in response.text


def test_custom_username_label_english():
    """Test custom username label in English."""
    config = {"registration": {"username_label": "Student Name"}}

    with custom_webquiz_server(config=config) as (proc, port):
        time.sleep(1)  # Wait for static files to be generated
        response = requests.get(f"http://localhost:{port}/")

        assert response.status_code == 200
        assert "Student Name:" in response.text
        assert "Ім'я користувача:" not in response.text


def test_custom_username_label_ukrainian():
    """Test custom username label with different Ukrainian text."""
    config = {"registration": {"username_label": "Логін учня"}}

    with custom_webquiz_server(config=config) as (proc, port):
        time.sleep(1)  # Wait for static files to be generated
        response = requests.get(f"http://localhost:{port}/")

        assert response.status_code == 200
        assert "Логін учня:" in response.text
