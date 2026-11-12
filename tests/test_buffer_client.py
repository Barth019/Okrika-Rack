
import pytest

import app.buffer_client as buffer_client


TEST_IMAGE_URL = (
    "https://res.cloudinary.com/demo/image/upload/sample.jpg"
)


def test_instagram_post_sends_correct_payload(monkeypatch):
    captured = {}

    def mock_graphql_request(access_token, query, variables=None):
        captured["access_token"] = access_token
        captured["query"] = query
        captured["variables"] = variables

        return {
            "createPost": {
                "post": {
                    "id": "mock-instagram-post-123",
                    "text": "Vintage Denim Jacket",
                    "dueAt": "2099-01-01T11:00:00Z",
                }
            }
        }

    monkeypatch.setattr(
        buffer_client,
        "buffer_graphql_request",
        mock_graphql_request,
    )

    result = buffer_client.create_buffer_post(
        access_token="mock-access-token",
        channel_id="test-instagram-channel",
        text="Vintage Denim Jacket",
        due_at="2099-01-01T11:00:00Z",
        image_url=TEST_IMAGE_URL,
        channel_service="instagram",
    )

    post_input = captured["variables"]["input"]

    assert result["id"] == "mock-instagram-post-123"
    assert captured["access_token"] == "mock-access-token"

    assert post_input["text"] == "Vintage Denim Jacket"
    assert post_input["channelId"] == "test-instagram-channel"
    assert post_input["dueAt"] == "2099-01-01T11:00:00Z"

    assert post_input["assets"] == [
        {
            "image": {
                "url": TEST_IMAGE_URL,
            }
        }
    ]

    assert post_input["metadata"] == {
        "instagram": {
            "type": "post",
            "shouldShareToFeed": True,
        }
    }

    assert post_input["needsApproval"] is False


def test_instagram_post_without_image_is_rejected(monkeypatch):
    def unexpected_request(*args, **kwargs):
        raise AssertionError(
            "Buffer must not be called without an Instagram image."
        )

    monkeypatch.setattr(
        buffer_client,
        "buffer_graphql_request",
        unexpected_request,
    )

    with pytest.raises(
        ValueError,
        match="Instagram posts require a product image",
    ):
        buffer_client.create_buffer_post(
            access_token="mock-access-token",
            channel_id="test-instagram-channel",
            text="Test caption",
            due_at="2099-01-01T11:00:00Z",
            image_url=None,
            channel_service="instagram",
        )


def test_non_https_image_url_is_rejected(monkeypatch):
    def unexpected_request(*args, **kwargs):
        raise AssertionError(
            "Buffer must not receive an insecure image URL."
        )

    monkeypatch.setattr(
        buffer_client,
        "buffer_graphql_request",
        unexpected_request,
    )

    with pytest.raises(
        ValueError,
        match="public HTTPS URL",
    ):
        buffer_client.create_buffer_post(
            access_token="mock-access-token",
            channel_id="test-channel",
            text="Test caption",
            due_at="2099-01-01T11:00:00Z",
            image_url="http://example.com/image.jpg",
            channel_service="instagram",
        )


# --------------------------------------------------
# BUFFER POST LOOKUP TESTS
# --------------------------------------------------

def test_get_buffer_post_returns_post_details(monkeypatch):
    captured = {}

    mock_post = {
        "id": "mock-buffer-post-123",
        "status": "sent",
        "sentAt": "2099-01-01T11:00:00Z",
        "dueAt": "2099-01-01T10:00:00Z",
        "externalLink": "https://instagram.com/p/example",
        "channelId": "mock-channel-123",
        "channelService": "instagram",
        "error": None,
    }

    def mock_graphql_request(access_token, query, variables=None):
        captured["access_token"] = access_token
        captured["query"] = query
        captured["variables"] = variables

        return {"post": mock_post}

    monkeypatch.setattr(
        buffer_client,
        "buffer_graphql_request",
        mock_graphql_request,
    )

    result = buffer_client.get_buffer_post(
        "mock-access-token",
        "mock-buffer-post-123",
    )

    assert result == mock_post
    assert result["status"] == "sent"
    assert result["sentAt"] == "2099-01-01T11:00:00Z"

    assert captured["access_token"] == "mock-access-token"

    assert captured["variables"] == {
        "input": {
            "id": "mock-buffer-post-123",
        }
    }

    assert "GetPost" in captured["query"]


def test_get_buffer_post_rejects_missing_access_token():
    with pytest.raises(
        ValueError,
        match="Buffer access token is required",
    ):
        buffer_client.get_buffer_post(
            None,
            "mock-buffer-post-123",
        )


def test_get_buffer_post_rejects_missing_post_id():
    with pytest.raises(
        ValueError,
        match="Buffer post ID is required",
    ):
        buffer_client.get_buffer_post(
            "mock-access-token",
            "",
        )


def test_get_buffer_post_rejects_invalid_response(monkeypatch):
    def mock_graphql_request(*args, **kwargs):
        return {"post": None}

    monkeypatch.setattr(
        buffer_client,
        "buffer_graphql_request",
        mock_graphql_request,
    )

    with pytest.raises(
        buffer_client.BufferAPIError,
        match="invalid post lookup response",
    ):
        buffer_client.get_buffer_post(
            "mock-access-token",
            "mock-buffer-post-123",
        )


def test_get_buffer_post_rejects_unexpected_post_id(monkeypatch):
    def mock_graphql_request(*args, **kwargs):
        return {
            "post": {
                "id": "different-post-456",
                "status": "sent",
            }
        }

    monkeypatch.setattr(
        buffer_client,
        "buffer_graphql_request",
        mock_graphql_request,
    )

    with pytest.raises(
        buffer_client.BufferAPIError,
        match="unexpected post ID",
    ):
        buffer_client.get_buffer_post(
            "mock-access-token",
            "mock-buffer-post-123",
        )


def test_get_buffer_post_rejects_missing_status(monkeypatch):
    def mock_graphql_request(*args, **kwargs):
        return {
            "post": {
                "id": "mock-buffer-post-123",
            }
        }

    monkeypatch.setattr(
        buffer_client,
        "buffer_graphql_request",
        mock_graphql_request,
    )

    with pytest.raises(
        buffer_client.BufferAPIError,
        match="without a status",
    ):
        buffer_client.get_buffer_post(
            "mock-access-token",
            "mock-buffer-post-123",
        )
