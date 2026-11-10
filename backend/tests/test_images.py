import io

import pytest
from PIL import Image

from app.llm import images
from app.llm.images import (
    MAX_SIDE,
    MAX_UPLOAD_BYTES,
    ImageTooLargeError,
    UnsupportedImageError,
    prepare_receipt,
)


def photo(fmt="JPEG", size=(400, 600), mode="RGB", **save_options) -> bytes:
    """A small made-up image in the given format."""
    out = io.BytesIO()
    Image.new(mode, size, "white").save(out, format=fmt, **save_options)
    return out.getvalue()


def half_a_jpeg() -> bytes:
    """A real JPEG cut off halfway through its pixels: the header is fine, so
    only decoding the whole picture notices."""
    out = io.BytesIO()
    Image.effect_noise((400, 600), 50).convert("RGB").save(out, format="JPEG")
    data = out.getvalue()
    return data[: len(data) // 2]


def as_image(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


@pytest.mark.parametrize(
    ("fmt", "mode"), [("JPEG", "RGB"), ("PNG", "RGBA"), ("HEIF", "RGB")]
)
def test_accepted_formats_come_out_as_jpeg(fmt, mode):
    result = as_image(prepare_receipt(photo(fmt, mode=mode)))

    assert result.format == "JPEG"
    assert result.size == (400, 600)


def test_too_large_is_rejected_before_opening():
    with pytest.raises(ImageTooLargeError):
        prepare_receipt(b"x" * (MAX_UPLOAD_BYTES + 1))


@pytest.mark.parametrize(
    "data",
    [
        b"hello, I am a text file",  # renamed to receipt.jpg
        b"%PDF-1.7 not a photo",
        photo("GIF"),  # a real image, but not one we accept
        half_a_jpeg(),
        b"",
    ],
    ids=["text", "pdf", "gif", "broken-jpeg", "empty"],
)
def test_anything_else_is_rejected(data):
    with pytest.raises(UnsupportedImageError):
        prepare_receipt(data)


def test_absurd_pixel_counts_are_rejected(monkeypatch):
    # A "decompression bomb": a tiny file claiming huge dimensions. Lowering
    # Pillow's limit lets a small test image stand in for one.
    monkeypatch.setattr(images.Image, "MAX_IMAGE_PIXELS", 1000)

    with pytest.raises(UnsupportedImageError):
        prepare_receipt(photo(size=(400, 600)))


def test_big_photos_are_shrunk_keeping_their_shape():
    result = as_image(prepare_receipt(photo(size=(3000, 4000))))

    assert max(result.size) == MAX_SIDE
    assert result.size == (1536, 2048)


def test_sideways_photos_are_turned_upright():
    exif = Image.Exif()
    exif[0x0112] = 6  # orientation tag: "rotate 90° to display"
    sideways = photo(size=(600, 400), exif=exif)

    assert as_image(prepare_receipt(sideways)).size == (400, 600)


def test_metadata_is_dropped():
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"  # camera make; GPS is stored the same way
    result = as_image(prepare_receipt(photo(exif=exif)))

    assert dict(result.getexif()) == {}
