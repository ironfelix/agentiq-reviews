"""
AgentIQ Chat Center API Tests

Run with: pytest tests/test_api.py -v
Requires: Backend running on localhost:8001

Test Coverage:
- Health endpoint
- Authentication (register, login, me, logout)
- Chats API (list, get, mark-read, close)
- Messages API (list, send)
"""
import pytest
import httpx


class TestHealth:
    """Health endpoint tests."""

    def test_health_returns_200(self, client: httpx.Client):
        """TC-HEALTH-01: Health check returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_root_returns_api_info(self, client: httpx.Client):
        """TC-ROOT-01: Root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data or "name" in data or "message" in data


class TestAuthRegister:
    """Authentication registration tests."""

    def test_register_valid_user(self, client: httpx.Client):
        """TC-AUTH-REG-01: Register new user returns JWT token."""
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        response = client.post("/api/auth/register", json={
            "email": f"newuser_{unique_id}@test.com",
            "password": "password123",
            "name": "New User",
            "marketplace": "wildberries"
        })
        assert response.status_code in [200, 201]
        data = response.json()
        assert "access_token" in data
        assert "seller" in data
        assert data["seller"]["email"] == f"newuser_{unique_id}@test.com"

    def test_register_duplicate_email(self, client: httpx.Client):
        """TC-AUTH-REG-02: Register with existing email returns 400."""
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        user_data = {
            "email": f"duplicate_{unique_id}@test.com",
            "password": "password123",
            "name": "Duplicate User",
            "marketplace": "wildberries"
        }
        # First registration
        response1 = client.post("/api/auth/register", json=user_data)
        assert response1.status_code in [200, 201]

        # Second registration with same email
        response2 = client.post("/api/auth/register", json=user_data)
        assert response2.status_code == 400

    def test_register_missing_fields(self, client: httpx.Client):
        """TC-AUTH-REG-03: Register with missing fields returns 422."""
        response = client.post("/api/auth/register", json={
            "email": "incomplete@test.com"
            # Missing password, name, marketplace
        })
        assert response.status_code == 422


class TestAuthLogin:
    """Authentication login tests."""

    def test_login_valid_credentials(self, client: httpx.Client, test_user_data: dict):
        """TC-AUTH-LOGIN-01: Login with valid credentials returns token."""
        # First register
        client.post("/api/auth/register", json=test_user_data)

        # Then login
        response = client.post("/api/auth/login", json={
            "email": test_user_data["email"],
            "password": test_user_data["password"]
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    def test_login_wrong_password(self, client: httpx.Client, test_user_data: dict):
        """TC-AUTH-LOGIN-02: Login with wrong password returns 401."""
        # First register
        client.post("/api/auth/register", json=test_user_data)

        # Login with wrong password
        response = client.post("/api/auth/login", json={
            "email": test_user_data["email"],
            "password": "wrongpassword"
        })
        assert response.status_code == 401

    def test_login_unknown_email(self, client: httpx.Client):
        """TC-AUTH-LOGIN-03: Login with unknown email returns 401."""
        response = client.post("/api/auth/login", json={
            "email": "nonexistent@test.com",
            "password": "password123"
        })
        assert response.status_code == 401


class TestAuthMe:
    """Get current user tests."""

    def test_me_with_valid_token(self, client: httpx.Client, auth_headers: dict):
        """TC-AUTH-ME-01: Get user with valid token returns user info."""
        response = client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "email" in data

    def test_me_without_token(self, client: httpx.Client):
        """TC-AUTH-ME-02: Get user without token returns 401."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_me_with_invalid_token(self, client: httpx.Client):
        """TC-AUTH-ME-03: Get user with invalid token returns 401."""
        response = client.get("/api/auth/me", headers={
            "Authorization": "Bearer invalid_token_here"
        })
        assert response.status_code == 401


class TestChatsList:
    """Chat list endpoint tests."""

    def test_list_chats_demo_mode(self, client: httpx.Client):
        """TC-CHATS-LIST-01: List all chats in demo mode."""
        response = client.get("/api/chats")
        assert response.status_code == 200
        data = response.json()
        assert "chats" in data
        assert "total" in data
        assert isinstance(data["chats"], list)

    def test_list_chats_filter_by_status(self, client: httpx.Client):
        """TC-CHATS-LIST-02: Filter chats by status."""
        response = client.get("/api/chats", params={"status": "open"})
        assert response.status_code == 200
        data = response.json()
        # All returned chats should be open
        for chat in data["chats"]:
            assert chat["status"] == "open"

    def test_list_chats_filter_by_priority(self, client: httpx.Client):
        """TC-CHATS-LIST-03: Filter chats by SLA priority."""
        response = client.get("/api/chats", params={"sla_priority": "urgent"})
        assert response.status_code == 200
        data = response.json()
        for chat in data["chats"]:
            assert chat["sla_priority"] == "urgent"

    def test_list_chats_filter_unread(self, client: httpx.Client):
        """TC-CHATS-LIST-04: Filter chats by unread status."""
        response = client.get("/api/chats", params={"has_unread": "true"})
        assert response.status_code == 200
        data = response.json()
        for chat in data["chats"]:
            assert chat["unread_count"] > 0

    def test_list_chats_with_search(self, client: httpx.Client):
        """TC-CHATS-LIST-05: Search chats."""
        response = client.get("/api/chats", params={"search": "Иван"})
        assert response.status_code == 200
        data = response.json()
        assert "chats" in data

    def test_list_chats_pagination(self, client: httpx.Client):
        """TC-CHATS-LIST-06: Pagination works correctly."""
        response = client.get("/api/chats", params={"page": 1, "page_size": 2})
        assert response.status_code == 200
        data = response.json()
        assert "page" in data
        assert "page_size" in data
        assert len(data["chats"]) <= 2


class TestChatsGet:
    """Get single chat tests."""

    def test_get_existing_chat(self, client: httpx.Client):
        """TC-CHATS-GET-01: Get existing chat returns chat data."""
        # First get list to find a chat ID
        list_response = client.get("/api/chats")
        if list_response.json()["chats"]:
            chat_id = list_response.json()["chats"][0]["id"]
            response = client.get(f"/api/chats/{chat_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == chat_id

    def test_get_nonexistent_chat(self, client: httpx.Client):
        """TC-CHATS-GET-02: Get non-existent chat returns 404."""
        response = client.get("/api/chats/999999")
        assert response.status_code == 404


class TestChatsActions:
    """Chat action tests (mark-read, close)."""

    def test_mark_chat_as_read(self, client: httpx.Client):
        """TC-CHATS-READ-01: Mark chat as read sets unread_count to 0."""
        # First get a chat
        list_response = client.get("/api/chats")
        if list_response.json()["chats"]:
            chat_id = list_response.json()["chats"][0]["id"]
            response = client.post(f"/api/chats/{chat_id}/mark-read")
            assert response.status_code == 200
            data = response.json()
            assert data["unread_count"] == 0

    def test_mark_nonexistent_chat_as_read(self, client: httpx.Client):
        """TC-CHATS-READ-02: Mark non-existent chat returns 404."""
        response = client.post("/api/chats/999999/mark-read")
        assert response.status_code == 404

    def test_close_chat(self, client: httpx.Client):
        """TC-CHATS-CLOSE-01: Close chat sets status to closed."""
        list_response = client.get("/api/chats", params={"status": "open"})
        if list_response.json()["chats"]:
            chat_id = list_response.json()["chats"][0]["id"]
            response = client.post(f"/api/chats/{chat_id}/close")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "closed"


class TestMessagesList:
    """Messages list tests."""

    def test_get_messages_for_chat(self, client: httpx.Client):
        """TC-MSG-LIST-01: Get messages for existing chat."""
        # First get a chat
        list_response = client.get("/api/chats")
        if list_response.json()["chats"]:
            chat_id = list_response.json()["chats"][0]["id"]
            response = client.get(f"/api/messages/chat/{chat_id}")
            assert response.status_code == 200
            data = response.json()
            assert "messages" in data
            assert isinstance(data["messages"], list)

    def test_get_messages_nonexistent_chat(self, client: httpx.Client):
        """TC-MSG-LIST-02: Get messages for non-existent chat returns 404."""
        response = client.get("/api/messages/chat/999999")
        assert response.status_code == 404


class TestMessagesSend:
    """Send message tests."""

    def test_send_message_to_chat(self, client: httpx.Client):
        """TC-MSG-SEND-01: Send message to existing chat."""
        # First get a chat
        list_response = client.get("/api/chats")
        if list_response.json()["chats"]:
            chat_id = list_response.json()["chats"][0]["id"]
            response = client.post("/api/messages", json={
                "chat_id": chat_id,
                "text": "Test message from pytest"
            })
            assert response.status_code in [200, 201]
            data = response.json()
            assert data["chat_id"] == chat_id
            assert data["text"] == "Test message from pytest"
            assert data["direction"] == "outgoing"

    def test_send_message_nonexistent_chat(self, client: httpx.Client):
        """TC-MSG-SEND-02: Send message to non-existent chat returns 404."""
        response = client.post("/api/messages", json={
            "chat_id": 999999,
            "text": "Test message"
        })
        assert response.status_code == 404

    def test_send_empty_message(self, client: httpx.Client):
        """TC-MSG-SEND-03: Send empty message returns 400 or 422."""
        list_response = client.get("/api/chats")
        if list_response.json()["chats"]:
            chat_id = list_response.json()["chats"][0]["id"]
            response = client.post("/api/messages", json={
                "chat_id": chat_id,
                "text": ""
            })
            assert response.status_code in [400, 422]


class TestSellers:
    """Sellers API tests (admin endpoints)."""

    def test_list_sellers(self, client: httpx.Client):
        """TC-SELLERS-LIST-01: List all sellers."""
        response = client.get("/api/sellers")
        assert response.status_code == 200
        data = response.json()
        # API returns {sellers: [...], total: N}
        assert "sellers" in data
        assert isinstance(data["sellers"], list)

    def test_get_seller(self, client: httpx.Client):
        """TC-SELLERS-GET-01: Get existing seller."""
        # First list sellers
        list_response = client.get("/api/sellers")
        data = list_response.json()
        if data.get("sellers"):
            seller_id = data["sellers"][0]["id"]
            response = client.get(f"/api/sellers/{seller_id}")
            assert response.status_code == 200

    def test_get_nonexistent_seller(self, client: httpx.Client):
        """TC-SELLERS-GET-02: Get non-existent seller returns 404."""
        response = client.get("/api/sellers/999999")
        assert response.status_code == 404


class TestIntegration:
    """Integration test scenarios."""

    def test_full_user_journey(self, client: httpx.Client):
        """Full user journey: register -> login -> view chats -> send message."""
        import uuid
        unique_id = uuid.uuid4().hex[:8]

        # Step 1: Register
        reg_response = client.post("/api/auth/register", json={
            "email": f"journey_{unique_id}@test.com",
            "password": "password123",
            "name": "Journey Test",
            "marketplace": "wildberries"
        })
        assert reg_response.status_code in [200, 201]
        token = reg_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Step 2: Get current user
        me_response = client.get("/api/auth/me", headers=headers)
        assert me_response.status_code == 200

        # Step 3: List chats
        chats_response = client.get("/api/chats", headers=headers)
        assert chats_response.status_code == 200

        # Step 4: Get messages for first chat (demo mode shows all)
        chats_demo = client.get("/api/chats")
        if chats_demo.json()["chats"]:
            chat_id = chats_demo.json()["chats"][0]["id"]

            # Step 5: Get messages
            msgs_response = client.get(f"/api/messages/chat/{chat_id}")
            assert msgs_response.status_code == 200

            # Step 6: Send message
            send_response = client.post("/api/messages", json={
                "chat_id": chat_id,
                "text": "Integration test message"
            })
            assert send_response.status_code in [200, 201]

            # Step 7: Mark as read
            read_response = client.post(f"/api/chats/{chat_id}/mark-read")
            assert read_response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
