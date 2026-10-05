"""Integration tests for the file transfer API endpoints.

The full flow between two servers is covered in test_transfer.py. These tests
start a real server without a tunnel and check access rules and errors.
"""

import requests

from conftest import custom_webquiz_server, get_admin_session

FILES = [{"type": "quizzes", "name": "default.yaml"}]


def test_transfer_admin_endpoints_require_session():
    with custom_webquiz_server() as (proc, port):
        base = f"http://localhost:{port}/api/admin/transfer"
        assert requests.get(base).status_code == 401
        assert requests.post(f"{base}/send", json={"to": "room-b", "files": FILES}).status_code == 401
        assert requests.post(f"{base}/abc/accept").status_code == 401
        assert requests.post(f"{base}/abc/reject").status_code == 401


def test_transfer_admin_endpoints_blocked_from_public_ip():
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)
        headers = {"X-Forwarded-For": "8.8.8.8"}
        response = requests.get(f"http://localhost:{port}/api/admin/transfer", cookies=cookies, headers=headers)
        assert response.status_code == 403


def test_transfer_state_without_tunnel():
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)
        response = requests.get(f"http://localhost:{port}/api/admin/transfer", cookies=cookies)
        assert response.status_code == 200
        assert response.json() == {"available": False, "name": None, "outgoing": [], "incoming": []}


def test_send_without_tunnel():
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)
        response = requests.post(
            f"http://localhost:{port}/api/admin/transfer/send",
            cookies=cookies,
            json={"to": "room-b", "files": FILES},
        )
        assert response.status_code == 409
        assert "not connected" in response.json()["error"]


def test_send_invalid_json():
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)
        url = f"http://localhost:{port}/api/admin/transfer/send"
        assert requests.post(url, cookies=cookies, data="not json").status_code == 400
        assert requests.post(url, cookies=cookies, json=["list"]).status_code == 400


def test_accept_and_reject_unknown_request():
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)
        base = f"http://localhost:{port}/api/admin/transfer"
        assert requests.post(f"{base}/unknown/accept", cookies=cookies).status_code == 404
        choices = {"files": [{"type": "quizzes", "name": "a.yaml", "action": "skip"}]}
        assert requests.post(f"{base}/unknown/accept", cookies=cookies, json=choices).status_code == 404
        assert requests.post(f"{base}/unknown/accept", cookies=cookies, data="not json").status_code == 400
        assert requests.post(f"{base}/unknown/reject", cookies=cookies).status_code == 404


def test_public_endpoints_work_from_public_ip():
    """Other servers call these through the tunnel: the token protects them, not the IP."""
    with custom_webquiz_server() as (proc, port):
        headers = {"X-Forwarded-For": "8.8.8.8"}
        base = f"http://localhost:{port}/api/transfer"

        # No tunnel on this server, so it cannot receive offers
        response = requests.post(
            f"{base}/offer",
            headers=headers,
            json={"from": "room-a", "token": "t" * 43, "files": FILES},
        )
        assert response.status_code == 409

        # Unknown token: nothing is served
        response = requests.get(f"{base}/download/{'t' * 43}/quizzes/default.yaml", headers=headers)
        assert response.status_code == 404

        response = requests.post(f"{base}/result", headers=headers, json={"token": "t" * 43, "status": "accepted"})
        assert response.status_code == 404

        response = requests.post(f"{base}/offer", headers=headers, data="not json")
        assert response.status_code == 400


def test_send_panel_hidden_until_tunnel_connected():
    """The page shows the send panel only after GET /api/admin/transfer says it is available."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)
        response = requests.get(f"http://localhost:{port}/files/", cookies=cookies)
        assert response.status_code == 200
        assert '<div id="transfer-panel" class="transfer-panel hidden">' in response.text
        assert "classList.toggle('hidden', !state.available)" in response.text
