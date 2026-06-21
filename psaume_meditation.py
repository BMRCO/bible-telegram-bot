"""
psaume_meditation.py
====================
Gera vídeo horizontal 1920×1080 de meditação completa de um Salmo.
Versículo a versículo com fade lento, música suave de fundo.

Uso:
    python psaume_meditation.py            → Salmo seguinte (progresso automático)
    python psaume_meditation.py 23         → Salmo 23 específico
    python psaume_meditation.py 119 1-22   → Salmo 119 versos 1-22 (para divisão)

Estado salvo em: progress_meditation.json
Temas dos Salmos:  psaumes_themes.json   (tema editorial -> título/caption)
Frase da Parola:   psaumes_titres.json   (frase da LSG -> cartão de abertura)
Ambos opcionais: fallback limpo para "Psaume N" se faltarem.
"""

import os
import sys
import json
import math
import random
import subprocess
import glob
import shutil

import requests
from PIL import Image, ImageDraw, ImageFont

# Reutiliza utilitários do bot
from bot import (
    load_json, save_json, load_verse, clean_text, strip_rubric, is_rubric,
    BIBLE_FILE, APP_URL, WATERMARK,
    FONT_SERIF, FONT_SERIF_BOLD, FONT_SANS,
)

YT_CLIENT_ID      = os.environ.get("YOUTUBE_CLIENT_ID", "")
YT_CLIENT_SECRET  = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YT_REFRESH_TOKEN  = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "")
FB_PAGE_ID       = os.environ.get("FB_PAGE_ID", "1018605031335601")
FB_PAGE_TOKEN    = os.environ.get("FB_PAGE_TOKEN", "")

PROGRESS_FILE = "progress_meditation.json"
THEMES_FILE   = "psaumes_themes.json"   # tema editorial (título/caption)
TITLES_FILE   = "psaumes_titres.json"   # frase da Parola (cartão)

# Configuração
W, H = 1920, 1080
FPS = 30
SECS_PER_VERSE = 10        # 10s por versículo (meditação lenta)
SECS_INTRO     = 5
SECS_OUTRO     = 5
FADE_DURATION  = 1.0        # 1s de fade in/out por versículo

# Sufixo padronizado do título (igual aos vídeos já publicados)
TITLE_SUFFIX = "Lecture Complète | Bible LSG1910"

# CTA partilhado da série (vouvoiement, sem clickbait)
PSAUME_CTA = "Que ce Psaume vous accompagne aujourd'hui. Partagez-le 🙏"


# ─── Mapas de títulos (tema + frase da Parola) ───
def _load_map(path):
    try:
        if os.path.exists(path):
            return load_json(path)
    except Exception as e:
        print(f"⚠️  {path} indisponível: {e}")
    return {}

PSAUME_THEMES = _load_map(THEMES_FILE)   # {"1": "La Voie des Justes", ...}
PSAUME_TITRES = _load_map(TITLES_FILE)   # {"1": "Heureux l'homme", ...}


def get_psaume_theme(num):
    """Tema editorial do Salmo (título/caption), ou None."""
    return PSAUME_THEMES.get(str(num)) or None


def get_psaume_titre(num):
    """Frase da Parola (cartão de abertura), ou None."""
    return PSAUME_TITRES.get(str(num)) or None


# Divisão do Salmo 119
PSAUME_119_PARTS = [
    (1, 22), (23, 44), (45, 66), (67, 88),
    (89, 110), (111, 132), (133, 154), (155, 176),
]

# Leque de 4 paletas serenas para Salmos — rotação por número (nunca 2 seguidas iguais)
# Cada uma: (BG_TOP, BG_BOTTOM, GOLD/accent, GOLD_BRIGHT, WHITE, SIL)
PSAUME_PALETTES = [
    # Bleu nuit
    ((8,14,38),  (4,8,24),   (160,190,220), (185,210,235), (240,245,255), (120,150,180)),
    # Navy + or
    ((10,16,42), (5,9,24),   (212,175,55),  (232,196,88),  (240,238,230), (150,160,180)),
    # Pourpre
    ((24,10,40), (14,5,26),  (190,160,210), (210,180,228), (245,240,250), (150,135,175)),
    # Teal
    ((6,28,30),  (3,16,18),  (130,200,195), (155,215,210), (235,250,248), (110,165,160)),
]


def get_palette(num):
    """Rotação por número do Salmo — garante variedade."""
    idx = (num - 1) % len(PSAUME_PALETTES)
    return PSAUME_PALETTES[idx]


def is_safe_music(path):
    """
    Filtro anti-Content-ID leve. Rejeita apenas nomes com aspeto de
    'título de vídeo YouTube' (espaços ou parênteses), p.ex.
    'Christian Background Music (Heavens...).mp3', que costumam apanhar
    reclamação. As maiúsculas são permitidas — muitos ficheiros Pixabay
    legítimos têm maiúsculas no nome.
    """
    stem = os.path.splitext(os.path.basename(path))[0]
    return True  # filtro por nome desativado: todas as faixas royalty-free sao aceites


def pick_safe_music(num):
    """Devolve a faixa a usar (rotação por nº), juntando TODAS as faixas das
    duas pastas de música (insensível a maiúsculas na extensão) e descartando
    só os nomes suspeitos."""
    all_tracks = []
    for folder in ("music", "music_meditation"):
        if not os.path.isdir(folder):
            continue
        all_tracks += [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith((".mp3", ".m4a", ".ogg", ".wav"))
        ]
    # dedup por CONTEUDO (apanha copias exatas: 'x', 'x_1', 'x_2'... mesmo com nomes diferentes)
    import hashlib
    _seen, _uniq = set(), []
    for _p in sorted(set(all_tracks)):
        try:
            with open(_p, "rb") as _fh:
                _h = hashlib.md5(_fh.read()).hexdigest()
        except Exception:
            _h = _p
        if _h in _seen:
            continue
        _seen.add(_h)
        _uniq.append(_p)
    all_tracks = _uniq
    if not all_tracks:
        print("⚠️  Nenhuma faixa de música encontrada — vídeo sem música.")
        return None
    safe = [t for t in all_tracks if is_safe_music(t)]
    if not safe:
        print("⚠️  Só faixas suspeitas (espaços/parênteses) — uso todas mesmo assim.")
        safe = all_tracks
    idx = (num - 1) % len(safe)
    print(f"🎵 Música: {safe[idx]} ({idx + 1}/{len(safe)} faixas)")
    return safe[idx]


def ease(t):
    t = max(0, min(1, t))
    return t * t * (3 - 2 * t)


def lerp_color(bg, target, a):
    """Interpola bg -> target por alpha a (para fades)."""
    return tuple(int(bg[i] + (target[i] - bg[i]) * a) for i in range(3))


def gradient_bg(W, H, top, bot):
    img = Image.new("RGB", (W, H), top)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (W, y)], fill=c)
    return img


def wrap(draw, text, font, max_w):
    words = text.split()
    if not words:
        return [""]
    lines, current = [], words[0]
    for w in words[1:]:
        if w.startswith('?') or w.startswith('!') or w == '»':
            current = current + '\u00a0' + w
            continue
        test = current + " " + w
        if draw.textlength(test, font=font) <= max_w:
            current = test
        else:
            lines.append(current)
            current = w
    lines.append(current)
    if len(lines) > 1 and lines[-1].strip() == '»':
        lines[-2] = lines[-2] + '\u00a0»'
        lines.pop()
    return lines


def autosize_font(draw, text, max_w, max_h):
    """Tamanho de fonte que cabe no espaço."""
    for size in range(78, 36, -2):
        fv = ImageFont.truetype(FONT_SERIF, size)
        lines = wrap(draw, text, fv, max_w)
        lh = size + 24
        max_line_w = max(draw.textbbox((0, 0), l, font=fv)[2] for l in lines)
        if max_line_w <= max_w and lh * len(lines) <= max_h:
            return fv, lines, lh
    fv = ImageFont.truetype(FONT_SERIF, 36)
    lines = wrap(draw, text, fv, max_w)
    return fv, lines, 60


def fetch_psaume_verses(num, vfrom=None, vto=None):
    """Carrega todos os versículos de um Salmo (ou um intervalo)."""
    data = load_json(BIBLE_FILE)
    verses = []
    for v in data["verses"]:
        if v["book_name"] == "Psaume" and int(v["chapter"]) == num:
            if vfrom is not None and int(v["verse"]) < vfrom:
                continue
            if vto is not None and int(v["verse"]) > vto:
                continue
            verses.append((int(v["verse"]), v["text"]))
    verses.sort(key=lambda x: x[0])
    return verses


def make_meditation_video(num, verses_with_idx, part_label=None):
    """
    Gera vídeo de meditação.
    verses_with_idx: lista de tuplos (verse_num, text)
    part_label: ex. "1-22" se for Salmo 119 dividido
    """
    n_verses = len(verses_with_idx)
    TOTAL = FPS * (SECS_INTRO + n_verses * SECS_PER_VERSE + SECS_OUTRO)

    # Paleta por rotação (número do Salmo)
    BG_TOP, BG_BOTTOM, GOLD, GOLD_BRIGHT, WHITE, SIL = get_palette(num)

    BORDER = 80
    CARD_PAD = 120
    MAX_TW = W - BORDER * 2 - CARD_PAD * 2
    max_text_h = int((H - BORDER * 2) * 0.55)

    # Pre-calcular fonte e linhas para cada versículo (otimização)
    tmp = Image.new("RGB", (10, 10))
    d_tmp = ImageDraw.Draw(tmp)
    verse_layouts = []
    for vnum, vtext in verses_with_idx:
        cleaned = clean_text(strip_rubric(vtext)).rstrip('.')
        text_q = f"« {cleaned} »"
        fv, lines, lh = autosize_font(d_tmp, text_q, MAX_TW, max_text_h)
        verse_layouts.append((vnum, fv, lines, lh))

    f_title     = ImageFont.truetype(FONT_SERIF_BOLD, 88)
    f_theme     = ImageFont.truetype(FONT_SERIF, 50)   # tema editorial (intro)
    f_phrase    = ImageFont.truetype(FONT_SERIF, 40)   # frase da Parola (intro)
    f_sub       = ImageFont.truetype(FONT_SERIF, 42)
    f_subsmall  = ImageFont.truetype(FONT_SERIF, 34)
    f_vnum      = ImageFont.truetype(FONT_SERIF_BOLD, 48)
    f_wm        = ImageFont.truetype(FONT_SANS, 32)
    f_outro     = ImageFont.truetype(FONT_SERIF_BOLD, 110)
    f_outro_sub = ImageFont.truetype(FONT_SERIF, 38)

    os.makedirs("frames", exist_ok=True)

    # ─── Conteúdo do cartão de abertura: número + tema + frase ───
    card_number = f"Psaume {num}"
    theme = get_psaume_theme(num)
    card_theme = theme or ""
    if part_label:
        card_theme = (f"{theme} ({part_label})" if theme else f"({part_label})")
    theme_lines = wrap(d_tmp, card_theme, f_theme, W - BORDER * 2 - 220) if card_theme else []

    phrase = get_psaume_titre(num)
    phrase_lines = wrap(d_tmp, f"« {phrase} »", f_phrase, W - BORDER * 2 - 260) if phrase else []

    for f in range(TOTAL):
        s = f / FPS
        img = gradient_bg(W, H, BG_TOP, BG_BOTTOM)
        draw = ImageDraw.Draw(img)

        # Border discreto
        draw.rounded_rectangle(
            [BORDER, BORDER, W - BORDER, H - BORDER],
            radius=24, outline=tuple(int(c * 0.7) for c in GOLD), width=2,
        )

        # ---------- INTRO ----------
        if s < SECS_INTRO:
            a = ease(s / 1.0) if s < 1.0 else (ease((SECS_INTRO - s) / 1.0) if s > SECS_INTRO - 1.0 else 1.0)
            c_title  = lerp_color(BG_TOP, GOLD_BRIGHT, a)
            c_theme  = lerp_color(BG_TOP, GOLD, a)
            c_phrase = lerp_color(BG_TOP, WHITE, a)
            c_sub    = lerp_color(BG_TOP, SIL, a * 0.8)

            sub = "Bible Louis Segond 1910"
            th_lh, ph_lh = 60, 52

            title_h = draw.textbbox((0, 0), card_number, font=f_title)[3]
            sub_h = draw.textbbox((0, 0), sub, font=f_subsmall)[3]

            block_h = title_h
            if theme_lines:
                block_h += 26 + th_lh * len(theme_lines)
            if phrase_lines:
                block_h += 22 + ph_lh * len(phrase_lines)
            block_h += 46 + sub_h
            y = (H - block_h) // 2

            # Número "Psaume N"
            bb = draw.textbbox((0, 0), card_number, font=f_title)
            draw.text(((W - (bb[2] - bb[0])) // 2, y), card_number, font=f_title, fill=c_title)
            y += title_h

            # Tema editorial (dourado)
            if theme_lines:
                y += 26
                for tl in theme_lines:
                    bbt = draw.textbbox((0, 0), tl, font=f_theme)
                    draw.text(((W - (bbt[2] - bbt[0])) // 2, y), tl, font=f_theme, fill=c_theme)
                    y += th_lh

            # Frase da Parola (branco)
            if phrase_lines:
                y += 22
                for pl in phrase_lines:
                    bbp = draw.textbbox((0, 0), pl, font=f_phrase)
                    draw.text(((W - (bbp[2] - bbp[0])) // 2, y), pl, font=f_phrase, fill=c_phrase)
                    y += ph_lh

            # Divisória + assinatura
            y += 22
            draw.line([((W - 360) // 2, y), ((W + 360) // 2, y)], fill=c_sub, width=1)
            y += 24
            bb2 = draw.textbbox((0, 0), sub, font=f_subsmall)
            draw.text(((W - (bb2[2] - bb2[0])) // 2, y), sub, font=f_subsmall, fill=c_sub)

        # ---------- VERSÍCULOS ----------
        elif s < SECS_INTRO + n_verses * SECS_PER_VERSE:
            verse_s = s - SECS_INTRO
            verse_idx = int(verse_s / SECS_PER_VERSE)
            verse_idx = min(verse_idx, n_verses - 1)
            local_s = verse_s - verse_idx * SECS_PER_VERSE

            # Fade in / hold / fade out
            if local_s < FADE_DURATION:
                a = ease(local_s / FADE_DURATION)
            elif local_s > SECS_PER_VERSE - FADE_DURATION:
                a = ease((SECS_PER_VERSE - local_s) / FADE_DURATION)
            else:
                a = 1.0

            vnum, fv, lines, lh = verse_layouts[verse_idx]

            # Versículo número no canto
            vnum_text = str(vnum)
            color_vnum = lerp_color(BG_TOP, GOLD, a * 0.85)
            draw.text((BORDER + 60, BORDER + 50), vnum_text, font=f_vnum, fill=color_vnum)

            # Texto do versículo centrado
            total_h = lh * len(lines)
            ty = BORDER + (H - BORDER * 2) // 2 - total_h // 2

            color_text = lerp_color(BG_TOP, WHITE, a)
            color_shadow = tuple(int(BG_TOP[i] * (1 - a * 0.5)) for i in range(3))

            for line in lines:
                bb = draw.textbbox((0, 0), line, font=fv)
                tw = bb[2] - bb[0]
                x = (W - tw) // 2
                draw.text((x + 2, ty + 2), line, font=fv, fill=color_shadow)
                draw.text((x, ty), line, font=fv, fill=color_text)
                ty += lh

            # Rodapé: referência + watermark
            color_ref = lerp_color(BG_TOP, GOLD, a * 0.7)
            ref_text = f"Psaume {num}:{vnum}"
            draw.text((BORDER + CARD_PAD, H - BORDER - 70), ref_text, font=f_sub, fill=color_ref)
            wm_bb = draw.textbbox((0, 0), WATERMARK, font=f_wm)
            draw.text(
                (W - BORDER - CARD_PAD - (wm_bb[2] - wm_bb[0]), H - BORDER - 65),
                WATERMARK, font=f_wm, fill=color_ref,
            )

        # ---------- OUTRO ----------
        else:
            outro_s = s - SECS_INTRO - n_verses * SECS_PER_VERSE
            a = ease(outro_s / 1.0) if outro_s < 1.0 else 1.0
            color_app = lerp_color(BG_TOP, GOLD_BRIGHT, a)
            color_sub = lerp_color(BG_TOP, SIL, a * 0.7)

            msg = "Méditez la Parole chaque jour"
            bb = draw.textbbox((0, 0), msg, font=f_sub)
            tw = bb[2] - bb[0]
            draw.text(((W - tw) // 2, H // 2 - 130), msg, font=f_sub, fill=color_sub)

            app = "LaBible.app"
            bb2 = draw.textbbox((0, 0), app, font=f_outro)
            tw2 = bb2[2] - bb2[0]
            draw.text(((W - tw2) // 2 + 3, H // 2 - 30 + 3), app, font=f_outro, fill=(0, 0, 0))
            draw.text(((W - tw2) // 2, H // 2 - 30), app, font=f_outro, fill=color_app)

            sub2 = "Gratuit · Sans publicité · LSG 1910"
            bb3 = draw.textbbox((0, 0), sub2, font=f_outro_sub)
            sw2 = bb3[2] - bb3[0]
            draw.text(((W - sw2) // 2, H // 2 + 110), sub2, font=f_outro_sub, fill=color_sub)

        img.save(f"frames/frame_{f:04d}.png")

    # Música — rotação por número do Salmo (cada Salmo usa uma faixa diferente,
    # nunca duas seguidas iguais quando há ≥2 faixas). A música faz loop
    # automático (-stream_loop -1) para cobrir toda a duração do vídeo, por isso
    # o comprimento de cada faixa não importa.
    output_path = f"meditation_psaume_{num}{'_' + part_label.replace('-', '_') if part_label else ''}.mp4"
    video_duration = SECS_INTRO + n_verses * SECS_PER_VERSE + SECS_OUTRO
    print(f"⏱️  Duração do vídeo: {video_duration}s ({video_duration/60:.1f} min)")

    # Só faixas "seguras" (Pixabay), rotação por nº do Salmo. Ignora ficheiros
    # com nome de título de vídeo do YouTube (risco de reclamação Content ID).
    music_file = pick_safe_music(num)

    if music_file:
        subprocess.run([
            'ffmpeg', '-framerate', str(FPS), '-i', 'frames/frame_%04d.png',
            '-stream_loop', '-1', '-i', music_file,
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20',
            '-c:a', 'aac', '-b:a', '192k',
            '-af', 'volume=0.5',
            '-shortest', output_path, '-y',
        ], capture_output=True)
    else:
        print("⚠️  Sem música disponível")
        subprocess.run([
            'ffmpeg', '-framerate', str(FPS), '-i', 'frames/frame_%04d.png',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20',
            output_path, '-y',
        ], capture_output=True)

    shutil.rmtree("frames", ignore_errors=True)
    print(f"✅ Vídeo: {output_path}")
    return output_path


def _meditation_head(num, part_label=None):
    """Cabeçalho legível p/ captions: 'Psaume N — Thème (part)' com fallback."""
    theme = get_psaume_theme(num)
    head = f"Psaume {num}" + (f" — {theme}" if theme else "")
    if part_label:
        head += f" ({part_label})"
    return head


def _video_title(num, part_label=None):
    """Título YouTube/Facebook: 'Psaume N — Thème (part) | Lecture Complète | Bible LSG1910'."""
    theme = get_psaume_theme(num)
    title = f"Psaume {num}" + (f" — {theme}" if theme else "")
    if part_label:
        title += f" ({part_label})"
    title += f" | {TITLE_SUFFIX}"
    if len(title) > 100:
        title = title[:97] + "..."
    return title


def post_to_telegram(video_path, num, part_label=None):
    """Publica a meditação no canal Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHANNEL:
        print("⚠️  Telegram credentials ausentes.")
        return
    head = _meditation_head(num, part_label)
    caption = (
        f"🎵 <b>{head}</b>\n"
        f"Bible Louis Segond 1910\n\n"
        f"{PSAUME_CTA}\n\n"
        f"📖 labible.app\n\n"
        f"#LaBible #Psaumes #Méditation #LSG1910"
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
                files={"video": f}, timeout=180,
            )
        if r.status_code == 200:
            print("✅ Telegram publié")
        else:
            print(f"❌ Telegram ({r.status_code}): {r.text[:200]}")
    except Exception as e:
        print(f"❌ Telegram: {e}")


def post_to_facebook(video_path, num, part_label=None):
    """Publica a meditação como vídeo na página Facebook."""
    if not FB_PAGE_TOKEN:
        print("⚠️  FB_PAGE_TOKEN ausente.")
        return
    head = _meditation_head(num, part_label)
    desc = (
        f"🎵 {head}\n"
        f"Bible Louis Segond 1910\n\n"
        f"{PSAUME_CTA}\n\n"
        f"📖 Lisez la Bible complète gratuitement → {APP_URL}\n\n"
        f"#Bible #Psaumes #Méditation #LSG1910 #ParoleDeDieu #Foi"
    )
    try:
        with open(video_path, "rb") as f:
            r = requests.post(
                f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/videos",
                data={"title": _video_title(num, part_label),
                      "description": desc, "access_token": FB_PAGE_TOKEN},
                files={"source": f}, timeout=300,
            )
        if r.status_code == 200:
            print(f"✅ Facebook publié — {r.json().get('id')}")
        else:
            print(f"❌ Facebook ({r.status_code}): {r.text[:200]}")
    except Exception as e:
        print(f"❌ Facebook: {e}")


def upload_to_youtube(video_path, num, verses_with_idx, part_label=None):
    """Upload do vídeo para YouTube como vídeo normal (não Short)."""
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
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    creds.refresh(Request())
    youtube = build("youtube", "v3", credentials=creds)

    title = _video_title(num, part_label)

    # Lista de versículos para descrição
    verses_text = "\n".join(
        f"Psaume {num}:{vnum} — {clean_text(strip_rubric(vtext)).rstrip('.')}."
        for vnum, vtext in verses_with_idx
    )

    head = _meditation_head(num, part_label)
    description = (
        f"🎵 Méditation — {head}\n"
        f"Bible Louis Segond 1910\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{verses_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{PSAUME_CTA}\n\n"
        f"📖 Lisez la Bible complète gratuitement → {APP_URL}\n"
        f"🔔 Abonnez-vous pour plus de méditations 🙏\n\n"
        f"#Bible #Psaumes #Méditation #LSG1910 #ParoleDeDieu "
        f"#Foi #Prière #Chrétien #BibleFrancaise #Adoration"
    )
    # YouTube limita descrição a 5000 chars
    if len(description) > 5000:
        description = description[:4997] + "..."

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": [
                "Bible", "Psaumes", "Méditation", "LSG1910",
                "ParoleDeDieu", "Foi", "Prière", "Chrétien", "BibleFrancaise",
            ],
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=1024 * 1024)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  ⏳ Upload: {int(status.progress() * 100)}%")

    video_id = response.get("id")
    print(f"✅ YouTube: https://youtube.com/watch?v={video_id}")
    return video_id


def main():
    # ─── Parse args ───
    args = sys.argv[1:]
    if args:
        # Modo manual: psaume_meditation.py 23  |  psaume_meditation.py 119 1-22
        num = int(args[0])
        if len(args) >= 2 and "-" in args[1]:
            vfrom_str, vto_str = args[1].split("-")
            vfrom, vto = int(vfrom_str), int(vto_str)
            part_label = f"{vfrom}-{vto}"
        else:
            vfrom = vto = None
            part_label = None
    else:
        # Modo automático: usa progress_meditation.json
        if os.path.exists(PROGRESS_FILE):
            progress = load_json(PROGRESS_FILE)
        else:
            progress = {"next_psaume": 1, "psaume_119_part": 0}

        num = progress.get("next_psaume", 1)
        part_label = None
        vfrom = vto = None

        # Caso especial: Psaume 119 dividido
        if num == 119:
            part_idx = progress.get("psaume_119_part", 0)
            if part_idx < len(PSAUME_119_PARTS):
                vfrom, vto = PSAUME_119_PARTS[part_idx]
                part_label = f"{vfrom}-{vto}"
                progress["psaume_119_part"] = part_idx + 1
                if part_idx + 1 >= len(PSAUME_119_PARTS):
                    # Acabou as 8 partes → seguir para 120
                    progress["next_psaume"] = 120
                    progress["psaume_119_part"] = 0
            else:
                progress["next_psaume"] = 120
                progress["psaume_119_part"] = 0
                num = 120
        else:
            progress["next_psaume"] = num + 1
            if progress["next_psaume"] > 150:
                progress["next_psaume"] = 1  # recomeça do início

        save_json(PROGRESS_FILE, progress)

    print(f"🎵 Méditation — {_meditation_head(num, part_label)}")

    # ─── Carregar versículos ───
    verses = fetch_psaume_verses(num, vfrom, vto)
    if not verses:
        print(f"❌ Nenhum versículo encontrado para Psaume {num}")
        sys.exit(1)

    # Remover rubricas demasiado curtas (linhas como "De David")
    filtered = [(vn, vt) for vn, vt in verses if not is_rubric(vt)]
    if filtered:
        verses = filtered

    print(f"📖 {len(verses)} versículos")

    # ─── Gerar vídeo ───
    video_path = make_meditation_video(num, verses, part_label)

    # ─── Upload YouTube ───
    upload_to_youtube(video_path, num, verses, part_label)

    # ─── Telegram + Facebook ───
    post_to_telegram(video_path, num, part_label)
    post_to_facebook(video_path, num, part_label)

    print("✅ Terminé (méditation).")


if __name__ == "__main__":
    main()
