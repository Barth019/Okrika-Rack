
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_login import current_user, login_required

from app.models import (
    db,
    Item,
    ScheduledPost,
    BufferConnection,
)

from app.buffer_client import (
    get_buffer_organizations,
    get_buffer_channels,
    create_buffer_post,
    delete_buffer_post,
    BufferAPIError,
)

from app.token_manager import get_valid_buffer_access_token
from app.post_sync import sync_seller_posts


scheduler_bp = Blueprint(
    "scheduler",
    __name__,
    url_prefix="/scheduler",
)

logger = logging.getLogger(__name__)

NIGERIA_TIMEZONE = ZoneInfo("Africa/Lagos")
MAX_CAPTION_LENGTH = 2000


def build_whatsapp_link(phone_number, item_name):
    """Build a product-specific WhatsApp ordering link."""

    if not phone_number:
        return None

    message = (
        f"Hello! I'm interested in buying the {item_name}. "
        "Is it still available?"
    )

    return (
        f"https://wa.me/{phone_number}?"
        f"{urlencode({'text': message})}"
    )


@scheduler_bp.route("/channels")
@login_required
def channels():
    """Display the logged-in seller's Buffer organizations and channels."""

    connection = BufferConnection.query.filter_by(
        seller_id=current_user.id
    ).first()

    if not connection:
        flash("Please connect your Buffer account first.", "error")
        return redirect(url_for("home"))

    organizations = []
    selected_organization = None
    channels = []

    try:
        access_token = get_valid_buffer_access_token(connection)

        organizations = get_buffer_organizations(access_token)

        organization_id = request.args.get(
            "organization_id",
            "",
        ).strip()

        if organization_id:
            selected_organization = next(
                (
                    organization
                    for organization in organizations
                    if organization.get("id") == organization_id
                ),
                None,
            )

            if not selected_organization:
                flash(
                    "Invalid Buffer organization selected.",
                    "error",
                )
                return redirect(url_for("scheduler.channels"))

            channels = get_buffer_channels(
                access_token,
                selected_organization["id"],
            )

    except (BufferAPIError, ValueError):
        logger.exception(
            "Failed to retrieve Buffer organizations or channels "
            "for seller %s.",
            current_user.id,
        )

        flash(
            "We couldn't retrieve your Buffer information. "
            "Please try again.",
            "error",
        )

    return render_template(
        "channels.html",
        organizations=organizations,
        selected_organization=selected_organization,
        channels=channels,
    )


@scheduler_bp.route("/history")
@login_required
def post_history():
    """Display the logged-in seller's scheduled post history."""

    allowed_statuses = {
        "pending",
        "scheduled",
        "published",
        "cancelled",
        "failed",
    }

    selected_status = request.args.get(
        "status",
        "all",
    ).strip().lower()

    if selected_status != "all" and selected_status not in allowed_statuses:
        selected_status = "all"

    # Retrieve only posts belonging to the logged-in seller.
    posts_query = ScheduledPost.query.filter_by(
        seller_id=current_user.id
    )

    if selected_status != "all":
        posts_query = posts_query.filter_by(
            status=selected_status
        )

    posts = (
        posts_query
        .order_by(ScheduledPost.created_at.desc())
        .all()
    )

    # Calculate post counts for the history filters.
    post_counts = {
        "all": ScheduledPost.query.filter_by(
            seller_id=current_user.id
        ).count(),
    }

    for status in allowed_statuses:
        post_counts[status] = ScheduledPost.query.filter_by(
            seller_id=current_user.id,
            status=status,
        ).count()

    # Generate product-specific WhatsApp ordering links.
    whatsapp_links = {}

    if current_user.whatsapp_number:
        whatsapp_links = {
            post.id: build_whatsapp_link(
                current_user.whatsapp_number,
                post.item.name,
            )
            for post in posts
            if post.item and post.item.availability == "available"
        }

    return render_template(
        "post_history.html",
        posts=posts,
        post_counts=post_counts,
        selected_status=selected_status,
        whatsapp_links=whatsapp_links,
    )


@scheduler_bp.route("/sync", methods=["POST"])
@login_required
def sync_posts():
    """Manually synchronize the seller's scheduled posts with Buffer."""

    selected_status = request.form.get(
        "status",
        "all",
    ).strip().lower()

    allowed_statuses = {
        "all",
        "pending",
        "scheduled",
        "published",
        "cancelled",
        "failed",
    }

    if selected_status not in allowed_statuses:
        selected_status = "all"

    try:
        results = sync_seller_posts(current_user.id)

        flash(
            (
                f"Buffer sync completed. "
                f"Checked: {results['checked']}, "
                f"Published: {results['published']}, "
                f"Failed: {results['failed']}, "
                f"Unchanged: {results['unchanged']}, "
                f"Errors: {results['errors']}."
            ),
            "success" if results["errors"] == 0 else "warning",
        )

    except Exception:
        db.session.rollback()

        logger.exception(
            "Unexpected Buffer synchronization failure "
            "for seller %s.",
            current_user.id,
        )

        flash(
            "We couldn't synchronize your posts. Please try again.",
            "error",
        )

    return redirect(
        url_for(
            "scheduler.post_history",
            status=selected_status,
        )
    )


@scheduler_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_schedule():
    """Schedule an available inventory item through Buffer."""

    item_id = request.values.get("item_id", type=int)

    if not item_id:
        flash("Please select an inventory item.", "error")
        return redirect(url_for("items.inventory"))

    item = Item.query.filter_by(
        id=item_id,
        seller_id=current_user.id,
        availability="available",
        is_deleted=False,
    ).first_or_404()

    connection = BufferConnection.query.filter_by(
        seller_id=current_user.id
    ).first()

    if not connection:
        flash("Please connect your Buffer account first.", "error")
        return redirect(url_for("home"))

    organizations = []
    channels = []

    selected_organization_id = request.values.get(
        "organization_id",
        "",
    ).strip()

    try:
        access_token = get_valid_buffer_access_token(connection)

        organizations = get_buffer_organizations(access_token)

        selected_organization = next(
            (
                organization
                for organization in organizations
                if organization.get("id") == selected_organization_id
            ),
            None,
        )

        if selected_organization_id and not selected_organization:
            flash("Invalid Buffer organization.", "error")

            return redirect(
                url_for(
                    "scheduler.new_schedule",
                    item_id=item.id,
                )
            )

        if selected_organization:
            channels = get_buffer_channels(
                access_token,
                selected_organization_id,
            )

        if request.method == "POST":

            # Prevent another active scheduled post for this item.
            existing_post = ScheduledPost.query.filter(
                ScheduledPost.seller_id == current_user.id,
                ScheduledPost.item_id == item.id,
                ScheduledPost.status.in_(["pending", "scheduled"]),
            ).first()

            if existing_post:
                flash(
                    "This item already has a pending or scheduled post. "
                    "Cancel the existing post before scheduling another.",
                    "error",
                )

                return render_template(
                    "schedule_post.html",
                    item=item,
                    organizations=organizations,
                    channels=channels,
                    selected_organization_id=selected_organization_id,
                )

            channel_id = request.form.get(
                "channel_id",
                "",
            ).strip()

            caption = request.form.get(
                "caption",
                "",
            ).strip()

            scheduled_input = request.form.get(
                "scheduled_at",
                "",
            ).strip()

            channel = next(
                (
                    channel
                    for channel in channels
                    if channel.get("id") == channel_id
                ),
                None,
            )

            channel_service = (
                channel.get("service", "").lower()
                if channel
                else ""
            )

            whatsapp_link = build_whatsapp_link(
                current_user.whatsapp_number,
                item.name,
            )

            # Instagram uses a clean caption.
            # Other platforms receive the ordering link in the caption.
            final_caption = caption

            if whatsapp_link and channel_service != "instagram":
                final_caption = (
                    f"{caption}\n\n"
                    f"To order: {whatsapp_link}"
                )

            if not channel:
                flash(
                    "Please select a valid Buffer channel.",
                    "error",
                )

            elif (
                channel.get("isDisconnected")
                or channel.get("isLocked")
            ):
                flash(
                    "This Buffer channel cannot publish posts.",
                    "error",
                )

            elif (
                channel_service == "instagram"
                and not item.image_url
            ):
                flash(
                    "This item needs a product image before it can "
                    "be scheduled to Instagram.",
                    "error",
                )

            elif not caption:
                flash(
                    "Please enter a post caption.",
                    "error",
                )

            elif len(final_caption) > MAX_CAPTION_LENGTH:
                flash(
                    "Your caption is too long. "
                    "Please shorten it to fit within Buffer's "
                    "2,000-character limit, including the WhatsApp link.",
                    "error",
                )

            elif not scheduled_input:
                flash(
                    "Please choose a publication date and time.",
                    "error",
                )

            else:
                try:
                    local_time = datetime.strptime(
                        scheduled_input,
                        "%Y-%m-%dT%H:%M",
                    ).replace(tzinfo=NIGERIA_TIMEZONE)

                    scheduled_utc = local_time.astimezone(
                        timezone.utc
                    )

                    if scheduled_utc <= datetime.now(timezone.utc):
                        raise ValueError(
                            "Choose a publication time in the future."
                        )

                    due_at = (
                        scheduled_utc
                        .isoformat(timespec="seconds")
                        .replace("+00:00", "Z")
                    )

                    # Create the post through Buffer with its
                    # inventory image and channel-specific metadata.
                    created_post = create_buffer_post(
                        access_token,
                        channel_id,
                        final_caption,
                        due_at,
                        image_url=item.image_url,
                        channel_service=channel.get("service"),
                    )

                    # Save the confirmed Buffer post locally.
                    try:
                        scheduled_post = ScheduledPost(
                            seller_id=current_user.id,
                            item_id=item.id,
                            buffer_connection_id=connection.id,
                            buffer_channel_id=channel_id,
                            buffer_channel_service=channel.get("service"),
                            buffer_post_id=created_post["id"],
                            caption=final_caption,
                            scheduled_at=scheduled_utc,
                            status="scheduled",
                        )

                        db.session.add(scheduled_post)
                        db.session.commit()

                    except Exception:
                        db.session.rollback()

                        # Attempt to remove the Buffer post if
                        # database persistence fails.
                        try:
                            delete_buffer_post(
                                access_token,
                                created_post["id"],
                            )

                            logger.warning(
                                "Compensated for unsaved Buffer post %s.",
                                created_post["id"],
                            )

                        except Exception:
                            logger.exception(
                                "CRITICAL: Buffer post %s was created "
                                "but could not be saved or deleted.",
                                created_post.get("id", "unknown"),
                            )

                        raise

                    if channel_service == "instagram" and whatsapp_link:
                        flash(
                            (
                                f"Your post for {item.name} was scheduled "
                                "successfully! Copy the WhatsApp ordering "
                                "link from Post History and add it as your "
                                "Instagram first comment."
                            ),
                            "success",
                        )
                    else:
                        flash(
                            f"Your post for {item.name} was scheduled successfully!",
                            "success",
                        )

                    return redirect(
                        url_for("items.inventory")
                    )

                except ValueError as exc:
                    flash(str(exc), "error")

                except BufferAPIError:
                    logger.exception(
                        "Buffer scheduling failed for seller %s.",
                        current_user.id,
                    )

                    flash(
                        "Buffer could not schedule your post. "
                        "Please try again after checking your account.",
                        "error",
                    )

                except Exception:
                    db.session.rollback()

                    logger.exception(
                        "Unexpected scheduling error for seller %s.",
                        current_user.id,
                    )

                    flash(
                        "We couldn't complete your scheduling request.",
                        "error",
                    )

    except (BufferAPIError, ValueError):
        logger.exception(
            "Could not load Buffer scheduling information "
            "for seller %s.",
            current_user.id,
        )

        flash(
            "We couldn't retrieve your Buffer channels. "
            "Please try again.",
            "error",
        )

    return render_template(
        "schedule_post.html",
        item=item,
        organizations=organizations,
        channels=channels,
        selected_organization_id=selected_organization_id,
    )
