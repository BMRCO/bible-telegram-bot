import os
import json
import random
import re
import datetime
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

TOKEN         = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL       = os.environ["TELEGRAM_CHANNEL"]

# Meta Facebook
FB_PAGE_ID    = os.environ.get("FB_PAGE_ID", "1018605031335601")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "")

# Instagram
IG_ACCOUNT_ID = os.environ.get("IG_ACCOUNT_ID", "17841447648424267")

# ImgBB (hébergement image public pour Instagram)
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "")

PROGRESS_FILE = "progress.json"
BIBLE_FILE    = "bible/lsg1910.json"

FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_SANS  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

WATERMARK    = "LaBible.app"
MINI_APP_URL = "https://t.me/BIBLE_APP_BOT/labible"
APP_URL      = "https://www.labible.app"

# Hashtags de base communs (Instagram — 3 fixas)
HASHTAGS_BASE_IG = [
    "#LaBible", "#VersetDuJour", "#Bible",
]

# Hashtags de base communs (Facebook — 5 max)
HASHTAGS_BASE_FB = [
    "#LaBible", "#VersetDuJour", "#Bible", "#Foi", "#BibleFrancais",
]

# Hashtags spécifiques par catégorie (Instagram — 2 supplémentaires = 5 total)
HASHTAGS_CAT_IG = {
    "promise":   ["#Promesse", "#Espérance"],
    "jesus":     ["#ParoleDeJésus", "#Foi"],
    "psaume":    ["#Psaume", "#Louange"],
    "proverbe":  ["#Sagesse", "#Confiance"],
    "prophetie": ["#Prophétie", "#Espérance"],
}

# Hashtags spécifiques par catégorie (Facebook — 2 supplémentaires)
HASHTAGS_CAT_FB = {
    "promise":   ["#Promesse", "#Espérance"],
    "jesus":     ["#ParoleDeJésus", "#Évangile"],
    "psaume":    ["#Psaume", "#Louange"],
    "proverbe":  ["#Sagesse", "#Proverbes"],
    "prophetie": ["#Prophétie", "#Révélation"],
}

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


def build_hashtags_ig(cat_name):
    specific = HASHTAGS_CAT_IG.get(cat_name, [])
    all_tags = HASHTAGS_BASE_IG + specific
    return " ".join(all_tags[:5])


def build_hashtags_fb(cat_name):
    specific = HASHTAGS_CAT_FB.get(cat_name, [])
    all_tags = HASHTAGS_BASE_FB + specific
    return " ".join(all_tags[:7])


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


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
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
    print("✅ Telegram publié")


# ---------------------------------------------------
# ENVOI FACEBOOK
# ---------------------------------------------------
def post_to_facebook(image_path, ref, text, cat, cat_name):
    if not FB_PAGE_TOKEN:
        print("⚠️  FB_PAGE_TOKEN non défini — publication Facebook ignorée.")
        return

    hashtags = build_hashtags_fb(cat_name)

    fb_message = (
        f"{cat['emoji']} {ref}\n\n"
        f"{text}\n\n"
        f"📖 Lisez la Bible complète gratuitement sur {APP_URL}\n\n"
        f"{hashtags}"
    )

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
        post_id = r.json().get("post_id") or r.json().get("id", "inconnu")
        print(f"✅ Facebook publié — post_id: {post_id}")
    else:
        print(f"❌ Erreur Facebook ({r.status_code}): {r.text}")


# ---------------------------------------------------
# UPLOAD IMAGE → ImgBB (URL public pour Instagram)
# ---------------------------------------------------
def upload_to_imgbb(image_path):
    if not IMGBB_API_KEY:
        print("⚠️  IMGBB_API_KEY non défini — upload ignoré.")
        return None

    with open(image_path, "rb") as f:
        r = requests.post(
            "https://api.imgbb.com/1/upload",
            params={"key": IMGBB_API_KEY},
            files={"image": f},
            timeout=60
        )

    if r.status_code == 200:
        url = r.json()["data"]["url"]
        print(f"✅ Image uploadée sur ImgBB : {url}")
        # Attendre que l'image soit accessible publiquement
        import time
        time.sleep(5)
        return url
    else:
        print(f"❌ Erreur ImgBB ({r.status_code}): {r.text}")
        return None


# ---------------------------------------------------
# ENVOI INSTAGRAM
# ---------------------------------------------------
def post_to_instagram(image_path, ref, text, cat, cat_name):
    if not FB_PAGE_TOKEN:
        print("⚠️  FB_PAGE_TOKEN non défini — publication Instagram ignorée.")
        return
    if not IMGBB_API_KEY:
        print("⚠️  IMGBB_API_KEY non défini — publication Instagram ignorée.")
        return

    image_url = upload_to_imgbb(image_path)
    if not image_url:
        return

    hashtags = build_hashtags_ig(cat_name)

    ig_caption = (
        f"{cat['emoji']} {ref}\n\n"
        f"{text}\n\n"
        f"📖 Bible complète gratuite sur {APP_URL}\n\n"
        f"{hashtags}"
    )

    container_url = f"https://graph.facebook.com/v25.0/{IG_ACCOUNT_ID}/media"
    r = requests.post(
        container_url,
        data={
            "image_url": image_url,
            "caption": ig_caption,
            "access_token": FB_PAGE_TOKEN,
        },
        timeout=60
    )

    if r.status_code != 200:
        print(f"❌ Erreur création container Instagram ({r.status_code}): {r.text}")
        return

    container_id = r.json().get("id")
    print(f"✅ Container Instagram créé : {container_id}")

    publish_url = f"https://graph.facebook.com/v25.0/{IG_ACCOUNT_ID}/media_publish"
    r2 = requests.post(
        publish_url,
        data={
            "creation_id": container_id,
            "access_token": FB_PAGE_TOKEN,
        },
        timeout=60
    )

    if r2.status_code == 200:
        post_id = r2.json().get("id", "inconnu")
        print(f"✅ Instagram publié — post_id: {post_id}")
    else:
        print(f"❌ Erreur publication Instagram ({r2.status_code}): {r2.text}")


# ---------------------------------------------------
# IMAGE — palettes simples, design limpo
# ---------------------------------------------------

# Palettes : (fundo_topo, fundo_base, cor_borda, cor_ref, cor_watermark)
PALETTES = [
    # Azul escuro — ouro (original)
    ((10, 14, 30),  (6,  10, 22),  (195, 165,  90), (195, 165,  90), (130, 120, 80)),
    # Azul marinho frio — azul claro
    ((8,  18, 38),  (5,  12, 28),  (160, 190, 220), (160, 190, 220), (100, 130, 160)),
    # Verde floresta — verde claro
    ((10, 22, 14),  (6,  15, 10),  (140, 195, 120), (140, 195, 120), (90,  140,  80)),
    # Bordeaux — laranja quente
    ((28, 10, 14),  (18,  6,  9),  (210, 160, 120), (210, 160, 120), (150, 110,  80)),
    # Preto puro — ouro
    ((10, 10, 10),  (4,   4,  4),  (200, 180, 120), (200, 180, 120), (120, 110,  70)),
    # Azul royal — ouro
    ((10, 20, 50),  (6,  14, 36),  (200, 165,  80), (200, 165,  80), (130, 110,  55)),
]


def _gradient(W, H, top, bot):
    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(top[0] + t * (bot[0] - top[0]))
        g = int(top[1] + t * (bot[1] - top[1]))
        b = int(top[2] + t * (bot[2] - top[2]))
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    return img


def wrap_text(draw, text, font, max_w):
    words = text.split()
    if not words:
        return [""]
    lines   = []
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
    palette                                          = random.choice(PALETTES)
    bg_top, bg_bot, color_border, color_ref, color_wm = palette

    W, H = 1080, 1080
    img  = _gradient(W, H, bg_top, bg_bot)
    draw = ImageDraw.Draw(img)

    # Borda exterior
    m = 60
    draw.rounded_rectangle(
        [m, m, W - m, H - m],
        radius=30, outline=color_border, width=6
    )
    # Borda interior
    inner = m + 16
    draw.rounded_rectangle(
        [inner, inner, W - inner, H - inner],
        radius=24, outline=color_border, width=1
    )

    # Margens do texto
    pad_x  = 140
    top    = 180
    bottom = 330
    max_w  = W - 2 * pad_x
    max_h  = H - top - bottom

    # Escolher tamanho de fonte que caiba
    chosen_font = chosen_lines = chosen_lh = None
    for size in range(66, 34, -2):
        font  = ImageFont.truetype(FONT_SERIF, size)
        lines = wrap_text(draw, text, font, max_w)
        lh    = int(size * 1.38)
        if lh * len(lines) <= max_h:
            chosen_font, chosen_lines, chosen_lh = font, lines, lh
            break

    if chosen_font is None:
        chosen_font  = ImageFont.truetype(FONT_SERIF, 34)
        chosen_lines = wrap_text(draw, text, chosen_font, max_w)
        chosen_lh    = int(34 * 1.38)

    # Centrar verticalmente
    total_h = chosen_lh * len(chosen_lines)
    y       = top + max(0, (max_h - total_h) // 2)

    for line in chosen_lines:
        lw = draw.textlength(line, font=chosen_font)
        x  = (W - lw) // 2
        draw.text((x + 2, y + 2), line, font=chosen_font, fill=(0, 0, 0))       # sombra
        draw.text((x,     y    ), line, font=chosen_font, fill=(245, 245, 245))  # texto
        y += chosen_lh

    # Linha separadora
    draw.line([(pad_x, H - 260), (W - pad_x, H - 260)],
              fill=color_border, width=2)

    # Referência e LSG 1910
    small = ImageFont.truetype(FONT_SANS, 36)
    tiny  = ImageFont.truetype(FONT_SANS, 28)

    draw.text((pad_x, H - 230), ref,        font=small, fill=color_ref)
    draw.text((pad_x, H - 185), "LSG 1910", font=tiny,  fill=color_wm)

    # Watermark à direita
    ww = draw.textlength(WATERMARK, font=tiny)
    draw.text((W - pad_x - ww, H - 185), WATERMARK, font=tiny, fill=color_wm)

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
    index       = progress.get(cat["key"], 0)
    arr, index  = reshuffle_if_needed(cat["file"], index)
    book, ch, v = arr[index]
    progress[cat["key"]] = index + 1
    return book, ch, v


# ---------------------------------------------------
# MAIN
# ---------------------------------------------------
def main():
    progress = load_json(PROGRESS_FILE)

    weekday  = datetime.datetime.utcnow().weekday()
    cat_name = DAY_SCHEDULE[weekday]
    cat      = CATEGORIES[cat_name]

    book, ch, v = pick_from_category(cat, progress)

    raw_text = load_verse(book, ch, v)
    text     = clean_text(raw_text)
    ref      = f"{book} {ch}:{v}"

    print(f"📖 Verset du jour : {ref} [{cat_name}]")

    img     = make_image(text, ref)
    caption = f"{cat['emoji']} <b>{ref}</b>\n#LaBible #LSG1910 #versetdujour {cat['tag']}"

    # Publier sur Telegram
    send_photo(img, caption)

    # Publier sur Facebook
    post_to_facebook(img, ref, text, cat, cat_name)

    # Publier sur Instagram
    post_to_instagram(img, ref, text, cat, cat_name)

    save_json(PROGRESS_FILE, progress)
    print("✅ Terminé.")


if __name__ == "__main__":
    main()
