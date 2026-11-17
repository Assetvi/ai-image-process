"""Original synthetic demo artwork. No company images or third-party stock assets."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

DESTINATION = Path(__file__).resolve().parent.parent / "frontend" / "public" / "samples"


def canvas():
    return Image.new("RGB", (1000, 800), "white")


def save(image, name):
    DESTINATION.mkdir(parents=True, exist_ok=True)
    image.save(DESTINATION / name)


def speaker():
    image = canvas()
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((360, 130, 640, 660), 35, fill="#d3c2a2")
    draw.rounded_rectangle((376, 143, 624, 644), 26, fill="#e6d8bc")
    draw.rounded_rectangle((388, 155, 612, 632), 20, fill="#494e41")
    for y in range(172, 620, 6):
        for x in range(402, 604, 6):
            draw.ellipse((x, y, x + 1, y + 1), fill="#7e8571")
    draw.ellipse((464, 188, 536, 260), fill="#333b32", outline="#a8ad98", width=2)
    draw.ellipse((474, 198, 526, 250), fill="#58654f")
    draw.ellipse((429, 355, 571, 497), fill="#252f29", outline="#8d967d", width=3)
    draw.ellipse((439, 365, 561, 487), fill="#3e493a")
    draw.ellipse((467, 393, 533, 459), fill="#707761")
    draw.rounded_rectangle((463, 565, 537, 583), 4, fill="#c1c4b0")
    draw.rectangle((390, 660, 418, 675), fill="#3b4539")
    draw.rectangle((582, 660, 610, 675), fill="#3b4539")
    save(image, "desk-speaker.png")


def bottle():
    image = canvas()
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((390, 200, 610, 660), 45, fill="#f3f2ed", outline="#d7dcd4", width=3)
    draw.rounded_rectangle((406, 218, 431, 618), 12, fill="#fcfcfa")
    draw.rounded_rectangle((415, 120, 585, 225), 18, fill="#d8dece")
    draw.rounded_rectangle((426, 125, 574, 199), 11, fill="#b2bfa0")
    for x in range(437, 574, 9):
        draw.line((x, 133, x, 191), fill="#a0b08e", width=2)
    draw.rounded_rectangle((420, 362, 580, 533), 4, fill="#e3e8d9")
    draw.ellipse((473, 389, 527, 443), fill="#a2b58d")
    draw.line((500, 405, 500, 432), fill="#e8efdf", width=3)
    draw.line((488, 418, 512, 418), fill="#e8efdf", width=3)
    for width, y in [(90, 466), (65, 479), (48, 501)]:
        draw.rounded_rectangle((500 - width // 2, y, 500 + width // 2, y + 3), 1, fill="#a8b39c")
    save(image, "white-bottle.png")


def headphones():
    image = canvas()
    draw = ImageDraw.Draw(image)
    draw.arc((280, 100, 720, 640), 180, 360, fill="#39443d", width=46)
    draw.arc((290, 112, 710, 650), 184, 356, fill="#84917e", width=22)
    draw.arc((307, 132, 693, 650), 190, 350, fill="#d3d9cc", width=7)
    draw.rounded_rectangle((284, 368, 354, 582), 29, fill="#535f51")
    draw.rounded_rectangle((646, 368, 716, 582), 29, fill="#535f51")
    draw.rounded_rectangle((323, 350, 426, 620), 43, fill="#c8cfbd", outline="#a9b49f", width=3)
    draw.rounded_rectangle((574, 350, 677, 620), 43, fill="#c8cfbd", outline="#a9b49f", width=3)
    draw.rounded_rectangle((359, 371, 420, 601), 28, fill="#73816b")
    draw.rounded_rectangle((580, 371, 641, 601), 28, fill="#73816b")
    draw.rounded_rectangle((373, 394, 415, 580), 18, fill="#46543f")
    draw.rounded_rectangle((585, 394, 627, 580), 18, fill="#46543f")
    save(image, "studio-headphones.png")


def camera():
    image = canvas()
    backdrop = Image.new("RGB", image.size)
    pixels = ImageDraw.Draw(backdrop)
    for y in range(image.height):
        t = y / image.height
        pixels.line(
            (0, y, image.width, y), fill=(round(231 - 16 * t), round(223 - 10 * t), round(207 - 3 * t))
        )
    image = backdrop
    shadow = Image.new("RGBA", image.size)
    ImageDraw.Draw(shadow).ellipse((245, 575, 805, 653), fill=(44, 55, 37, 75))
    image = Image.alpha_composite(image.convert("RGBA"), shadow.filter(ImageFilter.GaussianBlur(20))).convert(
        "RGB"
    )
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((235, 255, 765, 590), 30, fill="#333c35")
    draw.rounded_rectangle((235, 255, 765, 337), 21, fill="#bdc6ad")
    draw.rectangle((235, 306, 765, 337), fill="#bdc6ad")
    draw.rounded_rectangle((371, 211, 520, 274), 14, fill="#aebaa1")
    draw.rounded_rectangle((646, 233, 710, 258), 8, fill="#5b6a50")
    draw.ellipse((382, 309, 663, 590), fill="#1f2c26", outline="#8d9c7c", width=9)
    draw.ellipse((411, 337, 636, 563), fill="#404f3c", outline="#a1b192", width=4)
    draw.ellipse((437, 364, 609, 537), fill="#222f2b", outline="#778c73", width=6)
    draw.ellipse((461, 389, 585, 513), fill="#405b53")
    draw.ellipse((480, 406, 565, 491), fill="#182f2e")
    draw.ellipse((496, 415, 519, 438), fill="#9fb8a9")
    draw.rounded_rectangle((268, 358, 342, 555), 17, fill="#4d5c46")
    draw.rectangle((270, 282, 331, 305), fill="#e9ebdb")
    draw.ellipse((705, 358, 723, 376), fill="#d1a567")
    save(image, "travel-camera.png")


if __name__ == "__main__":
    for make in [speaker, bottle, headphones, camera]:
        make()
    print("Generated four original sample images.")
