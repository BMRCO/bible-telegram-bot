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

# Hashtags finais
FIXED_HASHTAGS = "#LaBible #LSG1910 #versetdujour"


# ---------------------------------------------------
# LIMPEZA + TIPOGRAFIA + ASPAS «…»
# ---------------------------------------------------
def clean_text(text: str) -> str:
    if not text:
        return ""

    # Remove marcações Strong/USFM
    text = re.sub(r"\\\+?w\b", "", text)
    text = re.sub(r'strong="[^"]+"', "", text)
    text = re.sub(r"\|[^ \t]+", "", text)
    text = re.sub(r"\\[a-zA-Z0-9]+\*?", "", text)
    text = text.replace("\\", "")

    # Apóstrofos tipográficos
    text = text.replace("’", "'")
    text = re.sub(r"\b([cdjlmntsCDJLMNTS])'", r"\1’", text)

    # Espaçamento francês
    text = re.sub(r"\s*([;:?!])", r" \1", text)
    text = re.sub(r"\s+([,.])", r"\1", text)

    text = re.sub(r"\s+", " ", text).strip()

    # Aspas francesas sempre
    if "«" not in text and "»" not in text:
        text = f"« {text} »"

    return text


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
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            },
            files={"photo": f},
            timeout=30
        )
    r.raise_for_status()


# ---------------------------------------------------
# TEXTO NA IMAGEM (auto-fit)
# ---------------------------------------------------
def _wrap_to_width(draw, text, font, max_width_px):
    words = text.split()
    lines = []
    current = words[0]

    for w in words[1:]:
        candidate = current + " " + w
        if draw.textlength(candidate, font=font) <= max_width_px:
            current = candidate
        else:
            lines.append(current)
            current = w

    lines.append(current)
    return lines


def _fit_text(draw, text, max_width_px, max_height_px):
    for size in range(62, 32, -2):
        font = ImageFont.truetype(FONT_SERIF, size)
        lines = _wrap_to_width(draw, text, font, max_width_px)
        line_h = int(size * 1.25)
        total_h = line_h * len(lines)

        if total_h <= max_height_px:
            return font, lines, line_h

    font = ImageFont.truetype(FONT_SERIF, 34)
    lines = _wrap_to_width(draw, text, font, max_width_px)
    line_h = int(34 * 1.25)
    return font, lines, line_h


def make_image(text: str, ref: str) -> str:
    W, H = 1080, 1080

    img = Image.new("RGB", (W, H), (10, 10, 14))
    draw = ImageDraw.Draw(img)

    gold = (195, 165, 90)
    gold2 = (140, 120, 65)

    margin = 60
    draw.rounded_rectangle([margin, margin, W - margin, H - margin],
                           radius=28, outline=gold, width=6)
    draw.rounded_rectangle([margin + 14, margin + 14, W - margin - 14, H - margin - 14],
                           radius=22, outline=gold2, width=2)

    pad_x = 110
    top_y = 150
    bottom_y = 260  # mais espaço para o texto

    max_w = W - 2 * pad_x
    max_h = H - top_y - bottom_y

    font, lines, line_h = _fit_text(draw, text, max_w, max_h)
    total_h = line_h * len(lines)
    y = top_y + (max_h - total_h) // 2

    for line in lines:
        draw.text((pad_x, y), line, font=font, fill=(245, 245, 245))
        y += line_h

    small = ImageFont.truetype(FONT_SANS, 34)
    tiny = ImageFont.truetype(FONT_SANS, 28)

    sep_y = H - 220
    draw.line([(pad_x, sep_y), (W - pad_x, sep_y)], fill=gold2, width=2)

    # Só referência + watermark
    draw.text((pad_x, H - 190), ref, font=small, fill=(220, 220, 230))

    wm_font = ImageFont.truetype(FONT_SANS, 28)
    wm_w = draw.textlength(WATERMARK, font=wm_font)
    draw.text((W - pad_x - wm_w, H - 190),
              WATERMARK, font=wm_font, fill=(145, 145, 155))

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
        progress["next"] = "jesus"
    else:
        book, ch, v = pick_from_curated(JESUS_LIST, "i_jesus", progress)
        progress["next"] = "promise"

    book_data = load_book(book)
    raw_text = book_data[str(ch)][str(v)]
    text = clean_text(raw_text)

    ref = f"{book} {ch}:{v}"

    img = make_image(text, ref)
    caption = f"📖 <b>{ref}</b>\n{FIXED_HASHTAGS}"

    send_photo(img, caption)
    save_json(PROGRESS_FILE, progress)


if __name__ == "__main__":
    main()