"""
holy_week.py — Publications spéciales Semaine Sainte
Publie en extra (en plus des publications normales du bot)
"""
import os, json, datetime, hashlib, math, subprocess, requests, numpy as np
from PIL import Image, ImageDraw, ImageFont

# ── Variables d'environnement (mêmes secrets que bot.py) ──
TOKEN              = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL            = os.environ["TELEGRAM_CHANNEL"]
FB_PAGE_ID         = os.environ.get("FB_PAGE_ID", "1018605031335601")
FB_PAGE_TOKEN      = os.environ.get("FB_PAGE_TOKEN", "")
IG_ACCOUNT_ID      = os.environ.get("IG_ACCOUNT_ID", "17841447648424267")
IMGBB_API_KEY      = os.environ.get("IMGBB_API_KEY", "")
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY    = os.environ.get("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")
THREADS_ACCESS_TOKEN  = os.environ.get("THREADS_ACCESS_TOKEN", "")
YT_CLIENT_ID       = os.environ.get("YOUTUBE_CLIENT_ID", "")
YT_CLIENT_SECRET   = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YT_REFRESH_TOKEN   = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

FONT_SERIF      = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_SERIF_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
FONT_SANS       = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
WATERMARK       = "LaBible.app"
MINI_APP_URL    = "https://t.me/BIBLE_APP_BOT/labible"
APP_URL         = "https://labible.app"

# ── Programme de la Semaine Sainte 2025 ──
HOLY_WEEK = {
    "2026-03-29": {
        "theme": "Dimanche des Rameaux",
        "emoji": "🌿",
        "tag":   "#DimancheDesRameaux",
        "verse": ("Et ceux qui précédaient et ceux qui suivaient criaient : "
                  "Hosanna ! Béni soit celui qui vient au nom du Seigneur !"),
        "ref":   "Marc 11:9",
        "palette": "bordeaux",
    },
    "2026-03-30": {
        "theme": "Lundi Saint — Le Temple purifié",
        "emoji": "🕊️",
        "tag":   "#SemaineSainte",
        "verse": ("Il leur dit : Il est écrit : Ma maison sera appelée "
                  "une maison de prière. Mais vous, vous en faites une caverne de voleurs."),
        "ref":   "Matthieu 21:13",
        "palette": "bordeaux",
    },
    "2026-03-31": {
        "theme": "Mardi Saint — Les derniers enseignements",
        "emoji": "✝️",
        "tag":   "#SemaineSainte",
        "verse": ("Jésus lui dit : Je suis le chemin, la vérité, et la vie. "
                  "Nul ne vient au Père que par moi."),
        "ref":   "Jean 14:6",
        "palette": "bordeaux",
    },
    "2026-04-01": {
        "theme": "Mercredi Saint — La trahison",
        "emoji": "🙏",
        "tag":   "#SemaineSainte",
        "verse": ("Le Fils de l'homme s'en va, selon ce qui est déterminé ; "
                  "mais malheur à l'homme par qui il est livré !"),
        "ref":   "Luc 22:22",
        "palette": "sombre",
    },
    "2026-04-02": {
        "theme": "Jeudi Saint — La Cène",
        "emoji": "🍞",
        "tag":   "#JeudiSaint",
        "verse": ("Il prit du pain ; et, après avoir rendu grâces, il le rompit, "
                  "et le leur donna, en disant : Ceci est mon corps, qui est donné pour vous."),
        "ref":   "Luc 22:19",
        "palette": "or",
    },
    "2026-04-03": {
        "theme": "Vendredi Saint — La Crucifixion",
        "emoji": "⛪",
        "tag":   "#VendrediSaint",
        "verse": ("Car Dieu a tant aimé le monde qu'il a donné son Fils unique, "
                  "afin que quiconque croit en lui ne périsse point, "
                  "mais qu'il ait la vie éternelle."),
        "ref":   "Jean 3:16",
        "palette": "sombre",
    },
    "2026-04-05": {
        "theme": "Dimanche de Pâques — La Résurrection",
        "emoji": "🌅",
        "tag":   "#Paques #Resurrection",
        "verse": ("Il n'est point ici, mais il est ressuscité. "
                  "Souvenez-vous de quelle manière il vous a parlé, "
                  "lorsqu'il était encore en Galilée."),
        "ref":   "Luc 24:6",
        "palette": "lumiere",
    },
}

# ── Palettes spéciales Semaine Sainte ──
PALETTES_HW = {
    "bordeaux": {
        "bg_top":  (28,  4,  8),
        "bg_bot":  (16,  2,  5),
        "border":  (180, 130, 60),
        "text":    (240, 225, 195),
        "accent":  (200, 150, 70),
    },
    "sombre": {
        "bg_top":  (8,   8,  14),
        "bg_bot":  (4,   4,   8),
        "border":  (120, 100, 60),
        "text":    (220, 210, 190),
        "accent":  (150, 120, 60),
    },
    "or": {
        "bg_top":  (20,  14,  4),
        "bg_bot":  (12,   8,  2),
        "border":  (210, 175, 80),
        "text":    (255, 245, 220),
        "accent":  (220, 185, 90),
    },
    "lumiere": {
        "bg_top":  (10,  20, 40),
        "bg_bot":  (6,   12, 25),
        "border":  (200, 175, 100),
        "text":    (255, 250, 230),
        "accent":  (210, 185, 110),
    },
}


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
    if len(lines) >= 2 and len(lines[-1].strip()) <= 2:
        lines[-2] += " " + lines.pop()
    return lines


def make_holy_week_image(day_data):
    pal = PALETTES_HW[day_data["palette"]]
    bg_top, bg_bot = pal["bg_top"], pal["bg_bot"]
    border_col  = pal["border"]
    text_col    = pal["text"]
    accent_col  = pal["accent"]

    W, H = 1080, 1080
    img  = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)

    # Fond dégradé
    for y in range(H):
        t = y / H
        c = tuple(int(bg_top[i] + t * (bg_bot[i] - bg_top[i])) for i in range(3))
        draw.line([(0, y), (W, y)], fill=c)

    # Bordures dorées
    m = 55
    draw.rounded_rectangle([m, m, W-m, H-m], radius=32, outline=border_col, width=6)
    draw.rounded_rectangle([m+14, m+14, W-m-14, H-m-14], radius=26, outline=(*border_col, 80), width=1)

    # Ligne décorative supérieure
    draw.line([(m+40, m+40), (W-m-40, m+40)], fill=border_col, width=1)

    # Thème du jour en haut
    font_theme = ImageFont.truetype(FONT_SANS, 22)
    theme_text = day_data["emoji"] + "  " + day_data["theme"].upper()
    tw = draw.textlength(theme_text, font=font_theme)
    draw.text(((W-tw)//2, m+52), theme_text, font=font_theme, fill=accent_col)

    # Ligne sous le thème
    draw.line([(m+40, m+88), (W-m-40, m+88)], fill=(*border_col, 100), width=1)

    # Texte du verset
    pad_x = 130
    top   = 200
    bottom = 300
    max_w  = W - 2 * pad_x
    max_h  = H - top - bottom

    chosen_font = chosen_lines = chosen_lh = None
    for size in range(62, 30, -2):
        font  = ImageFont.truetype(FONT_SERIF, size)
        lines = wrap_text(draw, day_data["verse"], font, max_w)
        lh    = int(size * 1.42)
        if lh * len(lines) <= max_h:
            chosen_font, chosen_lines, chosen_lh = font, lines, lh
            break

    if chosen_font is None:
        chosen_font  = ImageFont.truetype(FONT_SERIF, 30)
        chosen_lines = wrap_text(draw, day_data["verse"], chosen_font, max_w)
        chosen_lh    = int(30 * 1.42)

    if chosen_lines:
        chosen_lines[0]  = "« " + chosen_lines[0]
        chosen_lines[-1] = chosen_lines[-1] + " »"

    total_h = chosen_lh * len(chosen_lines)
    y       = top + max(0, (max_h - total_h) // 2)

    for line in chosen_lines:
        lw = draw.textlength(line, font=chosen_font)
        x  = (W - lw) // 2
        draw.text((x+2, y+2), line, font=chosen_font, fill=(0, 0, 0))
        draw.text((x, y),     line, font=chosen_font, fill=text_col)
        y += chosen_lh

    # Ligne de séparation et référence
    draw.line([(pad_x, H-260), (W-pad_x, H-260)], fill=border_col, width=2)

    font_ref = ImageFont.truetype(FONT_SERIF_BOLD, 38)
    font_sub = ImageFont.truetype(FONT_SANS, 26)

    rw = draw.textlength(day_data["ref"], font=font_ref)
    draw.text(((W-rw)//2, H-238), day_data["ref"], font=font_ref, fill=accent_col)

    ww = draw.textlength(WATERMARK, font=font_sub)
    draw.text(((W-ww)//2, H-192), WATERMARK, font=font_sub, fill=(*accent_col[:3], 180))

    out = "holy_week.png"
    img.save(out, "PNG")
    return out


def upload_to_cloudinary(image_path):
    import time as _time
    if not CLOUDINARY_CLOUD_NAME:
        return upload_to_imgbb(image_path)
    timestamp = str(int(_time.time()))
    sig_str   = f"timestamp={timestamp}{CLOUDINARY_API_SECRET.strip()}"
    signature = hashlib.sha1(sig_str.encode()).hexdigest()
    with open(image_path, "rb") as f:
        r = requests.post(
            f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload",
            data={"api_key": CLOUDINARY_API_KEY, "timestamp": timestamp, "signature": signature},
            files={"file": f}, timeout=60
        )
    if r.status_code == 200:
        url = r.json()["secure_url"]
        _time.sleep(3)
        return url
    return upload_to_imgbb(image_path)


def upload_to_imgbb(image_path):
    if not IMGBB_API_KEY:
        return None
    import time
    with open(image_path, "rb") as f:
        r = requests.post("https://api.imgbb.com/1/upload",
                          params={"key": IMGBB_API_KEY}, files={"image": f}, timeout=60)
    if r.status_code == 200:
        time.sleep(5)
        return r.json()["data"]["url"]
    return None


def post_telegram(image_path, caption):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    markup = json.dumps({"inline_keyboard": [[{"text": "📖 Lire dans LaBible.app", "url": MINI_APP_URL}]]})
    with open(image_path, "rb") as f:
        r = requests.post(url, data={"chat_id": CHANNEL, "caption": caption,
                                      "parse_mode": "HTML", "reply_markup": markup},
                          files={"photo": f}, timeout=30)
    r.raise_for_status()
    print("✅ Telegram publié")


def post_facebook(image_path, caption):
    if not FB_PAGE_TOKEN: return
    with open(image_path, "rb") as f:
        r = requests.post(
            f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/photos",
            data={"message": caption, "access_token": FB_PAGE_TOKEN},
            files={"source": f}, timeout=60
        )
    if r.status_code == 200:
        print(f"✅ Facebook publié — {r.json().get('id','?')}")
    else:
        print(f"❌ Facebook ({r.status_code}): {r.text}")


def post_instagram(image_path, caption):
    if not FB_PAGE_TOKEN: return
    image_url = upload_to_cloudinary(image_path)
    if not image_url: return
    if "cloudinary.com" in image_url:
        image_url = image_url.replace("/upload/", "/upload/f_jpg/")

    r = requests.post(
        f"https://graph.facebook.com/v25.0/{IG_ACCOUNT_ID}/media",
        data={"image_url": image_url, "caption": caption, "access_token": FB_PAGE_TOKEN},
        timeout=60
    )
    if r.status_code != 200:
        print(f"❌ Instagram container ({r.status_code}): {r.text}"); return

    container_id = r.json().get("id")
    import time
    for _ in range(8):
        time.sleep(10)
        rs = requests.get(f"https://graph.facebook.com/v25.0/{container_id}",
                          params={"fields": "status_code", "access_token": FB_PAGE_TOKEN}, timeout=30)
        status = rs.json().get("status_code", "")
        if status == "FINISHED": break
        if status == "ERROR": print("❌ Instagram ERROR"); return

    r2 = requests.post(
        f"https://graph.facebook.com/v25.0/{IG_ACCOUNT_ID}/media_publish",
        data={"creation_id": container_id, "access_token": FB_PAGE_TOKEN}, timeout=60
    )
    if r2.status_code == 200:
        print(f"✅ Instagram publié — {r2.json().get('id','?')}")
    else:
        print(f"❌ Instagram publish ({r2.status_code}): {r2.text}")


def post_threads(image_path, caption):
    if not THREADS_ACCESS_TOKEN: return
    image_url = upload_to_cloudinary(image_path)
    if not image_url: return
    if "cloudinary.com" in image_url:
        image_url = image_url.replace("/upload/", "/upload/f_jpg/")

    r = requests.post("https://graph.threads.net/v1.0/me/threads",
                      data={"media_type": "IMAGE", "image_url": image_url,
                            "text": caption, "access_token": THREADS_ACCESS_TOKEN}, timeout=60)
    if r.status_code != 200:
        print(f"❌ Threads container ({r.status_code}): {r.text}"); return

    import time; time.sleep(5)
    r2 = requests.post("https://graph.threads.net/v1.0/me/threads_publish",
                       data={"creation_id": r.json().get("id"),
                             "access_token": THREADS_ACCESS_TOKEN}, timeout=60)
    if r2.status_code == 200:
        print(f"✅ Threads publié — {r2.json().get('id','?')}")
    else:
        print(f"❌ Threads publish ({r2.status_code}): {r2.text}")


def main():
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    day   = HOLY_WEEK.get(today)

    if not day:
        print(f"📅 {today} — pas de publication Semaine Sainte aujourd'hui.")
        return

    print(f"✝️  Semaine Sainte — {day['theme']}")

    img = make_holy_week_image(day)

    hashtags = f"#SemaineSainte #Paques #Bible #BibleFrancaise #Jésus #JésusChrist {day['tag']} #LSG1910 #LaBible #Foi #Chrétien"

    caption_tg = (
        f"{day['emoji']} <b>{day['theme']}</b>\n\n"
        f"« {day['verse']} »\n\n"
        f"— <b>{day['ref']}</b> (LSG 1910)\n\n"
        f"#SemaineSainte {day['tag']}"
    )

    caption_social = (
        f"{day['emoji']} {day['theme']}\n\n"
        f"« {day['verse']} »\n\n"
        f"— {day['ref']} (LSG 1910)\n\n"
        f"📖 Bible complète gratuite sur {APP_URL}\n\n"
        f"{hashtags}"
    )

    post_telegram(img, caption_tg)
    post_facebook(img, caption_social)
    post_instagram(img, caption_social)
    post_threads(img, caption_social)

    print(f"✅ Semaine Sainte publiée — {day['theme']}")


if __name__ == "__main__":
    main()
