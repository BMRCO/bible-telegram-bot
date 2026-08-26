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

import bot
from bot import (
    FONT_SERIF, FONT_SERIF_BOLD, FONT_SANS,
    REEL_PALETTE_BY_CAT,
    send_video, post_reel_to_facebook, post_reel_to_instagram,
    post_reel_to_threads, post_to_pinterest, post_to_youtube,
    upload_to_cloudinary,
)

QUIZ_FILE = "data/quiz.json"
PROGRESS_FILE = "progress_quiz.json"
APP_URL = "https://labible.app"
QUIZ_URL = f"{APP_URL}/quiz"

W, H = 1080, 1920
FPS = 30
SEC_QUESTION = 6      # affichage question + options
SEC_COUNT = 3         # temps de reflexion (compte a rebours)
SEC_REVEAL = 5        # revelation de la reponse
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


def draw_frame(theme, q, phase, count_left=None):
    """phase: 'question' | 'count' | 'reveal'"""
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
    d.text(((W - d.textlength(lbl, font=f_theme)) / 2, 210), lbl, font=f_theme, fill=SIL)

    # question
    head = "« " + q["q"] + " …"
    f_q, q_lines = fit_font(d, head, FONT_SERIF, inner, 430, 62, 34, 18)
    y = 330
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

    for i, opt in enumerate(q["o"]):
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
        d.text(((W - d.textlength(txt, font=f_c)) / 2, y + 40), txt, font=f_c, fill=GOLD)
    elif phase == "reveal":
        f_r = ImageFont.truetype(FONT_SERIF_BOLD, 42)
        rt = q["r"]
        d.text(((W - d.textlength(rt, font=f_r)) / 2, y + 46), rt, font=f_r, fill=GOLD)
        cta = "Le quiz complet sur labible.app/quiz"
        d.text(((W - d.textlength(cta, font=f_small)) / 2, y + 112), cta, font=f_small, fill=SIL)
    else:
        cta = "Quelle est la suite ?"
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


def build_video(theme, q, out_path):
    tmp = tempfile.mkdtemp(prefix="quiz_")
    frames = []
    n = 0

    def dump(img, seconds):
        nonlocal n
        p = os.path.join(tmp, f"f{n:04d}.png")
        img.save(p)
        frames.append((p, seconds))
        n += 1

    dump(draw_frame(theme, q, "question"), SEC_QUESTION)
    for c in range(SEC_COUNT, 0, -1):
        dump(draw_frame(theme, q, "count", c), 1)
    dump(draw_frame(theme, q, "reveal"), SEC_REVEAL)

    listfile = os.path.join(tmp, "list.txt")
    with open(listfile, "w") as f:
        for p, s in frames:
            f.write(f"file '{p}'\nduration {s}\n")
        f.write(f"file '{frames[-1][0]}'\n")

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listfile,
           "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264",
           "-preset", "medium", "-crf", "22", "-movflags", "+faststart",
           out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


# ---------------------------------------------------------------
#  Legendes
# ---------------------------------------------------------------
def captions(theme, q):
    label = bank[theme]["label"]
    head = "« " + q["q"] + " … »"
    fb = (f"📖 Testez votre connaissance biblique\n\n{head}\n\n"
          f"Quelle est la suite de ce verset ? La réponse apparaît à la fin de la vidéo.\n\n"
          f"Thème du jour : {label}. Le quiz complet, en six thèmes, est disponible ici :\n"
          f"{QUIZ_URL}\n\nGratuit, sans compte, sans publicité.\n\n"
          f"#Bible #LouisSegond #LaBibleApp #QuizBiblique #Foi")
    ig = (f"{head}\n\nQuelle est la suite de ce verset ? La réponse apparaît à la fin.\n\n"
          f"Thème du jour : {label}.\n\n📖 Quiz complet — lien en bio\n\n"
          f"#Bible #LouisSegond #LaBibleApp #QuizBiblique #VersetDuJour #Foi #Chrétien")
    tg = (f"📖 <b>Testez votre connaissance biblique</b>\n\n{head}\n\n"
          f"La réponse apparaît à la fin de la vidéo.\n\n"
          f"Thème du jour : {label}.\n\n"
          f"👉 <a href=\"{QUIZ_URL}\">Le quiz complet sur labible.app</a>")
    th = (f"{head}\n\nQuelle est la suite ? La réponse à la fin de la vidéo.\n\n"
          f"Thème du jour : {label}.\n\n👉 labible.app/quiz")
    return fb, ig, tg, th


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
            bot.post_to_facebook(path, "LaBible.app", cap, REEL_PALETTE_BY_CAT["psaume"],
                                 "psaume", link_override=QUIZ_URL)
        except Exception as e:
            print("⚠️ Facebook:", e)
        try:
            bot.post_to_instagram(path, "LaBible.app", cap, REEL_PALETTE_BY_CAT["psaume"],
                                  "psaume", link_override=QUIZ_URL)
        except Exception as e:
            print("⚠️ Instagram:", e)
        try:
            bot.post_to_threads(path, "LaBible.app", cap, REEL_PALETTE_BY_CAT["psaume"],
                                "psaume", link_override=QUIZ_URL)
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
    build_video(theme, q, video)
    print(f"🎬 Vidéo prête ({TOTAL_SEC}s).")

    fb, ig, tg, th = captions(theme, q)
    cat = CAT_MAP[theme]
    pal = REEL_PALETTE_BY_CAT[cat]
    ref = q["r"]

    try:
        send_video(video, tg)
    except Exception as e:
        print("⚠️ Telegram:", e)
    try:
        post_reel_to_facebook(video, ref, fb, pal, cat, link_override=QUIZ_URL)
    except Exception as e:
        print("⚠️ Facebook:", e)
    try:
        post_reel_to_instagram(video, ref, ig, pal, cat, link_override=QUIZ_URL)
    except Exception as e:
        print("⚠️ Instagram:", e)
    try:
        post_reel_to_threads(video, ref, th, pal, cat, link_override=QUIZ_URL)
    except Exception as e:
        print("⚠️ Threads:", e)
    try:
        post_to_youtube(video, ref, fb, pal, cat, 10)
    except Exception as e:
        print("⚠️ YouTube:", e)

    print("✅ Quiz du jour publié.")
