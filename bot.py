import os
import json
import random
import re
import requests
from PIL import Image, ImageDraw, ImageFont

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL = os.environ["TELEGRAM_CHANNEL"]

PROGRESS_FILE = "progress.json"
PROMISES_LIST = "promesses_curated.json"
JESUS_LIST = "jesus_curated.json"
BIBLE_DIR = "bible"

FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
WATERMARK = "@appbible"


# ---------------------------------------------------
# LIMPEZA DE TEXTO (REMOVE STRONG, \+w, \w, tags etc)
# ---------------------------------------------------
def clean_text(text: str) -> str:
    # Remove padrões tipo \+w
    text = re.sub(r"\\\+?w", "", text)

    # Remove tags strong="H1234"
    text = re.sub(r'strong="[^"]+"', "", text)

    # Remove barras invertidas soltas
    text = text.replace("\\", "")

    # Remove múltiplos espaços
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ---------------------------------------------------

def safe_filename(name: str) -> str:
    t = name.lower()
    repl = (("é", "e"), ("è", "e"), ("ê", "e"), ("ë", "e"),
            ("à", "a"), ("â", "a"),
            ("î", "i"), ("ï", "i"),
            ("ô", "o"),
            ("ù", "u"), ("û", "u"),
            ("ç", "c"), ("œ", "oe"))
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
                "parse_mode": "HTML"
            },
            files={"photo": f},
            timeout=30
        )
    r.raise_for_status()


# ---------------------------------------------------
# TEXTO NA IMAGEM
# ---------------------------------------------------

def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = words[0]

    for w in words[1:]:
        test = current + " " + w
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            lines.append(current)
            current = w
    lines.append(current)
    return lines


def make_image(text: str, ref: str, tag_label: str) -> str:
    W, H = 1080, 1080
    img = Image.new("RGB", (W, H), (15, 15, 20))
    draw = ImageDraw.Draw(img)

    gold = (195, 165, 90)
    margin = 60

    draw.rounded_rectangle(
        [margin, margin, W - margin, H - margin],
        radius=30, outline=gold, width=6
    )

    pad = 140
    max_width = W - pad * 2

    font_size = 60
    font = ImageFont.truetype(FONT_SERIF, font_size)

    while True:
        lines = wrap_text(draw, text, font, max_width)
        total_height = len(lines) * (font_size + 10)
        if total_height < 550 or font_size < 36:
            break
        font_size -= 2
        font = ImageFont.truetype(FONT_SERIF, font_size)

    y = 220
    for line in lines:
        draw.text((pad, y), line, font=font, fill=(240, 240, 240))
        y += font_size + 10

    small = ImageFont.truetype(FONT_SANS, 30)

    draw.text((pad, H - 300), tag_label, font=small, fill=(170, 170, 180))
    draw.text((pad, H - 250), ref, font=small, fill=(220, 220, 230))
    draw.text((pad, H - 210),
              "Louis Segond (1910) • Domaine public",
              font=small, fill=(170, 170, 180))

    wm_width = draw.textlength(WATERMARK, font=small)
    draw.text((W - pad - wm_width, H - 210),
              WATERMARK, font=small, fill=(150, 150, 160))

    out = "verse.png"
    img.save(out)
    return out


# ---------------------------------------------------
# SELEÇÃO CURADA
# ---------------------------------------------------

def load_list(path):
    arr = load_json(path)
    if not arr:
        raise RuntimeError("Lista vazia")
    return arr


def reshuffle_if_needed(path, index):
    arr = load_list(path)
    if index >= len(arr):
        random.shuffle(arr)
        save_json(path, arr)
        index = 0
    return arr, index


def pick_from_curated(path, key, progress):
    index = progress.get(key, 0)
    arr, index = reshuffle_if_needed(path, index)
    book, ch, v = arr[index]
    progress[key] = index + 1
    return book, ch, v


# ---------------------------------------------------

def main():
    progress = load_json(PROGRESS_FILE)
    next_kind = progress.get("next", "promise")

    if next_kind == "promise":
        book, ch, v = pick_from_curated(PROMISES_LIST, "i_promise", progress)
        tag = "PROMESSE"
        hashtags = "#promesse #versetdujour"
        progress["next"] = "jesus"
    else:
        book, ch, v = pick_from_curated(JESUS_LIST, "i_jesus", progress)
        tag = "PAROLES DE JÉSUS"
        hashtags = "#jesus #versetdujour"
        progress["next"] = "promise"

    book_data = load_book(book)
    raw_text = book_data[str(ch)][str(v)]
    text = clean_text(raw_text)

    ref = f"{book} {ch}:{v}"

    img = make_image(text, ref, tag)
    caption = f"📖 <b>{ref}</b>\n{hashtags}"

    send_photo(img, caption)
    save_json(PROGRESS_FILE, progress)


if __name__ == "__main__":
    main()