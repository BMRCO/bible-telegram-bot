import os
import json
import textwrap
import requests
import random
from PIL import Image, ImageDraw, ImageFont

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL = os.environ["TELEGRAM_CHANNEL"]

PROGRESS_FILE = "progress.json"
INDEX_FILE = "verses_index.json"
BIBLE_DIR = "bible"

FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

WATERMARK = "@appbible"  # marca d’água discreta


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
            data={
                "chat_id": CHANNEL,
                "caption": caption,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            files={"photo": f},
            timeout=30
        )
    r.raise_for_status()


def make_image(text, ref):
    W, H = 1080, 1080

    # Fundo com gradiente escuro suave
    img = Image.new("RGB", (W, H), (10, 10, 14))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        v = int(10 + (y / H) * 18)
        draw.line([(0, y), (W, y)], fill=(v, v, v + 6))

    # Moldura dourada elegante
    gold = (195, 165, 90)
    gold2 = (140, 120, 65)

    margin = 60
    draw.rounded_rectangle(
        [margin, margin, W - margin, H - margin],
        radius=28,
        outline=gold,
        width=6
    )
    draw.rounded_rectangle(
        [margin + 14, margin + 14, W - margin - 14, H - margin - 14],
        radius=22,
        outline=gold2,
        width=2
    )

    # Tipografia
    font = ImageFont.truetype(FONT_SERIF, 56)
    small = ImageFont.truetype(FONT_SANS, 34)
    tiny = ImageFont.truetype(FONT_SANS, 28)

    # Texto do versículo
    lines = textwrap.wrap(text, width=34)
    line_h = 78
    text_h = min(len(lines), 10) * line_h
    y0 = int((H - text_h) * 0.40)

    x = 110
    y = y0
    for line in lines[:10]:
        draw.text((x, y), line, font=font, fill=(245, 245, 245))
        y += line_h

    # Separador dourado
    draw.line([(110, H - 245), (W - 110, H - 245)], fill=gold2, width=2)

    # Rodapé esquerdo
    draw.text((110, H - 220), ref, font=small, fill=(220, 220, 230))
    draw.text((110, H - 170), "Louis Segond (1910) • Domaine public", font=tiny, fill=(175, 175, 185))

    # Marca d’água discreta (rodapé direito)
    wm_font = ImageFont.truetype(FONT_SANS, 28)
    wm_w = draw.textlength(WATERMARK, font=wm_font)
    draw.text((W - 110 - wm_w, H - 170), WATERMARK, font=wm_font, fill=(145, 145, 155))

    out = "verse.png"
    img.save(out, "PNG")
    return out


def reshuffle_index(index):
    random.shuffle(index)
    save_json(INDEX_FILE, index)


def main():
    index = load_json(INDEX_FILE)
    progress = load_json(PROGRESS_FILE)

    i = int(progress.get("i", 0))

    # Se chegou ao fim, rebaralha e recomeça
    if i >= len(index):
        reshuffle_index(index)
        index = load_json(INDEX_FILE)
        i = 0

    book, chapter, verse = index[i]
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
