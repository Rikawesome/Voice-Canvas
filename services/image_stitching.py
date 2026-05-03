import io
from typing import List, Tuple

from PIL import Image


def stitch_panels_2x2(
    panel_images: List[bytes],
    panel_width: int = 768,
    panel_height: int = 768,
    border_width: int = 8,
    border_color: Tuple[int, int, int] = (10, 10, 10),
) -> Image.Image:
    if len(panel_images) != 4:
        raise ValueError(f"Expected 4 panels, got {len(panel_images)}")

    images = []
    for panel_bytes in panel_images:
        image = Image.open(io.BytesIO(panel_bytes))
        image = image.resize((panel_width, panel_height), Image.Resampling.LANCZOS)

        if image.mode in {"RGBA", "P"}:
            rgb_image = Image.new("RGB", image.size, (255, 255, 255))
            alpha = image.split()[-1] if image.mode == "RGBA" else None
            rgb_image.paste(image, mask=alpha)
            image = rgb_image
        else:
            image = image.convert("RGB")

        images.append(image)

    total_width = (panel_width * 2) + (border_width * 3)
    total_height = (panel_height * 2) + (border_width * 3)
    page = Image.new("RGB", (total_width, total_height), border_color)

    positions = [
        (border_width, border_width),
        (border_width * 2 + panel_width, border_width),
        (border_width, border_width * 2 + panel_height),
        (border_width * 2 + panel_width, border_width * 2 + panel_height),
    ]

    for image, position in zip(images, positions):
        page.paste(image, position)

    return page


def export_page(page: Image.Image, image_format: str = "WEBP", quality: int = 88) -> bytes:
    output = io.BytesIO()
    format_name = image_format.upper()

    if format_name == "WEBP":
        page.save(output, format="WEBP", quality=quality)
    elif format_name == "PNG":
        page.save(output, format="PNG")
    elif format_name in {"JPEG", "JPG"}:
        page.save(output, format="JPEG", quality=quality)
    else:
        raise ValueError(f"Unsupported export format: {image_format}")

    output.seek(0)
    return output.getvalue()
