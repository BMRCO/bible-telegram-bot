import os
import json
import textwrap
import requests
from PIL import Image, ImageDraw, ImageFont

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL = os.environ["TELEGRAM_CHANNEL"]

PROGRESS_FILE = "progress.json"
INDEX_FILE = "verses_index.json"
BIBLE_DIR = "bible"

FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def safe_filename(name: str) -> str:
    import re
    t = name.lower()
    repl = (("é","e"),("è","e"),("ê","e"),("ë","e"),
            ("à","a"),("â","a"),
            ("î","i"),("ï","i"),
            ("ô","o"),
            ("ù","u"),("û","u"),
            ("ç","c"),("œ","oe"))
    for a, b in repl:
        t = t.replace(a, b)
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return t

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_book(book_name: str) -> dict:
    path = f"{BIBLE_DIR}/{safe_filename(book_name)}.json"
    data = load_json(path)
    return data[book_name]

def send_photo(path, caption):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(path, "rb") as f:
        r = requests.post(
            url,
            data={"chat_id": CHANNEL, "caption": caption, "parse_mode": "HTML"},
            files={"photo": f},
            timeout=30
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
    for line in lines[:10]:
        draw.text((90, y), line, font=font, fill=(245, 245, 245))
        y += 80

    draw.text((90, H - 200), ref, font=small, fill=(200, 200, 210))
    draw.text((90, H - 150), "Louis Segond (1910) • Domaine public", font=small, fill=(160, 160, 170))

    out = "verse.png"
    img.save(out, "PNG")
    return out

def main():
    idx = load_json(INDEX_FILE)  # lista: [[book, ch, v], ...]
    progress = load_json(PROGRESS_FILE)

    i = int(progress.get("i", 0))
    if i >= len(idx):
        # recomeçar (mantém random atual; se quiser novo random, rode build_index novamente)
        i = 0

    book, chapter, verse = idx[i]
    book_data = load_book(book)

    text = book_data[str(chapter)][str(verse)]
    ref = f"{book} {chapter}:{verse}"

    img_path = make_image(text, ref)
    caption = f"📖 <b>{ref}</b>\n#versetdujour"

    send_photo(img_path, caption)

    progress["mode"] = "random"
    progress["i"] = i + 1
    save_json(PROGRESS_FILE, progress)

if __name__ == "__main__":
    main()
