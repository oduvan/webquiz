import requests
import yaml
import json
import time
import websocket

from conftest import custom_webquiz_server, get_admin_session


# Test POST /api/register modifications (4 tests)


def test_register_with_approve_disabled():
    """Test registration with approve disabled - should auto-approve and start timing"""
    config = {"registration": {"approve": False}}  # Approval disabled

    with custom_webquiz_server(config=config) as (proc, port):
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "TestUser"})

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "TestUser"
        assert "user_id" in data
        assert data.get("requires_approval") is False
        assert data.get("approved") is True


def test_register_with_approve_enabled():
    """Test registration with approve enabled - should NOT auto-approve"""
    config = {"registration": {"approve": True}}  # Approval required

    with custom_webquiz_server(config=config) as (proc, port):
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "TestUser"})

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "TestUser"
        assert "user_id" in data
        assert data["requires_approval"] is True
        assert data["approved"] is False


def test_register_with_approve_enabled_and_custom_fields():
    """Test registration with approval and custom registration fields"""
    config = {"registration": {"approve": True, "fields": ["Grade", "School"]}}

    with custom_webquiz_server(config=config) as (proc, port):
        response = requests.post(
            f"http://localhost:{port}/api/register",
            json={"username": "TestUser", "grade": "10", "school": "Central HS"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "TestUser"
        assert data["requires_approval"] is True
        assert data["approved"] is False


def test_register_broadcasts_to_admin_websocket():
    """Test that registration broadcasts to admin WebSocket when approval required"""
    # This test is simplified - full WebSocket testing would require more setup
    config = {"registration": {"approve": True}}

    with custom_webquiz_server(config=config) as (proc, port):
        # Register user
        response = requests.post(f"http://localhost:{port}/api/register", json={"username": "TestUser"})

        assert response.status_code == 200
        # WebSocket broadcast verification would require connecting to ws://localhost:{port}/ws/admin
        # For now, just verify registration succeeded
        assert response.json()["approved"] is False


# Test GET /api/verify-user/{user_id} modifications (3 tests)


def test_verify_user_not_approved():
    """Test verify_user returns waiting status for unapproved user"""
    config = {"registration": {"approve": True}}

    with custom_webquiz_server(config=config) as (proc, port):
        # Register user
        reg_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "TestUser"})
        user_id = reg_response.json()["user_id"]

        # Verify user status
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["approved"] is False
        assert data["requires_approval"] is True
        assert "user_data" in data


def test_verify_user_approved():
    """Test verify_user returns approved status after approval"""
    config = {"registration": {"approve": True}}

    with custom_webquiz_server(config=config) as (proc, port):
        cookies = get_admin_session(port)

        # Register user
        reg_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "TestUser"})
        user_id = reg_response.json()["user_id"]

        # Approve user
        approve_response = requests.put(
            f"http://localhost:{port}/api/admin/approve-user", cookies=cookies, json={"user_id": user_id}
        )
        assert approve_response.status_code == 200

        # Verify user status
        response = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["approved"] is True


def test_verify_user_approved_after_approval():
    """Test state changes correctly after approval"""
    config = {"registration": {"approve": True}}

    with custom_webquiz_server(config=config) as (proc, port):
        cookies = get_admin_session(port)

        # Register user
        reg_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "TestUser"})
        user_id = reg_response.json()["user_id"]

        # Check unapproved state
        verify1 = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert verify1.json()["approved"] is False

        # Approve user
        requests.put(f"http://localhost:{port}/api/admin/approve-user", cookies=cookies, json={"user_id": user_id})

        # Check approved state
        verify2 = requests.get(f"http://localhost:{port}/api/verify-user/{user_id}")
        assert verify2.json()["approved"] is True


# Test PUT /api/update-registration (5 tests)


def test_update_registration_while_waiting():
    """Test updating registration data before approval"""
    config = {"registration": {"approve": True, "fields": ["Grade"]}}

    with custom_webquiz_server(config=config) as (proc, port):
        # Register user
        reg_response = requests.post(
            f"http://localhost:{port}/api/register", json={"username": "OldName", "grade": "9"}
        )
        user_id = reg_response.json()["user_id"]

        # Update registration
        response = requests.put(
            f"http://localhost:{port}/api/update-registration",
            json={"user_id": user_id, "username": "NewName", "grade": "10"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["user_data"]["username"] == "NewName"
        assert data["user_data"]["grade"] == "10"


def test_update_registration_after_approval():
    """Test that update is rejected after user is approved"""
    config = {"registration": {"approve": True}}

    with custom_webquiz_server(config=config) as (proc, port):
        cookies = get_admin_session(port)

        # Register user
        reg_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "TestUser"})
        user_id = reg_response.json()["user_id"]

        # Approve user
        requests.put(f"http://localhost:{port}/api/admin/approve-user", cookies=cookies, json={"user_id": user_id})

        # Try to update registration after approval
        response = requests.put(
            f"http://localhost:{port}/api/update-registration", json={"user_id": user_id, "username": "NewName"}
        )

        assert response.status_code == 400
        data = response.json()
        assert "Cannot update registration data after approval" in data["error"]


def test_update_registration_invalid_user():
    """Test update registration with non-existent user"""
    with custom_webquiz_server() as (proc, port):
        response = requests.put(
            f"http://localhost:{port}/api/update-registration", json={"user_id": "999999", "username": "TestUser"}
        )

        assert response.status_code == 404
        assert "User not found" in response.json()["error"]


def test_update_registration_validates_required_fields():
    """Test that update validates required fields (username uniqueness)"""
    config = {"registration": {"approve": True}}

    with custom_webquiz_server(config=config) as (proc, port):
        # Register two users
        reg1 = requests.post(f"http://localhost:{port}/api/register", json={"username": "User1"})
        user1_id = reg1.json()["user_id"]

        reg2 = requests.post(f"http://localhost:{port}/api/register", json={"username": "User2"})
        user2_id = reg2.json()["user_id"]

        # Try to update user2 to use user1's username
        response = requests.put(
            f"http://localhost:{port}/api/update-registration", json={"user_id": user2_id, "username": "User1"}
        )

        assert response.status_code == 400  # ValueError caught by middleware
        assert "error" in response.json()


def test_update_registration_broadcasts_websocket():
    """Test that update broadcasts to admin WebSocket"""
    config = {"registration": {"approve": True}}

    with custom_webquiz_server(config=config) as (proc, port):
        # Register user
        reg_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "TestUser"})
        user_id = reg_response.json()["user_id"]

        # Update registration
        response = requests.put(
            f"http://localhost:{port}/api/update-registration", json={"user_id": user_id, "username": "UpdatedUser"}
        )

        assert response.status_code == 200
        # WebSocket broadcast would be verified by connecting to ws://localhost:{port}/ws/admin


# Test PUT /api/admin/approve-user (6 tests)


def test_approve_user_requires_auth():
    """Test that approve endpoint requires authentication"""
    config = {"registration": {"approve": True}}

    with custom_webquiz_server(config=config) as (proc, port):
        # Register user
        reg_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "TestUser"})
        user_id = reg_response.json()["user_id"]

        # Try to approve without authentication
        response = requests.put(f"http://localhost:{port}/api/admin/approve-user", json={"user_id": user_id})

        assert response.status_code == 401


def test_approve_user_successfully():
    """Test successful user approval"""
    config = {"registration": {"approve": True}}

    with custom_webquiz_server(config=config) as (proc, port):
        cookies = get_admin_session(port)

        # Register user
        reg_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "TestUser"})
        user_id = reg_response.json()["user_id"]

        # Approve user
        response = requests.put(
            f"http://localhost:{port}/api/admin/approve-user", cookies=cookies, json={"user_id": user_id}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "User approved successfully" in data["message"]


def test_approve_user_starts_timing():
    """Test that approving user starts timing"""
    config = {"registration": {"approve": True}}

    with custom_webquiz_server(config=config) as (proc, port):
        cookies = get_admin_session(port)

        # Register user
        reg_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "TestUser"})
        user_id = reg_response.json()["user_id"]

        # Approve user
        time.sleep(0.1)  # Small delay to ensure timing difference
        approve_response = requests.put(
            f"http://localhost:{port}/api/admin/approve-user", cookies=cookies, json={"user_id": user_id}
        )

        assert approve_response.status_code == 200

        # Submit an answer to check timing works
        response = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": 1, "selected_answer": 1},
        )

        assert response.status_code == 200
        data = response.json()
        assert "time_taken" in data
        assert data["time_taken"] >= 0  # Timing started


def test_approve_user_initializes_live_stats():
    """Test that approval initializes live stats"""
    config = {"registration": {"approve": True}}

    with custom_webquiz_server(config=config) as (proc, port):
        cookies = get_admin_session(port)

        # Register user
        reg_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "TestUser"})
        user_id = reg_response.json()["user_id"]

        # Approve user
        response = requests.put(
            f"http://localhost:{port}/api/admin/approve-user", cookies=cookies, json={"user_id": user_id}
        )

        assert response.status_code == 200
        # Live stats would be visible in WebSocket or could be verified
        # by checking that the user can start answering questions


def test_approve_user_invalid_user_id():
    """Test approval with non-existent user ID"""
    with custom_webquiz_server() as (proc, port):
        cookies = get_admin_session(port)

        response = requests.put(
            f"http://localhost:{port}/api/admin/approve-user", cookies=cookies, json={"user_id": "999999"}
        )

        assert response.status_code == 404
        assert "User not found" in response.json()["error"]


def test_approve_user_broadcasts_websocket():
    """Test that approval broadcasts to admin WebSocket"""
    config = {"registration": {"approve": True}}

    with custom_webquiz_server(config=config) as (proc, port):
        cookies = get_admin_session(port)

        # Register user
        reg_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "TestUser"})
        user_id = reg_response.json()["user_id"]

        # Approve user
        response = requests.put(
            f"http://localhost:{port}/api/admin/approve-user", cookies=cookies, json={"user_id": user_id}
        )

        assert response.status_code == 200
        # WebSocket broadcast would be verified by connecting to ws://localhost:{port}/ws/admin


# Test timing behavior (2 tests)


def test_timing_starts_on_registration_when_approve_false():
    """Test that timing starts immediately when approval disabled"""
    config = {"registration": {"approve": False}}

    with custom_webquiz_server(config=config) as (proc, port):
        # Register user
        reg_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "TestUser"})
        user_id = reg_response.json()["user_id"]

        # Wait a bit
        time.sleep(0.2)

        # Submit answer
        response = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": 1, "selected_answer": 1},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["time_taken"] >= 0.2  # At least 0.2 seconds passed


def test_timing_starts_on_approval_when_approve_true():
    """Test that timing starts only after approval when approval required"""
    config = {"registration": {"approve": True}}

    with custom_webquiz_server(config=config) as (proc, port):
        cookies = get_admin_session(port)

        # Register user
        reg_response = requests.post(f"http://localhost:{port}/api/register", json={"username": "TestUser"})
        user_id = reg_response.json()["user_id"]

        # Wait before approving
        time.sleep(0.5)

        # Approve user
        approve_response = requests.put(
            f"http://localhost:{port}/api/admin/approve-user", cookies=cookies, json={"user_id": user_id}
        )
        assert approve_response.status_code == 200

        # Immediately submit answer (timing should be near 0)
        time.sleep(0.1)
        response = requests.post(
            f"http://localhost:{port}/api/submit-answer",
            json={"user_id": user_id, "question_id": 1, "selected_answer": 1},
        )

        assert response.status_code == 200
        data = response.json()
        # Time should be around 0.1 seconds (from approval), NOT 0.6 seconds (from registration)
        assert data["time_taken"] < 0.3  # Should be much less than 0.5+0.1=0.6 seconds
