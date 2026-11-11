
import logging
from datetime import datetime, timezone
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


scheduler_bp = Blueprint(
    "scheduler",
    __name__,
    url_prefix="/scheduler",
)

logger = logging.getLogger(__name__)

NIGERIA_TIMEZONE = ZoneInfo("Africa/Lagos")
MAX_CAPTION_LENGTH = 2000


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

            elif not caption:
                flash(
                    "Please enter a post caption.",
                    "error",
                )

            elif len(caption) > MAX_CAPTION_LENGTH:
                flash(
                    "Your caption is too long.",
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

                    # Create the post through Buffer.
                    created_post = create_buffer_post(
                        access_token,
                        channel_id,
                        caption,
                        due_at,
                    )

                    # Save the confirmed Buffer post locally.
                    try:
                        scheduled_post = ScheduledPost(
                            seller_id=current_user.id,
                            item_id=item.id,
                            buffer_connection_id=connection.id,
                            buffer_channel_id=channel_id,
                            buffer_post_id=created_post["id"],
                            caption=caption,
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
