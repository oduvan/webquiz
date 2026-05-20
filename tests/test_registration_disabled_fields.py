"""Integration tests for registration.disabled_fields support.

A field that lives in `registration.disabled_fields` keeps its definition in the
config but is not shown or required during user registration. The admin form
toggles fields between `registration.fields` and `registration.disabled_fields`
without losing field names, so commonly-flipped fields don't have to be deleted
and recreated.
"""

import json
import re
import requests
import yaml

from conftest import custom_webquiz_server, get_admin_session


def test_disabled_field_not_required_at_register():
    """A field in disabled_fields must not be required during /api/register."""
    config = {"registration": {"fields": ["Grade"], "disabled_fields": ["School"]}}

    with custom_webquiz_server(config=config) as (proc, port):
        base_url = f"http://localhost:{port}"

        # Registering with only the enabled field should succeed
        response = requests.post(
            f"{base_url}/api/register", json={"username": "student_a", "grade": "10"}
        )
        assert response.status_code == 200, response.text
        assert "user_id" in response.json()


def test_disabled_field_becomes_required_when_enabled():
    """Moving a field from disabled_fields to fields makes it required again."""
    # First spin up server with the field disabled
    config = {"registration": {"fields": [], "disabled_fields": ["Grade"]}}

    with custom_webquiz_server(config=config) as (proc, port):
        base_url = f"http://localhost:{port}"

        # Without grade, registration works
        response = requests.post(f"{base_url}/api/register", json={"username": "stu1"})
        assert response.status_code == 200

        # Now flip Grade to enabled via admin API
        cookies = get_admin_session(port)
        response = requests.put(
            f"{base_url}/api/admin/config",
            cookies=cookies,
            json={
                "data": {
                    "registration": {"fields": ["Grade"], "disabled_fields": []}
                }
            },
        )
        assert response.status_code == 200, response.text

        # Quiz restart on config save resets users, so we can re-register
        # Now grade IS required
        response = requests.post(f"{base_url}/api/register", json={"username": "stu2"})
        assert response.status_code == 400

        response = requests.post(
            f"{base_url}/api/register", json={"username": "stu2", "grade": "9"}
        )
        assert response.status_code == 200


def test_partial_save_persists_disabled_fields():
    """JSON partial save must round-trip disabled_fields into the YAML file."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        response = requests.put(
            f"http://localhost:{port}/api/admin/config",
            cookies=cookies,
            json={
                "data": {
                    "registration": {
                        "fields": ["Grade"],
                        "disabled_fields": ["School", "Teacher"],
                    }
                }
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        config_path = data["config_path"]

        # Response reports both lists
        assert data["config_data"]["registration"]["fields"] == ["Grade"]
        assert data["config_data"]["registration"]["disabled_fields"] == [
            "School",
            "Teacher",
        ]

        # File on disk has both lists
        with open(config_path, "r", encoding="utf-8") as f:
            saved = yaml.safe_load(f.read())
        assert saved["registration"]["fields"] == ["Grade"]
        assert saved["registration"]["disabled_fields"] == ["School", "Teacher"]


def test_files_page_exposes_disabled_fields():
    """/files/ page must inject disabled_fields into CONFIG_DATA for the form editor."""
    with custom_webquiz_server() as (proc, port):
        session = requests.Session()
        auth_response = session.post(
            f"http://localhost:{port}/api/admin/auth", json={"master_key": "test123"}
        )
        assert auth_response.status_code == 200

        # Seed config with both lists
        config_content = (
            "registration:\n"
            "  fields:\n"
            "    - Grade\n"
            "  disabled_fields:\n"
            "    - School\n"
            "    - Teacher\n"
        )
        response = session.put(
            f"http://localhost:{port}/api/admin/config",
            json={"content": config_content},
        )
        assert response.status_code == 200

        # Load /files/ and pull CONFIG_DATA out of the script tag
        files_response = session.get(f"http://localhost:{port}/files/")
        assert files_response.status_code == 200
        match = re.search(r"const CONFIG_DATA = (.*?);", files_response.text)
        assert match is not None
        config_data = json.loads(match.group(1))
        assert config_data["registration"]["fields"] == ["Grade"]
        assert config_data["registration"]["disabled_fields"] == ["School", "Teacher"]


def test_validation_rejects_non_list_disabled_fields():
    """disabled_fields must be a list of strings."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        response = requests.put(
            f"http://localhost:{port}/api/admin/config",
            cookies=cookies,
            json={"data": {"registration": {"disabled_fields": "not_a_list"}}},
        )
        assert response.status_code == 400
        data = response.json()
        assert "validation failed" in data["error"].lower()
        assert any("disabled_fields" in err for err in data.get("errors", []))


def test_validation_rejects_non_string_disabled_fields():
    """disabled_fields list entries must all be strings."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        response = requests.put(
            f"http://localhost:{port}/api/admin/config",
            cookies=cookies,
            json={"data": {"registration": {"disabled_fields": ["ok", 42]}}},
        )
        assert response.status_code == 400
        data = response.json()
        assert "validation failed" in data["error"].lower()


def test_disabled_field_omitted_from_registration_html():
    """The injected registration <table> must not list disabled fields."""
    config = {"registration": {"fields": ["Grade"], "disabled_fields": ["School"]}}

    with custom_webquiz_server(config=config) as (proc, port):
        response = requests.get(f"http://localhost:{port}/")
        assert response.status_code == 200
        html = response.text
        # Enabled field shows up in the registration table
        assert "Grade" in html
        # Disabled field must not be rendered as a registration input row
        assert 'data-field-name="school"' not in html
