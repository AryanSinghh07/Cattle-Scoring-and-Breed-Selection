"""Safe image loading for uploads."""

from __future__ import annotations

import io
import warnings

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "MPO"}  # MPO = multi-picture JPEG from some phones


class ImageError(ValueError):
    """The upload is not a usable photo. ``status`` is the HTTP status to return."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def decode_image(data: bytes, max_bytes: int, max_pixels: int) -> np.ndarray:
    """Turn uploaded bytes into an RGB array, applying phone EXIF rotation.

    Checks the real file content (not the file name or declared type), the
    file size and the pixel count.
    """
    if not data:
        raise ImageError("The uploaded file is empty.")
    if len(data) > max_bytes:
        raise ImageError(f"The photo is too large (limit {max_bytes // (1024 * 1024)} MB).", status=413)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as im:
                if im.format not in ALLOWED_FORMATS:
                    raise ImageError(f"Unsupported image type {im.format}; use a JPEG or PNG photo.", status=415)
                if im.width * im.height > max_pixels:
                    raise ImageError("The photo has too many pixels; please use a smaller photo.", status=413)
                im = ImageOps.exif_transpose(im)
                return np.array(im.convert("RGB"))
    except ImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise ImageError("The file is not a readable photo.", status=415) from None
