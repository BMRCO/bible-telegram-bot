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
    send_video, send_photo, post_to_youtube,
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
SEC_QUESTION = 14     # lecture du verset + des trois options
SEC_COUNT = 8         # temps de reflexion (compte a rebours)
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

    if not forced:
        save_json(PROGRESS_FILE, prog)
    return theme, q, i + 1, len(qs)


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

    # bandeau haut
    f_kick = ImageFont.truetype(FONT_SANS, 30)
    kick = "TESTEZ VOTRE CONNAISSANCE BIBLIQUE"
    d.text(((W - d.textlength(kick, font=f_kick)) / 2, 150), kick, font=f_kick, fill=GOLD)

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

    # bloc d'options centre dans l'espace restant
    total_opts = sum(boxes) + 26 * (len(boxes) - 1)
    y = max(y + 50, min(870, H - 430 - total_opts))

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


def hook_for(q, seed):
    """Variante choisie a partir de la reference du verset : deterministe
    (meme question -> meme accroche) mais bien repartie, contrairement a un
    simple compteur qui retomberait toujours sur la meme variante pour un
    type donne."""
    variants = HOOKS.get(q.get("t"), HOOKS["suite"])
    h = sum(ord(c) for c in q.get("r", "")) + seed
    return variants[h % len(variants)]


def captions(theme, q, seed=0):
    label = bank[theme]["label"]
    head = q["q"]
    hook = hook_for(q, seed)
    plain = hook.replace("📖 ", "")

    fb = (f"{hook}\n\n{head}\n\n"
          f"La réponse apparaît à la fin de la vidéo.\n\n"
          f"Thème du jour : {label}. Le quiz complet, en six thèmes, est disponible ici :\n"
          f"{QUIZ_URL}\n\nGratuit, sans compte, sans publicité.\n\n"
          f"#Bible #LouisSegond #LaBibleApp #QuizBiblique #Foi")
    ig = (f"{head}\n\n{plain}\n\nLa réponse apparaît à la fin.\n\n"
          f"Thème du jour : {label}.\n\n📖 Quiz complet — lien en bio\n\n"
          f"#Bible #LouisSegond #LaBibleApp #QuizBiblique #VersetDuJour #Foi #Chrétien")
    tg = (f"📖 <b>{plain}</b>\n\n{head}\n\n"
          f"La réponse apparaît à la fin de la vidéo.\n\n"
          f"Thème du jour : {label}.\n\n"
          f"👉 <a href=\"{QUIZ_URL}\">Le quiz complet sur labible.app</a>")
    th = (f"{head}\n\n{plain}\n\nLa réponse à la fin de la vidéo.\n\n"
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

    theme, q, pos, total = next_question(bank, forced)
    print(f"🎯 {bank[theme]['label']} — question {pos}/{total}")
    print(f"   {q['q'][:70]}…")
    print(f"   réponse : {q['o'][q['a']][:60]}  ({q['r']})")

    video = "/tmp/quiz_du_jour.mp4"
    seed = (load_json(PROGRESS_FILE, {}) or {}).get("theme_idx", 0) + pos
    music = pick_music(seed)
    if music:
        print(f"🎵 {os.path.basename(music)}")
    build_video(theme, q, video, music)
    print(f"🎬 Vidéo prête ({TOTAL_SEC}s).")

    fb, ig, tg, th, tt = captions(theme, q, seed)
    cat = CAT_MAP[theme]
    ref = q["r"]

    try:
        send_video(video, tg)
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
        post_to_youtube(video, ref, q["q"], bot.CATEGORIES[cat], cat, 10)
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

    print("✅ Quiz du jour publié.")
    print("\n" + "─" * 56)
    print("TikTok — à publier manuellement, texte à copier :")
    print("─" * 56)
    print(tt)
    print("─" * 56)
