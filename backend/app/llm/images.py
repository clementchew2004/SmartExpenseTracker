"""Check an uploaded receipt photo before it costs anything to read.

Every check here runs before the OpenAI call, cheapest first:
1. size (just counting bytes),
2. what the file really is (Pillow reads its first bytes, not the name or the
   declared type, which the phone or anyone else can make up),
3. converting it to a reasonably sized JPEG the model accepts.

The photo is only ever held in memory: nothing here writes it to disk.
"""

import io
import logging

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

logger = logging.getLogger(__name__)

# Teaches Pillow to open iPhone HEIC photos. OpenAI doesn't accept HEIC, so
# they are converted to JPEG below like everything else.
register_heif_opener()

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

# Pillow's own names for the formats it detected from the file's contents.
# MPO is a JPEG with extra pictures inside: newer iPhones store an HDR gain map
# or depth map that way, and Safari keeps it when it converts a photo to JPEG.
# Pillow opens the main picture, and the fresh JPEG made below leaves the rest out.
ALLOWED_FORMATS = {"JPEG", "MPO", "PNG", "HEIF"}

# The model shrinks anything bigger than this anyway, so sending more only
# makes the upload to OpenAI slower. Receipt text stays readable at this size.
MAX_SIDE = 2048


class ImageTooLargeError(Exception):
    pass


class UnsupportedImageError(Exception):
    pass


def prepare_receipt(data: bytes) -> bytes:
    """Return the photo as a JPEG ready for the model, or raise."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise ImageTooLargeError("That photo is over 5 MB - try a smaller one")

    detected = None  # what Pillow thinks the file is, for the log
    try:
        image = Image.open(io.BytesIO(data))
        detected = image.format
        if image.format not in ALLOWED_FORMATS:
            raise UnsupportedImageError
        # open() only reads the header; load() decodes every pixel, so a file
        # that starts like a JPEG but is broken (or not a photo) fails here.
        image.load()
    except (
        UnidentifiedImageError,
        UnsupportedImageError,
        OSError,
        SyntaxError,
        Image.DecompressionBombError,
    ) as e:
        # The user only sees a friendly message; the log says exactly why, so the
        # next "my photo won't upload" doesn't need guessing. No image data logged.
        logger.warning(
            "Receipt rejected: detected format %s, %d bytes, %s",
            detected or "unknown",
            len(data),
            type(e).__name__,
        )
        # DecompressionBombError: a small file that claims to be enormous
        # (e.g. 50,000 x 50,000 pixels) and would fill the server's memory.
        raise UnsupportedImageError(
            "That isn't a photo we can read - use a JPEG, PNG or HEIC image"
        ) from e

    # Phones often save photos sideways plus a "rotate me" note (EXIF);
    # apply it so the model sees the receipt the right way up.
    image = ImageOps.exif_transpose(image)
    image.thumbnail((MAX_SIDE, MAX_SIDE))  # shrink only, keeps the shape
    image = image.convert("RGB")  # JPEG has no transparency (PNGs may)

    # Writing a fresh JPEG also leaves the original's metadata behind,
    # including any GPS location the phone stored in the photo.
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=85)
    return out.getvalue()
