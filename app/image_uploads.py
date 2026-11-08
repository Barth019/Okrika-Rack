
import cloudinary.uploader
from PIL import Image, UnidentifiedImageError
from io import BytesIO
from uuid import uuid4


ALLOWED_IMAGE_FORMATS = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_IMAGE_DIMENSION = 6000


class ImageUploadError(Exception):
    """Raised when an uploaded image is invalid or cannot be stored."""


def upload_item_image(file):
    """
    Validate and upload an item image to Cloudinary.

    Returns:
        A dictionary containing the secure image URL and public ID.
    """

    if not file or not file.filename:
        raise ImageUploadError("Please select an image.")

    image_data = file.read()

    if not image_data:
        raise ImageUploadError("The selected image is empty.")

    if len(image_data) > MAX_IMAGE_SIZE:
        raise ImageUploadError("Image must not exceed 5 MB.")

    try:
        image = Image.open(BytesIO(image_data))
        image.verify()

        # Reopen after verify because verify() consumes the image data.
        image = Image.open(BytesIO(image_data))

    except (UnidentifiedImageError, OSError, ValueError):
        raise ImageUploadError("Please upload a valid image.")

    if image.format not in ALLOWED_IMAGE_FORMATS:
        raise ImageUploadError(
            "Only JPEG, PNG and WebP images are supported."
        )

    width, height = image.size

    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise ImageUploadError(
            "Image dimensions must not exceed 6000 pixels."
        )

    # Fully decode the image before sending it to Cloudinary.
    image.load()

    result = cloudinary.uploader.upload(
        BytesIO(image_data),
        resource_type="image",
        folder="okrika-rack/items",
        public_id=uuid4().hex,
        overwrite=False,
        unique_filename=False,
    )

    secure_url = result.get("secure_url")
    public_id = result.get("public_id")

    if not secure_url or not public_id:
        raise ImageUploadError(
            "Cloudinary did not return the expected image details."
        )

    return {
        "image_url": secure_url,
        "image_public_id": public_id,
    }
