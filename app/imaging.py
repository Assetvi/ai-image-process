"""Pixel operations independent of HTTP, persistence, and the AI runtime."""

import io
import re
import warnings
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps, UnidentifiedImageError

from .config import MAX_PIXELS
from .schemas import Crop, Stroke

Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def decode_image(raw: bytes) -> Image.Image:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("Use a JPEG, PNG, or WebP image.")
                if getattr(image, "is_animated", False):
                    raise ValueError("Animated images are not supported.")
                if image.width * image.height > MAX_PIXELS:
                    raise ValueError("Images must be 24 megapixels or smaller.")
                image.load()
                # Normalize orientation once; browser and server then share coordinates.
                result = ImageOps.exif_transpose(image).convert("RGBA")
                result.info.clear()  # Do not carry EXIF/location data into exports.
                return result
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValueError("Invalid, damaged, or oversized image.") from exc


def save_png(image: Image.Image, destination: Path) -> None:
    temporary = destination.with_suffix(".tmp")
    image.save(temporary, format="PNG")
    temporary.replace(destination)


def auto_box(image: Image.Image, padding: int, threshold: int) -> tuple[list[int], str | None]:
    """Trim outer whitespace, never recolor pixels. Bounds use half-open coordinates."""
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] < 255:
        # A mask is more informative than RGB: a white product remains foreground.
        foreground = alpha.point(lambda value: 255 if value > 8 else 0)
    else:
        red, green, blue = rgba.convert("RGB").split()
        darkest = ImageChops.darker(ImageChops.darker(red, green), blue)
        foreground = darkest.point(lambda value: 255 if value < threshold else 0)
    bounds = foreground.getbbox()
    if bounds is None:
        return [0, 0, image.width, image.height], "No clear foreground; original bounds kept."
    left, top, right, bottom = bounds
    return [
        max(0, left - padding),
        max(0, top - padding),
        min(image.width, right + padding),
        min(image.height, bottom + padding),
    ], None


def apply_strokes(current: Image.Image, original: Image.Image, strokes: list[Stroke]) -> Image.Image:
    """Restore original RGBA pixels or erase alpha, at full source resolution."""
    result = current.copy()
    for stroke in strokes:
        brush = Image.new("L", result.size, 0)
        draw = ImageDraw.Draw(brush)
        points = [
            (
                min(result.width - 1, round(p.x * result.width)),
                min(result.height - 1, round(p.y * result.height)),
            )
            for p in stroke.points
        ]
        radius = stroke.radius
        if len(points) > 1:
            draw.line(points, fill=255, width=max(1, round(radius * 2)), joint="curve")
        for x, y in points:
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)
        if stroke.mode == "restore":
            result = Image.composite(original, result, brush)
        else:
            result.putalpha(ImageChops.subtract(result.getchannel("A"), brush))
    return result


def validate_crop(crop: Crop, size: tuple[int, int]) -> list[int]:
    if crop.x + crop.width > size[0] or crop.y + crop.height > size[1]:
        raise ValueError("Crop must be inside the original image.")
    return [crop.x, crop.y, crop.x + crop.width, crop.y + crop.height]


def safe_filename(filename: str) -> str:
    leaf = filename.replace("\\", "/").split("/")[-1]
    stem = Path(leaf).stem
    stem = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "_", stem).strip(" .")[:120] or "image"
    if re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])", stem):
        stem = "_" + stem
    return stem + ".png"


def unique_name(name: str, used: set[str]) -> str:
    candidate = name
    number = 2
    while candidate.casefold() in used:
        candidate = f"{Path(name).stem}-{number}.png"
        number += 1
    used.add(candidate.casefold())
    return candidate
