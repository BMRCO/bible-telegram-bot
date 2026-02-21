import os
import json
import random
import re
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL = os.environ["TELEGRAM_CHANNEL"]

PROGRESS_FILE = "progress.json"
PROMISES_LIST = "promesses_curated.json"
JESUS_LIST = "jesus_curated.json"
BIBLE_DIR = "bible"

FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

WATERMARK = "@appbible"
FIXED_HASHTAGS = "#LaBible #LSG1910 #versetdujour"


# ---------------------------------------------------
# CLEAN TEXT (seguro + francês)
# ---------------------------------------------------
def clean_text(text: str) -> str:
    if not text:
        return ""

    # remove apenas marcações técnicas
    text = re.sub(r'\\\+?w\b', '', text)
    text = re.sub(r'strong="[^"]+"', '', text)
    text = re.sub(r'\|[^ \t]+', '', text)
    text = re.sub(r'\\[a-zA-Z0-9]+\*?', '', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # A → À no início de frase
    text = re.sub(r'(^|\. )A ', r'\1À ', text)

    # espaço francês antes de ; : ? !
    text = re.sub(r'\s*([;:?!])', r' \1', text)

    # normaliza apóstrofos (sem destruir)
    text = text.replace("’", "'")

    # ponto final se faltar (antes das aspas)
    if not text.endswith(('.', '!', '?')):
        text += '.'

    # aspas francesas sempre
    return f"« {text} »"


# ---------------------------------------------------
def safe_filename(name: str) -> str:
    t = name.lower()
    repl = (("é","e"),("è","e"),("ê","e"),("ë","e"),
            ("à","a"),("â","a"),
            ("î","i"),("ï","i"),
            ("ô","o"),
            ("ù","u"),("û","u"),
            ("ç","c"),("œ","oe"))
    for a,b in repl:
        t = t.replace(a,b)
    t = re.sub(r"[^a-z0-9]+","_",t).strip("_")
    return t


def load_json(path):
    with open(path,"r",encoding="utf-8") as f:
        return json.load(f)


def save_json(path,data):
    with open(path,"w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2)


def load_book(book_name):
    path = f"{BIBLE_DIR}/{safe_filename(book_name)}.json"
    data = load_json(path)
    return data[book_name]


def send_photo(path,caption):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(path,"rb") as f:
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
# SIGNATURE BACKGROUND
# ---------------------------------------------------
def make_background(W, H):
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    for y in range(H):
        t = y / H
        r = int(10 + t * 18)
        g = int(10 + t * 18)
        b = int(18 + t * 25)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    return img.filter(ImageFilter.GaussianBlur(0.8))


def wrap_text(draw, text, font, max_w):
    words = text.split()
    if not words:
        return [""]

    lines = []
    current = words[0]
    for w in words[1:]:
        test = current + " " + w
        if draw.textlength(test, font=font) <= max_w:
            current = test
        else:
            lines.append(current)
            current = w
    lines.append(current)
    return lines


def make_image(text, ref):
    W, H = 1080, 1080
    img = make_background(W, H)
    draw = ImageDraw.Draw(img)

    gold = (195, 165, 90)
    gold2 = (140, 120, 65)

    margin = 60
    draw.rounded_rectangle([margin, margin, W - margin, H - margin],
                           radius=30, outline=gold, width=6)

    inner = margin + 16
    draw.rounded_rectangle([inner, inner, W - inner, H - inner],
                           radius=26, outline=gold2, width=2)

    # área editorial
    pad_x = 140
    top = 190
    bottom = 350  # margem segura para ref/linha

    max_w = W - 2 * pad_x
    max_h = H - top - bottom

    # auto-fit
    chosen_font = None
    chosen_lines = None
    chosen_line_h = None

    for size in range(66, 36, -2):
        font = ImageFont.truetype(FONT_SERIF, size)
        lines = wrap_text(draw, text, font, max_w)
        line_h = int(size * 1.35)
        if line_h * len(lines) <= max_h:
            chosen_font = font
            chosen_lines = lines
            chosen_line_h = line_h
            break

    if chosen_font is None:
        chosen_font = ImageFont.truetype(FONT_SERIF, 36)
        chosen_lines = wrap_text(draw, text, chosen_font, max_w)
        chosen_line_h = int(36 * 1.35)

    total_h = chosen_line_h * len(chosen_lines)
    y = top + max(0, (max_h - total_h) // 2)

    # estilo editorial: centrado tipo poesia
    for line in chosen_lines:
        line_w = draw.textlength(line, font=chosen_font)
        x = (W - line_w) // 2

        # sombra subtil
        draw.text((x + 2, y + 2), line, font=chosen_font, fill=(0, 0, 0))
        draw.text((x, y), line, font=chosen_font, fill=(245, 245, 245))
        y += chosen_line_h

    # rodapé
    small = ImageFont.truetype(FONT_SANS, 36)
    tiny = ImageFont.truetype(FONT_SANS, 28)

    draw.line([(pad_x, H - 260), (W - pad_x, H - 260)], fill=(150, 130, 70), width=2)

    draw.text((pad_x, H - 220), ref, font=small, fill=(220, 220, 230))
    draw.text((pad_x, H - 180), "LSG 1910", font=tiny, fill=(170, 170, 180))

    wm_w = draw.textlength(WATERMARK, font=tiny)
    draw.text((W - pad_x - wm_w, H - 180), WATERMARK, font=tiny, fill=(150, 150, 160))

    out = "verse.png"
    img.save(out, "PNG")
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
