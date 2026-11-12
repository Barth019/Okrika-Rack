
import logging
from datetime import datetime, timezone

from app.models import db, ScheduledPost, BufferConnection
from app.buffer_client import BufferAPIError, get_buffer_post
from app.token_manager import get_valid_buffer_access_token


logger = logging.getLogger(__name__)


def parse_buffer_timestamp(value):
    """Convert a Buffer ISO timestamp into a timezone-aware datetime."""

    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    except (ValueError, TypeError, AttributeError):
        logger.warning("Buffer returned an invalid publication timestamp.")
        return None


def sync_seller_posts(seller_id):
    """
    Synchronize scheduled posts belonging to one seller with Buffer.

    Only local posts currently marked as scheduled are checked.
    This function never creates or deletes Buffer posts.
    """

    results = {
        "checked": 0,
        "published": 0,
        "failed": 0,
        "unchanged": 0,
        "errors": 0,
    }

    posts = ScheduledPost.query.filter_by(
        seller_id=seller_id,
        status="scheduled",
    ).order_by(
        ScheduledPost.created_at.asc()
    ).all()

    for post in posts:

        # A scheduled post must have a Buffer post ID.
        if not post.buffer_post_id:
            results["errors"] += 1

            logger.error(
                "Scheduled post %s has no Buffer post ID.",
                post.id,
            )
            continue

        connection = BufferConnection.query.filter_by(
            id=post.buffer_connection_id,
            seller_id=seller_id,
        ).first()

        if connection is None:
            results["errors"] += 1

            logger.error(
                "No Buffer connection found for scheduled post %s.",
                post.id,
            )
            continue

        try:
            access_token = get_valid_buffer_access_token(
                connection
            )

            buffer_post = get_buffer_post(
                access_token,
                post.buffer_post_id,
            )

            results["checked"] += 1

            buffer_status = buffer_post["status"].lower()

            if buffer_status == "sent":

                published_at = parse_buffer_timestamp(
                    buffer_post.get("sentAt")
                )

                post.status = "published"
                post.published_at = published_at
                post.error_message = None

                db.session.commit()

                results["published"] += 1

                logger.info(
                    "Post %s synchronized as published.",
                    post.id,
                )

            elif buffer_status == "error":

                buffer_error = buffer_post.get("error")

                if isinstance(buffer_error, dict):
                    error_message = buffer_error.get("message")
                else:
                    error_message = None

                post.status = "failed"
                post.error_message = (
                    error_message or "Buffer reported a publishing failure."
                )

                db.session.commit()

                results["failed"] += 1

                logger.warning(
                    "Post %s synchronized as failed.",
                    post.id,
                )

            elif buffer_status == "scheduled":

                results["unchanged"] += 1

            else:
                results["unchanged"] += 1

                logger.warning(
                    "Post %s has an unrecognized Buffer status: %s",
                    post.id,
                    buffer_status,
                )

        except Exception:
            db.session.rollback()

            results["errors"] += 1

            logger.exception(
                "Could not synchronize scheduled post %s.",
                post.id,
            )

    return results
