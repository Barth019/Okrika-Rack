
from datetime import datetime, timezone

import app.scheduler as scheduler_module

from app.models import db, Item, ScheduledPost, BufferConnection, Seller

from test_item_availability import (
    create_seller_and_item,
    login_test_seller,
    create_buffer_connection,
)


def prepare_scheduling_test(app):
    with app.app_context():
        seller, item = create_seller_and_item()
        connection = create_buffer_connection(seller.id)

        seller_id = seller.id
        item_id = item.id
        connection_id = connection.id

        db.session.commit()

    return seller_id, item_id, connection_id


def mock_buffer_account(monkeypatch):
    monkeypatch.setattr(
        scheduler_module,
        "get_valid_buffer_access_token",
        lambda connection: "mock-access-token",
    )

    monkeypatch.setattr(
        scheduler_module,
        "get_buffer_organizations",
        lambda token: [
            {"id": "test-org", "name": "Test Organization"}
        ],
    )

    monkeypatch.setattr(
        scheduler_module,
        "get_buffer_channels",
        lambda token, organization_id: [
            {
                "id": "test-channel",
                "name": "Instagram",
                "displayName": "Test Instagram",
                "service": "instagram",
                "isDisconnected": False,
                "isLocked": False,
            }
        ],
    )


def test_successfully_schedules_post(client, app, monkeypatch):
    seller_id, item_id, connection_id = prepare_scheduling_test(app)

    login_test_seller(client, seller_id)
    mock_buffer_account(monkeypatch)

    def mock_create_post(token, channel_id, text, due_at):
        assert token == "mock-access-token"
        assert channel_id == "test-channel"
        assert text == "Vintage Denim Jacket promotion"
        assert due_at.endswith("Z")

        return {"id": "mock-buffer-post-123"}

    monkeypatch.setattr(
        scheduler_module,
        "create_buffer_post",
        mock_create_post,
    )

    response = client.post(
        "/scheduler/new",
        query_string={
            "item_id": item_id,
            "organization_id": "test-org",
        },
        data={
            "organization_id": "test-org",
            "channel_id": "test-channel",
            "caption": "Vintage Denim Jacket promotion",
            "scheduled_at": "2099-01-01T12:00",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.location.endswith("/items/")

    with app.app_context():
        post = ScheduledPost.query.filter_by(
            buffer_post_id="mock-buffer-post-123"
        ).first()

        assert post is not None
        assert post.item_id == item_id
        assert post.seller_id == seller_id
        assert post.buffer_connection_id == connection_id
        assert post.status == "scheduled"
        assert post.buffer_channel_id == "test-channel"


def test_past_publication_date_is_rejected(
    client, app, monkeypatch
):
    seller_id, item_id, connection_id = prepare_scheduling_test(app)

    login_test_seller(client, seller_id)
    mock_buffer_account(monkeypatch)

    def unexpected_create(*args, **kwargs):
        raise AssertionError("Buffer must not receive a past-dated post.")

    monkeypatch.setattr(
        scheduler_module,
        "create_buffer_post",
        unexpected_create,
    )

    response = client.post(
        "/scheduler/new",
        query_string={
            "item_id": item_id,
            "organization_id": "test-org",
        },
        data={
            "organization_id": "test-org",
            "channel_id": "test-channel",
            "caption": "Test caption",
            "scheduled_at": "2020-01-01T12:00",
        },
    )

    assert response.status_code == 200
    assert b"Choose a publication time in the future." in response.data

    with app.app_context():
        assert ScheduledPost.query.count() == 0


def test_invalid_channel_is_rejected(
    client, app, monkeypatch
):
    seller_id, item_id, connection_id = prepare_scheduling_test(app)

    login_test_seller(client, seller_id)
    mock_buffer_account(monkeypatch)

    def unexpected_create(*args, **kwargs):
        raise AssertionError("Buffer must not receive an invalid channel.")

    monkeypatch.setattr(
        scheduler_module,
        "create_buffer_post",
        unexpected_create,
    )

    response = client.post(
        "/scheduler/new",
        query_string={
            "item_id": item_id,
            "organization_id": "test-org",
        },
        data={
            "organization_id": "test-org",
            "channel_id": "invalid-channel",
            "caption": "Test caption",
            "scheduled_at": "2099-01-01T12:00",
        },
    )

    assert response.status_code == 200
    assert b"Please select a valid Buffer channel." in response.data

    with app.app_context():
        assert ScheduledPost.query.count() == 0


def test_empty_caption_is_rejected(
    client, app, monkeypatch
):
    seller_id, item_id, connection_id = prepare_scheduling_test(app)

    login_test_seller(client, seller_id)
    mock_buffer_account(monkeypatch)

    def unexpected_create(*args, **kwargs):
        raise AssertionError("Buffer must not receive an empty caption.")

    monkeypatch.setattr(
        scheduler_module,
        "create_buffer_post",
        unexpected_create,
    )

    response = client.post(
        "/scheduler/new",
        query_string={
            "item_id": item_id,
            "organization_id": "test-org",
        },
        data={
            "organization_id": "test-org",
            "channel_id": "test-channel",
            "caption": "   ",
            "scheduled_at": "2099-01-01T12:00",
        },
    )

    assert response.status_code == 200
    assert b"Please enter a post caption." in response.data

    with app.app_context():
        assert ScheduledPost.query.count() == 0


def test_buffer_api_failure_does_not_save_post(
    client, app, monkeypatch
):
    seller_id, item_id, connection_id = prepare_scheduling_test(app)

    login_test_seller(client, seller_id)
    mock_buffer_account(monkeypatch)

    def failed_create(*args, **kwargs):
        raise scheduler_module.BufferAPIError(
            "Mock Buffer API failure"
        )

    monkeypatch.setattr(
        scheduler_module,
        "create_buffer_post",
        failed_create,
    )

    response = client.post(
        "/scheduler/new",
        query_string={
            "item_id": item_id,
            "organization_id": "test-org",
        },
        data={
            "organization_id": "test-org",
            "channel_id": "test-channel",
            "caption": "Test caption",
            "scheduled_at": "2099-01-01T12:00",
        },
    )

    assert response.status_code == 200
    assert b"Buffer could not schedule your post." in response.data

    with app.app_context():
        assert ScheduledPost.query.count() == 0

def test_database_failure_triggers_buffer_post_deletion(
    client, app, monkeypatch
):
    seller_id, item_id, connection_id = prepare_scheduling_test(app)

    login_test_seller(client, seller_id)
    mock_buffer_account(monkeypatch)

    created_buffer_posts = []
    deleted_buffer_posts = []

    def mock_create_post(token, channel_id, text, due_at):
        created_buffer_posts.append("mock-buffer-post-789")
        return {"id": "mock-buffer-post-789"}

    def mock_delete_post(token, post_id):
        deleted_buffer_posts.append(post_id)
        return post_id

    monkeypatch.setattr(
        scheduler_module,
        "create_buffer_post",
        mock_create_post,
    )

    monkeypatch.setattr(
        scheduler_module,
        "delete_buffer_post",
        mock_delete_post,
    )

    # Simulate a database commit failure.
    session = db.session()

    def failed_commit():
        raise RuntimeError("Simulated database failure")

    monkeypatch.setattr(
        session,
        "commit",
        failed_commit,
    )

    response = client.post(
        "/scheduler/new",
        query_string={
            "item_id": item_id,
            "organization_id": "test-org",
        },
        data={
            "organization_id": "test-org",
            "channel_id": "test-channel",
            "caption": "Test recovery caption",
            "scheduled_at": "2099-01-01T12:00",
        },
    )

    assert response.status_code == 200

    # Buffer creation happened.
    assert created_buffer_posts == ["mock-buffer-post-789"]

    # Okrika-Rack attempted to delete the Buffer post.
    assert deleted_buffer_posts == ["mock-buffer-post-789"]

    # The failed database operation left no scheduled post record.
    db.session.rollback()

    with app.app_context():
        post = ScheduledPost.query.filter_by(
            buffer_post_id="mock-buffer-post-789"
        ).first()

        assert post is None


def test_duplicate_scheduling_is_blocked(
    client, app, monkeypatch
):
    seller_id, item_id, connection_id = prepare_scheduling_test(app)

    with app.app_context():
        seller = db.session.get(Seller, seller_id)
        item = db.session.get(Item, item_id)
        connection = db.session.get(BufferConnection, connection_id)

        existing_post = ScheduledPost(
            seller_id=seller.id,
            item_id=item.id,
            buffer_connection_id=connection.id,
            buffer_channel_id="test-channel",
            buffer_post_id="existing-buffer-post",
            caption="Existing promotion",
            scheduled_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
            status="scheduled",
        )

        db.session.add(existing_post)
        db.session.commit()

    login_test_seller(client, seller_id)
    mock_buffer_account(monkeypatch)

    def unexpected_create(*args, **kwargs):
        raise AssertionError(
            "Buffer must not be called for a duplicate post."
        )

    monkeypatch.setattr(
        scheduler_module,
        "create_buffer_post",
        unexpected_create,
    )

    response = client.post(
        "/scheduler/new",
        query_string={
            "item_id": item_id,
            "organization_id": "test-org",
        },
        data={
            "organization_id": "test-org",
            "channel_id": "test-channel",
            "caption": "Duplicate promotion",
            "scheduled_at": "2099-01-02T12:00",
        },
    )

    assert response.status_code == 200
    assert b"This item already has a pending or scheduled post." in response.data

    with app.app_context():
        posts = ScheduledPost.query.filter_by(
            item_id=item_id,
            status="scheduled",
        ).all()

        assert len(posts) == 1
