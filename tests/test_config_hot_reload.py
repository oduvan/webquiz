import requests
import time

from conftest import custom_webquiz_server, get_admin_session


def test_config_hot_reload_registration_fields():
    """Test that changing registration fields is applied without restart."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        # Update config with new registration fields
        new_config = """registration:
  fields:
    - "Grade"
    - "School"
"""
        response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": new_config}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "saved and applied" in data["message"]

        # Verify the index.html now has the new fields
        index_response = requests.get(f"http://localhost:{port}/")
        assert index_response.status_code == 200
        assert "Grade" in index_response.text
        assert "School" in index_response.text


def test_config_hot_reload_registration_approve():
    """Test that changing approve setting affects new registrations."""
    # Start with approve: false
    config = {"registration": {"approve": False}}

    with custom_webquiz_server(config=config) as (proc, port):
        cookies = get_admin_session(port)

        # Register a user - should auto-approve
        reg1 = requests.post(f"http://localhost:{port}/api/register", json={"username": "User1"})
        assert reg1.status_code == 200
        assert reg1.json()["approved"] is True

        # Update config to require approval
        new_config = """registration:
  approve: true
"""
        update_response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": new_config}
        )
        assert update_response.status_code == 200

        # Register another user - should now require approval
        reg2 = requests.post(f"http://localhost:{port}/api/register", json={"username": "User2"})
        assert reg2.status_code == 200
        assert reg2.json()["approved"] is False
        assert reg2.json()["requires_approval"] is True


def test_config_hot_reload_username_label():
    """Test that changing username_label regenerates index.html."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        # Verify default label
        index1 = requests.get(f"http://localhost:{port}/")
        # Default label is Ukrainian: "Ім'я користувача"
        assert "Ім'я користувача" in index1.text or "username" in index1.text.lower()

        # Update config with new username label
        new_config = """registration:
  username_label: "Student Name"
"""
        response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": new_config}
        )

        assert response.status_code == 200

        # Verify the index.html now has the new label
        index2 = requests.get(f"http://localhost:{port}/")
        assert index2.status_code == 200
        assert "Student Name" in index2.text


def test_config_hot_reload_trusted_ips():
    """Test that trusted_ips changes are applied."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        # Update config with new trusted IPs
        new_config = """admin:
  master_key: "test123"
  trusted_ips:
    - "192.168.1.100"
    - "10.0.0.1"
"""
        response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": new_config}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


def test_config_hot_reload_resets_quiz_state():
    """Test that config change clears user state."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        # Register a user
        reg_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "TestUser"})
        assert reg_response.status_code == 200
        user_id = reg_response.json()["user_id"]

        # Verify user exists
        verify1 = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert verify1.status_code == 200
        assert verify1.json()["valid"] is True

        # Update config
        new_config = """registration:
  approve: false
"""
        update_response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": new_config}
        )
        assert update_response.status_code == 200

        # Verify user state was cleared (returns 200 with valid: False)
        verify2 = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert verify2.status_code == 200
        assert verify2.json()["valid"] is False
        assert "not found" in verify2.json()["message"].lower()


def test_config_hot_reload_notifies_websocket_clients():
    """Test that config change notifies WebSocket clients of quiz restart."""
    import websocket
    import json
    import threading

    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        # Connect to live stats WebSocket
        ws_messages = []
        ws_connected = threading.Event()
        ws_closed = threading.Event()

        def on_message(ws, message):
            ws_messages.append(json.loads(message))

        def on_open(ws):
            ws_connected.set()

        def on_close(ws, close_status_code, close_msg):
            ws_closed.set()

        ws = websocket.WebSocketApp(
            f"ws://localhost:{port}/ws/live-stats", on_message=on_message, on_open=on_open, on_close=on_close
        )

        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()

        # Wait for connection
        ws_connected.wait(timeout=5)

        # Update config
        new_config = """registration:
  approve: false
"""
        update_response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": new_config}
        )
        assert update_response.status_code == 200

        # Wait a bit for WebSocket message
        time.sleep(0.5)

        # Check if quiz_switched message was received
        quiz_switched_msgs = [m for m in ws_messages if m.get("type") == "quiz_switched"]
        assert len(quiz_switched_msgs) > 0, f"Expected quiz_switched message, got: {ws_messages}"

        ws.close()


def test_config_hot_reload_without_active_quiz():
    """Test that config reload works when no quiz is currently selected."""
    # Create server with no quiz files
    with custom_webquiz_server(quizzes={}) as (proc, port):
        cookies = get_admin_session(port)

        # Update config - should work even without active quiz
        new_config = """registration:
  fields:
    - "Grade"
"""
        response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": new_config}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


def test_config_hot_reload_preserves_master_key():
    """Test that master key in config file is NOT applied (security)."""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        # Try to change master key via config
        # IMPORTANT: Must include trusted_ips: [] to prevent localhost bypass
        new_config = """admin:
  master_key: "new_master_key_12345"
  trusted_ips: []
"""
        response = requests.put(
            f"http://localhost:{port}/api/admin/config", cookies=cookies, json={"content": new_config}
        )
        assert response.status_code == 200

        # Old master key should still work
        auth_response = requests.post(f"http://localhost:{port}/api/admin/auth", json={"master_key": "test123"})
        assert auth_response.status_code == 200

        # New master key should NOT work
        auth_response2 = requests.post(
            f"http://localhost:{port}/api/admin/auth", json={"master_key": "new_master_key_12345"}
        )
        assert auth_response2.status_code == 401
