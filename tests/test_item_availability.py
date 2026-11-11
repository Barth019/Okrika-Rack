from datetime import datetime, timezone

import app.items as items_module
from app.models import db, Seller, Item, ScheduledPost, BufferConnection


def create_seller_and_item():
    seller = Seller(
        email="test@example.com",
        password_hash="test-password-hash",
    )
    db.session.add(seller)
    db.session.flush()

    item = Item(
        seller_id=seller.id,
        name="Vintage Denim Jacket",
        price=15000,
        condition="excellent",
        availability="available",
    )
    db.session.add(item)
    db.session.flush()

    return seller, item


def login_test_seller(client, seller_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(seller_id)
        session["_fresh"] = True


def create_buffer_connection(seller_id):
    connection = BufferConnection(
        seller_id=seller_id,
        buffer_account_id="test-buffer-account",
        access_token_encrypted="test-access-token",
        refresh_token_encrypted="test-refresh-token",
    )
    db.session.add(connection)
    db.session.flush()

    return connection


def create_scheduled_post(seller, item, connection, status, post_id=None):
    post = ScheduledPost(
        seller_id=seller.id,
        item_id=item.id,
        buffer_connection_id=connection.id,
        buffer_channel_id="test-channel",
        buffer_post_id=post_id,
        caption="Test product promotion",
        scheduled_at=datetime.now(timezone.utc),
        status=status,
    )
    db.session.add(post)
    db.session.flush()

    return post


def test_item_can_be_marked_sold_without_active_posts(client, app):
    with app.app_context():
        seller, item = create_seller_and_item()
        item_id = item.id
        seller_id = seller.id
        db.session.commit()

    login_test_seller(client, seller_id)

    response = client.post(
        f"/items/{item_id}/availability",
        data={"availability": "sold"},
    )

    assert response.status_code == 302

    with app.app_context():
        item = db.session.get(Item, item_id)
        assert item.availability == "sold"


def test_pending_post_is_cancelled_locally(client, app):
    with app.app_context():
        seller, item = create_seller_and_item()
        connection = create_buffer_connection(seller.id)

        post = create_scheduled_post(
            seller,
            item,
            connection,
            status="pending",
        )

        item_id = item.id
        seller_id = seller.id
        post_id = post.id
        db.session.commit()

    login_test_seller(client, seller_id)

    response = client.post(
        f"/items/{item_id}/availability",
        data={"availability": "sold"},
    )

    assert response.status_code == 302

    with app.app_context():
        item = db.session.get(Item, item_id)
        post = db.session.get(ScheduledPost, post_id)

        assert item.availability == "sold"
        assert post.status == "cancelled"


def test_scheduled_post_is_deleted_through_buffer(client, app, monkeypatch):
    with app.app_context():
        seller, item = create_seller_and_item()
        connection = create_buffer_connection(seller.id)

        post = create_scheduled_post(
            seller,
            item,
            connection,
            status="scheduled",
            post_id="buffer-post-123",
        )

        item_id = item.id
        seller_id = seller.id
        post_id = post.id
        db.session.commit()

    login_test_seller(client, seller_id)

    monkeypatch.setattr(
        items_module,
        "get_valid_buffer_access_token",
        lambda connection: "mock-access-token",
    )

    monkeypatch.setattr(
        items_module,
        "delete_buffer_post",
        lambda token, buffer_post_id: buffer_post_id,
    )

    response = client.post(
        f"/items/{item_id}/availability",
        data={"availability": "sold"},
    )

    assert response.status_code == 302

    with app.app_context():
        item = db.session.get(Item, item_id)
        post = db.session.get(ScheduledPost, post_id)

        assert item.availability == "sold"
        assert post.status == "cancelled"


def test_buffer_deletion_failure_keeps_item_available(
    client, app, monkeypatch
):
    with app.app_context():
        seller, item = create_seller_and_item()
        connection = create_buffer_connection(seller.id)

        post = create_scheduled_post(
            seller,
            item,
            connection,
            status="scheduled",
            post_id="buffer-post-456",
        )

        item_id = item.id
        seller_id = seller.id
        post_id = post.id
        db.session.commit()

    login_test_seller(client, seller_id)

    monkeypatch.setattr(
        items_module,
        "get_valid_buffer_access_token",
        lambda connection: "mock-access-token",
    )

    def failed_deletion(token, buffer_post_id):
        raise items_module.BufferAPIError("Mock Buffer failure")

    monkeypatch.setattr(
        items_module,
        "delete_buffer_post",
        failed_deletion,
    )

    response = client.post(
        f"/items/{item_id}/availability",
        data={"availability": "sold"},
    )

    assert response.status_code == 302

    with app.app_context():
        item = db.session.get(Item, item_id)
        post = db.session.get(ScheduledPost, post_id)

        assert item.availability == "available"
        assert post.status == "scheduled"

def test_scheduled_post_without_buffer_id_blocks_sale(client, app):
    with app.app_context():
        seller, item = create_seller_and_item()
        connection = create_buffer_connection(seller.id)

        post = create_scheduled_post(
            seller,
            item,
            connection,
            status="scheduled",
            post_id=None,
        )

        item_id = item.id
        seller_id = seller.id
        post_id = post.id
        db.session.commit()

    login_test_seller(client, seller_id)

    response = client.post(
        f"/items/{item_id}/availability",
        data={"availability": "sold"},
    )

    assert response.status_code == 302

    with app.app_context():
        item = db.session.get(Item, item_id)
        post = db.session.get(ScheduledPost, post_id)

        assert item.availability == "available"
        assert post.status == "scheduled"
