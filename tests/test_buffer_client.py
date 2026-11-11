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


def test_instagram_post_without_image_is_rejected(
    monkeypatch,
):
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