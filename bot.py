import os
import json
import textwrap
import requests
from PIL import Image, ImageDraw, ImageFont

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL = os.environ["TELEGRAM_CHANNEL"]

PROGRESS_FILE = "progress.json"
BIBLE_DIR = "bible"

FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# IMPORTANTE: os nomes aqui têm de bater com os nomes dentro dos JSON gerados.
# (No teu build, os ficheiros são tipo genese.json, matthieu.json, etc.)
BOOK_ORDER = [
    "Genèse","Exode","Lévitique","Nombres","Deutéronome",
    "Josué","Juges","Ruth","1 Samuel","2 Samuel","1 Rois","2 Rois",
    "1 Chroniques","2 Chroniques","Esdras","Néhémie","Esther",
    "Job","Psaumes","Proverbes","Ecclésiaste","Cantique des Cantiques",
    "Ésaïe","Jérémie","Lamentations","Ézéchiel","Daniel",
    "Osée","Joël","Amos","Abdias","Jonas","Michée","Nahum","Habacuc",
    "Sophonie","Aggée","Zacharie","Malachie",
    "Matthieu","Marc","Luc","Jean","Actes",
    "Romains","1 Corinthiens","2 Corinthiens","Galates","Éphésiens",
    "Philippiens","Colossiens","1 Thessaloniciens","2 Thessaloniciens",
    "1 Timothée","2 Timothée","Tite","Philémon","Hébreux",
    "Jacques","1 Pierre","2 Pierre","1 Jean","2 Jean","3 Jean","Jude","Apocalypse"
]

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
    return data[book_name]  # {chapter:{verse:text}}

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
    img = Image.new("RGB", (W, H), (18, 18, 24))  # fundo minimalista
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

def next_ref(book, chapter, verse, book_data):
    ch_keys = sorted(book_data.keys(), key=lambda x: int(x))
    ch = str(chapter)
    v = str(verse)

    if ch not in book_data:
        # fallback para primeiro capítulo
        ch = ch_keys[0]
        chapter = int(ch)
        v = "1"
        verse = 1

    verse_keys = sorted(book_data[ch].keys(), key=lambda x: int(x))
    if v not in book_data[ch]:
        v = verse_keys[0]
        verse = int(v)

    vi = verse_keys.index(str(verse))
    # próximo versículo
    if vi + 1 < len(verse_keys):
        return book, chapter, int(verse_keys[vi + 1])

    # próximo capítulo
    ci = ch_keys.index(str(chapter))
    if ci + 1 < len(ch_keys):
        return book, int(ch_keys[ci + 1]), 1

    # próximo livro
    bi = BOOK_ORDER.index(book)
    if bi + 1 < len(BOOK_ORDER):
        return BOOK_ORDER[bi + 1], 1, 1

    return None, None, None

def main():
    progress = load_json(PROGRESS_FILE)
    book = progress.get("book", "Genèse")
    chapter = int(progress.get("chapter", 1))
    verse = int(progress.get("verse", 1))

    book_data = load_book(book)
    text = book_data[str(chapter)][str(verse)]
    ref = f"{book} {chapter}:{verse}"

    img_path = make_image(text, ref)
    caption = f"📖 <b>{ref}</b>\n#versetdujour"

    send_photo(img_path, caption)

    nb, nc, nv = next_ref(book, chapter, verse, book_data)
    if nb is None:
        progress["done"] = True
    else:
        progress["book"] = nb
        progress["chapter"] = nc
        progress["verse"] = nv

    save_json(PROGRESS_FILE, progress)

if __name__ == "__main__":
    main()
