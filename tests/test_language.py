"""
Tests for the language configuration feature.

Tests that the quiz interface and error messages can be configured
to display in English or Ukrainian via the `language` config option.
"""

import os
import tempfile
import yaml
import requests

from webquiz.config import WebQuizConfig, load_config_from_yaml
from webquiz.translations import TRANSLATIONS, get_translations

from conftest import custom_webquiz_server


# --- Translation unit tests ---


def test_uk_and_en_have_same_keys():
    """Both language dicts must have identical keys."""
    uk_keys = set(TRANSLATIONS["uk"].keys())
    en_keys = set(TRANSLATIONS["en"].keys())
    assert uk_keys == en_keys, f"Missing in en: {uk_keys - en_keys}, Missing in uk: {en_keys - uk_keys}"


def test_get_translations_uk():
    """get_translations returns Ukrainian strings for 'uk'."""
    t = get_translations("uk")
    assert t["loading"] == "Завантаження..."


def test_get_translations_en():
    """get_translations returns English strings for 'en'."""
    t = get_translations("en")
    assert t["loading"] == "Loading..."


def test_get_translations_fallback():
    """get_translations falls back to Ukrainian for unknown language."""
    t = get_translations("fr")
    assert t["loading"] == "Завантаження..."


def test_no_empty_translations():
    """All translation values must be non-empty strings."""
    for lang, translations in TRANSLATIONS.items():
        for key, value in translations.items():
            assert isinstance(value, str), f"{lang}.{key} is not a string"
            assert len(value) > 0, f"{lang}.{key} is empty"


# --- Language config loading tests ---


def test_default_language_is_uk():
    """Default language should be Ukrainian."""
    config = WebQuizConfig()
    assert config.language == "uk"


def test_load_language_from_yaml():
    """Language should be read from YAML config."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({"language": "en"}, f)
        f.flush()
        config = load_config_from_yaml(f.name)
    os.unlink(f.name)
    assert config.language == "en"


def test_load_language_uk_from_yaml():
    """Ukrainian language should be read from YAML config."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({"language": "uk"}, f)
        f.flush()
        config = load_config_from_yaml(f.name)
    os.unlink(f.name)
    assert config.language == "uk"


def test_missing_language_defaults_to_uk():
    """Missing language in YAML defaults to Ukrainian."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump({"server": {"port": 9999}}, f)
        f.flush()
        config = load_config_from_yaml(f.name)
    os.unlink(f.name)
    assert config.language == "uk"


# --- Language in quiz page tests ---


def test_default_language_shows_ukrainian():
    """Default config (uk) should show Ukrainian strings in the quiz page."""
    with custom_webquiz_server() as (proc, port):
        # Switch to quiz first
        session = requests.Session()
        session.post(f"http://127.0.0.1:{port}/api/admin/auth", json={"master_key": "test123"})
        session.post(f"http://127.0.0.1:{port}/api/admin/switch-quiz", json={"filename": "test_quiz.yaml"})

        # Get the quiz page
        response = requests.get(f"http://127.0.0.1:{port}/")
        assert response.status_code == 200
        html = response.text
        assert "Зареєструйтеся для початку тесту" in html
        assert "Зареєструватися" in html
        assert "Відправити відповідь" in html


def test_english_language_shows_english():
    """English config should show English strings in the quiz page."""
    with custom_webquiz_server(config={"language": "en"}) as (proc, port):
        # Switch to quiz first
        session = requests.Session()
        session.post(f"http://127.0.0.1:{port}/api/admin/auth", json={"master_key": "test123"})
        session.post(f"http://127.0.0.1:{port}/api/admin/switch-quiz", json={"filename": "test_quiz.yaml"})

        # Get the quiz page
        response = requests.get(f"http://127.0.0.1:{port}/")
        assert response.status_code == 200
        html = response.text
        assert "Register to start the quiz" in html
        assert "Register" in html
        assert "Submit answer" in html
        # Should NOT contain Ukrainian
        assert "Зареєструйтеся" not in html
        assert "Відправити відповідь" not in html


def test_english_css_feedback_labels():
    """English config should have English CSS feedback labels."""
    with custom_webquiz_server(config={"language": "en"}) as (proc, port):
        session = requests.Session()
        session.post(f"http://127.0.0.1:{port}/api/admin/auth", json={"master_key": "test123"})
        session.post(f"http://127.0.0.1:{port}/api/admin/switch-quiz", json={"filename": "test_quiz.yaml"})

        response = requests.get(f"http://127.0.0.1:{port}/")
        html = response.text
        assert "Correct answer" in html
        assert "Your answer" in html
        assert "Also correct" in html


# --- Language in error messages tests ---


def test_english_registration_errors():
    """English config should return English error messages."""
    with custom_webquiz_server(config={"language": "en"}) as (proc, port):
        session = requests.Session()
        session.post(f"http://127.0.0.1:{port}/api/admin/auth", json={"master_key": "test123"})
        session.post(f"http://127.0.0.1:{port}/api/admin/switch-quiz", json={"filename": "test_quiz.yaml"})

        # Try to register with empty username
        response = requests.post(
            f"http://127.0.0.1:{port}/api/register",
            json={"username": ""},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "Username cannot be empty"


def test_english_duplicate_username_error():
    """English config should return English duplicate username error."""
    with custom_webquiz_server(config={"language": "en"}) as (proc, port):
        session = requests.Session()
        session.post(f"http://127.0.0.1:{port}/api/admin/auth", json={"master_key": "test123"})
        session.post(f"http://127.0.0.1:{port}/api/admin/switch-quiz", json={"filename": "test_quiz.yaml"})

        # Register first user
        requests.post(f"http://127.0.0.1:{port}/api/register", json={"username": "TestUser"})

        # Try to register with same username
        response = requests.post(f"http://127.0.0.1:{port}/api/register", json={"username": "TestUser"})
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "Username already exists"


def test_ukrainian_registration_errors():
    """Default (uk) config should return Ukrainian error messages."""
    with custom_webquiz_server() as (proc, port):
        session = requests.Session()
        session.post(f"http://127.0.0.1:{port}/api/admin/auth", json={"master_key": "test123"})
        session.post(f"http://127.0.0.1:{port}/api/admin/switch-quiz", json={"filename": "test_quiz.yaml"})

        response = requests.post(
            f"http://127.0.0.1:{port}/api/register",
            json={"username": ""},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "Ім'я користувача не може бути порожнім"


def test_english_submit_answer_user_not_found():
    """English config should return English user not found error."""
    with custom_webquiz_server(config={"language": "en"}) as (proc, port):
        session = requests.Session()
        session.post(f"http://127.0.0.1:{port}/api/admin/auth", json={"master_key": "test123"})
        session.post(f"http://127.0.0.1:{port}/api/admin/switch-quiz", json={"filename": "test_quiz.yaml"})

        response = requests.post(
            f"http://127.0.0.1:{port}/api/submit-answer",
            json={"user_id": "999999", "question_id": 0, "selected_answer": 1},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "User not found"


# --- Language config validation tests ---


def test_invalid_language_rejected():
    """Invalid language value should be rejected by config validation."""
    with custom_webquiz_server() as (proc, port):
        session = requests.Session()
        session.post(f"http://127.0.0.1:{port}/api/admin/auth", json={"master_key": "test123"})
        session.post(f"http://127.0.0.1:{port}/api/admin/switch-quiz", json={"filename": "test_quiz.yaml"})

        response = session.put(
            f"http://127.0.0.1:{port}/api/admin/config",
            json={"content": "language: fr\n"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "language" in str(data.get("errors", "")).lower() or "language" in str(data.get("error", "")).lower()


def test_valid_language_en_accepted():
    """Valid language 'en' should be accepted by config validation."""
    with custom_webquiz_server() as (proc, port):
        session = requests.Session()
        session.post(f"http://127.0.0.1:{port}/api/admin/auth", json={"master_key": "test123"})
        session.post(f"http://127.0.0.1:{port}/api/admin/switch-quiz", json={"filename": "test_quiz.yaml"})

        response = session.put(
            f"http://127.0.0.1:{port}/api/admin/config",
            json={"content": "language: en\n"},
        )
        assert response.status_code == 200
