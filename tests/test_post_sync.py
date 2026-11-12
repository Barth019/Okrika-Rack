
from datetime import datetime, timezone

import app.post_sync as post_sync

import app.scheduler as scheduler

from app.models import db, ScheduledPost

from test_item_availability import (
    create_seller_and_item,
    create_buffer_connection,
    create_scheduled_post,
    login_test_seller,
)


def test_sync_marks_sent_post_as_published(client, app, monkeypatch):
    with app.app_context():
        seller, item = create_seller_and_item()
        connection = create_buffer_connection(seller.id)

        post = create_scheduled_post(
            seller,
            item,
            connection,
            "scheduled",
            post_id="sync-sent-post",
        )

        post_id = post.id
        seller_id = seller.id

        db.session.commit()

        monkeypatch.setattr(
            post_sync,
            "get_valid_buffer_access_token",
            lambda connection: "mock-access-token",
        )

        monkeypatch.setattr(
            post_sync,
            "get_buffer_post",
            lambda token, buffer_id: {
                "id": buffer_id,
                "status": "sent",
                "sentAt": "2026-11-11T10:30:00Z",
                "error": None,
            },
        )

        result = post_sync.sync_seller_posts(seller_id)

        updated_post = db.session.get(ScheduledPost, post_id)

        assert result["checked"] == 1
        assert result["published"] == 1
        assert result["failed"] == 0
        assert updated_post.status == "published"
        assert updated_post.published_at is not None
        assert updated_post.published_at == datetime(
            2026, 11, 11, 10, 30,
        )
        assert updated_post.error_message is None


def test_sync_marks_error_post_as_failed(client, app, monkeypatch):
    with app.app_context():
        seller, item = create_seller_and_item()
        connection = create_buffer_connection(seller.id)

        post = create_scheduled_post(
            seller,
            item,
            connection,
            "scheduled",
            post_id="sync-error-post",
        )

        post_id = post.id
        seller_id = seller.id

        db.session.commit()

        monkeypatch.setattr(
            post_sync,
            "get_valid_buffer_access_token",
            lambda connection: "mock-access-token",
        )

        monkeypatch.setattr(
            post_sync,
            "get_buffer_post",
            lambda token, buffer_id: {
                "id": buffer_id,
                "status": "error",
                "sentAt": None,
                "error": {
                    "message": "Instagram publishing failed.",
                    "supportUrl": None,
                },
            },
        )

        result = post_sync.sync_seller_posts(seller_id)

        updated_post = db.session.get(ScheduledPost, post_id)

        assert result["checked"] == 1
        assert result["failed"] == 1
        assert updated_post.status == "failed"
        assert updated_post.error_message == (
            "Instagram publishing failed."
        )


def test_sync_keeps_scheduled_posts_unchanged(
    client, app, monkeypatch
):
    with app.app_context():
        seller, item = create_seller_and_item()
        connection = create_buffer_connection(seller.id)

        post = create_scheduled_post(
            seller,
            item,
            connection,
            "scheduled",
            post_id="sync-still-scheduled",
        )

        post_id = post.id
        seller_id = seller.id

        db.session.commit()

        monkeypatch.setattr(
            post_sync,
            "get_valid_buffer_access_token",
            lambda connection: "mock-access-token",
        )

        monkeypatch.setattr(
            post_sync,
            "get_buffer_post",
            lambda token, buffer_id: {
                "id": buffer_id,
                "status": "scheduled",
                "sentAt": None,
                "error": None,
            },
        )

        result = post_sync.sync_seller_posts(seller_id)

        updated_post = db.session.get(ScheduledPost, post_id)

        assert result["checked"] == 1
        assert result["unchanged"] == 1
        assert updated_post.status == "scheduled"
        assert updated_post.published_at is None


def test_sync_does_not_reactivate_cancelled_posts(
    client, app, monkeypatch
):
    with app.app_context():
        seller, item = create_seller_and_item()
        connection = create_buffer_connection(seller.id)

        post = create_scheduled_post(
            seller,
            item,
            connection,
            "cancelled",
            post_id="sync-cancelled-post",
        )

        post_id = post.id
        seller_id = seller.id

        db.session.commit()

        def unexpected_buffer_request(*args, **kwargs):
            raise AssertionError(
                "Cancelled posts must not be synchronized."
            )

        monkeypatch.setattr(
            post_sync,
            "get_buffer_post",
            unexpected_buffer_request,
        )

        result = post_sync.sync_seller_posts(seller_id)

        updated_post = db.session.get(ScheduledPost, post_id)

        assert result["checked"] == 0
        assert updated_post.status == "cancelled"


def test_sync_handles_buffer_api_failure(client, app, monkeypatch):
    with app.app_context():
        seller, item = create_seller_and_item()
        connection = create_buffer_connection(seller.id)

        post = create_scheduled_post(
            seller,
            item,
            connection,
            "scheduled",
            post_id="sync-api-failure",
        )

        post_id = post.id
        seller_id = seller.id

        db.session.commit()

        monkeypatch.setattr(
            post_sync,
            "get_valid_buffer_access_token",
            lambda connection: "mock-access-token",
        )

        def failed_buffer_request(*args, **kwargs):
            raise post_sync.BufferAPIError(
                "Mock Buffer API failure."
            )

        monkeypatch.setattr(
            post_sync,
            "get_buffer_post",
            failed_buffer_request,
        )

        result = post_sync.sync_seller_posts(seller_id)

        updated_post = db.session.get(ScheduledPost, post_id)

        assert result["errors"] == 1
        assert result["published"] == 0
        assert updated_post.status == "scheduled"


def test_sync_does_not_process_another_sellers_posts(
    client, app, monkeypatch
):
    with app.app_context():
        seller_one, item_one = create_seller_and_item()

        connection_one = create_buffer_connection(
            seller_one.id,
            buffer_account_id="first-test-buffer-account",
        )

        post_one = create_scheduled_post(
            seller_one,
            item_one,
            connection_one,
            "scheduled",
            post_id="sync-seller-one",
        )

        seller_two, item_two = create_seller_and_item(
            email="second-test@example.com"
        )

        connection_two = create_buffer_connection(
            seller_two.id,
            buffer_account_id="second-test-buffer-account",
        )

        post_two = create_scheduled_post(
            seller_two,
            item_two,
            connection_two,
            "scheduled",
            post_id="sync-seller-two",
        )

        seller_one_id = seller_one.id
        post_one_id = post_one.id
        post_two_id = post_two.id

        db.session.commit()

        monkeypatch.setattr(
            post_sync,
            "get_valid_buffer_access_token",
            lambda connection: "mock-access-token",
        )

        monkeypatch.setattr(
            post_sync,
            "get_buffer_post",
            lambda token, buffer_id: {
                "id": buffer_id,
                "status": "sent",
                "sentAt": "2026-11-11T10:30:00Z",
                "error": None,
            },
        )

        result = post_sync.sync_seller_posts(seller_one_id)

        updated_post_one = db.session.get(
            ScheduledPost, post_one_id
        )
        updated_post_two = db.session.get(
            ScheduledPost, post_two_id
        )

        assert result["checked"] == 1
        assert result["published"] == 1

        assert updated_post_one.status == "published"
        assert updated_post_two.status == "scheduled"


def test_sync_route_requires_login(client):
    response = client.post(
        "/scheduler/sync",
        data={"status": "scheduled"},
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_sync_route_runs_for_authenticated_seller(
    client, app, monkeypatch
):
    with app.app_context():
        seller, item = create_seller_and_item()
        seller_id = seller.id

        db.session.commit()

        login_test_seller(client, seller_id)

        calls = []

        def mock_sync_seller_posts(received_seller_id):
            calls.append(received_seller_id)

            return {
                "checked": 3,
                "published": 1,
                "failed": 1,
                "unchanged": 1,
                "errors": 0,
            }

        monkeypatch.setattr(
            scheduler,
            "sync_seller_posts",
            mock_sync_seller_posts,
        )

        response = client.post(
            "/scheduler/sync",
            data={"status": "scheduled"},
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith(
            "/scheduler/history?status=scheduled"
        )

        assert calls == [seller_id]

        with client.session_transaction() as session:
            flashes = session.get("_flashes", [])

        assert any(
            "Checked: 3" in message
            for category, message in flashes
        )


def test_sync_route_handles_unexpected_errors(
    client, app, monkeypatch
):
    with app.app_context():
        seller, item = create_seller_and_item()
        seller_id = seller.id

        db.session.commit()

        login_test_seller(client, seller_id)

        def mock_sync_failure(seller_id):
            raise RuntimeError("Mock synchronization failure.")

        monkeypatch.setattr(
            scheduler,
            "sync_seller_posts",
            mock_sync_failure,
        )

        response = client.post(
            "/scheduler/sync",
            data={"status": "published"},
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith(
            "/scheduler/history?status=published"
        )

        with client.session_transaction() as session:
            flashes = session.get("_flashes", [])

        assert any(
            "couldn't synchronize your posts" in message
            for category, message in flashes
        )
