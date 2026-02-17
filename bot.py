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

WATERMARK = "@appbible"


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


def _wrap_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width_px: int):
    """
    Quebra o texto em linhas para caber em max_width_px.
    """
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
    """
    Ajusta automaticamente o tamanho da fonte e as linhas para caber no bloco.
    Retorna (font, lines, line_h).
    """
    # tentativa: vai reduzindo o tamanho até caber
    for size in range(max_font_size, min_font_size - 1, -2):
        font = ImageFont.truetype(FONT_SERIF, size)

        lines = _wrap_to_width(draw, text, font, max_width_px)

        # altura por linha baseada no tamanho
        line_h = int(size * (1.0 + line_spacing_ratio))
        total_h = line_h * len(lines)

        # se houver linhas demais, tenta permitir “mais compressão” com fonte menor
        if total_h <= max_height_px:
            # também garante que nenhuma linha passa do width (por segurança)
            if all(draw.textlength(line, font=font) <= max_width_px for line in lines):
                return font, lines, line_h

    # fallback
    font = ImageFont.truetype(FONT_SERIF, min_font_size)
    lines = _wrap_to_width(draw, text, font, max_width_px)
    line_h = int(min_font_size * (1.0 + line_spacing_ratio))
    return font, lines, line_h


def make_image(text, ref):
    W, H = 1080, 1080

    # Fundo gradiente escuro suave
    img = Image.new("RGB", (W, H), (10, 10, 14))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        v = int(10 + (y / H) * 18)
        draw.line([(0, y), (W, y)], fill=(v, v, v + 6))

    # Moldura dourada
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
    bottom_y = 300  # reserva para a linha dourada + rodapé
    max_w = W - 2 * pad_x
    max_h = H - top_y - bottom_y

    # Ajuste automático (para nunca sair fora)
    font, lines, line_h = _fit_text(draw, text, max_w, max_h)

    # Centralizar verticalmente dentro do bloco
    total_h = line_h * len(lines)
    y = top_y + max(0, (max_h - total_h) // 2)
    x = pad_x

    for line in lines:
        draw.text((x, y), line, font=font, fill=(245, 245, 245))
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


def reshuffle_index(index):
    random.shuffle(index)
    save_json(INDEX_FILE, index)


def main():
    index = load_json(INDEX_FILE)  # [[book, chapter, verse], ...]
    progress = load_json(PROGRESS_FILE)

    i = int(progress.get("i", 0))

    # rebaralha ao chegar ao fim
    if i >= len(index):
        reshuffle_index(index)
        index = load_json(INDEX_FILE)
        i = 0

    book, chapter, verse = index[i]
    book_data = load_book(book)

    verse_text = book_data[str(chapter)][str(verse)]
    ref = f"{book} {chapter}:{verse}"

    img_path = make_image(verse_text, ref)
    caption = f"📖 <b>{ref}</b>\n#versetdujour"

    send_photo(img_path, caption)

    progress["mode"] = "random"
    progress["i"] = i + 1
    save_json(PROGRESS_FILE, progress)


if __name__ == "__main__":
    main()
