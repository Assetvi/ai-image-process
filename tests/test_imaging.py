import io

from PIL import Image, ImageDraw

from app.imaging import auto_box, decode_image


def test_transparent_white_subject_uses_alpha_not_color():
    image = Image.new("RGBA", (100, 80))
    ImageDraw.Draw(image).rectangle((25, 20, 74, 59), fill="white")
    assert auto_box(image, padding=5, threshold=254) == ([20, 15, 80, 65], None)


def test_ambiguous_all_white_image_is_kept():
    image = Image.new("RGBA", (100, 80), "white")
    box, warning = auto_box(image, 16, 254)
    assert box == [0, 0, 100, 80]
    assert warning


def test_exif_orientation_is_normalized_and_metadata_removed():
    image = Image.new("RGB", (100, 80), "red")
    metadata = Image.Exif()
    metadata[274] = 6
    metadata[270] = "Private metadata"
    output = io.BytesIO()
    image.save(output, format="JPEG", exif=metadata)
    normalized = decode_image(output.getvalue())
    assert normalized.size == (80, 100)
    assert not normalized.info
