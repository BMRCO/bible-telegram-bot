"""
thematic_meditation.py
======================
Gera vídeo horizontal 1920×1080 de meditação TEMÁTICA (7 versículos sobre um tema),
no mesmo estilo das meditações de Salmos, mas com COR POR TEMA.
Publica em YouTube + Facebook + Telegram.

Rotação automática: a cada execução, avança um tema (protection → paix → … ) e
puxa os 7 versículos seguintes desse tema (cicla por todos com o tempo).

Uso:
    python thematic_meditation.py                 → tema seguinte (rotação automática)
    python thematic_meditation.py protection      → tema específico (avança o seu offset)
    python thematic_meditation.py paix 0          → tema 'paix' a começar no índice 0

Estado salvo em: progress_thematic.json
"""

import os
import sys
import json
import subprocess
import shutil

import requests
from PIL import Image, ImageDraw, ImageFont

# Reutiliza utilitários do bot
from bot import (
    load_json, save_json, clean_text, strip_rubric,
    BIBLE_FILE, APP_URL, WATERMARK,
    FONT_SERIF, FONT_SERIF_BOLD, FONT_SANS,
)
# Reutiliza helpers de render + música das meditações de Salmos
from psaume_meditation import (
    ease, gradient_bg, wrap, autosize_font, pick_safe_music,
    W, H, FPS, SECS_INTRO, SECS_OUTRO, FADE_DURATION,
)

# Credenciais (mesmas secrets do meditation.yml)
YT_CLIENT_ID     = os.environ.get("YOUTUBE_CLIENT_ID", "")
YT_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "")
FB_PAGE_ID       = os.environ.get("FB_PAGE_ID", "1018605031335601")
FB_PAGE_TOKEN    = os.environ.get("FB_PAGE_TOKEN", "")

PROGRESS_FILE   = "progress_thematic.json"
THEMATIC_VERSES = 7      # versículos por vídeo
SECS_PER_VERSE  = 11     # ritmo de meditação

BOOK_NAME_MAP = {"Psaumes": "Psaume"}

# ─────────────────────────────────────────────────────────────────────────────
#  Definição dos temas: ficheiro, título, emoji, hashtag e PALETA (cor por tema)
#  Paleta = (BG_TOP, BG_BOTTOM, ACCENT, ACCENT_BRIGHT, WHITE, SIL)
# ─────────────────────────────────────────────────────────────────────────────
THEMES = {
    "protection": dict(
        file="protection_curated.json", title="La protection de Dieu",
        lines=["La protection", "de Dieu"], emoji="🛡️", tag="Protection",
        palette=((30, 12, 16), (16, 6, 9), (196, 112, 124), (216, 140, 150), (245, 238, 235), (150, 110, 118))),
    "paix": dict(
        file="paix_curated.json", title="La paix de Dieu",
        lines=["La paix", "de Dieu"], emoji="🕊️", tag="Paix",
        palette=((8, 30, 28), (4, 16, 15), (116, 190, 178), (150, 215, 205), (235, 250, 248), (110, 160, 155))),
    "amour": dict(
        file="amour_curated.json", title="L'amour de Dieu",
        lines=["L'amour", "de Dieu"], emoji="❤️", tag="Amour",
        palette=((32, 12, 18), (18, 6, 10), (218, 140, 156), (235, 165, 180), (250, 238, 240), (160, 115, 128))),
    "esperance": dict(
        file="esperance_curated.json", title="L'espérance en Dieu",
        lines=["L'espérance", "en Dieu"], emoji="🌅", tag="Espérance",
        palette=((10, 28, 18), (5, 16, 10), (150, 200, 150), (180, 220, 175), (240, 248, 238), (120, 160, 125))),
    "priere": dict(
        file="priere_curated.json", title="La prière",
        lines=["La prière", ""], emoji="🙏", tag="Prière",
        palette=((24, 12, 40), (12, 6, 24), (178, 146, 210), (200, 175, 228), (245, 240, 250), (145, 125, 170))),
    "promesses": dict(
        file="promesses_curated.json", title="Les promesses de Dieu",
        lines=["Les promesses", "de Dieu"], emoji="🌿", tag="Promesses",
        palette=((8, 26, 18), (4, 14, 10), (120, 184, 142), (150, 205, 165), (238, 248, 240), (110, 150, 125))),
    "sagesse": dict(
        file="proverbes_curated.json", title="La sagesse de la Parole",
        lines=["La sagesse", "de la Parole"], emoji="💡", tag="Sagesse",
        palette=((28, 20, 8), (16, 11, 4), (212, 175, 90), (232, 196, 120), (245, 240, 228), (160, 140, 100))),
    "jesus": dict(
        file="jesus_curated.json", title="Les paroles de Jésus",
        lines=["Les paroles", "de Jésus"], emoji="✝️", tag="Jésus",
        palette=((10, 16, 42), (5, 9, 24), (150, 180, 225), (180, 205, 240), (240, 244, 252), (130, 150, 185))),
    "psaumes": dict(
        file="psaumes_curated.json", title="Méditation des Psaumes",
        lines=["Méditation", "des Psaumes"], emoji="🎵", tag="Psaumes",
        palette=((8, 14, 38), (4, 8, 24), (160, 190, 220), (185, 210, 235), (240, 245, 255), (120, 150, 180))),
    "propheties": dict(
        file="propheties_curated.json", title="Les prophéties de la Parole",
        lines=["Les prophéties", "de la Parole"], emoji="📯", tag="Prophéties",
        palette=((20, 8, 34), (10, 4, 20), (170, 130, 200), (195, 160, 222), (244, 238, 250), (140, 115, 165))),
}

# Ordem de rotação automática (um tema por dia). Edita à vontade — "depois vou alimentando".
ROTATION = ["protection", "paix", "esperance", "amour", "priere", "promesses", "sagesse"]


# ─────────────────────────────────────────────────────────────────────────────
#  Carregar versículos de um tema
# ─────────────────────────────────────────────────────────────────────────────
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
    """Texto limpo de um versículo ou intervalo (junta vs)."""
    idx = _bible_index()
    bk = BOOK_NAME_MAP.get(book, book)
    if bk not in idx:
        # fallback insensível à grafia
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
    """Devolve (total_entradas, [(ref, texto), ...]) — n versículos a partir de offset, ciclando."""
    entries = load_json(THEMES[theme_key]["file"])
    total = len(entries)
    out = []
    for i in range(n):
        e = entries[(offset + i) % total]
        book, ch = e[0], e[1]
        vs = e[2:] if len(e) > 2 else [1]
        out.append((_ref_label(book, ch, vs), _verse_text(book, ch, vs)))
    return total, out


# ─────────────────────────────────────────────────────────────────────────────
#  Render do vídeo
# ─────────────────────────────────────────────────────────────────────────────
def make_thematic_video(theme_key, verses, rot):
    th = THEMES[theme_key]
    BG_TOP, BG_BOTTOM, ACCENT, ACCENT_BRIGHT, WHITE, SIL = th["palette"]
    n = len(verses)
    TOTAL = FPS * (SECS_INTRO + n * SECS_PER_VERSE + SECS_OUTRO)

    BORDER = 80
    CARD_PAD = 120
    MAX_TW = W - BORDER * 2 - CARD_PAD * 2
    max_text_h = int((H - BORDER * 2) * 0.55)

    # Pré-cálculo de layout por versículo
    tmp = Image.new("RGB", (10, 10))
    d_tmp = ImageDraw.Draw(tmp)
    layouts = []
    for ref, text in verses:
        text_q = f"« {text.rstrip('.')} »"
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
            sub = "Versets bibliques · LSG 1910"
            sw = draw.textlength(sub, font=f_sub)
            draw.line([((W - 460) // 2, ty + 20), ((W + 460) // 2, ty + 20)], fill=lerp(BG_TOP, SIL, a, 0.8), width=1)
            draw.text(((W - sw) / 2, ty + 40), sub, font=f_sub, fill=lerp(BG_TOP, SIL, a, 0.85))

        # ---------- VERSÍCULOS ----------
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

            # Rodapé: divisória + referência + LSG (esq.) · marca (dir.)
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
            msg = "Lisez la Bible complète gratuitement"
            mw = draw.textlength(msg, font=f_sub)
            draw.text(((W - mw) / 2, H // 2 - 130), msg, font=f_sub, fill=lerp(BG_TOP, SIL, a, 0.85))
            app = "LaBible.app"
            aw = draw.textlength(app, font=f_outro)
            draw.text(((W - aw) / 2 + 3, H // 2 - 30 + 3), app, font=f_outro, fill=(0, 0, 0))
            draw.text(((W - aw) / 2, H // 2 - 30), app, font=f_outro, fill=lerp(BG_TOP, ACCENT_BRIGHT, a))
            sub2 = "Gratuit · Sans publicité · LSG 1910"
            s2w = draw.textlength(sub2, font=f_outrosub)
            draw.text(((W - s2w) / 2, H // 2 + 110), sub2, font=f_outrosub, fill=lerp(BG_TOP, SIL, a, 0.8))

        img.save(f"frames/frame_{f:04d}.png")

    out_path = f"meditation_thematique_{theme_key}.mp4"
    dur = SECS_INTRO + n * SECS_PER_VERSE + SECS_OUTRO
    print(f"⏱️  Duração: {dur}s ({dur/60:.1f} min)")

    music = pick_safe_music(rot + 1)   # rotação de música (reaproveita lógica anti-Content-ID)
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
    print(f"✅ Vídeo: {out_path}")
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
#  Publicação
# ─────────────────────────────────────────────────────────────────────────────
def _refs_line(verses):
    return " · ".join(ref for ref, _ in verses)


def post_to_telegram(video_path, theme_key, verses):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHANNEL:
        print("⚠️  Telegram credentials ausentes.")
        return
    th = THEMES[theme_key]
    caption = (
        f"{th['emoji']} <b>{th['title']}</b>\n"
        f"Bible Louis Segond 1910\n\n"
        f"{_refs_line(verses)}\n\n"
        f"Prenez un moment pour méditer la Parole. 🙏\n\n"
        f"📖 labible.app\n\n"
        f"#LaBible #{th['tag']} #Méditation #LSG1910"
    )
    reply_markup = json.dumps({"inline_keyboard": [[
        {"text": "📖 Lire dans LaBible.app", "url": "https://t.me/BIBLE_APP_BOT/labible"}
    ]]})
    try:
        with open(video_path, "rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo",
                data={"chat_id": TELEGRAM_CHANNEL, "caption": caption,
                      "parse_mode": "HTML", "disable_web_page_preview": True,
                      "reply_markup": reply_markup},
                files={"video": f}, timeout=180)
        print("✅ Telegram publié" if r.status_code == 200 else f"❌ Telegram ({r.status_code}): {r.text[:200]}")
    except Exception as e:
        print(f"❌ Telegram: {e}")


def post_to_facebook(video_path, theme_key, verses):
    if not FB_PAGE_TOKEN:
        print("⚠️  FB_PAGE_TOKEN ausente.")
        return
    th = THEMES[theme_key]
    desc = (
        f"{th['emoji']} {th['title']}\n"
        f"Bible Louis Segond 1910\n\n"
        f"{_refs_line(verses)}\n\n"
        f"Prenez un moment pour méditer la Parole de Dieu. 🙏\n\n"
        f"📖 Lisez la Bible complète gratuitement → {APP_URL}\n\n"
        f"#Bible #{th['tag']} #Méditation #LSG1910 #ParoleDeDieu #Foi"
    )
    try:
        with open(video_path, "rb") as f:
            r = requests.post(
                f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/videos",
                data={"title": f"{th['title']} | LSG1910",
                      "description": desc, "access_token": FB_PAGE_TOKEN},
                files={"source": f}, timeout=300)
        print(f"✅ Facebook publié — {r.json().get('id')}" if r.status_code == 200 else f"❌ Facebook ({r.status_code}): {r.text[:200]}")
    except Exception as e:
        print(f"❌ Facebook: {e}")


def upload_to_youtube(video_path, theme_key, verses):
    if not YT_CLIENT_ID or not YT_CLIENT_SECRET or not YT_REFRESH_TOKEN:
        print("⚠️  Credentials YouTube ausentes.")
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
    title = f"{th['emoji']} {th['title']} — Versets bibliques (LSG 1910)"
    if len(title) > 100:
        title = title[:97] + "..."

    verses_text = "\n".join(f"{ref} — {text.rstrip('.')}." for ref, text in verses)
    description = (
        f"{th['emoji']} {th['title']} — méditée à travers la Parole.\n"
        f"Bible Louis Segond 1910\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{verses_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📖 Lisez la Bible complète gratuitement → {APP_URL}\n"
        f"🔔 Abonnez-vous pour une méditation chaque jour 🙏\n\n"
        f"#Bible #{th['tag']} #Méditation #LSG1910 #ParoleDeDieu "
        f"#Foi #Prière #Chrétien #BibleFrancaise"
    )
    if len(description) > 5000:
        description = description[:4997] + "..."

    body = {
        "snippet": {
            "title": title, "description": description,
            "tags": ["Bible", th["tag"], "Méditation", "LSG1910", "ParoleDeDieu",
                     "Foi", "Prière", "Chrétien", "BibleFrancaise"],
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
            print(f"  ⏳ Upload: {int(status.progress() * 100)}%")
    vid = response.get("id")
    print(f"✅ YouTube: https://youtube.com/watch?v={vid}")
    return vid


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    progress = load_json(PROGRESS_FILE) if os.path.exists(PROGRESS_FILE) else {}
    offsets = progress.get("offsets", {})
    theme_index = progress.get("theme_index", 0)
    rot = progress.get("rot", 0)

    if args and args[0] in THEMES:
        # Modo manual: tema indicado (e offset opcional)
        theme_key = args[0]
        offset = int(args[1]) if len(args) >= 2 and args[1].isdigit() else offsets.get(theme_key, 0)
    else:
        # Modo automático: rotação de temas
        theme_key = ROTATION[theme_index % len(ROTATION)]
        offset = offsets.get(theme_key, 0)
        theme_index = (theme_index + 1) % len(ROTATION)

    print(f"🎬 Méditation thématique — {THEMES[theme_key]['title']} (offset {offset})")

    total, verses = load_theme_verses(theme_key, THEMATIC_VERSES, offset)
    for ref, _ in verses:
        print(f"  • {ref}")

    video_path = make_thematic_video(theme_key, verses, rot)

    upload_to_youtube(video_path, theme_key, verses)
    post_to_telegram(video_path, theme_key, verses)
    post_to_facebook(video_path, theme_key, verses)

    # Atualiza progresso
    offsets[theme_key] = (offset + THEMATIC_VERSES) % max(total, 1)
    progress["offsets"] = offsets
    progress["theme_index"] = theme_index
    progress["rot"] = rot + 1
    save_json(PROGRESS_FILE, progress)

    print("✅ Terminé (méditation thématique).")


if __name__ == "__main__":
    main()
