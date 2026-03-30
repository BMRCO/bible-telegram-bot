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

# Meta Facebook
FB_PAGE_ID    = os.environ.get("FB_PAGE_ID", "1018605031335601")
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "")

# Instagram
IG_ACCOUNT_ID = os.environ.get("IG_ACCOUNT_ID", "17841447648424267")

# ImgBB (hébergement image public pour Pinterest)
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "")

# YouTube
YT_CLIENT_ID      = os.environ.get("YOUTUBE_CLIENT_ID", "")
YT_CLIENT_SECRET  = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YT_REFRESH_TOKEN  = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

# Cloudinary
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY    = os.environ.get("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")

# Threads
THREADS_ACCESS_TOKEN = os.environ.get("THREADS_ACCESS_TOKEN", "")

# Pinterest
PINTEREST_ACCESS_TOKEN = os.environ.get("PINTEREST_ACCESS_TOKEN", "")
PINTEREST_BOARD_ID     = os.environ.get("PINTEREST_BOARD_ID", "1092404522055080754")

PROGRESS_FILE = "progress.json"
BIBLE_FILE    = "bible/lsg1910.json"

FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_SERIF_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
FONT_SANS  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

WATERMARK    = "LaBible.app"
MINI_APP_URL = "https://t.me/BIBLE_APP_BOT/labible"
APP_URL      = "https://labible.app"

# Hashtags de base communs (Instagram — base SEO forte)
HASHTAGS_BASE_IG = [
    "#Bible", "#VersetDuJour", "#BibleFrancaise",
    "#Chrétien", "#Foi", "#Évangile", "#Jésus",
    "#ParoleDeDieu", "#LSG1910", "#LaBible",
]

# Hashtags de base communs (Facebook — 5 max)
HASHTAGS_BASE_FB = [
    "#Bible", "#VersetDuJour", "#Foi", "#BibleFrancaise", "#Chrétien",
]

# Hashtags spécifiques par catégorie (Instagram — 5 supplémentaires = 15 total)
HASHTAGS_CAT_IG = {
    "promise":   ["#Promesse", "#Espérance", "#PromesseDeDieu", "#Bénédiction", "#Confiance"],
    "jesus":     ["#JésusChrist", "#ParoleDeJésus", "#GrâceDeDieu", "#Rédemption", "#Amour"],
    "psaume":    ["#Psaumes", "#Louange", "#Adoration", "#Prière", "#Cantique"],
    "proverbe":  ["#Sagesse", "#Proverbes", "#SagesseDeJésus", "#Discernement", "#Conseil"],
    "prophetie": ["#Prophétie", "#EspoirEnDieu", "#Révélation", "#Accomplissement", "#GloireDeDieu"],
}

# Hashtags spécifiques par catégorie (Facebook — 2 supplémentaires)
HASHTAGS_CAT_FB = {
    "promise":   ["#Promesse", "#Bénédiction"],
    "jesus":     ["#JésusChrist", "#GrâceDeDieu"],
    "psaume":    ["#Louange", "#Adoration"],
    "proverbe":  ["#Sagesse", "#Discernement"],
    "prophetie": ["#Prophétie", "#EspoirEnDieu"],
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
        "tag":   "#Psaumes"
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
    return " ".join(all_tags[:15])


def build_hashtags_fb(cat_name):
    specific = HASHTAGS_CAT_FB.get(cat_name, [])
    all_tags = HASHTAGS_BASE_FB + specific
    return " ".join(all_tags[:7])


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
            real_sentences = []
            for s in sentences:
                if not any(kw in s.lower() for kw in rubric_keywords):
                    real_sentences.append(s)
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
    words = t.split()
    if len(words) < 18:
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
    text = re.sub(r'\s*([;:?!])', r' \1', text)
    text = text.replace("'", "\u2019").replace("'", "\u2019")
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
            bn = v["book_name"]
            ch = str(v["chapter"])
            vs = str(v["verse"])
            if bn not in _bible_index:
                _bible_index[bn] = {}
            if ch not in _bible_index[bn]:
                _bible_index[bn][ch] = {}
            _bible_index[bn][ch][vs] = v["text"]
    return _bible_index


BOOK_NAME_MAP = {
    "Psaumes":      "Psaume",
    "Cantique des Cantiques": "Cantique des cantiques",
    "1 Rois":       "1 Rois",
    "2 Rois":       "2 Rois",
    "1 Samuel":     "1 Samuel",
    "2 Samuel":     "2 Samuel",
    "1 Chroniques": "1 Chroniques",
    "2 Chroniques": "2 Chroniques",
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


def send_video(path, caption):
    url = f"https://api.telegram.org/bot{TOKEN}/sendVideo"
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
            files={"video": f},
            timeout=60
        )
    r.raise_for_status()
    print("✅ Telegram vidéo publié")


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
        f"« {text} »\n\n"
        f"📖 Lisez la Bible complète gratuitement sur {APP_URL}\n\n"
        f"{hashtags}"
    )

    upload_url = f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/photos"
    with open(image_path, "rb") as f:
        r = requests.post(
            upload_url,
            data={"message": fb_message, "access_token": FB_PAGE_TOKEN},
            files={"source": f},
            timeout=60
        )

    if r.status_code == 200:
        post_id = r.json().get("post_id") or r.json().get("id", "inconnu")
        print(f"✅ Facebook publié — post_id: {post_id}")
    else:
        print(f"❌ Erreur Facebook ({r.status_code}): {r.text}")


def post_reel_to_facebook(video_path, ref, text, cat, cat_name):
    if not FB_PAGE_TOKEN:
        print("⚠️  FB_PAGE_TOKEN non défini — reel Facebook ignoré.")
        return

    hashtags = build_hashtags_fb(cat_name)
    description = (
        f"{cat['emoji']} {ref}\n\n"
        f"« {text} »\n\n"
        f"📖 Bible complète gratuite sur {APP_URL}\n\n"
        f"{hashtags}"
    )

    upload_url = f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/videos"
    with open(video_path, "rb") as f:
        r = requests.post(
            upload_url,
            data={
                "description": description,
                "access_token": FB_PAGE_TOKEN,
            },
            files={"source": f},
            timeout=120
        )

    if r.status_code == 200:
        vid_id = r.json().get("id", "inconnu")
        print(f"✅ Facebook reel publié — id: {vid_id}")
    else:
        print(f"❌ Erreur Facebook reel ({r.status_code}): {r.text}")


# ---------------------------------------------------
# UPLOAD IMAGE → ImgBB (Pinterest apenas)
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
        import time; time.sleep(5)
        return url
    else:
        print(f"❌ Erreur ImgBB ({r.status_code}): {r.text}")
        return None


# ---------------------------------------------------
# UPLOAD IMAGE → Cloudinary (Instagram / Threads)
# ---------------------------------------------------
def upload_to_cloudinary(image_path):
    if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
        print("⚠️  Cloudinary non configuré — fallback ImgBB.")
        return upload_to_imgbb(image_path)

    import hashlib, time as _time
    timestamp = str(int(_time.time()))
    signature_str = f"timestamp={timestamp}{CLOUDINARY_API_SECRET.strip()}"
    signature = hashlib.sha1(signature_str.encode()).hexdigest()

    with open(image_path, "rb") as f:
        r = requests.post(
            f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload",
            data={
                "api_key":   CLOUDINARY_API_KEY,
                "timestamp": timestamp,
                "signature": signature,
            },
            files={"file": f},
            timeout=60
        )

    if r.status_code == 200:
        url = r.json()["secure_url"]
        print(f"✅ Image uploadée sur Cloudinary : {url}")
        _time.sleep(3)
        return url
    else:
        print(f"❌ Erreur Cloudinary ({r.status_code}): {r.text}")
        return upload_to_imgbb(image_path)


# ---------------------------------------------------
# UPLOAD VIDÉO → Cloudinary
# ---------------------------------------------------
def upload_video_public(video_path):
    if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
        print("⚠️  Cloudinary non configuré — upload vidéo ignoré.")
        return None

    import hashlib, time as _time
    print("⏳ Upload vidéo vers Cloudinary...")
    timestamp = str(int(_time.time()))
    signature_str = f"timestamp={timestamp}{CLOUDINARY_API_SECRET.strip()}"
    signature = hashlib.sha1(signature_str.encode()).hexdigest()

    with open(video_path, "rb") as f:
        r = requests.post(
            f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/video/upload",
            data={
                "api_key":       CLOUDINARY_API_KEY,
                "timestamp":     timestamp,
                "signature":     signature,
                "resource_type": "video",
            },
            files={"file": f},
            timeout=180
        )

    if r.status_code == 200:
        url = r.json()["secure_url"]
        print(f"✅ Vidéo uploadée sur Cloudinary : {url}")
        _time.sleep(5)
        return url
    else:
        print(f"❌ Erreur Cloudinary vidéo ({r.status_code}): {r.text}")
        return None


# ---------------------------------------------------
# ENVOI INSTAGRAM
# ---------------------------------------------------
def post_to_instagram(image_path, ref, text, cat, cat_name):
    if not FB_PAGE_TOKEN:
        print("⚠️  FB_PAGE_TOKEN manquant — Instagram ignoré.")
        return

    image_url = upload_to_cloudinary(image_path)
    if not image_url:
        return
    if "cloudinary.com" in image_url:
        image_url = image_url.replace("/upload/", "/upload/f_jpg/")

    hashtags = build_hashtags_ig(cat_name)
    ig_caption = (
        f"{cat['emoji']} {ref}\n\n"
        f"« {text} »\n\n"
        f"📖 Bible complète gratuite sur {APP_URL}\n\n"
        f"{hashtags}"
    )

    container_url = f"https://graph.facebook.com/v25.0/{IG_ACCOUNT_ID}/media"
    r = requests.post(
        container_url,
        data={"image_url": image_url, "caption": ig_caption, "access_token": FB_PAGE_TOKEN},
        timeout=60
    )

    if r.status_code != 200:
        print(f"❌ Erreur container Instagram ({r.status_code}): {r.text}")
        return

    container_id = r.json().get("id")
    print(f"✅ Container Instagram créé : {container_id}")

    import time
    for attempt in range(8):
        time.sleep(8)
        status_url = f"https://graph.facebook.com/v25.0/{container_id}"
        rs = requests.get(
            status_url,
            params={"fields": "status_code", "access_token": FB_PAGE_TOKEN},
            timeout=30
        )
        status = rs.json().get("status_code", "")
        print(f"  ⏳ Statut image : {status} (tentative {attempt+1})")
        if status == "FINISHED":
            break
        if status == "ERROR":
            print("❌ Erreur traitement image Instagram.")
            return

    publish_url = f"https://graph.facebook.com/v25.0/{IG_ACCOUNT_ID}/media_publish"
    r2 = requests.post(
        publish_url,
        data={"creation_id": container_id, "access_token": FB_PAGE_TOKEN},
        timeout=60
    )

    if r2.status_code == 200:
        print(f"✅ Instagram publié — post_id: {r2.json().get('id', 'inconnu')}")
    else:
        print(f"❌ Erreur publication Instagram ({r2.status_code}): {r2.text}")


def post_reel_to_instagram(video_path, ref, text, cat, cat_name):
    if not FB_PAGE_TOKEN:
        print("⚠️  FB_PAGE_TOKEN manquant — reel Instagram ignoré.")
        return

    video_url = upload_video_public(video_path)
    if not video_url:
        return

    hashtags = build_hashtags_ig(cat_name)
    ig_caption = (
        f"{cat['emoji']} {ref}\n\n"
        f"« {text} »\n\n"
        f"📖 Bible complète gratuite sur {APP_URL}\n\n"
        f"{hashtags}"
    )

    cover_path = make_cover_image(ref)
    cover_url = upload_to_cloudinary(cover_path)
    if cover_url and "cloudinary.com" in cover_url:
        cover_url = cover_url.replace("/upload/", "/upload/f_jpg/")

    container_url = f"https://graph.facebook.com/v25.0/{IG_ACCOUNT_ID}/media"
    container_data = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": ig_caption,
        "access_token": FB_PAGE_TOKEN,
    }
    if cover_url:
        container_data["cover_url"] = cover_url
        print(f"✅ Cover URL: {cover_url}")
    else:
        container_data["thumb_offset"] = "4000"

    r = requests.post(container_url, data=container_data, timeout=60)

    if r.status_code != 200:
        print(f"❌ Erreur container reel Instagram ({r.status_code}): {r.text}")
        return

    container_id = r.json().get("id")
    print(f"✅ Container reel créé : {container_id}")

    import time
    for attempt in range(10):
        time.sleep(15)
        status_url = f"https://graph.facebook.com/v25.0/{container_id}"
        rs = requests.get(
            status_url,
            params={"fields": "status_code", "access_token": FB_PAGE_TOKEN},
            timeout=30
        )
        status = rs.json().get("status_code", "")
        print(f"  ⏳ Statut reel : {status} (tentative {attempt+1})")
        if status == "FINISHED":
            break
        if status == "ERROR":
            print("❌ Erreur traitement vidéo Instagram.")
            return

    publish_url = f"https://graph.facebook.com/v25.0/{IG_ACCOUNT_ID}/media_publish"
    r2 = requests.post(
        publish_url,
        data={"creation_id": container_id, "access_token": FB_PAGE_TOKEN},
        timeout=60
    )

    if r2.status_code == 200:
        print(f"✅ Instagram reel publié — id: {r2.json().get('id', 'inconnu')}")
    else:
        print(f"❌ Erreur publication reel Instagram ({r2.status_code}): {r2.text}")


# ---------------------------------------------------
# ENVOI PINTEREST
# ---------------------------------------------------
def post_to_pinterest(image_path, ref, text, cat, cat_name):
    if not PINTEREST_ACCESS_TOKEN:
        print("⚠️  PINTEREST_ACCESS_TOKEN non défini — Pinterest ignoré.")
        return

    image_url = upload_to_imgbb(image_path)
    if not image_url:
        print("❌ Pinterest ignoré — impossible d'uploader l'image.")
        return

    book_chapter = ref.replace(" ", "-")
    app_link = f"{APP_URL}/#{book_chapter}"

    pin_keywords = {
        "promise":   "Promesse de Dieu",
        "jesus":     "Parole de Jésus",
        "psaume":    "Psaume Biblique",
        "proverbe":  "Sagesse de la Bible",
        "prophetie": "Prophétie Accomplie",
    }
    pin_kw = pin_keywords.get(cat_name, "Verset Biblique")
    pin_base = f"{cat['emoji']} {pin_kw} — {ref} | LaBible.app"
    words_pin = text.split()
    snippet_pin = ""
    for w in words_pin:
        test = snippet_pin + (" " if snippet_pin else "") + w
        if len(pin_base + " — " + test) > 100:
            break
        snippet_pin = test
    pin_title = pin_base
    pin_description = (
        f"{cat['emoji']} « {text} »\n\n"
        f"— {ref} (LSG 1910)\n\n"
        f"📖 Lisez la Bible complète gratuitement sur LaBible.app\n\n"
        f"#Bible #VersetDuJour #LaBible #LSG1910 #BibleFrancais #Foi #Chrétien #Évangile #Jésus #Dieu"
    )

    payload = {
        "board_id": PINTEREST_BOARD_ID,
        "title": pin_title,
        "description": pin_description,
        "link": app_link,
        "media_source": {
            "source_type": "image_url",
            "url": image_url
        }
    }

    r = requests.post(
        "https://api.pinterest.com/v5/pins",
        headers={
            "Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=60
    )

    if r.status_code in (200, 201):
        pin_id = r.json().get("id", "inconnu")
        print(f"✅ Pinterest publié — pin_id: {pin_id}")
    else:
        print(f"❌ Erreur Pinterest ({r.status_code}): {r.text}")


# ---------------------------------------------------
# ENVOI THREADS
# ---------------------------------------------------
def post_to_threads(image_path, ref, text, cat, cat_name):
    if not THREADS_ACCESS_TOKEN:
        print("⚠️  THREADS_ACCESS_TOKEN non défini — Threads ignoré.")
        return

    image_url = upload_to_cloudinary(image_path)
    if not image_url:
        print("❌ Threads ignoré — impossible d'uploader l'image.")
        return

    if "cloudinary.com" in image_url:
        image_url = image_url.replace("/upload/", "/upload/f_jpg/")

    hashtags = build_hashtags_ig(cat_name)
    caption = (
        f"{cat['emoji']} {ref}\n\n"
        f"« {text} »\n\n"
        f"📖 Bible complète gratuite sur {APP_URL}\n\n"
        f"{hashtags}"
    )

    r = requests.post(
        "https://graph.threads.net/v1.0/me/threads",
        data={
            "media_type":  "IMAGE",
            "image_url":   image_url,
            "text":        caption,
            "access_token": THREADS_ACCESS_TOKEN,
        },
        timeout=60
    )

    if r.status_code != 200:
        print(f"❌ Erreur container Threads ({r.status_code}): {r.text}")
        return

    container_id = r.json().get("id")
    print(f"✅ Container Threads créé : {container_id}")

    import time; time.sleep(5)

    r2 = requests.post(
        "https://graph.threads.net/v1.0/me/threads_publish",
        data={
            "creation_id":  container_id,
            "access_token": THREADS_ACCESS_TOKEN,
        },
        timeout=60
    )

    if r2.status_code == 200:
        print(f"✅ Threads publié — id: {r2.json().get('id', 'inconnu')}")
    else:
        print(f"❌ Erreur publication Threads ({r2.status_code}): {r2.text}")


# ---------------------------------------------------
# IMAGE — palettes simples, design limpo
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

    m = 60
    draw.rounded_rectangle([m, m, W - m, H - m], radius=30, outline=color_border, width=6)
    inner = m + 16
    draw.rounded_rectangle([inner, inner, W - inner, H - inner], radius=24, outline=color_border, width=1)

    pad_x  = 140
    top    = 180
    bottom = 330
    max_w  = W - 2 * pad_x
    max_h  = H - top - bottom

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

    if chosen_lines:
        chosen_lines[0]  = "« " + chosen_lines[0]
        chosen_lines[-1] = chosen_lines[-1] + " »"

    total_h = chosen_lh * len(chosen_lines)
    y       = top + max(0, (max_h - total_h) // 2)

    for line in chosen_lines:
        lw = draw.textlength(line, font=chosen_font)
        x  = (W - lw) // 2
        draw.text((x + 2, y + 2), line, font=chosen_font, fill=(0, 0, 0))
        draw.text((x,     y    ), line, font=chosen_font, fill=(245, 245, 245))
        y += chosen_lh

    draw.line([(pad_x, H - 260), (W - pad_x, H - 260)], fill=color_border, width=2)

    small = ImageFont.truetype(FONT_SANS, 36)
    tiny  = ImageFont.truetype(FONT_SANS, 28)

    draw.text((pad_x, H - 230), ref,        font=small, fill=color_ref)
    draw.text((pad_x, H - 185), "LSG 1910", font=tiny,  fill=color_wm)

    ww = draw.textlength(WATERMARK, font=tiny)
    draw.text((W - pad_x - ww, H - 185), WATERMARK, font=tiny, fill=color_wm)

    out = "verse.png"
    img.save(out, "PNG")
    return out


# ---------------------------------------------------
# COVER — imagem estática para capa do reel Instagram
# ---------------------------------------------------
def make_cover_image(ref):
    W, H = 1080, 1920
    fp  = FONT_SERIF
    fpb = FONT_SERIF_BOLD
    BORDER = 80

    REEL_PALETTES = [
        ((10, 14, 38),  (180, 148, 72),   (192, 158, 80),   (230, 228, 220),  (160, 160, 175)),
        ((30,  8, 12),  (210, 155, 75),   (220, 168, 85),   (255, 245, 225),  (170, 145, 115)),
        (( 8, 24, 16),  (130, 190, 110),  (145, 205, 125),  (235, 255, 235),  (110, 155, 100)),
        ((22,  8, 40),  (195, 160, 75),   (210, 175, 88),   (250, 245, 255),  (155, 135, 180)),
        ((10, 10, 10),  (195, 172,  95),  (210, 187, 108),  (250, 248, 235),  (145, 135,  95)),
    ]
    seed = abs(hash(ref)) % (2**31)
    BG, GOLD, GOLD_L, _, SILVER = REEL_PALETTES[seed % len(REEL_PALETTES)]
    BG_BOT = tuple(max(0, int(c * 0.7)) for c in BG)

    def gradient(img, top, bot):
        draw = ImageDraw.Draw(img)
        for y in range(H):
            t = y / H
            c = tuple(int(top[i] + (bot[i]-top[i])*t) for i in range(3))
            draw.line([(0, y), (W, y)], fill=c)

    def blend(base, a, bg=BG):
        a = max(0, min(1, a))
        return tuple(int(bg[i] + (base[i]-bg[i])*a) for i in range(3))

    img = Image.new("RGB", (W, H))
    gradient(img, BG, BG_BOT)
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([BORDER, BORDER, W-BORDER, H-BORDER],
                            radius=50, outline=blend(GOLD, 1.0), width=5)
    draw.rounded_rectangle([BORDER+12, BORDER+12, W-BORDER-12, H-BORDER-12],
                            radius=42, outline=blend(GOLD, 0.3), width=1)

    try:
        logo_raw = Image.open("logo.png").convert("RGBA")
    except Exception:
        logo_raw = None

    LOGO_SIZE = 380
    ly = H // 2 - LOGO_SIZE // 2 - 80

    if logo_raw:
        logo_r = logo_raw.resize((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)
        lx = (W - LOGO_SIZE) // 2
        base = img.convert("RGBA")
        base.paste(logo_r, (lx, ly), logo_r)
        img = base.convert("RGB")
        draw = ImageDraw.Draw(img)

    f_ref = ImageFont.truetype(fpb, 96)
    bbox = draw.textbbox((0, 0), ref, font=f_ref)
    tw = bbox[2] - bbox[0]
    ry = ly + LOGO_SIZE + 60
    draw.text(((W-tw)//2+3, ry+3), ref, font=f_ref, fill=(0, 0, 0))
    draw.text(((W-tw)//2,   ry),   ref, font=f_ref, fill=GOLD_L)

    f_wm = ImageFont.truetype(FONT_SANS, 36)
    bbox3 = draw.textbbox((0, 0), WATERMARK, font=f_wm)
    tw3 = bbox3[2] - bbox3[0]
    draw.text(((W-tw3)//2, H-180), WATERMARK, font=f_wm, fill=blend(SILVER, 0.5))

    out = "cover.png"
    img.save(out, "PNG")
    return out


# ---------------------------------------------------
# REEL — format vertical 9:16, style bot
# ---------------------------------------------------
def wrap_text_with_quotes(draw, text, font, max_w):
    words = text.split()
    if not words: return [""]
    q_open = draw.textlength("« ", font=font)
    lines = []; current = words[0]
    for w in words[1:]:
        test = current + " " + w
        is_first = (len(lines) == 0)
        margin = q_open if is_first else 0
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
                new_last = new_last + " " + w
            else:
                lines[-1] = new_last
                lines.append(w)
                new_last = w
        lines[-1] = new_last
    if lines:
        lines[0]  = "« " + lines[0]
        lines[-1] = lines[-1] + " »"
    return lines


def make_reel_video(text, ref, progress=None):
    W, H = 1080, 1920
    FPS = 30
    TOTAL = FPS * 15
    seed = abs(hash(ref)) % (2**31)
    rng = np.random.default_rng(seed)

    fp  = FONT_SERIF
    fpb = FONT_SERIF_BOLD

    text_clean = text.rstrip('.')
    BORDER = 100; CARD_PAD = 100
    MAX_TW = W - BORDER*2 - CARD_PAD*2

    size = 88
    while size > 32:
        fv = ImageFont.truetype(fp, size)
        tmp = Image.new("RGB", (10, 10)); d = ImageDraw.Draw(tmp)
        test_lines = wrap_text_with_quotes(d, text_clean, fv, MAX_TW)
        lh = size + 20
        max_line_w = max(d.textbbox((0,0), l, font=fv)[2] for l in test_lines)
        total_h = lh * len(test_lines)
        max_text_h = int((H - BORDER*2) * 0.65)
        if max_line_w <= MAX_TW and total_h <= max_text_h:
            break
        size -= 2

    fv = ImageFont.truetype(fp, size)
    tmp = Image.new("RGB", (10, 10)); d = ImageDraw.Draw(tmp)
    verse_lines = wrap_text_with_quotes(d, text_clean, fv, MAX_TW)

    fr = ImageFont.truetype(fpb, 36)
    fl = ImageFont.truetype(fp, 28)
    fw = ImageFont.truetype(fp, 28)

    REEL_PALETTES = [
        ((10, 14, 38),  (180, 148, 72),   (192, 158, 80),   (230, 228, 220),  (160, 160, 175)),
        ((30,  8, 12),  (210, 155, 75),   (220, 168, 85),   (255, 245, 225),  (170, 145, 115)),
        (( 8, 24, 16),  (130, 190, 110),  (145, 205, 125),  (235, 255, 235),  (110, 155, 100)),
        ((22,  8, 40),  (195, 160, 75),   (210, 175, 88),   (250, 245, 255),  (155, 135, 180)),
        ((10, 10, 10),  (195, 172,  95),  (210, 187, 108),  (250, 248, 235),  (145, 135,  95)),
    ]
    palette_idx = seed % len(REEL_PALETTES)
    BG, GOLD, GR, WHITE, SIL = REEL_PALETTES[palette_idx]

    CX1 = BORDER; CY1 = BORDER; CX2 = W - BORDER; CY2 = H - BORDER

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
    FL = CY2 - 200; FT = CY2 - 170

    os.makedirs("frames", exist_ok=True)

    for f in range(TOTAL):
        s = f / FPS
        alpha = ease(s/0.8) if s < 0.8 else (ease((15-s)/1.5) if s > 13.5 else 1.0)

        img = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)

        for y in range(0, H, 4):
            t2 = y/H
            bg_y = tuple(max(0, int(BG[i] * (1 - t2*0.3))) for i in range(3))
            draw.rectangle([(0, y), (W, min(y+4, H))], fill=bg_y)

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
            r  = int(pr[i])
            bright = (math.sin(tp+pa[i])+1)/2*0.3+0.1
            a_p = int(bright*alpha*90)
            gc = blend(GOLD, bright*0.6)
            pd.ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=(*gc, a_p))
        img = Image.alpha_composite(img.convert("RGBA"), pl).convert("RGB")
        draw = ImageDraw.Draw(img)

        for i, line in enumerate(verse_lines):
            ls = 0.6 + i*0.20; le = ls + 0.5
            la = (0 if s<ls else (ease((s-ls)/(le-ls)) if s<le else 1.0)) * alpha
            bbox = draw.textbbox((0,0), line, font=fv); tw = bbox[2]-bbox[0]
            x = (W-tw)//2; y = start_y + i*LINE_H
            draw.text((x+2, y+2), line, font=fv, fill=blend((0,0,0), la*0.6))
            draw.text((x, y),     line, font=fv, fill=blend(WHITE, la))

        fs = 0.6 + len(verse_lines)*0.20 + 0.3
        fa = (0 if s<fs else (ease((s-fs)/0.6) if s<fs+0.6 else 1.0)) * alpha
        lx1 = CX1 + CARD_PAD; lx2 = CX2 - CARD_PAD
        draw.line([(lx1, FL), (lx2, FL)], fill=blend(GOLD, fa*0.8), width=2)
        draw.text((lx1, FT),    ref,        font=fr, fill=blend(GR,  fa))
        draw.text((lx1, FT+44), "LSG 1910", font=fl, fill=blend(SIL, fa*0.85))
        wbbox = draw.textbbox((0,0), WATERMARK, font=fw); wtw = wbbox[2]-wbbox[0]
        draw.text((lx2-wtw, FT+44), WATERMARK, font=fw, fill=blend(SIL, fa*0.85))

        img.save(f"frames/frame_{f:04d}.png")

    output_path = "reel.mp4"

    import glob, shutil
    music_files = glob.glob("music/*.mp3") + glob.glob("music/*.m4a") + glob.glob("music/*.ogg")
    music_file  = None
    if music_files:
        last_music = progress.get("last_music", "") if progress else ""
        available  = [m for m in music_files if m != last_music]
        if not available:
            available = music_files
        music_file = random.choice(available)
        if progress is not None:
            progress["last_music"] = music_file

    if music_file:
        print(f"🎵 Musique : {music_file}")
        subprocess.run([
            'ffmpeg', '-framerate', '30',
            '-i', 'frames/frame_%04d.png',
            '-ss', '2',
            '-i', music_file,
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20',
            '-c:a', 'aac', '-b:a', '192k',
            '-shortest',
            output_path, '-y'
        ], capture_output=True)
    else:
        subprocess.run([
            'ffmpeg', '-framerate', '30',
            '-i', 'frames/frame_%04d.png',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20',
            output_path, '-y'
        ], capture_output=True)

    shutil.rmtree("frames", ignore_errors=True)

    print(f"✅ Reel généré : {output_path}")
    return output_path


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
    index      = progress.get(cat["key"], 0)
    arr, index = reshuffle_if_needed(cat["file"], index)
    book, ch, v = arr[index]
    progress[cat["key"]] = index + 1
    return book, ch, v


def pick_verse(progress):
    weekday  = datetime.datetime.utcnow().weekday()
    cat_name = DAY_SCHEDULE[weekday]
    cat      = CATEGORIES[cat_name]
    for attempt in range(5):
        book, ch, v = pick_from_category(cat, progress)
        raw_text    = load_verse(book, ch, v)
        if not is_rubric(raw_text):
            break
        print(f"⏭️  Rubrique ignorée : {book} {ch}:{v} — essai {attempt+1}")
    raw_text = strip_rubric(raw_text)
    text     = clean_text(raw_text)
    display_book = "Psaumes" if book == "Psaume" else book
    ref      = f"{display_book} {ch}:{v}"
    return text, ref, cat, cat_name


# ---------------------------------------------------
# ENVOI YOUTUBE SHORTS
# ---------------------------------------------------
def post_to_youtube(video_path, ref, text, cat, cat_name):
    if not YT_CLIENT_ID or not YT_CLIENT_SECRET or not YT_REFRESH_TOKEN:
        print("⚠️  Credentials YouTube manquants — publication ignorée.")
        return

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.auth.transport.requests import Request

        creds = Credentials(
            token=None,
            refresh_token=YT_REFRESH_TOKEN,
            client_id=YT_CLIENT_ID,
            client_secret=YT_CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/youtube.upload"]
        )
        creds.refresh(Request())

        youtube = build("youtube", "v3", credentials=creds)

        # Titre SEO YouTube — keyword + ref + snippet
        yt_keywords = {
            "promise":   "Promesse de Dieu",
            "jesus":     "Parole de Jésus",
            "psaume":    "Psaume du Jour",
            "proverbe":  "Sagesse Biblique",
            "prophetie": "Prophétie Biblique",
        }
        kw = yt_keywords.get(cat_name, "Verset du Jour")
        base = f"{cat['emoji']} {kw} — {ref} | Bible LSG 1910"
        words = text.split()
        snippet = ""
        for w in words:
            test = snippet + (" " if snippet else "") + w
            if len(base + " — " + test) > 97:
                break
            snippet = test
        title = f"{base} — {snippet}" if snippet else base
        description = (
            f"{cat['emoji']} {ref}\n\n"
            f"« {text} »\n\n"
            f"📖 Bible complète gratuite sur {APP_URL}\n\n"
            f"#Shorts #Bible #BibleFrancaise #VersetDuJour #Jésus #JésusChrist #Dieu #Foi #Évangile #Chrétien #ParoleDeDieu #Espérance #LSG1910 #Louange #GrâceDeDieu #Prière #Bénédiction #Adoration #{cat['tag'].lstrip('#')}"
        )

        body = {
            "snippet": {
                "title":       title,
                "description": description,
                "tags":        ["Bible", "LaBible", "VersetDuJour", "LSG1910", "Shorts", "BibleFrancaise"],
                "categoryId":  "22"
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"  ⏳ Upload YouTube : {int(status.progress() * 100)}%")

        video_id = response.get("id", "inconnu")
        print(f"✅ YouTube Short publié — https://youtube.com/shorts/{video_id}")

    except Exception as e:
        print(f"❌ Erreur YouTube : {e}")


# ---------------------------------------------------
# MAIN IMAGE
# ---------------------------------------------------
def main():
    progress = load_json(PROGRESS_FILE)
    text, ref, cat, cat_name = pick_verse(progress)
    print(f"📖 Image — {ref} [{cat_name}]")

    img     = make_image(text, ref)
    caption = f"{cat['emoji']} <b>{ref}</b>\n#LaBible #LSG1910 #versetdujour {cat['tag']}"

    send_photo(img, caption)
    post_to_facebook(img, ref, text, cat, cat_name)
    post_to_instagram(img, ref, text, cat, cat_name)
    post_to_pinterest(img, ref, text, cat, cat_name)
    post_to_threads(img, ref, text, cat, cat_name)

    save_json(PROGRESS_FILE, progress)
    print("✅ Terminé (image).")


# ---------------------------------------------------
# MAIN REEL
# ---------------------------------------------------
def main_reel():
    progress = load_json(PROGRESS_FILE)
    text, ref, cat, cat_name = pick_verse(progress)
    print(f"🎬 Reel — {ref} [{cat_name}]")

    if not os.path.exists("logo.png"):
        try:
            r = requests.get("https://labible.app/icons/icon-512x512.png", timeout=10)
            if r.status_code == 200:
                with open("logo.png", "wb") as f:
                    f.write(r.content)
                print("✅ Logo descarregado")
        except Exception as e:
            print(f"⚠️ Logo não disponível: {e}")

    video   = make_reel_video(text, ref, progress)
    caption = f"{cat['emoji']} <b>{ref}</b>\n#LaBible #LSG1910 #versetdujour {cat['tag']}"

    send_video(video, caption)
    post_reel_to_facebook(video, ref, text, cat, cat_name)
    post_reel_to_instagram(video, ref, text, cat, cat_name)
    post_to_youtube(video, ref, text, cat, cat_name)
    post_to_threads(make_image(text, ref), ref, text, cat, cat_name)

    save_json(PROGRESS_FILE, progress)
    print("✅ Terminé (reel).")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "reel":
        main_reel()
    else:
        main()
