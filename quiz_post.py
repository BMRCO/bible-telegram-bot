#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
quiz_post.py — Publication quotidienne du quiz biblique (midi, heure de France).

Genere une video verticale courte : un verset incomplet, trois suites
proposees, un temps de reflexion, puis la revelation de la bonne reponse.
Publie sur Telegram, Facebook, Instagram, Threads, Pinterest et YouTube.

La banque de questions est celle de la PWA (data/quiz.json), afin que le
site et les reseaux montrent exactement le meme contenu.

Usage :
    python quiz_post.py                # question suivante (rotation)
    python quiz_post.py psaumes        # force un theme
    python quiz_post.py --annonce      # carte d'annonce (1re publication)
"""

import os
import sys
import json
import math
import random
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

import requests

import bot
from bot import (
    FONT_SERIF, FONT_SERIF_BOLD, FONT_SANS,
    REEL_PALETTE_BY_CAT,
    send_video, send_photo,
    upload_video_public, upload_to_cloudinary,
)

MUSIC_DIR = "music_meditation"

# Pistes ayant deja fait l'objet d'une revendication Content ID sur la chaine :
# elles restent dans le dossier pour les anciennes videos mais ne sont plus
# utilisees pour les nouvelles publications.
CLAIMED = ("heaven's whisper", "heavens whisper", "flute meditation music 8")


def pick_music(seed):
    """Choisit une piste libre de droits, en rotation, en ecartant les pistes
    deja revendiquees. Retourne None si aucune piste n'est disponible."""
    if not os.path.isdir(MUSIC_DIR):
        return None
    tracks = sorted(
        os.path.join(MUSIC_DIR, f) for f in os.listdir(MUSIC_DIR)
        if f.lower().endswith((".mp3", ".m4a", ".ogg", ".wav"))
    )
    tracks = [t for t in tracks
              if not any(c in os.path.basename(t).lower() for c in CLAIMED)]
    if not tracks:
        print("⚠️  Aucune piste disponible — vidéo sans musique.")
        return None
    return tracks[seed % len(tracks)]


QUIZ_FILE = "data/quiz.json"
PROGRESS_FILE = "progress_quiz.json"
APP_URL = "https://labible.app"
QUIZ_URL = f"{APP_URL}/quiz"

W, H = 1080, 1920
FPS = 30
SEC_QUESTION = 18     # lecture du verset + des trois options, sans pression
SEC_COUNT = 8         # compte a rebours : court, il cree la tension
SEC_REVEAL = 8        # revelation de la reponse
TOTAL_SEC = SEC_QUESTION + SEC_COUNT + SEC_REVEAL

# cle du quiz -> cle de categorie du bot (pour reutiliser les palettes)
CAT_MAP = {
    "psaumes": "psaume",
    "promesses": "promise",
    "jesus": "jesus",
    "proverbes": "proverbe",
    "propheties": "prophetie",
    "protection": "protection",
}
ROTATION = ["psaumes", "promesses", "jesus", "proverbes", "propheties", "protection"]

LABEL_EMOJI = {
    "psaumes": "🎵", "promesses": "🌿", "jesus": "✝️",
    "proverbes": "💡", "propheties": "📯", "protection": "🛡️",
}



# ---------------------------------------------------------------
#  Publication — legendes propres au quiz
#  Les fonctions de bot.py reconstruisent leur propre message a partir
#  du verset ; ici il faut publier la legende du quiz telle quelle.
# ---------------------------------------------------------------
def fb_reel(video_path, caption):
    if not bot.FB_PAGE_TOKEN:
        print("⚠️  FB_PAGE_TOKEN non défini.")
        return
    with open(video_path, "rb") as f:
        r = requests.post(
            f"https://graph.facebook.com/v25.0/{bot.FB_PAGE_ID}/videos",
            data={"description": caption, "access_token": bot.FB_PAGE_TOKEN},
            files={"source": f}, timeout=180)
    if r.status_code == 200:
        print(f"✅ Facebook publié — {r.json().get('id')}")
    else:
        print(f"❌ Facebook ({r.status_code}): {r.text[:300]}")


def ig_reel(video_url, caption):
    if not bot.FB_PAGE_TOKEN or not video_url:
        return
    r = requests.post(
        f"https://graph.facebook.com/v25.0/{bot.IG_ACCOUNT_ID}/media",
        data={"media_type": "REELS", "video_url": video_url, "caption": caption,
              "access_token": bot.FB_PAGE_TOKEN, "thumb_offset": "1000"}, timeout=60)
    if r.status_code != 200:
        print(f"❌ Instagram container ({r.status_code}): {r.text[:300]}")
        return
    cid = r.json().get("id")
    import time
    for attempt in range(10):
        time.sleep(15)
        rs = requests.get(f"https://graph.facebook.com/v25.0/{cid}",
                          params={"fields": "status_code",
                                  "access_token": bot.FB_PAGE_TOKEN}, timeout=30)
        st = rs.json().get("status_code", "")
        print(f"  ⏳ {st} ({attempt + 1})")
        if st == "FINISHED":
            break
        if st == "ERROR":
            print("❌ Instagram : container en erreur.")
            return
    r2 = requests.post(
        f"https://graph.facebook.com/v25.0/{bot.IG_ACCOUNT_ID}/media_publish",
        data={"creation_id": cid, "access_token": bot.FB_PAGE_TOKEN}, timeout=60)
    if r2.status_code == 200:
        print(f"✅ Instagram publié — {r2.json().get('id')}")
    else:
        print(f"❌ Instagram publication ({r2.status_code}): {r2.text[:300]}")


def threads_reel(video_url, caption):
    if not bot.THREADS_ACCESS_TOKEN or not video_url:
        return
    r = requests.post("https://graph.threads.net/v1.0/me/threads",
                      data={"media_type": "VIDEO", "video_url": video_url,
                            "text": caption,
                            "access_token": bot.THREADS_ACCESS_TOKEN}, timeout=60)
    if r.status_code != 200:
        print(f"❌ Threads container ({r.status_code}): {r.text[:300]}")
        return
    import time
    time.sleep(30)
    bot._threads_publish(r.json().get("id"))


def pinterest_pin(image_path, title, description):
    """Pinterest ne prend pas la video du quiz : on epingle l'image de la
    reponse, qui contient le verset complet et la reference."""
    if not bot.PINTEREST_ACCESS_TOKEN or not bot.PINTEREST_BOARD_ID:
        print("⏭️  Pinterest non configuré.")
        return
    img_url = upload_to_cloudinary(image_path)
    if not img_url:
        return
    r = requests.post(
        "https://api.pinterest.com/v5/pins",
        headers={"Authorization": f"Bearer {bot.PINTEREST_ACCESS_TOKEN}"},
        json={"board_id": bot.PINTEREST_BOARD_ID,
              "title": title[:100],
              "description": description[:500],
              "link": QUIZ_URL,
              "media_source": {"source_type": "image_url", "url": img_url}},
        timeout=60)
    if r.status_code in (200, 201):
        print(f"✅ Pinterest publié — {r.json().get('id')}")
    else:
        print(f"❌ Pinterest ({r.status_code}): {r.text[:300]}")



def yt_upload(video_path, theme, q, seed):
    """Upload YouTube avec un titre pense pour la recherche.

    bot.post_to_youtube construit son propre titre au format des versets
    quotidiens : il annonce la reference exacte, ce qui devoile la reponse,
    et ne contient jamais le mot « quiz », alors que c'est precisement ce que
    les gens tapent. D'ou cette fonction dediee.
    """
    if not (bot.YT_CLIENT_ID and bot.YT_CLIENT_SECRET and bot.YT_REFRESH_TOKEN):
        print("⚠️  Credentials YouTube manquants.")
        return
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.auth.transport.requests import Request

        creds = Credentials(
            token=None, refresh_token=bot.YT_REFRESH_TOKEN,
            client_id=bot.YT_CLIENT_ID, client_secret=bot.YT_CLIENT_SECRET,
            token_uri="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/youtube.upload"])
        creds.refresh(Request())
        youtube = build("youtube", "v3", credentials=creds)

        label = bank[theme]["label"]
        titles = {
            "suite":  f"Quiz biblique : quelle est la suite de ce verset ? | {label} LSG 1910",
            "debut":  f"Quiz biblique : quel est le début de ce verset ? | {label} LSG 1910",
            "livre":  f"Quiz biblique : dans quel livre se trouve ce verset ? | {label} LSG 1910",
            "psaume": f"Quiz biblique : de quel Psaume vient ce verset ? | Bible LSG 1910",
        }
        title = titles.get(q.get("t"), titles["suite"])[:100]

        # La reference n'apparait qu'en fin de description : elle ne doit pas
        # devoiler la reponse dans l'apercu.
        description = (
            f"{q['q']}\n\n"
            f"Testez votre connaissance biblique. "
            f"Saurez-vous répondre avant la fin de la vidéo ?\n\n"
            f"Thème : {label} — Bible Louis Segond 1910.\n\n"
            f"📖 Le quiz complet, en six thèmes, gratuit et sans compte :\n"
            f"{QUIZ_URL}\n\n"
            f"🔔 Un quiz biblique chaque jour à midi 🙏\n\n"
            f"Réponse : {q['o'][q['a']]}\n"
            f"({q['r']} — LSG 1910)\n\n"
            f"#QuizBiblique #Bible #LSG1910 #LaBibleApp #ParoleDeDieu #Shorts")

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": ["quiz biblique", "quiz bible", "bible quiz français",
                         "test connaissance biblique", "verset biblique",
                         "Louis Segond 1910", "LSG 1910", "Bible", label,
                         "culture biblique", "Shorts"],
                "categoryId": "22",
            },
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
        }
        media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
        req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while resp is None:
            status, resp = req.next_chunk()
            if status:
                print(f"  ⏳ YouTube : {int(status.progress() * 100)}%")
        vid = resp.get("id")
        print(f"✅ YouTube Short — https://youtube.com/shorts/{vid}")

        # Vignette : la question, sans les options ni la reponse.
        try:
            thumb_path = "/tmp/quiz_thumb.png"
            make_quiz_thumb(theme, q).save(thumb_path)
            youtube.thumbnails().set(
                videoId=vid,
                media_body=MediaFileUpload(thumb_path, mimetype="image/png")).execute()
            print("✅ Vignette définie")
        except Exception as e:
            print(f"⚠️  Vignette : {str(e)[:160]}")
    except Exception as e:
        print(f"❌ YouTube : {str(e)[:300]}")


def make_quiz_thumb(theme, q):
    """Vignette 1280x720 : annonce le quiz, sans devoiler la reponse."""
    cat = CAT_MAP[theme]
    BG, GOLD, REF, TXT, SIL = REEL_PALETTE_BY_CAT[cat]
    TW, TH_ = 1280, 720
    img = Image.new("RGB", (TW, TH_))
    d = ImageDraw.Draw(img)
    for yy in range(TH_):
        t = yy / TH_
        d.line([(0, yy), (TW, yy)],
               fill=tuple(int(BG[i] + (max(0, BG[i] - 8) - BG[i]) * t) for i in range(3)))
    d.rounded_rectangle([26, 26, TW - 26, TH_ - 26], radius=20, outline=GOLD, width=4)

    f_k = ImageFont.truetype(FONT_SERIF_BOLD, 46)
    kw = _tracked(d, "QUIZ", f_k, 58, GOLD, tracking=12, largeur=TW)
    ly = 58 + 46 * 0.40
    ecart = kw / 2 + 34
    d.line([(TW / 2 - ecart - 70, ly), (TW / 2 - ecart, ly)], fill=GOLD, width=3)
    d.line([(TW / 2 + ecart, ly), (TW / 2 + ecart + 70, ly)], fill=GOLD, width=3)

    prompt = q.get("p", "Quelle est la suite de ce verset ?")
    f_p = ImageFont.truetype(FONT_SANS, 40)
    while d.textlength(prompt, font=f_p) > TW - 160 and f_p.size > 24:
        f_p = ImageFont.truetype(FONT_SANS, f_p.size - 2)
    d.text(((TW - d.textlength(prompt, font=f_p)) / 2, 130), prompt, font=f_p, fill=SIL)

    body = q["q"]
    f_v, lines = fit_font(d, body, FONT_SERIF, TW - 180, 300, 62, 30, 12)
    yy = 230
    for ln in lines[:5]:
        d.text(((TW - d.textlength(ln, font=f_v)) / 2, yy), ln, font=f_v, fill=TXT)
        yy += f_v.size + 12

    f_f = ImageFont.truetype(FONT_SANS, 26)
    d.text((60, TH_ - 76), "LSG 1910", font=f_f, fill=SIL)
    bt = "LaBible.app"
    d.text((TW - 60 - d.textlength(bt, font=f_f), TH_ - 76), bt, font=f_f, fill=GOLD)
    return img


# ---------------------------------------------------------------
#  Etat
# ---------------------------------------------------------------
def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def next_question(bank, forced=None):
    """
    Rotation sequentielle des themes ; a l'interieur d'un theme, on avance
    dans la liste sans repeter, puis on repart au debut.

    La progression n'est PAS ecrite ici : l'etat calcule est renvoye au
    programme principal, qui l'enregistre seulement apres une publication
    reussie. Une execution qui echoue ne « brule » donc plus la question
    du jour, meme lancee a la main hors de GitHub Actions.
    """
    prog = load_json(PROGRESS_FILE, {}) or {}
    if forced:
        theme = forced
    else:
        theme = ROTATION[prog.get("theme_idx", 0) % len(ROTATION)]
        prog["theme_idx"] = (prog.get("theme_idx", 0) + 1) % len(ROTATION)

    qs = bank[theme]["questions"]
    used = prog.setdefault("used", {})
    i = used.get(theme, 0)
    if i >= len(qs):
        i = 0
        print(f"🔁 {theme} : toutes les questions ont ete publiees — retour au debut.")
    q = qs[i]
    used[theme] = i + 1

    return theme, q, i + 1, len(qs), prog


# ---------------------------------------------------------------
#  Rendu
# ---------------------------------------------------------------
def gradient(top, bot_):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)],
               fill=tuple(int(top[i] + (bot_[i] - top[i]) * t) for i in range(3)))
    return img


def wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_font(draw, text, path, max_w, max_h, start, minimum=30, line_gap=16):
    size = start
    while size > minimum:
        f = ImageFont.truetype(path, size)
        lines = wrap(draw, text, f, max_w)
        if len(lines) * (size + line_gap) <= max_h:
            return f, lines
        size -= 2
    f = ImageFont.truetype(path, minimum)
    return f, wrap(draw, text, f, max_w)


def _tracked(d, text, font, y, fill, tracking=0, largeur=None):
    """Mot avec interlettrage, centre. PIL ne gere pas le letter-spacing :
    on dessine caractere par caractere. Retourne la largeur totale."""
    L = largeur or W
    total = sum(d.textlength(c, font=font) for c in text) + tracking * (len(text) - 1)
    x = (L - total) / 2
    for c in text:
        d.text((x, y), c, font=font, fill=fill)
        x += d.textlength(c, font=font) + tracking
    return total


def draw_frame(theme, q, phase, count_left=None, n_opts=None, bar=None):
    """phase : 'question' | 'count' | 'reveal'
    n_opts : n'afficher que les n premieres options (apparition progressive)
    bar    : fraction de temps restant (0..1) -> barre de progression"""
    cat = CAT_MAP[theme]
    BG, GOLD, REF, TXT, SIL = REEL_PALETTE_BY_CAT[cat]
    dark = tuple(max(0, c - 6) for c in BG)
    img = gradient(BG, dark)
    d = ImageDraw.Draw(img)

    M = 60
    d.rounded_rectangle([M, M, W - M, H - M], radius=28, outline=GOLD, width=4)

    inner = W - 2 * M - 120
    x0 = M + 60

    # Bandeau haut : le mot « QUIZ » seul, traite comme un logo.
    # « Testez votre connaissance biblique » est passe dans la legende : dans
    # l'image, une ligne de 34 caracteres en petit ne se lisait pas au defilement
    # et volait la place au theme.
    f_kick = ImageFont.truetype(FONT_SERIF_BOLD, 62)
    kw = _tracked(d, "QUIZ", f_kick, 100, GOLD, tracking=16)
    ly = 100 + 62 * 0.40
    ecart = kw / 2 + 44
    d.line([(W / 2 - ecart - 92, ly), (W / 2 - ecart, ly)], fill=GOLD, width=3)
    d.line([(W / 2 + ecart, ly), (W / 2 + ecart + 92, ly)], fill=GOLD, width=3)

    f_theme = ImageFont.truetype(FONT_SERIF_BOLD, 40)
    lbl = bank[theme]["label"]
    d.text(((W - d.textlength(lbl, font=f_theme)) / 2, 204), lbl, font=f_theme, fill=SIL)

    # consigne : bien visible, avant le verset — beaucoup de gens ne lisent
    # pas la legende, l'instruction doit etre dans l'image.
    prompt = q.get("p", "Quelle est la suite de ce verset ?")
    f_p = ImageFont.truetype(FONT_SANS, 40)
    while d.textlength(prompt, font=f_p) > inner and f_p.size > 26:
        f_p = ImageFont.truetype(FONT_SANS, f_p.size - 2)
    pw = d.textlength(prompt, font=f_p)
    py = 286
    d.rounded_rectangle([(W - pw) / 2 - 34, py - 16, (W + pw) / 2 + 34, py + f_p.size + 20],
                        radius=14, outline=GOLD, width=2)
    d.text(((W - pw) / 2, py), prompt, font=f_p, fill=GOLD)

    # question
    head = q["q"]
    f_q, q_lines = fit_font(d, head, FONT_SERIF, inner, 400, 60, 34, 18)
    y = py + f_p.size + 78
    for ln in q_lines:
        d.text(((W - d.textlength(ln, font=f_q)) / 2, y), ln, font=f_q, fill=TXT)
        y += f_q.size + 18

    # options — police commune, la plus grande qui fasse tenir les 3 en entier
    f_key = ImageFont.truetype(FONT_SANS, 34)
    opt_w = inner - 150
    size = 42
    while size > 24:
        f_try = ImageFont.truetype(FONT_SERIF, size)
        wrapped = [wrap(d, o, f_try, opt_w) for o in q["o"]]
        if max(len(x) for x in wrapped) <= 3:
            break
        size -= 2
    f_opt = ImageFont.truetype(FONT_SERIF, size)
    wrapped = [wrap(d, o, f_opt, opt_w) for o in q["o"]]
    lh = size + 12
    boxes = [max(130, len(x) * lh + 52) for x in wrapped]

    # Bloc d'options centre dans l'espace restant.
    # Le plafond etait a 870 : sur les questions courtes, tout le bas de la
    # carte restait vide (un cinquieme de l'image). Descendu a 1010 — la borne
    # « H - 430 - total_opts » continue de remonter le bloc quand les options
    # sont longues, et de reserver la place du decompte et de la barre.
    total_opts = sum(boxes) + 26 * (len(boxes) - 1)
    y = max(y + 50, min(1010, H - 430 - total_opts))

    shown = len(q["o"]) if n_opts is None else n_opts
    for i, opt in enumerate(q["o"]):
        if i >= shown:
            break
        good = (i == q["a"])
        reveal = (phase == "reveal")
        border = GOLD if (reveal and good) else (60, 58, 54)
        width = 5 if (reveal and good) else 2
        if reveal and not good:
            fill_txt = tuple(int(c * 0.42) for c in TXT)
            fill_key = tuple(int(c * 0.42) for c in GOLD)
        else:
            fill_txt, fill_key = TXT, GOLD
        bh = boxes[i]
        d.rounded_rectangle([x0, y, W - x0, y + bh], radius=16,
                            outline=border, width=width)
        d.text((x0 + 34, y + bh / 2 - 22), chr(65 + i), font=f_key, fill=fill_key)
        lines = wrapped[i]
        ty = y + bh / 2 - (len(lines) * lh) / 2
        for ln in lines:
            d.text((x0 + 100, ty), ln, font=f_opt, fill=fill_txt)
            ty += lh
        if reveal and good:
            f_mark = ImageFont.truetype(FONT_SANS, 46)
            d.text((W - x0 - 62, y + bh / 2 - 28), "\u2713", font=f_mark, fill=GOLD)
        y += bh + 26

    # bas de carte
    f_small = ImageFont.truetype(FONT_SANS, 32)
    if phase == "count":
        txt = str(count_left)
        f_c = ImageFont.truetype(FONT_SERIF_BOLD, 96)
        d.text(((W - d.textlength(txt, font=f_c)) / 2, y + 30), txt, font=f_c, fill=GOLD)
        if bar is not None:
            bx0, bx1 = x0 + 60, W - x0 - 60
            by = y + 150
            d.rounded_rectangle([bx0, by, bx1, by + 12], radius=6,
                                fill=tuple(int(c * 0.28) for c in GOLD))
            filled = bx0 + int((bx1 - bx0) * max(0.0, min(1.0, bar)))
            if filled > bx0 + 6:
                d.rounded_rectangle([bx0, by, filled, by + 12], radius=6, fill=GOLD)
    elif phase == "reveal":
        f_r = ImageFont.truetype(FONT_SERIF_BOLD, 42)
        rt = q["r"]
        d.text(((W - d.textlength(rt, font=f_r)) / 2, y + 46), rt, font=f_r, fill=GOLD)
        cta = "Le quiz complet sur labible.app/quiz"
        d.text(((W - d.textlength(cta, font=f_small)) / 2, y + 112), cta, font=f_small, fill=SIL)
    else:
        cta = "A, B ou C ?"
        d.text(((W - d.textlength(cta, font=f_small)) / 2, y + 46), cta, font=f_small, fill=SIL)

    # pied
    f_foot = ImageFont.truetype(FONT_SANS, 28)
    d.text((M + 40, H - M - 60), "LSG 1910", font=f_foot, fill=SIL)
    bt = "LaBible.app"
    d.text((W - M - 40 - d.textlength(bt, font=f_foot), H - M - 60), bt, font=f_foot, fill=GOLD)
    return img


def make_annonce_card(theme="psaumes"):
    cat = CAT_MAP[theme]
    BG, GOLD, REF, TXT, SIL = REEL_PALETTE_BY_CAT[cat]
    img = gradient(BG, tuple(max(0, c - 6) for c in BG))
    d = ImageDraw.Draw(img)
    M = 60
    d.rounded_rectangle([M, M, W - M, H - M], radius=28, outline=GOLD, width=4)
    f_k = ImageFont.truetype(FONT_SANS, 32)
    d.text(((W - d.textlength("N O U V E A U", font=f_k)) / 2, 300), "N O U V E A U", font=f_k, fill=GOLD)
    f_t = ImageFont.truetype(FONT_SERIF_BOLD, 92)
    for i, ln in enumerate(["Testez votre", "connaissance", "biblique"]):
        d.text(((W - d.textlength(ln, font=f_t)) / 2, 420 + i * 118), ln, font=f_t, fill=TXT)
    d.line([(W / 2 - 90, 810), (W / 2 + 90, 810)], fill=GOLD, width=3)
    f_s = ImageFont.truetype(FONT_SANS, 36)
    for i, ln in enumerate(["Six thèmes · Bible Louis Segond 1910",
                            "Un verset incomplet, trois suites.",
                            "À vous de reconnaître la bonne."]):
        d.text(((W - d.textlength(ln, font=f_s)) / 2, 890 + i * 62), ln, font=f_s, fill=SIL)
    f_u = ImageFont.truetype(FONT_SERIF_BOLD, 58)
    d.text(((W - d.textlength("labible.app/quiz", font=f_u)) / 2, 1210), "labible.app/quiz", font=f_u, fill=GOLD)
    f_g = ImageFont.truetype(FONT_SANS, 32)
    g = "Gratuit · sans compte · sans publicité"
    d.text(((W - d.textlength(g, font=f_g)) / 2, 1300), g, font=f_g, fill=SIL)
    f_foot = ImageFont.truetype(FONT_SANS, 28)
    d.text((M + 40, H - M - 60), "LSG 1910", font=f_foot, fill=SIL)
    bt = "LaBible.app"
    d.text((W - M - 40 - d.textlength(bt, font=f_foot), H - M - 60), bt, font=f_foot, fill=GOLD)
    return img


def build_video(theme, q, out_path, music=None):
    tmp = tempfile.mkdtemp(prefix="quiz_")
    frames = []
    n = 0

    def dump(img, seconds):
        nonlocal n
        p = os.path.join(tmp, f"f{n:04d}.png")
        img.save(p)
        frames.append((p, seconds))
        n += 1

    # Apparition progressive : le verset seul, puis les options une a une.
    # Un plan totalement fixe est mal distribue sur TikTok/Reels ; ces
    # changements donnent du mouvement sans trahir la sobriete de la marque.
    intro = min(3.0, SEC_QUESTION / 3.0)
    step = intro / 3.0
    for k in range(3):
        dump(draw_frame(theme, q, "question", n_opts=k), step)
    dump(draw_frame(theme, q, "question"), SEC_QUESTION - intro)

    # Compte a rebours : demi-secondes, avec barre de progression qui se vide.
    total = SEC_COUNT
    for i in range(total * 2):
        left = total - i / 2.0
        dump(draw_frame(theme, q, "count", math.ceil(left), bar=left / total), 0.5)

    dump(draw_frame(theme, q, "reveal"), SEC_REVEAL)

    listfile = os.path.join(tmp, "list.txt")
    with open(listfile, "w") as f:
        for p, s in frames:
            f.write(f"file '{p}'\nduration {s}\n")
        f.write(f"file '{frames[-1][0]}'\n")

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile]
    if music:
        cmd += ["-i", music]
    # Leger zoom continu (~4% sur toute la duree) : le flux ne parait jamais
    # fige, ce qui aide la distribution sur les plateformes video.
    frames_total = FPS * TOTAL_SEC
    zoom = (f"fps={FPS},scale={W * 2}:{H * 2},"
            f"zoompan=z='min(1+0.04*on/{frames_total},1.04)'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d=1:s={W}x{H}:fps={FPS}")
    cmd += ["-vf", f"{zoom},format=yuv420p", "-c:v", "libx264",
            "-preset", "medium", "-crf", "22", "-movflags", "+faststart"]
    if music:
        fade_out = max(0, TOTAL_SEC - 2)
        cmd += ["-c:a", "aac", "-b:a", "128k",
                "-af", (f"volume=0.32,afade=t=in:st=0:d=1.2,"
                        f"afade=t=out:st={fade_out}:d=2"),
                "-map", "0:v:0", "-map", "1:a:0", "-shortest"]
    cmd += [out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


# ---------------------------------------------------------------
#  Legendes
# ---------------------------------------------------------------
# Accroches variees, adaptees au type de question : evite la repetition
# d'un titre unique jour apres jour.
HOOKS = {
    "suite": [
        "📖 Quiz : quelle est la suite de ce verset ?",
        "📖 Quiz biblique : sauriez-vous compléter ce verset ?",
        "📖 Quiz : comment se termine ce verset ?",
    ],
    "debut": [
        "📖 Quiz : par quoi commence ce verset ?",
        "📖 Quiz biblique : reconnaissez-vous le début de ce verset ?",
        "📖 Quiz : quel est le début de ce verset ?",
    ],
    "livre": [
        "📖 Quiz : dans quel livre se trouve ce verset ?",
        "📖 Quiz biblique : sauriez-vous situer ce verset ?",
        "📖 Quiz : de quel livre vient ce verset ?",
    ],
    "psaume": [
        "📖 Quiz : de quel Psaume vient ce verset ?",
        "📖 Quiz biblique : sauriez-vous retrouver ce Psaume ?",
        "📖 Quiz : quel Psaume dit cela ?",
    ],
}

HASHTAGS_TIKTOK = ("#bible #versetdujour #quizbiblique #foi #chretien "
                   "#parolededieu #louissegond #dieu #priere #jesus")


# Formulation de reference par type de question. C'est TOUT ce que le modele
# recoit : ni le verset, ni les options, ni la reference. Il ne peut donc pas
# reveler ce qu'il ne voit pas — la garantie anti-spoiler est structurelle,
# pas declarative.
ASK_BY_TYPE = {
    "suite":  "quelle est la suite de ce verset",
    "debut":  "par quoi commence ce verset",
    "livre":  "dans quel livre se trouve ce verset",
    "psaume": "de quel Psaume vient ce verset",
}

_QUIZ_HOOK_CACHE = {}


def _hook_fixe(q, seed):
    """Repli : rotation dans les 3 variantes ecrites a la main du type voulu.
    Deterministe par question (meme question -> meme accroche) mais bien
    repartie, contrairement a un simple compteur."""
    variants = HOOKS.get(q.get("t"), HOOKS["suite"])
    h = sum(ord(c) for c in q.get("r", "")) + seed
    return variants[h % len(variants)]


def generate_quiz_hook_ai(q):
    """Reformule la question d'accroche. Retourne None en cas d'echec —
    ne leve JAMAIS : un souci d'API ne doit pas bloquer la publication."""
    if not bot.ANTHROPIC_API_KEY:
        return None
    ask = ASK_BY_TYPE.get(q.get("t"))
    if not ask:
        return None
    try:
        prompt = (
            "Tu reformules la question d'accroche d'un quiz biblique quotidien "
            "(LaBible.app).\n\n"
            f"Formulation de reference : « {ask} ? »\n\n"
            "Ecris UNE autre maniere de poser exactement la meme question.\n\n"
            "Regles strictes :\n"
            "- Francais, vouvoiement si la phrase s'adresse au lecteur.\n"
            "- Ton sobre et serieux. Aucun clickbait, aucune exageration, "
            "aucune promesse, aucune flatterie.\n"
            "- Tu ne connais pas le verset : n'ecris rien sur son contenu.\n"
            "- Aucun nom de livre biblique, aucun nom propre, aucun chiffre.\n"
            "- 10 mots maximum. Termine par un point d'interrogation.\n"
            "- Reponds UNIQUEMENT avec la question, sans guillemets."
        )
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": bot.ANTHROPIC_API_KEY,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": bot.ANTHROPIC_MODEL, "max_tokens": 60,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=10,
        )
        if r.status_code != 200:
            print(f"⚠️  Accroche quiz IA ({r.status_code}) : {r.text[:150]}")
            return None
        txt = "".join(b.get("text", "") for b in r.json().get("content", [])
                      if b.get("type") == "text").strip().strip('"').strip("«»").strip()
        # Garde-fous : question courte, sans chiffre (un numero de Psaume
        # fuiterait), et qui ne contient aucun mot de la reponse.
        # 10 mots + « ? » au maximum, comme demande dans le prompt.
        if not txt or not txt.endswith("?") or len(txt) > 70 or len(txt.split()) > 11:
            print(f"⚠️  Accroche quiz rejetee (forme) : {txt[:60]!r}")
            return None
        if any(c.isdigit() for c in txt):
            print(f"⚠️  Accroche quiz rejetee (chiffre) : {txt[:60]!r}")
            return None
        # « Quiz : » est ajoute par le code ; sinon on obtiendrait « Quiz : quiz... ».
        if txt.lower().startswith("quiz"):
            print(f"⚠️  Accroche quiz rejetee (repete « Quiz ») : {txt[:60]!r}")
            return None
        # Meme liste de formules interdites que les accroches de versets.
        if bot._HOOK_INTERDIT.search(txt):
            print(f"⚠️  Accroche quiz rejetee (formule interdite) : {txt[:60]!r}")
            return None
        bas = txt.lower()
        interdits = set()
        for mot in (q.get("r", "") + " " + q["o"][q["a"]]).replace(":", " ").split():
            if len(mot) > 3:
                interdits.add(mot.lower().strip(",.;!?"))
        if any(m in bas for m in interdits):
            print(f"⚠️  Accroche quiz rejetee (mot de la reponse) : {txt[:60]!r}")
            return None
        return txt
    except Exception as e:
        print(f"⚠️  Accroche quiz indisponible : {str(e)[:150]}")
        return None


def hook_for(q, seed):
    """Accroche du quiz : « 📖 Quiz : <question> ».

    Les 12 formulations ecrites a la main servaient 2032 questions — qui suit
    le canal voyait la meme phrase tous les jours. L'IA en propose une autre a
    chaque publication ; le pool fixe reste le repli.
    Mise en cache : hook_for est appele deux fois (legendes + titre Pinterest)."""
    cle = (q.get("r", ""), q.get("t", ""), seed)
    if cle in _QUIZ_HOOK_CACHE:
        return _QUIZ_HOOK_CACHE[cle]
    phrase = None
    if bot.USE_AI_HOOK:
        phrase = generate_quiz_hook_ai(q)
        if phrase:
            print(f"✍️  Accroche quiz IA : {phrase}")
    hook = f"📖 Quiz : {phrase[0].lower()}{phrase[1:]}" if phrase else _hook_fixe(q, seed)
    _QUIZ_HOOK_CACHE[cle] = hook
    return hook


def captions(theme, q, seed=0):
    label = bank[theme]["label"]
    head = q["q"]
    hook = hook_for(q, seed)
    plain = hook.replace("📖 ", "")

    fb = (f"{hook}\n\nTestez votre connaissance biblique.\n\n{head}\n\n"
          f"La réponse apparaît à la fin de la vidéo.\n\n"
          f"Thème du jour : {label}. Le quiz complet, en six thèmes, est disponible ici :\n"
          f"{QUIZ_URL}\n\nGratuit, sans compte, sans publicité.\n\n"
          f"#Bible #LouisSegond #LaBibleApp #QuizBiblique #Foi")
    ig = (f"{head}\n\n{plain}\nTestez votre connaissance biblique.\n\n"
          f"La réponse apparaît à la fin.\n\n"
          f"Thème du jour : {label}.\n\n📖 Quiz complet — lien en bio\n\n"
          f"#Bible #LouisSegond #LaBibleApp #QuizBiblique #VersetDuJour #Foi #Chrétien")
    tg = (f"📖 <b>{plain}</b>\n\nTestez votre connaissance biblique.\n\n{head}\n\n"
          f"La réponse apparaît à la fin de la vidéo.\n\n"
          f"Thème du jour : {label}.\n\n"
          f"👉 <a href=\"{QUIZ_URL}\">Le quiz complet sur labible.app</a>")
    th = (f"{head}\n\n{plain}\nTestez votre connaissance biblique.\n\n"
          f"La réponse à la fin de la vidéo.\n\n"
          f"Thème du jour : {label}.\n\n👉 labible.app/quiz")
    tt = (f"{plain}\n\n{head}\n\nRéponse à la fin 🙏\n\n"
          f"Quiz complet sur labible.app/quiz\n\n{HASHTAGS_TIKTOK}")
    return fb, ig, tg, th, tt


# ---------------------------------------------------------------
#  Main
# ---------------------------------------------------------------
if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    annonce = "--annonce" in args
    args = [a for a in args if not a.startswith("--")]

    bank = load_json(QUIZ_FILE)
    if not bank:
        print(f"❌ {QUIZ_FILE} introuvable.")
        sys.exit(1)

    if annonce:
        img = make_annonce_card()
        path = "/tmp/quiz_annonce.png"
        img.save(path)
        cap = ("📖 Testez votre connaissance biblique\n\n"
               "Une nouvelle page est disponible sur LaBible.app : un quiz en six thèmes, "
               "fondé sur la Bible Louis Segond 1910.\n\n"
               "Un verset vous est présenté, incomplet. Trois suites vous sont proposées. "
               "À vous de reconnaître la bonne.\n\n"
               "À partir d'aujourd'hui, une question chaque jour à midi.\n\n"
               f"👉 {QUIZ_URL}\n\nGratuit, sans compte, sans publicité.")
        tg_cap = cap.replace(f"👉 {QUIZ_URL}",
                             f"👉 <a href=\"{QUIZ_URL}\">labible.app/quiz</a>")
        print("📤 Annonce…")
        try:
            bot.send_photo(path, tg_cap)
        except Exception as e:
            print("⚠️ Telegram:", e)
        try:
            if bot.FB_PAGE_TOKEN:
                with open(path, "rb") as f:
                    r = requests.post(
                        f"https://graph.facebook.com/v25.0/{bot.FB_PAGE_ID}/photos",
                        data={"message": cap, "access_token": bot.FB_PAGE_TOKEN},
                        files={"source": f}, timeout=90)
                print("✅ Facebook publié" if r.status_code == 200
                      else f"❌ Facebook ({r.status_code}): {r.text[:200]}")
        except Exception as e:
            print("⚠️ Facebook:", e)

        img_url = None
        try:
            img_url = upload_to_cloudinary(path)
        except Exception as e:
            print("⚠️ Cloudinary:", e)

        try:
            if img_url and bot.FB_PAGE_TOKEN:
                r = requests.post(
                    f"https://graph.facebook.com/v25.0/{bot.IG_ACCOUNT_ID}/media",
                    data={"image_url": img_url, "caption": cap,
                          "access_token": bot.FB_PAGE_TOKEN}, timeout=60)
                if r.status_code == 200:
                    cid = r.json().get("id")
                    import time
                    time.sleep(8)
                    r2 = requests.post(
                        f"https://graph.facebook.com/v25.0/{bot.IG_ACCOUNT_ID}/media_publish",
                        data={"creation_id": cid,
                              "access_token": bot.FB_PAGE_TOKEN}, timeout=60)
                    print("✅ Instagram publié" if r2.status_code == 200
                          else f"❌ Instagram ({r2.status_code}): {r2.text[:200]}")
                else:
                    print(f"❌ Instagram container ({r.status_code}): {r.text[:200]}")
        except Exception as e:
            print("⚠️ Instagram:", e)

        try:
            if img_url and bot.THREADS_ACCESS_TOKEN:
                u = img_url.replace("/upload/", "/upload/f_jpg/")
                r = requests.post("https://graph.threads.net/v1.0/me/threads",
                                  data={"media_type": "IMAGE", "image_url": u,
                                        "text": cap,
                                        "access_token": bot.THREADS_ACCESS_TOKEN},
                                  timeout=60)
                if r.status_code == 200:
                    import time
                    time.sleep(10)
                    bot._threads_publish(r.json().get("id"))
                else:
                    print(f"❌ Threads container ({r.status_code}): {r.text[:200]}")
        except Exception as e:
            print("⚠️ Threads:", e)
        print("✅ Annonce publiée.")
        sys.exit(0)

    forced = args[0].lower() if args else None
    if forced and forced not in bank:
        print(f"❌ Thème inconnu : {forced}. Choix : {', '.join(bank.keys())}")
        sys.exit(1)

    theme, q, pos, total, prog = next_question(bank, forced)
    print(f"🎯 {bank[theme]['label']} — question {pos}/{total}")
    print(f"   {q['q'][:70]}…")
    print(f"   réponse : {q['o'][q['a']][:60]}  ({q['r']})")

    video = "/tmp/quiz_du_jour.mp4"
    # Meme valeur qu'avant : "prog" contient deja le theme_idx incremente
    # (rotation) ou celui du fichier (theme force).
    seed = prog.get("theme_idx", 0) + pos
    music = pick_music(seed)
    if music:
        print(f"🎵 {os.path.basename(music)}")
    build_video(theme, q, video, music)
    print(f"🎬 Vidéo prête ({TOTAL_SEC}s).")

    fb, ig, tg, th, tt = captions(theme, q, seed)
    cat = CAT_MAP[theme]
    ref = q["r"]

    try:
        send_video(video, tg, ref)
    except Exception as e:
        print("⚠️ Telegram:", e)

    try:
        fb_reel(video, fb)
    except Exception as e:
        print("⚠️ Facebook:", e)

    video_url = None
    try:
        video_url = upload_video_public(video)
    except Exception as e:
        print("⚠️ Upload vidéo:", e)

    try:
        ig_reel(video_url, ig)
    except Exception as e:
        print("⚠️ Instagram:", e)

    try:
        threads_reel(video_url, th)
    except Exception as e:
        print("⚠️ Threads:", e)

    try:
        yt_upload(video, theme, q, seed)
    except Exception as e:
        print("⚠️ YouTube:", e)

    try:
        reveal_png = "/tmp/quiz_reveal.png"
        draw_frame(theme, q, "reveal").save(reveal_png)
        pin_title = hook_for(q, seed).replace("📖 ", "")
        pin_desc = (f"{q['q']}\n\nRéponse : {q['o'][q['a']]}\n{q['r']} — "
                    f"Bible Louis Segond 1910.\nLe quiz complet sur labible.app/quiz")
        pinterest_pin(reveal_png, pin_title, pin_desc)
    except Exception as e:
        print("⚠️ Pinterest:", e)

    # ─── Progression (uniquement apres publication reussie) ───
    # Un theme force est un tir ponctuel : il ne fait pas avancer la rotation.
    if not forced:
        save_json(PROGRESS_FILE, prog)
        print(f"💾 Progression enregistree — prochain thème : "
              f"{ROTATION[prog.get('theme_idx', 0) % len(ROTATION)]}")

    print("✅ Quiz du jour publié.")
    print("\n" + "─" * 56)
    print("TikTok — à publier manuellement, texte à copier :")
    print("─" * 56)
    print(tt)
    print("─" * 56)
