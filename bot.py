import os
import json
import textwrap
import requests
from PIL import Image, ImageDraw, ImageFont

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL = os.environ["TELEGRAM_CHANNEL"]

BIBLE_FILE = "bible_ls1910.json"
PROGRESS_FILE = "progress.json"

FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def send_photo(path, caption):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(path, "rb") as f:
        r = requests.post(
            url,
            data={
                "chat_id": CHANNEL,
                "caption": caption,
                "parse_mode": "HTML"
            },
            files={"photo": f}
        )
    r.raise_for_status()


def make_image(text, ref):
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), (18, 18, 24))
    draw = ImageDraw.Draw(img)

    font = ImageFont.truetype(FONT_SERIF, 56)
    small = ImageFont.truetype(FONT_SANS, 34)

    lines = textwrap.wrap(text, width=34)
    y = 200

    for line in lines:
        draw.text((90, y), line, font=font, fill=(245, 245, 245))
        y += 80

    draw.text((90, H - 200), ref, font=small, fill=(200, 200, 210))
    draw.text((90, H - 150), "Louis Segond (1910) • Domaine public", font=small, fill=(160, 160, 170))

    path = "verse.png"
    img.save(path)
    return path


def main():
    bible = load_json(BIBLE_FILE)
    progress = load_json(PROGRESS_FILE)

    book = progress["book"]
    chapter = str(progress["chapter"])
    verse = str(progress["verse"])

    text = bible[book][chapter][verse]
    ref = f"{book} {chapter}:{verse}"

    img_path = make_image(text, ref)

    caption = f"📖 <b>{ref}</b>\n#versetdujour"

    send_photo(img_path, caption)


if __name__ == "__main__":
    main()
