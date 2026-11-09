import logging

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_login import current_user, login_required

from app.models import BufferConnection
from app.buffer_client import (
    get_buffer_organizations,
    get_buffer_channels,
    BufferAPIError,
)
from app.token_manager import get_valid_buffer_access_token


scheduler_bp = Blueprint(
    "scheduler",
    __name__,
    url_prefix="/scheduler",
)

logger = logging.getLogger(__name__)


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

        organization_id = request.args.get("organization_id")

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
                flash("Invalid Buffer organization selected.", "error")
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