
from app.models import db, Seller, Item, BufferConnection, ScheduledPost

from test_item_availability import (
    create_seller_and_item,
    create_buffer_connection,
    create_scheduled_post,
    login_test_seller,
)


def test_post_history_displays_sellers_own_posts(client, app):
    with app.app_context():
        seller, item = create_seller_and_item()
        connection = create_buffer_connection(seller.id)

        create_scheduled_post(
            seller, item, connection, "scheduled",
            post_id="history-post-1",
        )

        create_scheduled_post(
            seller, item, connection, "cancelled",
            post_id=None,
        )

        seller_id = seller.id
        db.session.commit()

    login_test_seller(client, seller_id)

    response = client.get("/scheduler/history")

    assert response.status_code == 200
    assert b"Post history" in response.data
    assert b"Vintage Denim Jacket" in response.data
    assert b"Scheduled" in response.data
    assert b"Cancelled" in response.data


def test_post_history_does_not_show_another_sellers_posts(
    client, app
):
    with app.app_context():
        seller_one, item_one = create_seller_and_item()
        connection_one = create_buffer_connection(seller_one.id)

        create_scheduled_post(
            seller_one,
            item_one,
            connection_one,
            "scheduled",
            post_id="seller-one-post",
        )

        seller_two = Seller(
            email="another-seller@example.com",
            password_hash="test-password-hash",
        )
        db.session.add(seller_two)
        db.session.flush()

        item_two = Item(
            seller_id=seller_two.id,
            name="Another Seller's Shoes",
            price=20000,
            condition="good",
            availability="available",
        )
        db.session.add(item_two)
        db.session.flush()

        connection_two = BufferConnection(
            seller_id=seller_two.id,
            buffer_account_id="another-buffer-account",
            access_token_encrypted="test-access-token",
            refresh_token_encrypted="test-refresh-token",
        )
        db.session.add(connection_two)
        db.session.flush()

        create_scheduled_post(
            seller_two,
            item_two,
            connection_two,
            "published",
            post_id="seller-two-post",
        )

        seller_one_id = seller_one.id
        db.session.commit()

    login_test_seller(client, seller_one_id)

    response = client.get("/scheduler/history")

    assert response.status_code == 200
    assert b"Vintage Denim Jacket" in response.data
    assert b"Another Seller" not in response.data


def test_post_history_filters_by_status(client, app):
    statuses = [
        "pending",
        "scheduled",
        "published",
        "cancelled",
        "failed",
    ]

    with app.app_context():
        seller, item = create_seller_and_item()
        connection = create_buffer_connection(seller.id)

        for index, status in enumerate(statuses):
            create_scheduled_post(
                seller,
                item,
                connection,
                status,
                post_id=f"filter-post-{index}",
            )

        seller_id = seller.id
        db.session.commit()

    login_test_seller(client, seller_id)

    for status in statuses:
        response = client.get(
            f"/scheduler/history?status={status}"
        )

        assert response.status_code == 200
        assert status.title().encode() in response.data

        with app.app_context():
            matching_posts = ScheduledPost.query.filter_by(
                seller_id=seller_id,
                status=status,
            ).count()

            assert matching_posts == 1


def test_invalid_history_filter_defaults_to_all(client, app):
    with app.app_context():
        seller, item = create_seller_and_item()
        connection = create_buffer_connection(seller.id)

        create_scheduled_post(
            seller, item, connection, "scheduled",
            post_id="valid-filter-post",
        )

        seller_id = seller.id
        db.session.commit()

    login_test_seller(client, seller_id)

    response = client.get(
        "/scheduler/history?status=unknown"
    )

    assert response.status_code == 200
    assert b"Vintage Denim Jacket" in response.data


def test_post_history_requires_authentication(client):
    response = client.get(
        "/scheduler/history",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

# WhatsApp ordering link tests

def test_build_whatsapp_link_generates_correct_product_link():
    from urllib.parse import parse_qs, urlparse
    from app.scheduler import build_whatsapp_link

    link = build_whatsapp_link("2348012345678", "Vintage Denim Jacket")
    parsed = urlparse(link)

    assert parsed.scheme == "https"
    assert parsed.netloc == "wa.me"
    assert parsed.path == "/2348012345678"
    assert parse_qs(parsed.query)["text"][0] == (
        "Hello! I'm interested in buying the Vintage Denim Jacket. "
        "Is it still available?"
    )


def test_build_whatsapp_link_encodes_special_characters():
    from urllib.parse import parse_qs, urlparse
    from app.scheduler import build_whatsapp_link

    link = build_whatsapp_link("2348012345678", "Men's Shirt & Trousers")
    message = parse_qs(urlparse(link).query)["text"][0]

    assert "Men's Shirt & Trousers" in message


def test_build_whatsapp_link_returns_none_without_phone_number():
    from app.scheduler import build_whatsapp_link

    assert build_whatsapp_link(None, "Test Item") is None
    assert build_whatsapp_link("", "Test Item") is None


def test_post_history_shows_whatsapp_link_for_available_product(client, app):
    with app.app_context():
        seller, item = create_seller_and_item()
        seller.whatsapp_number = "2348012345678"
        connection = create_buffer_connection(seller.id)

        create_scheduled_post(
            seller, item, connection, "scheduled",
            post_id="whatsapp-available-post",
        )

        seller_id = seller.id
        db.session.commit()

    login_test_seller(client, seller_id)
    response = client.get("/scheduler/history")

    assert response.status_code == 200
    assert b"WhatsApp ordering link" in response.data
    assert b"Copy WhatsApp link" in response.data
    assert b"wa.me/2348012345678" in response.data


def test_post_history_hides_whatsapp_link_for_sold_product(client, app):
    with app.app_context():
        seller, item = create_seller_and_item()
        seller.whatsapp_number = "2348012345678"
        item.availability = "sold"
        connection = create_buffer_connection(seller.id)

        create_scheduled_post(
            seller, item, connection, "cancelled",
            post_id=None,
        )

        seller_id = seller.id
        db.session.commit()

    login_test_seller(client, seller_id)
    response = client.get("/scheduler/history")

    assert response.status_code == 200
    assert b"WhatsApp ordering link unavailable" in response.data
    assert b"marked as sold" in response.data
    assert b"wa.me/2348012345678" not in response.data
    assert b"data-copy-text=" not in response.data
