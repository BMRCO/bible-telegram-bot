"""
thematic_meditation.py
======================
Gera v\u00eddeo horizontal 1920\u00d71080 de medita\u00e7\u00e3o TEM\u00c1TICA (7 vers\u00edculos sobre um tema),
no mesmo estilo das medita\u00e7\u00f5es de Salmos, mas com COR POR TEMA.
Publica em YouTube + Facebook + Telegram.

Rota\u00e7\u00e3o autom\u00e1tica: a cada execu\u00e7\u00e3o, avan\u00e7a um tema (protection \u2192 paix \u2192 \u2026 ) e
puxa os 7 vers\u00edculos seguintes desse tema (cicla por todos com o tempo).

Uso:
    python thematic_meditation.py                 \u2192 tema seguinte (rota\u00e7\u00e3o autom\u00e1tica)
    python thematic_meditation.py protection      \u2192 tema espec\u00edfico (avan\u00e7a o seu offset)
    python thematic_meditation.py paix 0          \u2192 tema 'paix' a come\u00e7ar no \u00edndice 0

Estado salvo em: progress_thematic.json
"""

import os
import sys
import json
import subprocess
import shutil
import random
import hashlib

import requests
from PIL import Image, ImageDraw, ImageFont

# Reutiliza utilitarios do bot
from bot import (
    load_json, save_json, clean_text, strip_rubric,
    post_reel_to_instagram, post_reel_to_threads, make_thumbnail,
    BIBLE_FILE, APP_URL, WATERMARK, parse_ref_to_chapter_url,
    FONT_SERIF, FONT_SERIF_BOLD, FONT_SANS,
)
# Reutiliza helpers de render + musica das meditacoes de Salmos
from psaume_meditation import (
    ease, gradient_bg, wrap, autosize_font, pick_safe_music,
    FPS, SECS_INTRO, SECS_OUTRO, FADE_DURATION,
)

# Tematicas em VERTICAL 9:16 (1080x1920) -> caem nos Shorts do YouTube (duracao < 3 min)
W, H = 1080, 1920

# Credenciais (mesmas secrets do meditation.yml)
YT_CLIENT_ID     = os.environ.get("YOUTUBE_CLIENT_ID", "")
YT_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "")
FB_PAGE_ID       = os.environ.get("FB_PAGE_ID", "1018605031335601")
FB_PAGE_TOKEN    = os.environ.get("FB_PAGE_TOKEN", "")

PROGRESS_FILE   = "progress_thematic.json"
THEMATIC_VERSES = 5      # versiculos por video (para o Short ficar < 60s)
SECS_PER_VERSE  = 9      # ritmo de meditacao
# intro/outro mais curtos SO nos tematicos (sombreia o import; nao afeta os Salmos)
SECS_INTRO = 3
SECS_OUTRO = 3           # total = 3 + 5*9 + 3 = 51s  (< 60s -> regra de Short mais leve)

BOOK_NAME_MAP = {"Psaumes": "Psaume"}

# 
#  Definicao dos temas: ficheiro, titulo, emoji, hashtag e PALETA (cor por tema)
#  Paleta = (BG_TOP, BG_BOTTOM, ACCENT, ACCENT_BRIGHT, WHITE, SIL)
# 
THEMES = {
    "protection": dict(
        file="protection_curated.json", title="La protection de Dieu",
        lines=["La protection", "de Dieu"], emoji="\U0001f6e1\ufe0f", tag="Protection",
        palette=((30, 12, 16), (16, 6, 9), (196, 112, 124), (216, 140, 150), (245, 238, 235), (150, 110, 118))),
    "paix": dict(
        file="paix_curated.json", title="La paix de Dieu",
        lines=["La paix", "de Dieu"], emoji="\U0001f54a\ufe0f", tag="Paix",
        palette=((8, 30, 28), (4, 16, 15), (116, 190, 178), (150, 215, 205), (235, 250, 248), (110, 160, 155))),
    "amour": dict(
        file="amour_curated.json", title="L'amour de Dieu",
        lines=["L'amour", "de Dieu"], emoji="\u2764\ufe0f", tag="Amour",
        palette=((32, 12, 18), (18, 6, 10), (218, 140, 156), (235, 165, 180), (250, 238, 240), (160, 115, 128))),
    "esperance": dict(
        file="esperance_curated.json", title="L'esp\u00e9rance en Dieu",
        lines=["L'esp\u00e9rance", "en Dieu"], emoji="\U0001f305", tag="Esp\u00e9rance",
        palette=((10, 28, 18), (5, 16, 10), (150, 200, 150), (180, 220, 175), (240, 248, 238), (120, 160, 125))),
    "priere": dict(
        file="priere_curated.json", title="La pri\u00e8re",
        lines=["La pri\u00e8re", ""], emoji="\U0001f64f", tag="Pri\u00e8re",
        palette=((24, 12, 40), (12, 6, 24), (178, 146, 210), (200, 175, 228), (245, 240, 250), (145, 125, 170))),
    "promesses": dict(
        file="promesses_curated.json", title="Les promesses de Dieu",
        lines=["Les promesses", "de Dieu"], emoji="\U0001f33f", tag="Promesses",
        palette=((8, 26, 18), (4, 14, 10), (120, 184, 142), (150, 205, 165), (238, 248, 240), (110, 150, 125))),
    "sagesse": dict(
        file="proverbes_curated.json", title="La sagesse de la Parole",
        lines=["La sagesse", "de la Parole"], emoji="\U0001f4a1", tag="Sagesse",
        palette=((28, 20, 8), (16, 11, 4), (212, 175, 90), (232, 196, 120), (245, 240, 228), (160, 140, 100))),
    "jesus": dict(
        file="jesus_curated.json", title="Les paroles de J\u00e9sus",
        lines=["Les paroles", "de J\u00e9sus"], emoji="\u271d\ufe0f", tag="J\u00e9sus",
        palette=((10, 16, 42), (5, 9, 24), (150, 180, 225), (180, 205, 240), (240, 244, 252), (130, 150, 185))),
    "psaumes": dict(
        file="psaumes_curated.json", title="M\u00e9ditation des Psaumes",
        lines=["M\u00e9ditation", "des Psaumes"], emoji="\U0001f3b5", tag="Psaumes",
        palette=((8, 14, 38), (4, 8, 24), (160, 190, 220), (185, 210, 235), (240, 245, 255), (120, 150, 180))),
    "propheties": dict(
        file="propheties_curated.json", title="Les proph\u00e9ties de la Parole",
        lines=["Les proph\u00e9ties", "de la Parole"], emoji="\U0001f4ef", tag="Proph\u00e9ties",
        palette=((20, 8, 34), (10, 4, 20), (170, 130, 200), (195, 160, 222), (244, 238, 250), (140, 115, 165))),
    "guerison": dict(
        file="guerison_curated.json", title="La gu\u00e9rison de Dieu",
        lines=["La gu\u00e9rison", "de Dieu"], emoji="\U0001f49a", tag="Gu\u00e9rison",
        palette=((6, 26, 30), (3, 14, 17), (120, 195, 200), (155, 222, 225), (236, 249, 250), (110, 158, 162))),
    "peur": dict(
        file="peur_curated.json", title="Face \u00e0 la peur et l'angoisse",
        lines=["Face \u00e0 la peur", "et l'angoisse"], emoji="\U0001f499", tag="Encouragement",
        palette=((14, 20, 30), (7, 11, 17), (140, 175, 200), (170, 205, 225), (236, 242, 248), (115, 145, 170))),
    "pardon": dict(
        file="pardon_curated.json", title="Le pardon de Dieu",
        lines=["Le pardon", "de Dieu"], emoji="\U0001f90d", tag="Pardon",
        palette=((26, 20, 30), (14, 10, 17), (200, 170, 200), (225, 200, 225), (248, 242, 248), (155, 130, 155))),
    "deuil": dict(
        file="deuil_curated.json", title="Le r\u00e9confort dans le deuil",
        lines=["Le r\u00e9confort", "dans le deuil"], emoji="\U0001f56f\ufe0f", tag="R\u00e9confort",
        palette=((18, 18, 28), (9, 9, 15), (150, 160, 195), (180, 190, 215), (238, 240, 248), (118, 128, 160))),
    "confiance": dict(
        file="confiance_curated.json", title="La confiance en Dieu",
        lines=["La confiance", "en Dieu"], emoji="\u2693", tag="Confiance",
        palette=((12, 16, 32), (6, 9, 18), (140, 160, 210), (170, 190, 228), (236, 240, 250), (115, 135, 180))),
    "force": dict(
        file="force_curated.json", title="La force et le courage",
        lines=["La force", "et le courage"], emoji="\U0001f981", tag="Force",
        palette=((30, 18, 8), (17, 10, 4), (214, 150, 90), (234, 178, 120), (246, 238, 228), (165, 130, 95))),
    "gratitude": dict(
        file="gratitude_curated.json", title="La gratitude",
        lines=["La gratitude", ""], emoji="\U0001f64c", tag="Louange",
        palette=((28, 22, 6), (16, 12, 3), (220, 190, 100), (238, 210, 135), (248, 244, 228), (168, 148, 105))),
    "combat": dict(
        file="combat_curated.json", title="Le combat spirituel",
        lines=["Le combat", "spirituel"], emoji="\u2694\ufe0f", tag="CombatSpirituel",
        palette=((28, 10, 12), (15, 5, 6), (200, 90, 90), (225, 120, 120), (245, 232, 232), (160, 95, 98))),
    "solitude": dict(
        file="solitude_curated.json", title="La pr\u00e9sence de Dieu",
        lines=["La pr\u00e9sence", "de Dieu"], emoji="\U0001f463", tag="Pr\u00e9sence",
        palette=((26, 22, 16), (14, 12, 8), (200, 180, 150), (222, 205, 178), (246, 242, 234), (160, 148, 125))),
    "famille": dict(
        file="famille_curated.json", title="La famille selon Dieu",
        lines=["La famille", "selon Dieu"], emoji="\U0001f3e1", tag="Famille",
        palette=((28, 20, 12), (16, 11, 6), (210, 165, 120), (230, 190, 150), (246, 240, 230), (165, 135, 108))),
}

# Ordre de rotation automatique (un theme par jour. Edite a vontade "depois vou alimentando".
ROTATION = ["protection", "paix", "peur", "esperance", "confiance", "amour", "pardon", "guerison", "deuil", "solitude", "priere", "gratitude", "force", "combat", "promesses", "famille", "sagesse", "jesus", "psaumes", "propheties"]

# Themes ayant une page dediee sur labible.app/versets/{theme}. Les 4 restants
# (sagesse, jesus, psaumes, propheties) n'ont pas de page thematique equivalente ;
# pour ceux-la, _theme_url() renvoie plutot le chapitre du premier verset.
THEMES_WITH_VERSETS_PAGE = {
    "protection", "paix", "amour", "esperance", "priere", "promesses",
    "guerison", "peur", "pardon", "deuil", "confiance", "force",
    "famille", "gratitude", "combat", "solitude",
}


def _theme_url(theme_key, verses):
    if theme_key in THEMES_WITH_VERSETS_PAGE:
        return f"{APP_URL}/versets/{theme_key}"
    first_ref = verses[0][0] if verses else ""
    return parse_ref_to_chapter_url(first_ref)


# 
#  Carregar versiculos de um tema
# 
_BIBLE_IDX = None

def _bible_index():
    global _BIBLE_IDX
    if _BIBLE_IDX is None:
        data = load_json(BIBLE_FILE)
        idx = {}
        for v in data["verses"]:
            idx.setdefault(v["book_name"], {}).setdefault(int(v["chapter"]), {})[int(v["verse"])] = v["text"]
        _BIBLE_IDX = idx
    return _BIBLE_IDX


def _verse_text(book, ch, vs):
    """Texto limpo de um vers\u00edculo ou intervalo (junta vs)."""
    idx = _bible_index()
    bk = BOOK_NAME_MAP.get(book, book)
    if bk not in idx:
        # fallback insensivel a grafia
        for k in idx:
            if k.lower() == bk.lower():
                bk = k
                break
    parts = [clean_text(strip_rubric(idx[bk][int(ch)][int(x)])) for x in vs]
    return " ".join(parts).strip()


def _ref_label(book, ch, vs):
    if len(vs) == 1:
        return f"{book} {ch}:{vs[0]}"
    return f"{book} {ch}:{vs[0]}-{vs[-1]}"


def load_theme_verses(theme_key, n, offset):
    """Devolve (total_entradas, [(ref, texto), ...]) \u2014 n vers\u00edculos a partir de offset, ciclando."""
    entries = load_json(THEMES[theme_key]["file"])
    total = len(entries)
    out = []
    for i in range(n):
        e = entries[(offset + i) % total]
        book, ch = e[0], e[1]
        vs = e[2:] if len(e) > 2 else [1]
        out.append((_ref_label(book, ch, vs), _verse_text(book, ch, vs)))
    return total, out


# 
#  Render do video
# 
def _distinct_safe_tracks():
    """Junta as faixas das duas pastas e remove duplicados por CONTEUDO (md5),
    para que copias com nomes diferentes (x, x_1, x_2...) contem como uma so."""
    tracks = []
    for folder in ("music_meditation",):
        if not os.path.isdir(folder):
            continue
        tracks += [os.path.join(folder, f) for f in os.listdir(folder)
                   if f.lower().endswith((".mp3", ".m4a", ".ogg", ".wav"))]
    seen, uniq = set(), []
    for p in sorted(set(tracks)):
        try:
            with open(p, "rb") as fh:
                h = hashlib.md5(fh.read()).hexdigest()
        except Exception:
            h = p
        if h in seen:
            continue
        seen.add(h)
        uniq.append(p)
    return uniq


def pick_music_varied(progress):
    """Toca TODAS as faixas distintas antes de repetir (saco baralhado).
    Faixas apagadas sao ignoradas; faixas novas entram JA no ciclo atual."""
    pool = _distinct_safe_tracks()
    if not pool:
        print("\u26a0\ufe0f  Nenhuma faixa de musica encontrada \u2014 video sem musica.")
        return None
    pset = set(pool)
    played = [t for t in progress.get("music_played", []) if t in pset]
    bag = [t for t in progress.get("music_bag", []) if t in pset]
    known = set(played) | set(bag)
    new = [t for t in pool if t not in known]
    if new:
        bag += new
        random.shuffle(bag)
    if not bag:
        bag = pool[:]
        random.shuffle(bag)
        played = []
        last = progress.get("last_music")
        if last and len(bag) > 1 and bag[0] == last:
            bag.append(bag.pop(0))
    choice = bag.pop(0)
    played.append(choice)
    progress["music_bag"] = bag
    progress["music_played"] = played
    progress["last_music"] = choice
    print(f"\U0001f3b5 Musica (tematico): {choice}  [{len(pool)} distintas; restam {len(bag)} no ciclo]")
    return choice


def make_thematic_video(theme_key, verses, music):
    th = THEMES[theme_key]
    BG_TOP, BG_BOTTOM, ACCENT, ACCENT_BRIGHT, WHITE, SIL = th["palette"]
    n = len(verses)
    TOTAL = FPS * (SECS_INTRO + n * SECS_PER_VERSE + SECS_OUTRO)

    BORDER = 80
    CARD_PAD = 120
    MAX_TW = W - BORDER * 2 - CARD_PAD * 2
    max_text_h = int((H - BORDER * 2) * 0.55)

    # Pre-calculo de layout por versiculo
    tmp = Image.new("RGB", (10, 10))
    d_tmp = ImageDraw.Draw(tmp)
    layouts = []
    for ref, text in verses:
        text_q = f"\u00ab {text.rstrip('.')} \u00bb"
        fv, lines, lh = autosize_font(d_tmp, text_q, MAX_TW, max_text_h)
        layouts.append((ref, fv, lines, lh))

    f_brand    = ImageFont.truetype(FONT_SANS, 34)
    f_title    = ImageFont.truetype(FONT_SERIF_BOLD, 100)
    f_sub      = ImageFont.truetype(FONT_SERIF, 42)
    f_ref      = ImageFont.truetype(FONT_SERIF_BOLD, 40)
    f_lsg      = ImageFont.truetype(FONT_SERIF, 28)
    f_wm       = ImageFont.truetype(FONT_SANS, 32)
    f_outro    = ImageFont.truetype(FONT_SERIF_BOLD, 110)
    f_outrosub = ImageFont.truetype(FONT_SERIF, 38)

    os.makedirs("frames", exist_ok=True)

    def lerp(base, target, a, k=1.0):
        return tuple(int(base[i] + (target[i] - base[i]) * a * k) for i in range(3))

    for f in range(TOTAL):
        s = f / FPS
        img = gradient_bg(W, H, BG_TOP, BG_BOTTOM)
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle(
            [BORDER, BORDER, W - BORDER, H - BORDER],
            radius=26, outline=tuple(int(c * 0.7) for c in ACCENT), width=2)

        # ---------- INTRO ----------
        if s < SECS_INTRO:
            if s < 1.0:
                a = ease(s / 1.0)
            elif s > SECS_INTRO - 1.0:
                a = ease((SECS_INTRO - s) / 1.0)
            else:
                a = 1.0
            brand = "LaBible.app"
            bw = draw.textlength(brand, font=f_brand)
            draw.text(((W - bw) / 2, H // 2 - 230), brand, font=f_brand, fill=lerp(BG_TOP, SIL, a, 0.9))
            lines = [l for l in th["lines"] if l]
            ty = H // 2 - 110
            for ln in lines:
                lw = draw.textlength(ln, font=f_title)
                draw.text(((W - lw) / 2, ty), ln, font=f_title, fill=lerp(BG_TOP, ACCENT_BRIGHT, a))
                ty += 118
            sub = "Versets bibliques \u00b7 LSG 1910"
            sw = draw.textlength(sub, font=f_sub)
            draw.line([((W - 460) // 2, ty + 20), ((W + 460) // 2, ty + 20)], fill=lerp(BG_TOP, SIL, a, 0.8), width=1)
            draw.text(((W - sw) / 2, ty + 40), sub, font=f_sub, fill=lerp(BG_TOP, SIL, a, 0.85))

        # ---------- VERSICULOS ----------
        elif s < SECS_INTRO + n * SECS_PER_VERSE:
            vs_s = s - SECS_INTRO
            vi = min(int(vs_s / SECS_PER_VERSE), n - 1)
            local = vs_s - vi * SECS_PER_VERSE
            if local < FADE_DURATION:
                a = ease(local / FADE_DURATION)
            elif local > SECS_PER_VERSE - FADE_DURATION:
                a = ease((SECS_PER_VERSE - local) / FADE_DURATION)
            else:
                a = 1.0

            ref, fv, lines, lh = layouts[vi]
            total_h = lh * len(lines)
            ty = BORDER + (H - BORDER * 2) // 2 - total_h // 2
            col_text = lerp(BG_TOP, WHITE, a)
            col_shadow = tuple(int(BG_TOP[i] * (1 - a * 0.5)) for i in range(3))
            for line in lines:
                lw = draw.textlength(line, font=fv)
                x = (W - lw) // 2
                draw.text((x + 2, ty + 2), line, font=fv, fill=col_shadow)
                draw.text((x, ty), line, font=fv, fill=col_text)
                ty += lh

            # Rodape: divisoria + referencia + LSG (esq.)  marca (dir.)
            col_acc = lerp(BG_TOP, ACCENT, a, 0.95)
            lx = BORDER + CARD_PAD
            draw.line([lx, H - BORDER - 150, lx + 230, H - BORDER - 150], fill=col_acc, width=2)
            draw.text((lx, H - BORDER - 128), ref, font=f_ref, fill=col_acc)
            draw.text((lx, H - BORDER - 78), "LSG 1910", font=f_lsg, fill=lerp(BG_TOP, SIL, a, 0.9))
            ww = draw.textlength(WATERMARK, font=f_wm)
            draw.text((W - BORDER - CARD_PAD - ww, H - BORDER - 92), WATERMARK, font=f_wm, fill=col_acc)

        # ---------- OUTRO ----------
        else:
            o_s = s - SECS_INTRO - n * SECS_PER_VERSE
            a = ease(o_s / 1.0) if o_s < 1.0 else 1.0
            msg = "Lisez la Bible compl\u00e8te gratuitement"
            mw = draw.textlength(msg, font=f_sub)
            draw.text(((W - mw) / 2, H // 2 - 130), msg, font=f_sub, fill=lerp(BG_TOP, SIL, a, 0.85))
            app = "LaBible.app"
            aw = draw.textlength(app, font=f_outro)
            draw.text(((W - aw) / 2 + 3, H // 2 - 30 + 3), app, font=f_outro, fill=(0, 0, 0))
            draw.text(((W - aw) / 2, H // 2 - 30), app, font=f_outro, fill=lerp(BG_TOP, ACCENT_BRIGHT, a))
            sub2 = "Gratuit \u00b7 Sans publicit\u00e9 \u00b7 LSG 1910"
            s2w = draw.textlength(sub2, font=f_outrosub)
            draw.text(((W - s2w) / 2, H // 2 + 110), sub2, font=f_outrosub, fill=lerp(BG_TOP, SIL, a, 0.8))

        img.save(f"frames/frame_{f:04d}.png")

    out_path = f"meditation_thematique_{theme_key}.mp4"
    dur = SECS_INTRO + n * SECS_PER_VERSE + SECS_OUTRO
    print(f"\u23f1\ufe0f  Dura\u00e7\u00e3o: {dur}s ({dur/60:.1f} min)")

    music = music   # faixa escolhida em main() (aleatoria, evita repeticoes)
    if music:
        subprocess.run([
            'ffmpeg', '-framerate', str(FPS), '-i', 'frames/frame_%04d.png',
            '-stream_loop', '-1', '-i', music,
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20',
            '-c:a', 'aac', '-b:a', '192k', '-af', 'volume=0.5',
            '-shortest', out_path, '-y',
        ], capture_output=True)
    else:
        subprocess.run([
            'ffmpeg', '-framerate', str(FPS), '-i', 'frames/frame_%04d.png',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', out_path, '-y',
        ], capture_output=True)

    shutil.rmtree("frames", ignore_errors=True)
    print(f"\u2705 V\u00eddeo: {out_path}")
    return out_path


# 
#  Publicacao
# 
def _refs_line(verses):
    return " \u00b7 ".join(ref for ref, _ in verses)


def post_to_telegram(video_path, theme_key, verses):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHANNEL:
        print("\u26a0\ufe0f  Telegram credentials ausentes.")
        return
    th = THEMES[theme_key]
    theme_url = _theme_url(theme_key, verses)
    caption = (
        f"{th['emoji']} <b>{th['title']}</b>\n"
        f"Bible Louis Segond 1910\n\n"
        f"{_refs_line(verses)}\n\n"
        f"Prenez un moment pour m\u00e9diter la Parole. \U0001f64f\n\n"
        f"\U0001f4d6 {theme_url}\n\n"
        f"#LaBibleApp #{th['tag']} #M\u00e9ditation #LSG1910"
    )
    reply_markup = json.dumps({"inline_keyboard": [[
        {"text": "\U0001f4d6 Lire dans LaBible.app", "url": "https://t.me/BIBLE_APP_BOT/labible"}
    ]]})
    try:
        with open(video_path, "rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo",
                data={"chat_id": TELEGRAM_CHANNEL, "caption": caption,
                      "parse_mode": "HTML", "disable_web_page_preview": True,
                      "reply_markup": reply_markup},
                files={"video": f}, timeout=180)
        print("\u2705 Telegram publi\u00e9" if r.status_code == 200 else f"\u274c Telegram ({r.status_code}): {r.text[:200]}")
    except Exception as e:
        print(f"\u274c Telegram: {e}")


def post_to_facebook(video_path, theme_key, verses):
    if not FB_PAGE_TOKEN:
        print("\u26a0\ufe0f  FB_PAGE_TOKEN ausente.")
        return
    th = THEMES[theme_key]
    theme_url = _theme_url(theme_key, verses)
    desc = (
        f"{th['emoji']} {th['title']}\n"
        f"Bible Louis Segond 1910\n\n"
        f"{_refs_line(verses)}\n\n"
        f"Prenez un moment pour m\u00e9diter la Parole de Dieu. \U0001f64f\n\n"
        f"\U0001f4d6 D\u00e9couvrez tous les versets sur ce th\u00e8me \u2192 {theme_url}\n\n"
        f"#Bible #{th['tag']} #M\u00e9ditation #LSG1910 #ParoleDeDieu #Foi"
    )
    try:
        with open(video_path, "rb") as f:
            r = requests.post(
                f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/videos",
                data={"title": f"{th['title']} | LSG1910",
                      "description": desc, "access_token": FB_PAGE_TOKEN},
                files={"source": f}, timeout=300)
        print(f"\u2705 Facebook publi\u00e9 \u2014 {r.json().get('id')}" if r.status_code == 200 else f"\u274c Facebook ({r.status_code}): {r.text[:200]}")
    except Exception as e:
        print(f"\u274c Facebook: {e}")


def upload_to_youtube(video_path, theme_key, verses):
    if not YT_CLIENT_ID or not YT_CLIENT_SECRET or not YT_REFRESH_TOKEN:
        print("\u26a0\ufe0f  Credentials YouTube ausentes.")
        return None
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.auth.transport.requests import Request

    creds = Credentials(
        token=None, refresh_token=YT_REFRESH_TOKEN, client_id=YT_CLIENT_ID,
        client_secret=YT_CLIENT_SECRET, token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"])
    creds.refresh(Request())
    youtube = build("youtube", "v3", credentials=creds)

    th = THEMES[theme_key]
    title = f"{th['emoji']} {th['title']} \u2014 Versets bibliques (LSG 1910)"
    if len(title) > 100:
        title = title[:97] + "..."

    verses_text = "\n".join(f"{ref} \u2014 {text.rstrip('.')}." for ref, text in verses)
    theme_url = _theme_url(theme_key, verses)
    description = (
        f"{th['emoji']} {th['title']} \u2014 m\u00e9dit\u00e9e \u00e0 travers la Parole.\n"
        f"Bible Louis Segond 1910\n\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
        f"{verses_text}\n\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n\n"
        f"\U0001f4d6 D\u00e9couvrez tous les versets sur ce th\u00e8me : {theme_url}\n"
        f"\U0001f514 Abonnez-vous pour une m\u00e9ditation chaque jour \U0001f64f\n\n"
        f"#Bible #{th['tag']} #M\u00e9ditation #LSG1910 #ParoleDeDieu "
        f"#Foi #Pri\u00e8re #Chr\u00e9tien #BibleFrancaise"
    )
    if len(description) > 5000:
        description = description[:4997] + "..."

    body = {
        "snippet": {
            "title": title, "description": description,
            "tags": ["Bible", th["tag"], "M\u00e9ditation", "LSG1910", "ParoleDeDieu",
                     "Foi", "Pri\u00e8re", "Chr\u00e9tien", "BibleFrancaise"],
            "categoryId": "22",
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=1024 * 1024)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  \u23f3 Upload: {int(status.progress() * 100)}%")
    vid = response.get("id")
    print(f"\u2705 YouTube: https://youtube.com/watch?v={vid}")

    # Vignette : une video longue affiche partout la vignette definie.
    try:
        thumb = make_thumbnail(th["title"], subtitle="Versets bibliques \u2014 LSG 1910",
                               palette=th["palette"], out="thumb_theme.png")
        youtube.thumbnails().set(
            videoId=vid,
            media_body=MediaFileUpload(thumb, mimetype="image/png"),
        ).execute()
        print("\u2705 Vignette YouTube definie")
    except Exception as e:
        print(f"\u26a0\ufe0f  Vignette non definie : {str(e)[:200]}")

    return vid


# 
#  Main
# 
def main():
    args = sys.argv[1:]
    progress = load_json(PROGRESS_FILE) if os.path.exists(PROGRESS_FILE) else {}
    offsets = progress.get("offsets", {})
    theme_index = progress.get("theme_index", 0)

    if args and args[0] in THEMES:
        # Modo manual: tema indicado (e offset opcional)
        theme_key = args[0]
        offset = int(args[1]) if len(args) >= 2 and args[1].isdigit() else offsets.get(theme_key, 0)
    else:
        # Modo automatico: rotacao de temas
        theme_key = ROTATION[theme_index % len(ROTATION)]
        offset = offsets.get(theme_key, 0)
        theme_index = (theme_index + 1) % len(ROTATION)

    print(f"\U0001f3ac M\u00e9ditation th\u00e9matique \u2014 {THEMES[theme_key]['title']} (offset {offset})")

    total, verses = load_theme_verses(theme_key, THEMATIC_VERSES, offset)
    for ref, _ in verses:
        print(f"  \u2022 {ref}")

    music = pick_music_varied(progress)
    video_path = make_thematic_video(theme_key, verses, music)

    upload_to_youtube(video_path, theme_key, verses)
    post_to_telegram(video_path, theme_key, verses)
    post_to_facebook(video_path, theme_key, verses)
    theme_url = _theme_url(theme_key, verses)
    # Instagram (Reel) - agora que e vertical 9:16, encaixa perfeitamente
    post_reel_to_instagram(
        video_path,
        THEMES[theme_key]["title"],
        verses[0][1] if verses else "",
        THEMES[theme_key],
        theme_key,
        link_override=theme_url,
    )
    post_reel_to_threads(
        video_path,
        THEMES[theme_key]["title"],
        verses[0][1] if verses else "",
        THEMES[theme_key],
        theme_key,
        link_override=theme_url,
    )

    # Atualiza progresso
    offsets[theme_key] = (offset + THEMATIC_VERSES) % max(total, 1)
    progress["offsets"] = offsets
    progress["theme_index"] = theme_index
    save_json(PROGRESS_FILE, progress)

    print("\u2705 Termin\u00e9 (m\u00e9ditation th\u00e9matique).")


if __name__ == "__main__":
    main()