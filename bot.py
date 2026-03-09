import os
import json
import random
import re
import datetime
import requests
import os
import json
import random
import re
import datetime
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL = os.environ["TELEGRAM_CHANNEL"]

# Meta Facebook
FB_PAGE_ID    = os.environ.get("FB_PAGE_ID", "1018605031335601")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "")

PROGRESS_FILE = "progress.json"
BIBLE_FILE = "bible/lsg1910.json"

FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_SANS  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

WATERMARK    = "LaBible.app"
MINI_APP_URL = "https://t.me/BIBLE_APP_BOT/labible"
APP_URL      = "https://labible.app"

# Categorias disponíveis
CATEGORIES = {
    "promise": {
        "key":   "i_promise",
        "file":  "promesses_curated.json",
        "emoji": "🌿",
        "tag":   "#Promesse"
    },
    "jesus": {
        "key":   "i_jesus",
        "file":  "jesus_curated.json",
        "emoji": "✝️",
        "tag":   "#ParoleDeJésus"
    },
    "psaume": {
        "key":   "i_psaume",
        "file":  "psaumes_curated.json",
        "emoji": "🎵",
        "tag":   "#Psaume"
    },
    "proverbe": {
        "key":   "i_proverbe",
        "file":  "proverbes_curated.json",
        "emoji": "💡",
        "tag":   "#Sagesse"
    },
    "prophetie": {
        "key":   "i_prophetie",
        "file":  "propheties_curated.json",
        "emoji": "🔯",
        "tag":   "#Prophétie"
    },
}

# Rotation par jour de la semaine (0=lundi … 6=dimanche)
DAY_SCHEDULE = {
    0: "promise",    # Lundi
    1: "proverbe",   # Mardi
    2: "jesus",      # Mercredi
    3: "psaume",     # Jeudi
    4: "prophetie",  # Vendredi
    5: "proverbe",   # Samedi
    6: "psaume",     # Dimanche
}


# ---------------------------------------------------
# CLEAN TEXT
# ---------------------------------------------------
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("¶", "").strip()
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([;:?!])', r' \1', text)
    text = text.replace("'", "\u2019").replace("'", "\u2019")
    if not text.endswith(('.', '!', '?')):
        text += '.'
    return f"« {text} »"

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


def save_json(path, data):
    with open(path,"w",encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# Index du fichier Bible chargé une seule fois
_bible_index = None

def get_bible_index():
    global _bible_index
    if _bible_index is None:
        data = load_json(BIBLE_FILE)
        _bible_index = {}
        for v in data["verses"]:
            bn = v["book_name"]
            ch = str(v["chapter"])
            vs = str(v["verse"])
            if bn not in _bible_index:
                _bible_index[bn] = {}
            if ch not in _bible_index[bn]:
                _bible_index[bn][ch] = {}
            _bible_index[bn][ch][vs] = v["text"]
    return _bible_index

def load_verse(book_name, chapter, verse):
    index = get_bible_index()
    return index[book_name][str(chapter)][str(verse)]


# ---------------------------------------------------
# ENVOI TELEGRAM
# ---------------------------------------------------
def send_photo(path, caption):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    reply_markup = json.dumps({
        "inline_keyboard": [[
            {"text": "📖 Lire dans LaBible.app", "url": MINI_APP_URL}
        ]]
    })
    with open(path, "rb") as f:
        r = requests.post(
            url,
            data={
                "chat_id": CHANNEL,
                "caption": caption,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": reply_markup
            },
            files={"photo": f},
            timeout=30
        )
    r.raise_for_status()
    print(f"✅ Telegram publié")


# ---------------------------------------------------
# ENVOI FACEBOOK
# ---------------------------------------------------
def post_to_facebook(image_path, ref, text, cat):
    if not FB_PAGE_TOKEN:
        print("⚠️  FB_PAGE_TOKEN non défini — publication Facebook ignorée.")
        return

    fb_message = (
        f"{cat['emoji']} Verset du jour — {ref}\n\n"
        f"{text}\n\n"
        f"📖 Lisez la Bible complète gratuitement sur {APP_URL}\n\n"
        f"#LaBible #LSG1910 #VersetDuJour #Bible {cat['tag']} #Foi #Chrétien"
    )

    # Étape 1 — Upload de la photo
    upload_url = f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/photos"
    with open(image_path, "rb") as f:
        r = requests.post(
            upload_url,
            data={
                "message": fb_message,
                "access_token": FB_PAGE_TOKEN,
            },
            files={"source": f},
            timeout=60
        )

    if r.status_code == 200:
        result = r.json()
        post_id = result.get("post_id") or result.get("id", "inconnu")
        print(f"✅ Facebook publié — post_id: {post_id}")
    else:
        print(f"❌ Erreur Facebook ({r.status_code}): {r.text}")


# ---------------------------------------------------
# IMAGE
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
    img  = make_background(W, H)
    draw = ImageDraw.Draw(img)

    gold  = (195, 165, 90)
    gold2 = (140, 120, 65)

    margin = 60
    draw.rounded_rectangle([margin, margin, W - margin, H - margin],
                            radius=30, outline=gold, width=6)
    inner = margin + 16
    draw.rounded_rectangle([inner, inner, W - inner, H - inner],
                            radius=26, outline=gold2, width=2)

    pad_x  = 140
    top    = 190
    bottom = 350
    max_w  = W - 2 * pad_x
    max_h  = H - top - bottom

    chosen_font = chosen_lines = chosen_line_h = None
    for size in range(66, 36, -2):
        font   = ImageFont.truetype(FONT_SERIF, size)
        lines  = wrap_text(draw, text, font, max_w)
        line_h = int(size * 1.35)
        if line_h * len(lines) <= max_h:
            chosen_font   = font
            chosen_lines  = lines
            chosen_line_h = line_h
            break

    if chosen_font is None:
        chosen_font   = ImageFont.truetype(FONT_SERIF, 36)
        chosen_lines  = wrap_text(draw, text, chosen_font, max_w)
        chosen_line_h = int(36 * 1.35)

    total_h = chosen_line_h * len(chosen_lines)
    y = top + max(0, (max_h - total_h) // 2)

    for line in chosen_lines:
        line_w = draw.textlength(line, font=chosen_font)
        x = (W - line_w) // 2
        draw.text((x + 2, y + 2), line, font=chosen_font, fill=(0, 0, 0))
        draw.text((x, y),         line, font=chosen_font, fill=(245, 245, 245))
        y += chosen_line_h

    small = ImageFont.truetype(FONT_SANS, 36)
    tiny  = ImageFont.truetype(FONT_SANS, 28)

    draw.line([(pad_x, H - 260), (W - pad_x, H - 260)], fill=(150, 130, 70), width=2)
    draw.text((pad_x, H - 220), ref,        font=small, fill=(220, 220, 230))
    draw.text((pad_x, H - 180), "LSG 1910", font=tiny,  fill=(170, 170, 180))

    wm_w = draw.textlength(WATERMARK, font=tiny)
    draw.text((W - pad_x - wm_w, H - 180), WATERMARK, font=tiny, fill=(150, 150, 160))

    out = "verse.png"
    img.save(out, "PNG")
    return out


# ---------------------------------------------------
# SÉLECTION PAR JOUR
# ---------------------------------------------------
def load_list(path):
    arr = load_json(path)
    if not arr:
        raise RuntimeError(f"Liste vide : {path}")
    return arr


def reshuffle_if_needed(path, index):
    arr = load_list(path)
    if index >= len(arr):
        random.shuffle(arr)
        save_json(path, arr)
        index = 0
    return arr, index


def pick_from_category(cat, progress):
    index        = progress.get(cat["key"], 0)
    arr, index   = reshuffle_if_needed(cat["file"], index)
    book, ch, v  = arr[index]
    progress[cat["key"]] = index + 1
    return book, ch, v


def main():
    progress = load_json(PROGRESS_FILE)

    weekday  = datetime.datetime.utcnow().weekday()
    cat_name = DAY_SCHEDULE[weekday]
    cat      = CATEGORIES[cat_name]

    book, ch, v = pick_from_category(cat, progress)

    raw_text = load_verse(book, ch, v)
    text      = clean_text(raw_text)
    ref       = f"{book} {ch}:{v}"

    print(f"📖 Verset du jour : {ref} [{cat_name}]")

    img     = make_image(text, ref)
    caption = f"{cat['emoji']} <b>{ref}</b>\n#LaBible #LSG1910 #versetdujour {cat['tag']}"

    # Publier sur Telegram
    send_photo(img, caption)

    # Publier sur Facebook
    post_to_facebook(img, ref, text, cat)

    save_json(PROGRESS_FILE, progress)
    print("✅ Terminé.")


if __name__ == "__main__":
    main()
from PIL import Image, ImageDraw, ImageFont, ImageFilter

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL = os.environ["TELEGRAM_CHANNEL"]

# Meta Facebook
FB_PAGE_ID    = os.environ.get("FB_PAGE_ID", "1018605031335601")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "")

PROGRESS_FILE = "progress.json"
BIBLE_FILE = "bible/lsg1910.json"

FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_SANS  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

WATERMARK    = "LaBible.app"
MINI_APP_URL = "https://t.me/BIBLE_APP_BOT/labible"

# Categorias disponíveis
CATEGORIES = {
    "promise": {
        "key":   "i_promise",
        "file":  "promesses_curated.json",
        "emoji": "🌿",
        "tag":   "#Promesse"
    },
    "jesus": {
        "key":   "i_jesus",
        "file":  "jesus_curated.json",
        "emoji": "✝️",
        "tag":   "#ParoleDeJésus"
    },
    "psaume": {
        "key":   "i_psaume",
        "file":  "psaumes_curated.json",
        "emoji": "🎵",
        "tag":   "#Psaume"
    },
    "proverbe": {
        "key":   "i_proverbe",
        "file":  "proverbes_curated.json",
        "emoji": "💡",
        "tag":   "#Sagesse"
    },
    "prophetie": {
        "key":   "i_prophetie",
        "file":  "propheties_curated.json",
        "emoji": "🔯",
        "tag":   "#Prophétie"
    },
}

# Rotation par jour de la semaine (0=lundi … 6=dimanche)
DAY_SCHEDULE = {
    0: "promise",    # Lundi
    1: "proverbe",   # Mardi
    2: "jesus",      # Mercredi
    3: "psaume",     # Jeudi
    4: "prophetie",  # Vendredi
    5: "proverbe",   # Samedi
    6: "psaume",     # Dimanche
}


# ---------------------------------------------------
# CLEAN TEXT
# ---------------------------------------------------
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("¶", "").strip()
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([;:?!])', r' \1', text)
    text = text.replace("'", "\u2019").replace("'", "\u2019")
    if not text.endswith(('.', '!', '?')):
        text += '.'
    return f"« {text} »"

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


def save_json(path, data):
    with open(path,"w",encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# Index du fichier Bible chargé une seule fois
_bible_index = None

def get_bible_index():
    global _bible_index
    if _bible_index is None:
        data = load_json(BIBLE_FILE)
        _bible_index = {}
        for v in data["verses"]:
            bn = v["book_name"]
            ch = str(v["chapter"])
            vs = str(v["verse"])
            if bn not in _bible_index:
                _bible_index[bn] = {}
            if ch not in _bible_index[bn]:
                _bible_index[bn][ch] = {}
            _bible_index[bn][ch][vs] = v["text"]
    return _bible_index

def load_verse(book_name, chapter, verse):
    index = get_bible_index()
    return index[book_name][str(chapter)][str(verse)]


# ---------------------------------------------------
# ENVOI TELEGRAM
# ---------------------------------------------------
def send_photo(path, caption):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    reply_markup = json.dumps({
        "inline_keyboard": [[
            {"text": "📖 Lire dans LaBible.app", "url": MINI_APP_URL}
        ]]
    })
    with open(path, "rb") as f:
        r = requests.post(
            url,
            data={
                "chat_id": CHANNEL,
                "caption": caption,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": reply_markup
            },
            files={"photo": f},
            timeout=30
        )
    r.raise_for_status()


# ---------------------------------------------------
# ENVOI FACEBOOK
# ---------------------------------------------------
def post_to_facebook(image_path, ref, text, cat):
    if not FB_PAGE_TOKEN:
        print("FB_PAGE_TOKEN non défini — publication Facebook ignorée.")
        return

    # Texte du post Facebook
    fb_message = (
        f"{cat['emoji']} {ref}\n\n"
        f"{text}\n\n"
        f"📖 Lisez la Bible complète gratuitement sur labible.app\n\n"
        f"#LaBible #LSG1910 #VersetDuJour #Bible {cat['tag']} #Foi #Chrétien"
    )

    # Upload image + publication en une seule requête
    upload_url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
    with open(image_path, "rb") as f:
        r = requests.post(
            upload_url,
            data={
                "message": fb_message,
                "access_token": FB_PAGE_TOKEN,
            },
            files={"source": f},
            timeout=60
        )

    if r.status_code == 200:
        print(f"✅ Facebook publié : {r.json()}")
    else:
        print(f"❌ Erreur Facebook : {r.status_code} — {r.text}")


# ---------------------------------------------------
# IMAGE
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
    img  = make_background(W, H)
    draw = ImageDraw.Draw(img)

    gold  = (195, 165, 90)
    gold2 = (140, 120, 65)

    margin = 60
    draw.rounded_rectangle([margin, margin, W - margin, H - margin],
                            radius=30, outline=gold, width=6)
    inner = margin + 16
    draw.rounded_rectangle([inner, inner, W - inner, H - inner],
                            radius=26, outline=gold2, width=2)

    pad_x  = 140
    top    = 190
    bottom = 350
    max_w  = W - 2 * pad_x
    max_h  = H - top - bottom

    chosen_font = chosen_lines = chosen_line_h = None
    for size in range(66, 36, -2):
        font   = ImageFont.truetype(FONT_SERIF, size)
        lines  = wrap_text(draw, text, font, max_w)
        line_h = int(size * 1.35)
        if line_h * len(lines) <= max_h:
            chosen_font   = font
            chosen_lines  = lines
            chosen_line_h = line_h
            break

    if chosen_font is None:
        chosen_font   = ImageFont.truetype(FONT_SERIF, 36)
        chosen_lines  = wrap_text(draw, text, chosen_font, max_w)
        chosen_line_h = int(36 * 1.35)

    total_h = chosen_line_h * len(chosen_lines)
    y = top + max(0, (max_h - total_h) // 2)

    for line in chosen_lines:
        line_w = draw.textlength(line, font=chosen_font)
        x = (W - line_w) // 2
        draw.text((x + 2, y + 2), line, font=chosen_font, fill=(0, 0, 0))
        draw.text((x, y),         line, font=chosen_font, fill=(245, 245, 245))
        y += chosen_line_h

    small = ImageFont.truetype(FONT_SANS, 36)
    tiny  = ImageFont.truetype(FONT_SANS, 28)

    draw.line([(pad_x, H - 260), (W - pad_x, H - 260)], fill=(150, 130, 70), width=2)
    draw.text((pad_x, H - 220), ref,        font=small, fill=(220, 220, 230))
    draw.text((pad_x, H - 180), "LSG 1910", font=tiny,  fill=(170, 170, 180))

    wm_w = draw.textlength(WATERMARK, font=tiny)
    draw.text((W - pad_x - wm_w, H - 180), WATERMARK, font=tiny, fill=(150, 150, 160))

    out = "verse.png"
    img.save(out, "PNG")
    return out


# ---------------------------------------------------
# SÉLECTION PAR JOUR
# ---------------------------------------------------
def load_list(path):
    arr = load_json(path)
    if not arr:
        raise RuntimeError(f"Liste vide : {path}")
    return arr


def reshuffle_if_needed(path, index):
    arr = load_list(path)
    if index >= len(arr):
        random.shuffle(arr)
        save_json(path, arr)
        index = 0
    return arr, index


def pick_from_category(cat, progress):
    index        = progress.get(cat["key"], 0)
    arr, index   = reshuffle_if_needed(cat["file"], index)
    book, ch, v  = arr[index]
    progress[cat["key"]] = index + 1
    return book, ch, v


def main():
    progress = load_json(PROGRESS_FILE)

    weekday  = datetime.datetime.utcnow().weekday()
    cat_name = DAY_SCHEDULE[weekday]
    cat      = CATEGORIES[cat_name]

    book, ch, v = pick_from_category(cat, progress)

    raw_text = load_verse(book, ch, v)
    text      = clean_text(raw_text)
    ref       = f"{book} {ch}:{v}"

    img     = make_image(text, ref)
    caption = f"{cat['emoji']} <b>{ref}</b>\n#LaBible #LSG1910 #versetdujour {cat['tag']}"

    # Publier sur Telegram
    send_photo(img, caption)

    # Publier sur Facebook
    post_to_facebook(img, ref, text, cat)

    save_json(PROGRESS_FILE, progress)


if __name__ == "__main__":
    main()
