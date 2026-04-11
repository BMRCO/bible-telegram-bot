import os
import json
import random
import re
import datetime
import math
import subprocess
import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

TOKEN         = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL       = os.environ["TELEGRAM_CHANNEL"]

FB_PAGE_ID    = os.environ.get("FB_PAGE_ID", "1018605031335601")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "")
IG_ACCOUNT_ID = os.environ.get("IG_ACCOUNT_ID", "17841447648424267")
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "")
YT_CLIENT_ID      = os.environ.get("YOUTUBE_CLIENT_ID", "")
YT_CLIENT_SECRET  = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YT_REFRESH_TOKEN  = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY    = os.environ.get("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")
PINTEREST_ACCESS_TOKEN = os.environ.get("PINTEREST_ACCESS_TOKEN", "")
PINTEREST_BOARD_ID     = os.environ.get("PINTEREST_BOARD_ID", "1092404522055080754")

PROGRESS_FILE = "progress.json"
BIBLE_FILE    = "bible/lsg1910.json"

FONT_SERIF      = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_SERIF_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
FONT_SANS       = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

WATERMARK    = "LaBible.app"
MINI_APP_URL = "https://t.me/BIBLE_APP_BOT/labible"
APP_URL      = "https://labible.app"

HASHTAGS_BASE_IG = [
    "#Bible", "#VersetDuJour", "#BibleFrancaise",
    "#Chrétien", "#Foi", "#Évangile", "#Jésus",
    "#ParoleDeDieu", "#LSG1910", "#LaBible",
]

HASHTAGS_BASE_FB = [
    "#Bible", "#VersetDuJour", "#Foi", "#BibleFrancaise", "#Chrétien",
]

HASHTAGS_CAT_IG = {
    "promise":   ["#Promesse", "#Espérance", "#PromesseDeDieu", "#Bénédiction", "#Confiance"],
    "jesus":     ["#JésusChrist", "#ParoleDeJésus", "#GrâceDeDieu", "#Rédemption", "#Amour"],
    "psaume":    ["#Psaumes", "#Louange", "#Adoration", "#Prière", "#Cantique"],
    "proverbe":  ["#Sagesse", "#Proverbes", "#SagesseDeJésus", "#Discernement", "#Conseil"],
    "prophetie": ["#Prophétie", "#EspoirEnDieu", "#Révélation", "#Accomplissement", "#GloireDeDieu"],
}

HASHTAGS_CAT_FB = {
    "promise":   ["#Promesse", "#Bénédiction"],
    "jesus":     ["#JésusChrist", "#GrâceDeDieu"],
    "psaume":    ["#Louange", "#Adoration"],
    "proverbe":  ["#Sagesse", "#Discernement"],
    "prophetie": ["#Prophétie", "#EspoirEnDieu"],
}

CATEGORIES = {
    "promise":   {"key": "i_promise",   "file": "promesses_curated.json",  "emoji": "🌿", "tag": "#Promesse"},
    "jesus":     {"key": "i_jesus",     "file": "jesus_curated.json",       "emoji": "✝️", "tag": "#ParoleDeJésus"},
    "psaume":    {"key": "i_psaume",    "file": "psaumes_curated.json",     "emoji": "🎵", "tag": "#Psaumes"},
    "proverbe":  {"key": "i_proverbe",  "file": "proverbes_curated.json",   "emoji": "💡", "tag": "#Sagesse"},
    "prophetie": {"key": "i_prophetie", "file": "propheties_curated.json",  "emoji": "📯", "tag": "#Prophétie"},
}

# ---------------------------------------------------
# ROTATION PAR HEURE UTC — alignée avec publish.yml
# 05h UTC → 07h France — image → psaume  (Matin)
# 06h UTC → 08h France — reel  → promise
# 11h UTC → 13h France — image → proverbe
# 13h UTC → 15h France — reel  → jesus
# 17h UTC → 19h France — image → prophetie
# 19h UTC → 21h France — reel  → psaume  (Soir)
# ---------------------------------------------------
HOUR_SCHEDULE = {
    5:  "psaume",
    6:  "promise",
    11: "proverbe",
    13: "jesus",
    17: "prophetie",
    19: "psaume",
}

# Fallback par heure approximative — évite la répétition du même thème
HOUR_FALLBACK = {
    0:  "promise",
    1:  "psaume",
    2:  "proverbe",
    3:  "jesus",
    4:  "prophetie",
    5:  "psaume",
    6:  "promise",
    7:  "proverbe",
    8:  "jesus",
    9:  "prophetie",
    10: "promise",
    11: "proverbe",
    12: "jesus",
    13: "jesus",
    14: "prophetie",
    15: "promise",
    16: "proverbe",
    17: "prophetie",
    18: "promise",
    19: "psaume",
    20: "proverbe",
    21: "jesus",
    22: "promise",
    23: "psaume",
}


def build_yt_title(cat_name, cat, ref, hour_utc):
    if cat_name == "psaume":
        label = "Psaume du Matin" if hour_utc == 5 else "Psaume du Soir"
    elif cat_name == "promise":
        label = "Promesses de Dieu"
    elif cat_name == "jesus":
        label = "Paroles de Jésus"
    elif cat_name == "proverbe":
        label = "Sagesse Biblique"
    elif cat_name == "prophetie":
        label = "Prophéties Bibliques"
    else:
        label = "Verset Biblique"
    title = f"{cat['emoji']} {label} — {ref} | Bible LSG1910"
    if len(title) > 100:
        title = title[:97] + "..."
    return title


def build_hashtags_ig(cat_name):
    specific = HASHTAGS_CAT_IG.get(cat_name, [])
    return " ".join((HASHTAGS_BASE_IG + specific)[:15])


def build_hashtags_fb(cat_name):
    specific = HASHTAGS_CAT_FB.get(cat_name, [])
    return " ".join((HASHTAGS_BASE_FB + specific)[:7])


def strip_rubric(text: str) -> str:
    rubric_keywords = [
        "chef des chantres", "maschil", "michtam", "cantique",
        "psaume de david", "prière de", "fils de koré", "sur alamoth",
        "sur les", "au chef", "à jouer", "pour les", "jeduthun",
        "higgaion", "sheminith", "nehiloth", "neginoth", "gittith",
    ]
    t = text.lower()
    for kw in rubric_keywords:
        if kw in t:
            sentences = text.split(". ")
            real_sentences = [s for s in sentences if not any(kw in s.lower() for kw in rubric_keywords)]
            if real_sentences:
                return ". ".join(real_sentences).strip()
    return text


def is_rubric(text: str) -> bool:
    rubric_keywords = [
        "chef des chantres", "maschil", "michtam",
        "fils de koré", "sur alamoth", "au chef",
        "jeduthun", "higgaion", "sheminith", "nehiloth", "neginoth", "gittith",
    ]
    t = text.lower()
    if len(t.split()) < 18:
        for kw in rubric_keywords:
            if kw in t:
                return True
    return False


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("¶", "").strip()
    text = re.sub(r'\s*[-—]\s*Pause\.?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*Sélah\.?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*Selah\.?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s*([?!])', r' \1', text)
    text = text.replace("'", "\u2019").replace("'", "\u2019")
    text = text.replace("Eternel", "Éternel")
    text = text.rstrip(';').rstrip(':').strip()
    if not text.endswith(('.', '!', '?')):
        text += '.'
    return text


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


_bible_index = None

def get_bible_index():
    global _bible_index
    if _bible_index is None:
        data = load_json(BIBLE_FILE)
        _bible_index = {}
        for v in data["verses"]:
            bn, ch, vs = v["book_name"], str(v["chapter"]), str(v["verse"])
            if bn not in _bible_index:
                _bible_index[bn] = {}
            if ch not in _bible_index[bn]:
                _bible_index[bn][ch] = {}
            _bible_index[bn][ch][vs] = v["text"]
    return _bible_index


BOOK_NAME_MAP = {
    "Psaumes": "Psaume", "Cantique des Cantiques": "Cantique des cantiques",
    "1 Rois": "1 Rois", "2 Rois": "2 Rois",
    "1 Samuel": "1 Samuel", "2 Samuel": "2 Samuel",
    "1 Chroniques": "1 Chroniques", "2 Chroniques": "2 Chroniques",
}

def load_verse(book_name, chapter, verse):
    index = get_bible_index()
    real_name = BOOK_NAME_MAP.get(book_name, book_name)
    if real_name not in index:
        for key in index:
            if key.lower() == real_name.lower():
                real_name = key
                break
    return index[real_name][str(chapter)][str(verse)]


# ---------------------------------------------------
# TELEGRAM
# ---------------------------------------------------
def send_photo(path, caption):
    reply_markup = json.dumps({"inline_keyboard": [[{"text": "📖 Lire dans LaBible.app", "url": MINI_APP_URL}]]})
    with open(path, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
            data={"chat_id": CHANNEL, "caption": caption, "parse_mode": "HTML", "disable_web_page_preview": True, "reply_markup": reply_markup},
            files={"photo": f}, timeout=30)
    r.raise_for_status()
    print("✅ Telegram publié")


def send_video(path, caption):
    reply_markup = json.dumps({"inline_keyboard": [[{"text": "📖 Lire dans LaBible.app", "url": MINI_APP_URL}]]})
    with open(path, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendVideo",
            data={"chat_id": CHANNEL, "caption": caption, "parse_mode": "HTML", "disable_web_page_preview": True, "reply_markup": reply_markup},
            files={"video": f}, timeout=60)
    r.raise_for_status()
    print("✅ Telegram vidéo publié")


# ---------------------------------------------------
# FACEBOOK
# ---------------------------------------------------
def post_to_facebook(image_path, ref, text, cat, cat_name):
    if not FB_PAGE_TOKEN:
        print("⚠️  FB_PAGE_TOKEN non défini.")
        return
    msg = f"{cat['emoji']} {ref}\n\n« {text} »\n\n📖 Lisez la Bible complète gratuitement sur {APP_URL}\n\n👇 Partage ce verset avec quelqu'un qui en a besoin 🙏\n\n{build_hashtags_fb(cat_name)}"
    with open(image_path, "rb") as f:
        r = requests.post(f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/photos",
            data={"message": msg, "access_token": FB_PAGE_TOKEN}, files={"source": f}, timeout=60)
    if r.status_code == 200:
        print(f"✅ Facebook publié — {r.json().get('post_id') or r.json().get('id')}")
    else:
        print(f"❌ Erreur Facebook ({r.status_code}): {r.text}")


def post_reel_to_facebook(video_path, ref, text, cat, cat_name):
    if not FB_PAGE_TOKEN:
        print("⚠️  FB_PAGE_TOKEN non défini.")
        return
    desc = f"{cat['emoji']} {ref}\n\n« {text} »\n\n📖 Bible complète gratuite sur {APP_URL}\n\n👇 Partage ce verset avec quelqu'un qui en a besoin 🙏\n\n{build_hashtags_fb(cat_name)}"
    with open(video_path, "rb") as f:
        r = requests.post(f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/videos",
            data={"description": desc, "access_token": FB_PAGE_TOKEN}, files={"source": f}, timeout=120)
    if r.status_code == 200:
        print(f"✅ Facebook reel publié — {r.json().get('id')}")
    else:
        print(f"❌ Erreur Facebook reel ({r.status_code}): {r.text}")


# ---------------------------------------------------
# IMGBB / CLOUDINARY
# ---------------------------------------------------
def upload_to_imgbb(image_path):
    if not IMGBB_API_KEY:
        return None
    with open(image_path, "rb") as f:
        r = requests.post("https://api.imgbb.com/1/upload", params={"key": IMGBB_API_KEY}, files={"image": f}, timeout=60)
    if r.status_code == 200:
        url = r.json()["data"]["url"]
        print(f"✅ ImgBB : {url}")
        import time; time.sleep(5)
        return url
    print(f"❌ ImgBB ({r.status_code}): {r.text}")
    return None


def upload_to_cloudinary(image_path):
    if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
        return upload_to_imgbb(image_path)
    import hashlib, time as _time
    ts = str(int(_time.time()))
    sig = hashlib.sha1(f"timestamp={ts}{CLOUDINARY_API_SECRET.strip()}".encode()).hexdigest()
    with open(image_path, "rb") as f:
        r = requests.post(f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload",
            data={"api_key": CLOUDINARY_API_KEY, "timestamp": ts, "signature": sig}, files={"file": f}, timeout=60)
    if r.status_code == 200:
        url = r.json()["secure_url"]
        print(f"✅ Cloudinary : {url}")
        _time.sleep(3)
        return url
    print(f"❌ Cloudinary ({r.status_code}): {r.text}")
    return upload_to_imgbb(image_path)


def upload_video_public(video_path):
    if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
        return None
    import hashlib, time as _time
    print("⏳ Upload vidéo Cloudinary...")
    ts = str(int(_time.time()))
    sig = hashlib.sha1(f"timestamp={ts}{CLOUDINARY_API_SECRET.strip()}".encode()).hexdigest()
    with open(video_path, "rb") as f:
        r = requests.post(f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/video/upload",
            data={"api_key": CLOUDINARY_API_KEY, "timestamp": ts, "signature": sig, "resource_type": "video"},
            files={"file": f}, timeout=180)
    if r.status_code == 200:
        url = r.json()["secure_url"]
        print(f"✅ Cloudinary vidéo : {url}")
        _time.sleep(5)
        return url
    print(f"❌ Cloudinary vidéo ({r.status_code}): {r.text}")
    return None


# ---------------------------------------------------
# INSTAGRAM
# ---------------------------------------------------
def post_to_instagram(image_path, ref, text, cat, cat_name):
    if not FB_PAGE_TOKEN:
        return
    image_url = upload_to_cloudinary(image_path)
    if not image_url:
        return
    if "cloudinary.com" in image_url:
        image_url = image_url.replace("/upload/", "/upload/f_jpg/")
    caption = f"{cat['emoji']} {ref}\n\n« {text} »\n\n📖 Bible complète gratuite sur {APP_URL}\n\n👇 Partage ce verset avec quelqu'un qui en a besoin 🙏\n\n{build_hashtags_ig(cat_name)}"
    r = requests.post(f"https://graph.facebook.com/v25.0/{IG_ACCOUNT_ID}/media",
        data={"image_url": image_url, "caption": caption, "access_token": FB_PAGE_TOKEN}, timeout=60)
    if r.status_code != 200:
        print(f"❌ Instagram container ({r.status_code}): {r.text}")
        return
    container_id = r.json().get("id")
    print(f"✅ Container Instagram : {container_id}")
    import time
    for attempt in range(8):
        time.sleep(8)
        rs = requests.get(f"https://graph.facebook.com/v25.0/{container_id}",
            params={"fields": "status_code", "access_token": FB_PAGE_TOKEN}, timeout=30)
        status = rs.json().get("status_code", "")
        print(f"  ⏳ {status} (tentative {attempt+1})")
        if status == "FINISHED":
            break
        if status == "ERROR":
            print("❌ Erreur Instagram.")
            return
    r2 = requests.post(f"https://graph.facebook.com/v25.0/{IG_ACCOUNT_ID}/media_publish",
        data={"creation_id": container_id, "access_token": FB_PAGE_TOKEN}, timeout=60)
    if r2.status_code == 200:
        print(f"✅ Instagram publié — {r2.json().get('id')}")
    else:
        print(f"❌ Instagram publication ({r2.status_code}): {r2.text}")


def post_reel_to_instagram(video_path, ref, text, cat, cat_name):
    if not FB_PAGE_TOKEN:
        return
    video_url = upload_video_public(video_path)
    if not video_url:
        return
    caption = f"{cat['emoji']} {ref}\n\n« {text} »\n\n📖 Bible complète gratuite sur {APP_URL}\n\n👇 Partage ce verset avec quelqu'un qui en a besoin 🙏\n\n{build_hashtags_ig(cat_name)}"
    r = requests.post(f"https://graph.facebook.com/v25.0/{IG_ACCOUNT_ID}/media",
        data={"media_type": "REELS", "video_url": video_url, "caption": caption, "access_token": FB_PAGE_TOKEN, "thumb_offset": "7500"}, timeout=60)
    if r.status_code != 200:
        print(f"❌ Reel Instagram container ({r.status_code}): {r.text}")
        return
    container_id = r.json().get("id")
    print(f"✅ Container reel : {container_id}")
    import time
    for attempt in range(10):
        time.sleep(15)
        rs = requests.get(f"https://graph.facebook.com/v25.0/{container_id}",
            params={"fields": "status_code", "access_token": FB_PAGE_TOKEN}, timeout=30)
        status = rs.json().get("status_code", "")
        print(f"  ⏳ {status} (tentative {attempt+1})")
        if status == "FINISHED":
            break
        if status == "ERROR":
            print("❌ Erreur reel Instagram.")
            return
    r2 = requests.post(f"https://graph.facebook.com/v25.0/{IG_ACCOUNT_ID}/media_publish",
        data={"creation_id": container_id, "access_token": FB_PAGE_TOKEN}, timeout=60)
    if r2.status_code == 200:
        print(f"✅ Instagram reel publié — {r2.json().get('id')}")
    else:
        print(f"❌ Instagram reel publication ({r2.status_code}): {r2.text}")


# ---------------------------------------------------
# PINTEREST
# ---------------------------------------------------
def post_to_pinterest(image_path, ref, text, cat, cat_name):
    if not PINTEREST_ACCESS_TOKEN:
        return
    image_url = upload_to_imgbb(image_path)
    if not image_url:
        return
    pin_keywords = {"promise": "Promesses de Dieu", "jesus": "Paroles de Jésus",
                    "psaume": "Psaumes Bibliques", "proverbe": "Sagesse Biblique", "prophetie": "Prophéties Bibliques"}
    payload = {
        "board_id": PINTEREST_BOARD_ID,
        "title": f"{cat['emoji']} {pin_keywords.get(cat_name, 'Verset Biblique')} — {ref} | LaBible.app",
        "description": f"{cat['emoji']} « {text} »\n\n— {ref} (LSG 1910)\n\n📖 Lisez la Bible sur LaBible.app\n\n#Bible #VersetDuJour #LaBible #LSG1910 #Foi",
        "link": f"{APP_URL}/#{ref.replace(' ', '-')}",
        "media_source": {"source_type": "image_url", "url": image_url}
    }
    r = requests.post("https://api.pinterest.com/v5/pins",
        headers={"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}", "Content-Type": "application/json"},
        json=payload, timeout=60)
    if r.status_code in (200, 201):
        print(f"✅ Pinterest publié — {r.json().get('id')}")
    else:
        print(f"❌ Pinterest ({r.status_code}): {r.text}")


# ---------------------------------------------------
# THREADS
# ---------------------------------------------------
def post_to_threads(image_path, ref, text, cat, cat_name):
    if not THREADS_ACCESS_TOKEN:
        return
    image_url = upload_to_cloudinary(image_path)
    if not image_url:
        return
    if "cloudinary.com" in image_url:
        image_url = image_url.replace("/upload/", "/upload/f_jpg/")
    caption = f"{cat['emoji']} {ref}\n\n« {text} »\n\n📖 Bible complète gratuite sur {APP_URL}\n\n👇 Partage ce verset avec quelqu'un qui en a besoin 🙏\n\n{build_hashtags_ig(cat_name)}"
    r = requests.post("https://graph.threads.net/v1.0/me/threads",
        data={"media_type": "IMAGE", "image_url": image_url, "text": caption, "access_token": THREADS_ACCESS_TOKEN}, timeout=60)
    if r.status_code != 200:
        print(f"❌ Threads container ({r.status_code}): {r.text}")
        return
    container_id = r.json().get("id")
    import time; time.sleep(5)
    r2 = requests.post("https://graph.threads.net/v1.0/me/threads_publish",
        data={"creation_id": container_id, "access_token": THREADS_ACCESS_TOKEN}, timeout=60)
    if r2.status_code == 200:
        print(f"✅ Threads publié — {r2.json().get('id')}")
    else:
        print(f"❌ Threads publication ({r2.status_code}): {r2.text}")


# ---------------------------------------------------
# IMAGE
# ---------------------------------------------------
PALETTES = [
    ((10, 14, 30),  (6,  10, 22),  (195, 165,  90), (195, 165,  90), (130, 120, 80)),
    ((8,  18, 38),  (5,  12, 28),  (160, 190, 220), (160, 190, 220), (100, 130, 160)),
    ((10, 22, 14),  (6,  15, 10),  (140, 195, 120), (140, 195, 120), (90,  140,  80)),
    ((28, 10, 14),  (18,  6,  9),  (210, 160, 120), (210, 160, 120), (150, 110,  80)),
    ((10, 10, 10),  (4,   4,  4),  (200, 180, 120), (200, 180, 120), (120, 110,  70)),
    ((10, 20, 50),  (6,  14, 36),  (200, 165,  80), (200, 165,  80), (130, 110,  55)),
]


def _gradient(W, H, top, bot):
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        draw.line([(0, y), (W, y)], fill=tuple(int(top[i] + t * (bot[i] - top[i])) for i in range(3)))
    return img


def wrap_text(draw, text, font, max_w):
    words = text.split()
    if not words:
        return [""]
    lines, current = [], words[0]
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
    palette = random.choice(PALETTES)
    bg_top, bg_bot, color_border, color_ref, color_wm = palette
    W, H = 1080, 1080
    img = _gradient(W, H, bg_top, bg_bot)
    draw = ImageDraw.Draw(img)
    m = 60
    draw.rounded_rectangle([m, m, W-m, H-m], radius=30, outline=color_border, width=6)
    draw.rounded_rectangle([m+16, m+16, W-m-16, H-m-16], radius=24, outline=color_border, width=1)
    pad_x, top, bottom = 140, 180, 330
    max_w, max_h = W - 2*pad_x, H - top - bottom
    chosen_font = chosen_lines = chosen_lh = None
    for size in range(66, 34, -2):
        font = ImageFont.truetype(FONT_SERIF, size)
        lines = wrap_text(draw, text, font, max_w)
        lh = int(size * 1.38)
        if lh * len(lines) <= max_h:
            chosen_font, chosen_lines, chosen_lh = font, lines, lh
            break
    if chosen_font is None:
        chosen_font = ImageFont.truetype(FONT_SERIF, 34)
        chosen_lines = wrap_text(draw, text, chosen_font, max_w)
        chosen_lh = int(34 * 1.38)
    if chosen_lines:
        chosen_lines[0] = "« " + chosen_lines[0]
        chosen_lines[-1] = chosen_lines[-1] + " »"
    y = top + max(0, (max_h - chosen_lh * len(chosen_lines)) // 2)
    for line in chosen_lines:
        lw = draw.textlength(line, font=chosen_font)
        x = (W - lw) // 2
        draw.text((x+2, y+2), line, font=chosen_font, fill=(0, 0, 0))
        draw.text((x, y), line, font=chosen_font, fill=(245, 245, 245))
        y += chosen_lh
    draw.line([(pad_x, H-260), (W-pad_x, H-260)], fill=color_border, width=2)
    small = ImageFont.truetype(FONT_SANS, 36)
    tiny = ImageFont.truetype(FONT_SANS, 28)
    draw.text((pad_x, H-230), ref, font=small, fill=color_ref)
    draw.text((pad_x, H-185), "LSG 1910", font=tiny, fill=color_wm)
    ww = draw.textlength(WATERMARK, font=tiny)
    draw.text((W-pad_x-ww, H-185), WATERMARK, font=tiny, fill=color_wm)
    out = "verse.png"
    img.save(out, "PNG")
    return out


# ---------------------------------------------------
# REEL
# ---------------------------------------------------
def wrap_text_with_quotes(draw, text, font, max_w):
    words = text.split()
    if not words:
        return [""]
    q_open = draw.textlength("« ", font=font)
    lines, current = [], words[0]
    for w in words[1:]:
        test = current + " " + w
        margin = q_open if not lines else 0
        if draw.textlength(test, font=font) + margin <= max_w:
            current = test
        else:
            lines.append(current)
            current = w
    lines.append(current)
    last = lines[-1]
    if draw.textlength(last + " »", font=font) > max_w:
        words_last = last.split()
        new_last = words_last[0]
        for w in words_last[1:]:
            if draw.textlength(new_last + " " + w + " »", font=font) <= max_w:
                new_last += " " + w
            else:
                lines[-1] = new_last
                lines.append(w)
                new_last = w
        lines[-1] = new_last
    if lines:
        lines[0] = "« " + lines[0]
        lines[-1] = lines[-1] + " »"
    return lines


def make_reel_video(text, ref, progress=None):
    W, H = 1080, 1920
    FPS, TOTAL = 30, 30 * 15
    seed = abs(hash(ref)) % (2**31)
    rng = np.random.default_rng(seed)
    fp, fpb = FONT_SERIF, FONT_SERIF_BOLD
    text_clean = text.rstrip('.')
    BORDER, CARD_PAD = 100, 100
    MAX_TW = W - BORDER*2 - CARD_PAD*2
    size = 88
    while size > 32:
        fv = ImageFont.truetype(fp, size)
        tmp = Image.new("RGB", (10, 10)); d = ImageDraw.Draw(tmp)
        test_lines = wrap_text_with_quotes(d, text_clean, fv, MAX_TW)
        lh = size + 20
        max_line_w = max(d.textbbox((0,0), l, font=fv)[2] for l in test_lines)
        total_h = lh * len(test_lines)
        if max_line_w <= MAX_TW and total_h <= int((H - BORDER*2) * 0.65):
            break
        size -= 2
    fv = ImageFont.truetype(fp, size)
    tmp = Image.new("RGB", (10, 10)); d = ImageDraw.Draw(tmp)
    verse_lines = wrap_text_with_quotes(d, text_clean, fv, MAX_TW)
    fr = ImageFont.truetype(fpb, 36)
    fl = ImageFont.truetype(fp, 28)
    fw = ImageFont.truetype(fp, 28)
    REEL_PALETTES = [
        ((10, 14, 38), (180, 148, 72),  (192, 158, 80),  (230, 228, 220), (160, 160, 175)),
        ((30,  8, 12), (210, 155, 75),  (220, 168, 85),  (255, 245, 225), (170, 145, 115)),
        (( 8, 24, 16), (130, 190, 110), (145, 205, 125), (235, 255, 235), (110, 155, 100)),
        ((22,  8, 40), (195, 160, 75),  (210, 175, 88),  (250, 245, 255), (155, 135, 180)),
        ((10, 10, 10), (195, 172,  95), (210, 187, 108), (250, 248, 235), (145, 135,  95)),
    ]
    BG, GOLD, GR, WHITE, SIL = REEL_PALETTES[seed % len(REEL_PALETTES)]
    CX1, CY1, CX2, CY2 = BORDER, BORDER, W-BORDER, H-BORDER
    N_P = 30
    px = rng.uniform(CX1+20, CX2-20, N_P); py = rng.uniform(CY1+20, CY2-20, N_P)
    ps = rng.uniform(0.2, 0.8, N_P); pr = rng.uniform(2, 5, N_P)
    pa = rng.uniform(0, 2*math.pi, N_P)
    def ease(t): t = max(0, min(1, t)); return t*t*(3-2*t)
    def blend(base, a, bg=BG):
        a = max(0, min(1, a))
        return tuple(int(bg[i] + (base[i]-bg[i])*a) for i in range(3))
    LINE_H = size + 20
    start_y = int(CY1 + (CY2-CY1)*0.42 - len(verse_lines)*LINE_H//2)
    FL, FT = CY2-200, CY2-170
    os.makedirs("frames", exist_ok=True)
    for f in range(TOTAL):
        s = f / FPS
        alpha = ease(s/0.5) if s < 0.5 else (ease((15-s)/1.5) if s > 13.5 else 1.0)
        img = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)
        for y in range(0, H, 4):
            t2 = y/H
            draw.rectangle([(0, y), (W, min(y+4, H))], fill=tuple(max(0, int(BG[i]*(1-t2*0.3))) for i in range(3)))
        cl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        cd = ImageDraw.Draw(cl)
        cd.rounded_rectangle([CX1,CY1,CX2,CY2], radius=40, fill=(*BG, int(alpha*230)))
        img = Image.alpha_composite(img.convert("RGBA"), cl).convert("RGB")
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([CX1,CY1,CX2,CY2], radius=40, outline=blend(GOLD, alpha), width=5)
        draw.rounded_rectangle([CX1+10,CY1+10,CX2-10,CY2-10], radius=34, outline=blend(GOLD, alpha*0.3), width=1)
        pl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        pd = ImageDraw.Draw(pl)
        for i in range(N_P):
            tp = s * ps[i]
            cx = int((px[i] + math.sin(tp*0.5+pa[i])*20) % W)
            cy = int((py[i] - s*ps[i]*12) % H)
            bright = (math.sin(tp+pa[i])+1)/2*0.3+0.1
            a_p = int(bright*alpha*90)
            pd.ellipse([(cx-int(pr[i]), cy-int(pr[i])), (cx+int(pr[i]), cy+int(pr[i]))], fill=(*blend(GOLD, bright*0.6), a_p))
        img = Image.alpha_composite(img.convert("RGBA"), pl).convert("RGB")
        draw = ImageDraw.Draw(img)
        for i, line in enumerate(verse_lines):
            ls = 0.1 + i*0.20; le = ls + 0.5
            la = (0 if s<ls else (ease((s-ls)/(le-ls)) if s<le else 1.0)) * alpha
            bbox = draw.textbbox((0,0), line, font=fv); tw = bbox[2]-bbox[0]
            x = (W-tw)//2; y = start_y + i*LINE_H
            draw.text((x+2, y+2), line, font=fv, fill=blend((0,0,0), la*0.6))
            draw.text((x, y), line, font=fv, fill=blend(WHITE, la))
        fs = 0.6 + len(verse_lines)*0.20 + 0.3
        fa = (0 if s<fs else (ease((s-fs)/0.6) if s<fs+0.6 else 1.0)) * alpha
        lx1, lx2 = CX1+CARD_PAD, CX2-CARD_PAD
        draw.line([(lx1, FL), (lx2, FL)], fill=blend(GOLD, fa*0.8), width=2)
        draw.text((lx1, FT), ref, font=fr, fill=blend(GR, fa))
        draw.text((lx1, FT+44), "LSG 1910", font=fl, fill=blend(SIL, fa*0.85))
        wbbox = draw.textbbox((0,0), WATERMARK, font=fw)
        draw.text((lx2-(wbbox[2]-wbbox[0]), FT+44), WATERMARK, font=fw, fill=blend(SIL, fa*0.85))
        img.save(f"frames/frame_{f:04d}.png")
    output_path = "reel.mp4"
    import glob, shutil
    music_files = glob.glob("music/*.mp3") + glob.glob("music/*.m4a") + glob.glob("music/*.ogg")
    music_file = None
    if music_files:
        last_music = progress.get("last_music", "") if progress else ""
        available = [m for m in music_files if m != last_music] or music_files
        music_file = random.choice(available)
        if progress is not None:
            progress["last_music"] = music_file
    if music_file:
        print(f"🎵 {music_file}")
        subprocess.run(['ffmpeg', '-framerate', '30', '-i', 'frames/frame_%04d.png', '-ss', '2', '-i', music_file,
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-c:a', 'aac', '-b:a', '192k', '-shortest', output_path, '-y'], capture_output=True)
    else:
        subprocess.run(['ffmpeg', '-framerate', '30', '-i', 'frames/frame_%04d.png',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', output_path, '-y'], capture_output=True)
    shutil.rmtree("frames", ignore_errors=True)
    print(f"✅ Reel : {output_path}")
    return output_path


# ---------------------------------------------------
# SÉLECTION PAR HEURE UTC
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
    index = progress.get(cat["key"], 0)
    arr, index = reshuffle_if_needed(cat["file"], index)
    book, ch, v = arr[index]
    progress[cat["key"]] = index + 1
    return book, ch, v


def pick_verse(progress):
    hour_utc = datetime.datetime.utcnow().hour
    cat_name = HOUR_SCHEDULE.get(hour_utc)
    if cat_name is None:
        cat_name = HOUR_FALLBACK.get(hour_utc, "promise")
        print(f"⚠️  {hour_utc}h UTC hors créneau — fallback : {cat_name}")
    else:
        print(f"🕐 {hour_utc}h UTC → {cat_name}")
    cat = CATEGORIES[cat_name]
    for attempt in range(5):
        book, ch, v = pick_from_category(cat, progress)
        raw_text = load_verse(book, ch, v)
        if not is_rubric(raw_text):
            break
        print(f"⏭️  Rubrique ignorée : {book} {ch}:{v}")
    raw_text = strip_rubric(raw_text)
    text = clean_text(raw_text)
    display_book = "Psaumes" if book == "Psaume" else book
    ref = f"{display_book} {ch}:{v}"
    return text, ref, cat, cat_name, hour_utc


# ---------------------------------------------------
# YOUTUBE
# ---------------------------------------------------
def post_to_youtube(video_path, ref, text, cat, cat_name, hour_utc):
    if not YT_CLIENT_ID or not YT_CLIENT_SECRET or not YT_REFRESH_TOKEN:
        print("⚠️  Credentials YouTube manquants.")
        return
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.auth.transport.requests import Request
        creds = Credentials(token=None, refresh_token=YT_REFRESH_TOKEN, client_id=YT_CLIENT_ID,
            client_secret=YT_CLIENT_SECRET, token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/youtube.upload"])
        creds.refresh(Request())
        youtube = build("youtube", "v3", credentials=creds)
        title = build_yt_title(cat_name, cat, ref, hour_utc)
        description = (f"{cat['emoji']} {ref}\n\n« {text} »\n\n📖 Bible complète gratuite sur {APP_URL}\n\n"
            f"#Shorts #Bible #BibleFrancaise #VersetDuJour #Jésus #JésusChrist #Dieu #Foi #Évangile "
            f"#Chrétien #ParoleDeDieu #Espérance #LSG1910 #Louange #GrâceDeDieu #Prière #Bénédiction #{cat['tag'].lstrip('#')}")
        body = {"snippet": {"title": title, "description": description,
            "tags": ["Bible", "LaBible", "VersetDuJour", "LSG1910", "Shorts", "BibleFrancaise"], "categoryId": "22"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
        media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"  ⏳ YouTube : {int(status.progress()*100)}%")
        print(f"✅ YouTube Short — https://youtube.com/shorts/{response.get('id')}")
    except Exception as e:
        print(f"❌ YouTube : {e}")


# ---------------------------------------------------
# MAIN
# ---------------------------------------------------
def main():
    progress = load_json(PROGRESS_FILE)
    text, ref, cat, cat_name, hour_utc = pick_verse(progress)
    print(f"📖 Image — {ref} [{cat_name}]")
    img = make_image(text, ref)
    caption = f"{cat['emoji']} <b>{ref}</b>\n#LaBible #LSG1910 #versetdujour {cat['tag']}"
    send_photo(img, caption)
    post_to_facebook(img, ref, text, cat, cat_name)
    post_to_instagram(img, ref, text, cat, cat_name)
    post_to_pinterest(img, ref, text, cat, cat_name)
    post_to_threads(img, ref, text, cat, cat_name)
    save_json(PROGRESS_FILE, progress)
    print("✅ Terminé (image).")


def main_reel():
    progress = load_json(PROGRESS_FILE)
    text, ref, cat, cat_name, hour_utc = pick_verse(progress)
    print(f"🎬 Reel — {ref} [{cat_name}]")
    if not os.path.exists("logo.png"):
        try:
            r = requests.get("https://labible.app/icons/icon-512x512.png", timeout=10)
            if r.status_code == 200:
                with open("logo.png", "wb") as f:
                    f.write(r.content)
        except Exception as e:
            print(f"⚠️ Logo : {e}")
    video = make_reel_video(text, ref, progress)
    caption = f"{cat['emoji']} <b>{ref}</b>\n#LaBible #LSG1910 #versetdujour {cat['tag']}"
    send_video(video, caption)
    post_reel_to_facebook(video, ref, text, cat, cat_name)
    post_reel_to_instagram(video, ref, text, cat, cat_name)
    post_to_youtube(video, ref, text, cat, cat_name, hour_utc)
    post_to_threads(make_image(text, ref), ref, text, cat, cat_name)
    save_json(PROGRESS_FILE, progress)
    print("✅ Terminé (reel).")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "reel":
        main_reel()
    else:
        main()