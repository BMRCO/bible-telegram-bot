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

# Hashtags fixas (como pediste)
FIXED_HASHTAGS = "#LaBible.app #LSG1910 #versetdujour"


# ---------------------------------------------------
# LIMPEZA + TIPOGRAFIA (FR) + ASPAS «…» SEMPRE
# ---------------------------------------------------
def clean_text(text: str) -> str:
    if not text:
        return ""

    # Remove padrões Strong/USFM comuns
    text = re.sub(r"\\\+?w\b", "", text)                 # \+w / \w
    text = re.sub(r'strong="[^"]+"', "", text)          # strong="H1234"
    text = re.sub(r"\|[^ \t]+", "", text)               # |strong=...
    text = re.sub(r"\\[a-zA-Z0-9]+\*?", "", text)        # \x \v etc (caso apareçam)
    text = text.replace("\\", "")                        # barras invertidas soltas

    # Normaliza apóstrofos para tipográfico
    text = text.replace("’", "'")
    text = re.sub(r"\b([cdjlmntsCDJLMNTS])'", r"\1’", text)  # c' -> c’

    # Espaçamento francês antes de ; : ? !
    text = re.sub(r"\s*([;:?!])", r" \1", text)
    # Remove espaço antes de , e .
    text = re.sub(r"\s+([,.])", r"\1", text)

    # Normaliza espaços
    text = re.sub(r"\s+", " ", text).strip()

    # Aspas francesas sempre no versículo (se ainda não tiver)
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
def _wrap_to_width(draw: ImageDraw.ImageDraw, text: str, font, max_width_px: int):
    words = text.replace("\n", " ").split()
    if not words:
        return [""]

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


def _fit_text(draw: ImageDraw.ImageDraw, text: str, max_width_px: int, max_height_px: int,
              max_font_size: int = 62, min_font_size: int = 34, line_spacing_ratio: float = 0.28):
    for size in range(max_font_size, min_font_size - 1, -2):
        font = ImageFont.truetype(FONT_SERIF, size)
        lines = _wrap_to_width(draw, text, font, max_width_px)
        line_h = int(size * (1.0 + line_spacing_ratio))
        total_h = line_h * len(lines)
        if total_h <= max_height_px and all(draw.textlength(line, font=font) <= max_width_px for line in lines):
            return font, lines, line_h

    font = ImageFont.truetype(FONT_SERIF, min_font_size)
    lines = _wrap_to_width(draw, text, font, max_width_px)
    line_h = int(min_font_size * (1.0 + line_spacing_ratio))
    return font, lines, line_h


def make_image(text: str, ref: str) -> str:
    W, H = 1080, 1080

    # Fundo gradiente escuro suave
    img = Image.new("RGB", (W, H), (10, 10, 14))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        v = int(10 + (y / H) * 18)
        draw.line([(0, y), (W, y)], fill=(v, v, v + 6))

    # Moldura dourada elegante
    gold = (195, 165, 90)
    gold2 = (140, 120, 65)

    margin = 60
    draw.rounded_rectangle([margin, margin, W - margin, H - margin],
                           radius=28, outline=gold, width=6)
    draw.rounded_rectangle([margin + 14, margin + 14, W - margin - 14, H - margin - 14],
                           radius=22, outline=gold2, width=2)

    # Área útil dentro da moldura
    pad_x = 110
    top_y = 150
    bottom_y = 300
    max_w = W - 2 * pad_x
    max_h = H - top_y - bottom_y

    # Ajuste automático do texto
    font, lines, line_h = _fit_text(draw, text, max_w, max_h)
    total_h = line_h * len(lines)
    y = top_y + max(0, (max_h - total_h) // 2)

    for line in lines:
        draw.text((pad_x, y), line, font=font, fill=(245, 245, 245))
        y += line_h

    # Rodapé + separador
    small = ImageFont.truetype(FONT_SANS, 34)
    tiny = ImageFont.truetype(FONT_SANS, 28)

    sep_y = H - 245
    draw.line([(pad_x, sep_y), (W - pad_x, sep_y)], fill=gold2, width=2)

    draw.text((pad_x, H - 220), ref, font=small, fill=(220, 220, 230))
    draw.text((pad_x, H - 170), "Louis Segond (1910) • Domaine public", font=tiny, fill=(175, 175, 185))

    # watermark à direita
    wm_font = ImageFont.truetype(FONT_SANS, 28)
    wm_w = draw.textlength(WATERMARK, font=wm_font)
    draw.text((W - pad_x - wm_w, H - 170), WATERMARK, font=wm_font, fill=(145, 145, 155))

    out = "verse.png"
    img.save(out, "PNG")
    return out


# ---------------------------------------------------
# SELEÇÃO CURADA + rebaralhar
# ---------------------------------------------------
def load_list(path: str):
    arr = load_json(path)
    if not isinstance(arr, list) or not arr:
        raise RuntimeError(f"Lista vazia ou inválida: {path}")
    return arr


def reshuffle_if_needed(path: str, i: int):
    arr = load_list(path)
    if i >= len(arr):
        random.shuffle(arr)
        save_json(path, arr)
        arr = load_list(path)
        i = 0
    return arr, i


def pick_from_curated(path: str, i_key: str, progress: dict):
    i = int(progress.get(i_key, 0))
    arr, i = reshuffle_if_needed(path, i)
    book, ch, v = arr[i]
    progress[i_key] = i + 1
    return str(book), int(ch), int(v)


# ---------------------------------------------------
def main():
    progress = load_json(PROGRESS_FILE)

    # Alternância diária permanente (mantemos, mas não mostramos na imagem)
    next_kind = progress.get("next", "promise")

    if next_kind == "promise":
        book, chapter, verse = pick_from_curated(PROMISES_LIST, "i_promise", progress)
        progress["next"] = "jesus"
    else:
        book, chapter, verse = pick_from_curated(JESUS_LIST, "i_jesus", progress)
        progress["next"] = "promise"

    book_data = load_book(book)
    raw_text = book_data[str(chapter)][str(verse)]
    text = clean_text(raw_text)

    ref = f"{book} {chapter}:{verse}"

    img_path = make_image(text, ref)
    caption = f"📖 <b>{ref}</b>\n{FIXED_HASHTAGS}"

    send_photo(img_path, caption)

    progress["mode"] = "alt_curated_no_labels"
    save_json(PROGRESS_FILE, progress)


if __name__ == "__main__":
    main()