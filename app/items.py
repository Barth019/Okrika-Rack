
from decimal import Decimal, InvalidOperation

import cloudinary.uploader

import logging

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.models import db, Item
from app.image_uploads import upload_item_image, ImageUploadError


items_bp = Blueprint("items", __name__, url_prefix="/items")
logger = logging.getLogger(__name__)


ALLOWED_CONDITIONS = {
    "new",
    "excellent",
    "good",
    "fair",
}


@items_bp.route("/")
@login_required
def inventory():
    """Display only the logged-in seller's inventory."""

    items = Item.query.filter_by(
        seller_id=current_user.id
    ).order_by(Item.created_at.desc()).all()

    return render_template(
        "inventory.html",
        items=items,
    )


@items_bp.route("/new", methods=["GET", "POST"])
@login_required
def add_item():
    """Create a new inventory item for the logged-in seller."""

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        price_input = request.form.get("price", "").strip()
        size = request.form.get("size", "").strip()
        condition = request.form.get("condition", "").strip().lower()
        notes = request.form.get("notes", "").strip()

        image_file = request.files.get("image")

        if not name:
            flash("Please enter an item name.", "error")
            return redirect(url_for("items.add_item"))

        if len(name) > 150:
            flash("Item name cannot exceed 150 characters.", "error")
            return redirect(url_for("items.add_item"))

        if condition not in ALLOWED_CONDITIONS:
            flash("Please select a valid item condition.", "error")
            return redirect(url_for("items.add_item"))

        try:
            price = Decimal(price_input)
        except InvalidOperation:
            flash("Please enter a valid price.", "error")
            return redirect(url_for("items.add_item"))

        if not price.is_finite() or price < 0:
            flash("Price must be a valid non-negative amount.", "error")
            return redirect(url_for("items.add_item"))

        if price > Decimal("99999999.99"):
            flash("Price exceeds the maximum supported amount.", "error")
            return redirect(url_for("items.add_item"))

        if price.as_tuple().exponent < -2:
            flash("Price cannot have more than two decimal places.", "error")
            return redirect(url_for("items.add_item"))

        if len(size) > 50:
            flash("Size cannot exceed 50 characters.", "error")
            return redirect(url_for("items.add_item"))

        # Upload an image only if the seller selected one.
        image_details = None

        if image_file and image_file.filename:
            try:
                image_details = upload_item_image(image_file)
            except ImageUploadError as error:
                flash(str(error), "error")
                return redirect(url_for("items.add_item"))
            except Exception:
                flash(
                    "We couldn't upload your image. Please try again.",
                    "error",
                )
                return redirect(url_for("items.add_item"))

        item = Item(
            seller_id=current_user.id,
            name=name,
            description=description or None,
            price=price,
            size=size or None,
            condition=condition,
            notes=notes or None,
            availability="available",
            image_url=image_details["image_url"] if image_details else None,
            image_public_id=(
                image_details["image_public_id"] if image_details else None
            ),
        )

        try:
            db.session.add(item)
            db.session.commit()

        except Exception:
            db.session.rollback()

            # Remove the Cloudinary image if the database save fails.
            if image_details:
                try:
                    cloudinary.uploader.destroy(
                        image_details["image_public_id"],
                        resource_type="image",
                    )
                except Exception:
                    # Do not hide the original database error.
                    pass

            flash("We couldn't save your item. Please try again.", "error")
            return redirect(url_for("items.add_item"))

        flash("Your item has been added successfully!", "success")
        return redirect(url_for("items.inventory"))

    return render_template("add_item.html")


@items_bp.route("/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id):
    """Edit an inventory item belonging to the logged-in seller."""

    item = Item.query.filter_by(
        id=item_id,
        seller_id=current_user.id,
    ).first_or_404()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        price_input = request.form.get("price", "").strip()
        size = request.form.get("size", "").strip()
        condition = request.form.get("condition", "").strip().lower()
        notes = request.form.get("notes", "").strip()

        image_file = request.files.get("image")
        remove_image = request.form.get("remove_image") == "true"

        # Validate item name.
        if not name:
            flash("Please enter an item name.", "error")
            return redirect(url_for("items.edit_item", item_id=item.id))

        if len(name) > 150:
            flash("Item name cannot exceed 150 characters.", "error")
            return redirect(url_for("items.edit_item", item_id=item.id))

        # Validate condition.
        if condition not in ALLOWED_CONDITIONS:
            flash("Please select a valid item condition.", "error")
            return redirect(url_for("items.edit_item", item_id=item.id))

        # Validate price.
        try:
            price = Decimal(price_input)
        except InvalidOperation:
            flash("Please enter a valid price.", "error")
            return redirect(url_for("items.edit_item", item_id=item.id))

        if not price.is_finite() or price < 0:
            flash("Price must be a valid non-negative amount.", "error")
            return redirect(url_for("items.edit_item", item_id=item.id))

        if price > Decimal("99999999.99"):
            flash("Price exceeds the maximum supported amount.", "error")
            return redirect(url_for("items.edit_item", item_id=item.id))

        if price.as_tuple().exponent < -2:
            flash("Price cannot have more than two decimal places.", "error")
            return redirect(url_for("items.edit_item", item_id=item.id))

        if len(size) > 50:
            flash("Size cannot exceed 50 characters.", "error")
            return redirect(url_for("items.edit_item", item_id=item.id))

        # Upload a replacement image before changing the database.
        new_image = None

        if image_file and image_file.filename:
            try:
                new_image = upload_item_image(image_file)
            except ImageUploadError as error:
                flash(str(error), "error")
                return redirect(url_for("items.edit_item", item_id=item.id))
            except Exception:
                logger.exception("Cloudinary image replacement failed.")
                flash(
                    "We couldn't upload your new image. Please try again.",
                    "error",
                )
                return redirect(url_for("items.edit_item", item_id=item.id))

        # Remember the old image so it can be deleted after a successful save.
        old_image_public_id = item.image_public_id

        # Update the item's details.
        item.name = name
        item.description = description or None
        item.price = price
        item.size = size or None
        item.condition = condition
        item.notes = notes or None

        if new_image:
            item.image_url = new_image["image_url"]
            item.image_public_id = new_image["image_public_id"]

        elif remove_image:
            item.image_url = None
            item.image_public_id = None

        try:
            db.session.commit()

        except Exception:
            db.session.rollback()

            # Remove the newly uploaded image if saving the update fails.
            if new_image:
                try:
                    cloudinary.uploader.destroy(
                        new_image["image_public_id"],
                        resource_type="image",
                    )
                except Exception:
                    logger.exception(
                        "Failed to clean up an image after an edit failure."
                    )

            flash("We couldn't update your item. Please try again.", "error")
            return redirect(url_for("items.edit_item", item_id=item.id))

        # Delete the previous image only after the database update succeeds.
        image_was_replaced_or_removed = bool(new_image) or remove_image

        if image_was_replaced_or_removed and old_image_public_id:
            try:
                cloudinary.uploader.destroy(
                    old_image_public_id,
                    resource_type="image",
                )
            except Exception:
                logger.exception(
                    "Failed to delete an old Cloudinary image after an item update."
                )

        flash("Your item has been updated successfully!", "success")
        return redirect(url_for("items.inventory"))

    return render_template(
        "edit_item.html",
        item=item,
    )


@items_bp.route("/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id):
    """Delete an inventory item belonging to the logged-in seller."""

    item = Item.query.filter_by(
        id=item_id,
        seller_id=current_user.id,
    ).first_or_404()

    image_public_id = item.image_public_id

    # Delete the database record first.
    try:
        db.session.delete(item)
        db.session.commit()

    except Exception:
        db.session.rollback()
        logger.exception("Failed to delete inventory item from database.")

        flash(
            "We couldn't delete your item. Please try again.",
            "error",
        )
        return redirect(url_for("items.inventory"))

    # Clean up the Cloudinary image after database deletion.
    if image_public_id:
        try:
            result = cloudinary.uploader.destroy(
                image_public_id,
                resource_type="image",
            )

            if result.get("result") not in {"ok", "not found"}:
                logger.error(
                    "Cloudinary cleanup failed for deleted item."
                )
                flash(
                    "Your item was deleted, but its image could not "
                    "be removed. Please contact support.",
                    "warning",
                )
                return redirect(url_for("items.inventory"))

        except Exception:
            logger.exception(
                "Cloudinary cleanup failed for deleted inventory image."
            )
            flash(
                "Your item was deleted, but its image could not "
                "be removed. Please contact support.",
                "warning",
            )
            return redirect(url_for("items.inventory"))

    flash("Your item has been deleted successfully!", "success")
    return redirect(url_for("items.inventory"))