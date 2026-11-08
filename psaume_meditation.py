"""
psaume_meditation.py
====================
Gera vídeo horizontal 1920×1080 de meditação completa de um Salmo.
Versículo a versículo com fade lento, NARRADO (voz neuronal Henri, edge-tts)
e música suave por baixo. Cada versículo fica no ecrã o tempo da sua leitura.

Uso:
    python psaume_meditation.py            → Salmo seguinte (progresso automático)
    python psaume_meditation.py 23         → Salmo 23 específico
    python psaume_meditation.py 119 1-22   → Salmo 119 versos 1-22 (para divisão)
    ESSAI=1 python psaume_meditation.py 23 → gera o vídeo em echantillons/, NÃO publica

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
import asyncio
import time
import wave
import bisect

import numpy as np
import requests
# edge_tts est importe plus bas, seulement quand on synthetise la voix :
# thematic_meditation.py importe ce module sans avoir besoin de la voix,
# et son workflow n'installe pas edge-tts (panne des 2 au 4 novembre 2026).
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

# Reutiliza utilitários do bot
from bot import (
    load_json, save_json, load_verse, clean_text, strip_rubric, is_rubric,
    make_thumbnail,
    telegram_markup, _rotate, TG_CLOSERS, _strip_share_clause,
    BIBLE_FILE, APP_URL, WATERMARK,
    FONT_SERIF, FONT_SERIF_BOLD, FONT_SANS,
    # Alertes de panne : importees de bot.py, pas redefinies ici.
    # bot.py porte aussi socket.setdefaulttimeout(120), applique des
    # l'import — googleapiclient/httplib2 n'a aucun timeout par defaut,
    # et le `while response is None: next_chunk()` plus bas n'a sinon
    # aucun filet.
    signaler_echec, publier, finaliser,
)

YT_CLIENT_ID      = os.environ.get("YOUTUBE_CLIENT_ID", "")
YT_CLIENT_SECRET  = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YT_REFRESH_TOKEN  = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "")
FB_PAGE_ID       = os.environ.get("FB_PAGE_ID", "")
FB_PAGE_TOKEN    = os.environ.get("FB_PAGE_TOKEN", "")

PROGRESS_FILE = "progress_meditation.json"
THEMES_FILE   = "psaumes_themes.json"   # tema editorial (título/caption)
TITLES_FILE   = "psaumes_titres.json"   # frase da Parola (cartão)

ESSAI = os.environ.get("ESSAI", "") == "1"   # gera o vídeo, não publica nada

# Playlist da série narrada (criada pelo bot se não existir).
PLAYLIST_NARREE = "🎙️ Les Psaumes lus à voix haute"
PLAYLIST_DESC = (
    "Les 150 Psaumes lus à voix haute, en entier, dans le texte de la Bible "
    "Louis Segond 1910 (domaine public), sans commentaire ajouté. Un Psaume "
    "chaque jour. Le texte complet est accessible gratuitement, hors ligne et "
    "sans publicité sur LaBible.app."
)

# Linha de tempo do último vídeo gerado (capítulos e legendas do YouTube).
TIMELINE = {}

# Configuração
W, H = 1920, 1080
FPS = 30
SECS_INTRO     = 5          # mínimo: cresce se « Psaume N » demorar mais
SECS_OUTRO     = 5
SECS_VERSE_MIN = 4.0        # um versículo curto fica pelo menos 4 s
FADE_DURATION  = 0.8        # fade in/out por versículo

# ─── Narração ───
# Escolhida por BC a 2 de novembro de 2026 (amostras do Salmo 23) :
# Henri, débito -8 %, tom normal. Remy (multilingue) foi afastado : começa
# em inglês ou espanhol. Gérard e as vozes Piper também foram afastados.
VOIX          = "fr-FR-HenriNeural"
DEBIT_VOIX    = "-8%"
SR            = 24000       # Hz, mono
LEAD          = 0.8         # silêncio antes da voz (o texto aparece primeiro)
TAIL          = 1.4         # silêncio depois da voz, antes do versículo seguinte
VOLUME_MUSIQUE = 0.12       # a música fica por baixo da voz (antes : 0.5 sem voz)

# edge-tts escreve xml:lang='en-US' no SSML. Forçamos o francês (mesmo SSML
# que as amostras aprovadas ; a balise <lang> é recusada pelo serviço).
def _mkssml_fr(tc, escaped_text):
    if isinstance(escaped_text, bytes):
        escaped_text = escaped_text.decode("utf-8")
    return (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='fr-FR'>"
        f"<voice name='{tc.voice}'>"
        f"<prosody pitch='{tc.pitch}' rate='{tc.rate}' volume='{tc.volume}'>"
        f"{escaped_text}"
        "</prosody></voice></speak>"
    )


# Sufixo padronizado do título (igual aos vídeos já publicados)
TITLE_SUFFIX = "Lecture Audio | Bible LSG1910"   # serie narree (2 nov. 2026)

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



def _too_similar(a, b):
    """Le theme editorial et la phrase d'ouverture disent-ils la meme chose ?

    Certains Psaumes ont un theme tire du verset lui-meme : le Psaume 91
    affichait « A l'Ombre du Tres-Haut » puis « Sous l'abri du Tres-Haut »,
    deux fois la meme idee sur la meme carte. 22 Psaumes sur 59 etaient dans
    ce cas. Quand c'est trop proche, on n'en garde qu'un seul.
    """
    import unicodedata as _u

    stop = {"de", "du", "la", "le", "les", "des", "a", "au", "aux", "et",
            "en", "l", "d", "un", "une", "mon", "ma", "ta", "ton", "sa",
            "son", "qui", "que", "est", "je", "tu", "il", "ce", "se"}

    def words(x):
        x = _u.normalize("NFD", (x or "").lower())
        x = "".join(c for c in x if _u.category(c) != "Mn")
        # sans regex : ce module n'importe pas `re`
        x = "".join(c if "a" <= c <= "z" else " " for c in x)
        return {w for w in x.split() if w not in stop}

    wa, wb = words(a), words(b)
    if not wa or not wb:
        return False
    return len(wa & wb) / min(len(wa), len(wb)) >= 0.5


def get_psaume_theme(num):
    """Tema editorial do Salmo (título/caption), ou None."""
    return PSAUME_THEMES.get(str(num)) or None


def get_psaume_titre(num):
    """Frase da Parola (cartão de abertura), ou None."""
    return PSAUME_TITRES.get(str(num)) or None


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


# Pistes ayant deja fait l'objet d'une revendication Content ID sur la chaine.
# Elles restent dans le dossier (les anciennes videos les utilisent deja) mais
# ne sont plus retenues pour les nouvelles publications.
CLAIMED_TRACKS = ("heaven's whisper", "heavens whisper", "flute meditation music 8")


def is_claimed(path):
    name = os.path.basename(path).lower()
    return any(c in name for c in CLAIMED_TRACKS)


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
    for folder in ("music_meditation",):
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
    # ecarter les pistes deja revendiquees (Content ID)
    filtered = [t for t in safe if not is_claimed(t)]
    if filtered:
        skipped = len(safe) - len(filtered)
        if skipped:
            print(f"🚫 {skipped} faixa(s) com reivindicação Content ID ignorada(s).")
        safe = filtered
    else:
        print("⚠️  Todas as faixas estão reivindicadas — uso na mesma.")
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


def texte_a_lire(texte):
    """Entrada da síntese = o texto mostrado no ecrã, com espaços normais.
    O ficheiro bíblico nunca é alterado : só esta cópia em memória."""
    t = texte
    for esp in ("\u00a0", "\u202f", "\u2009", "\u2007", "\u200a"):
        t = t.replace(esp, " ")
    return " ".join(t.split())


async def _tts(texte, chemin):
    import edge_tts
    import edge_tts.communicate as _comm
    _comm.mkssml = _mkssml_fr
    await edge_tts.Communicate(texte, VOIX, rate=DEBIT_VOIX).save(chemin)


def synthese(texte, base):
    """Lê `texte` com a voz escolhida. Devolve um array float32 mono a SR Hz.
    3 tentativas : o serviço da Microsoft falha de vez em quando."""
    mp3, wav = base + ".mp3", base + ".wav"
    derniere = None
    for essai in range(3):
        try:
            asyncio.run(_tts(texte, mp3))
            r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3,
                                "-ar", str(SR), "-ac", "1", "-sample_fmt", "s16", wav],
                               capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"ffmpeg : {r.stderr[-200:]}")
            with wave.open(wav, "rb") as w:
                data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
            if len(data) < SR // 10:
                raise RuntimeError("áudio vazio")
            return data.astype(np.float32) / 32768.0
        except Exception as e:
            derniere = e
            print(f"⚠️  Síntese falhou (tentativa {essai + 1}/3) : {e}")
            time.sleep(5 * (essai + 1))
    raise RuntimeError(f"síntese de voz impossível : {derniere}")


# ─── Spectre de la voix (demande de BC, 5 nov. 2026) ───
# Des barres qui suivent la voix reelle, a partir du centre. Partage avec
# bible_audio.py.
PAS_ENV = 0.01   # une valeur d'enveloppe toutes les 10 ms


def enveloppe_voix(piste, fen=0.06):
    """Volume de la narration (0 a 1) toutes les 10 ms."""
    cs = np.concatenate([[0.0], np.cumsum(piste.astype(np.float64) ** 2)])
    n = int(len(piste) / (SR * PAS_ENV)) + 1
    out = np.zeros(n, dtype=np.float32)
    demi = int(fen / 2 * SR)
    for k in range(n):
        c = int(k * PAS_ENV * SR)
        i0, i1 = max(0, c - demi), min(len(piste), c + demi)
        if i1 > i0:
            out[k] = math.sqrt((cs[i1] - cs[i0]) / (i1 - i0))
    ref = float(np.percentile(out[out > 0], 97)) if np.any(out > 0) else 1.0
    return np.clip(out / max(ref, 1e-6), 0, 1)


_JITTER = [0.55 + 0.45 * random.Random(3 + i).random() for i in range(200)]


def dessiner_spectre(img, env, t, cy, couleur, largeur=560, amp=24, n=44, force=1.0):
    """Barres centrees en (W/2, cy), hauteur selon la voix a l'instant t."""
    VW = img.width
    x0 = (VW - largeur) // 2
    haut = int(amp + 24)
    zone = (x0 - 30, cy - haut, x0 + largeur + 30, cy + haut)
    cal = Image.new("RGB", (zone[2] - zone[0], zone[3] - zone[1]), (0, 0, 0))
    dc = ImageDraw.Draw(cal)
    bw = 6
    gap = (largeur - n * bw) / (n - 1)
    col = tuple(int(c * 0.75 * force) for c in couleur)
    for i in range(n):
        dist = abs(i - (n - 1) / 2) / ((n - 1) / 2)
        k = int((t - dist * 0.15) / PAS_ENV)
        lvl = float(env[k]) if 0 <= k < len(env) else 0.0
        forme = math.sin(math.pi * (i + 0.5) / n) ** 1.1
        h = max(2.5, amp * forme * _JITTER[i] * (0.12 + 0.88 * lvl))
        x = 30 + i * (bw + gap)
        dc.rounded_rectangle([x, haut - h, x + bw, haut + h], radius=3, fill=col)
    morceau = img.crop(zone)
    morceau = ImageChops.add(morceau, cal.filter(ImageFilter.GaussianBlur(6)))
    morceau = ImageChops.add(morceau, cal)
    img.paste(morceau, zone[:2])
    return img


def palette_ciel(num):
    """Couleurs de la video = celles de la vignette du meme Psaume (CIELS)."""
    haut, horizon, soleil, proche, loin = CIELS[(num * 3) % len(CIELS)]
    top = tuple(int(haut[i] * 0.85 + horizon[i] * 0.10) for i in range(3))
    blanc = (250, 246, 238)
    sil = tuple(int(horizon[i] * 0.55 + blanc[i] * 0.45) for i in range(3))
    return top, loin, horizon, soleil, blanc, sil


def make_meditation_video(num, verses_with_idx, part_label=None):
    """
    Gera vídeo de meditação.
    verses_with_idx: lista de tuplos (verse_num, text)
    part_label: ex. "1-22" se for Salmo 119 dividido
    """
    n_verses = len(verses_with_idx)

    # Paleta = a da vignette (ceu do mesmo Salmo), pedido de BC a 5 nov. 2026
    BG_TOP, BG_BOTTOM, GOLD, GOLD_BRIGHT, WHITE, SIL = palette_ciel(num)

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

    # ─── Narração : uma síntese por versículo, para saber quanto dura cada um ───
    os.makedirs("narration", exist_ok=True)
    voix_titre = synthese(f"Psaume {num}.", "narration/titre")
    voix_versets = []
    for i, (vnum, vtext) in enumerate(verses_with_idx):
        lu = texte_a_lire(clean_text(strip_rubric(vtext)))
        voix_versets.append(synthese(lu, f"narration/v{i:03d}"))
        print(f"  🎙️  {i + 1}/{n_verses}", end="\r")
    print()

    # Linha de tempo : intro, depois cada versículo = LEAD + voz + TAIL.
    T_TITRE = 1.0                                   # depois do fade-in do cartão
    intro_secs = max(SECS_INTRO, T_TITRE + len(voix_titre) / SR + 1.5)
    durees = [max(SECS_VERSE_MIN, LEAD + len(a) / SR + TAIL) for a in voix_versets]
    debuts = []
    t = intro_secs
    for d in durees:
        debuts.append(t)
        t += d
    fin_versets = t
    total_secs = fin_versets + SECS_OUTRO
    TOTAL = int(round(total_secs * FPS))

    piste = np.zeros(int(total_secs * SR) + SR, dtype=np.float32)
    def poser(audio, a_secs):
        i0 = int(a_secs * SR)
        piste[i0:i0 + len(audio)] += audio
    poser(voix_titre, T_TITRE)
    for d0, audio in zip(debuts, voix_versets):
        poser(audio, d0 + LEAD)
    piste = piste[:int(total_secs * SR)]
    TIMELINE.clear()
    TIMELINE.update(intro=intro_secs, debuts=debuts, durees=durees,
                    versets=list(verses_with_idx), total=total_secs)
    env_voix = enveloppe_voix(piste)
    narration_wav = "narration/narration.wav"
    with wave.open(narration_wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(piste, -1, 1) * 32767).astype(np.int16).tobytes())

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
    # Eviter de dire deux fois la meme chose sur la carte d'ouverture.
    if phrase and card_theme and _too_similar(card_theme, phrase):
        phrase = None
    phrase_lines = wrap(d_tmp, f"« {phrase} »", f_phrase, W - BORDER * 2 - 260) if phrase else []

    fond = gradient_bg(W, H, BG_TOP, BG_BOTTOM)
    for f in range(TOTAL):
        s = f / FPS
        img = fond.copy()
        draw = ImageDraw.Draw(img)

        # Border discreto
        draw.rounded_rectangle(
            [BORDER, BORDER, W - BORDER, H - BORDER],
            radius=24, outline=tuple(int(c * 0.7) for c in GOLD), width=2,
        )

        # ---------- INTRO ----------
        if s < intro_secs:
            a = ease(s / 1.0) if s < 1.0 else (ease((intro_secs - s) / 1.0) if s > intro_secs - 1.0 else 1.0)
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
        elif s < fin_versets:
            verse_idx = min(bisect.bisect_right(debuts, s) - 1, n_verses - 1)
            local_s = s - debuts[verse_idx]
            duree_v = durees[verse_idx]

            # Fade in / hold / fade out
            if local_s < FADE_DURATION:
                a = ease(local_s / FADE_DURATION)
            elif local_s > duree_v - FADE_DURATION:
                a = ease((duree_v - local_s) / FADE_DURATION)
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
            outro_s = s - fin_versets
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

        # Spectre de la voix, sous le texte ; il s'efface pendant la fin.
        if s < fin_versets + 0.8:
            force = 1.0 if s < fin_versets else max(0.0, 1 - (s - fin_versets) / 0.8)
            dessiner_spectre(img, env_voix, s, H - BORDER - 138, GOLD, force=force)
        img.save(f"frames/frame_{f:05d}.png")

    # Voz + música. A música (rotação por nº do Salmo, em loop) fica por baixo
    # da voz e desaparece nos 3 últimos segundos. A duração é a da narração,
    # que cobre exatamente o vídeo.
    output_path = f"meditation_psaume_{num}{'_' + part_label.replace('-', '_') if part_label else ''}.mp4"
    print(f"⏱️  Duração do vídeo: {total_secs:.0f}s ({total_secs/60:.1f} min)")

    music_file = pick_safe_music(num)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error',
           '-framerate', str(FPS), '-i', 'frames/frame_%05d.png',
           '-i', narration_wav]
    if music_file:
        fondu = max(0.0, total_secs - 3)
        cmd += ['-stream_loop', '-1', '-i', music_file,
                '-filter_complex',
                f"[2:a]volume={VOLUME_MUSIQUE},afade=t=out:st={fondu:.2f}:d=3[m];"
                f"[1:a][m]amix=inputs=2:duration=first:normalize=0[a]",
                '-map', '0:v', '-map', '[a]']
    else:
        print("⚠️  Sem música disponível : só a voz")
        cmd += ['-map', '0:v', '-map', '1:a']
    cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20',
            '-c:a', 'aac', '-b:a', '192k', '-shortest', output_path]
    r = subprocess.run(cmd, capture_output=True, text=True)

    shutil.rmtree("frames", ignore_errors=True)
    shutil.rmtree("narration", ignore_errors=True)
    if r.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError(f"ffmpeg (montagem) : {r.stderr[-300:]}")
    print(f"✅ Vídeo: {output_path}")
    return output_path


# ─── Vignette de la serie narree (style « B », choisi par BC le 3 nov. 2026) ───
# Volontairement differente de la serie muette (cadre, fond uni, texte blanc) :
# un ciel d'aube ou de soir, un soleil sur des collines, une onde sonore qui
# brille sur l'horizon, et le bandeau LECTURE AUDIO.
# Le ciel change chaque jour : 10 ciels, et (num * 3) % 10 garantit que deux
# Psaumes qui se suivent n'ont jamais le meme. La position du soleil et le
# dessin des collines dependent du numero : aucune vignette n'en repete une autre.
# La composition, elle, ne change pas : la serie se reconnait dans la liste.
FONT_SANS_BOLD = FONT_SANS.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf")

# (haut du ciel, horizon, soleil, collines proches, collines lointaines)
CIELS = [
    ((22, 34, 78), (232, 150, 86), (255, 240, 170), (16, 18, 40), (8, 10, 26)),      # aube orangee
    ((40, 20, 70), (236, 120, 140), (255, 220, 200), (30, 14, 44), (16, 8, 28)),     # crepuscule rose
    ((14, 40, 90), (120, 190, 230), (255, 250, 220), (20, 44, 70), (10, 26, 44)),    # matin bleu
    ((60, 24, 20), (240, 170, 60), (255, 236, 150), (40, 18, 14), (22, 10, 8)),      # coucher dore
    ((10, 30, 50), (70, 150, 150), (220, 250, 230), (8, 30, 40), (4, 18, 26)),       # nuit turquoise
    ((50, 16, 60), (250, 150, 90), (255, 230, 170), (34, 12, 40), (18, 6, 24)),      # soir pourpre
    ((24, 44, 60), (214, 200, 170), (255, 250, 230), (30, 40, 50), (16, 22, 30)),    # brume du matin
    ((80, 20, 30), (250, 110, 70), (255, 210, 150), (50, 14, 20), (28, 8, 12)),      # rouge du soir
    ((16, 24, 60), (150, 140, 220), (240, 235, 255), (20, 20, 50), (10, 10, 30)),    # lavande
    ((10, 50, 60), (240, 190, 110), (255, 240, 190), (10, 36, 44), (4, 22, 28)),     # lagune doree
]


def vignette_audio(num, part_label=None, out="thumb_psaume.png", titre=None, sous_titre=None):
    """titre / sous_titre : pour la Bible audio (bible_audio.py), ex. « Marc 1 »
    et « Évangile selon Marc ». Par defaut : « Psaume N » et son theme."""
    VW, VH = 1280, 720
    haut, horizon, soleil, proche, loin = CIELS[(num * 3) % len(CIELS)]
    rnd = random.Random(num)
    yy, xx = np.mgrid[0:VH, 0:VW].astype(np.float32)

    # Ciel + soleil (double halo)
    sx, sy = VW * rnd.uniform(0.62, 0.84), rnd.uniform(520, 575)
    t = (yy / VH)[..., None]
    ciel = np.array(haut, np.float32) * (1 - t) + np.array(horizon, np.float32) * t
    for r, k in ((700, 0.55), (150, 1.2)):
        dist = np.sqrt((xx - sx) ** 2 + (yy - sy) ** 2) / r
        ciel = ciel + (np.clip(1 - dist, 0, 1) ** 2 * k)[..., None] * (np.array(soleil, np.float32) * 0.5)
    img = Image.fromarray(np.clip(ciel, 0, 255).astype(np.uint8))

    # Onde sonore sur l'horizon, couleur du soleil, avec lueur
    calque = Image.new("RGB", (VW, VH), (0, 0, 0))
    dc = ImageDraw.Draw(calque)
    n, bw, base = 64, 10, 500
    gap = (VW - 160 - n * bw) / (n - 1)
    couleur_onde = tuple(int(c * 0.55) for c in soleil)
    for i in range(n):
        env = math.sin(math.pi * i / (n - 1)) ** 1.2
        h = max(5, 40 * env * (0.45 + 0.55 * rnd.random()))
        x = 80 + i * (bw + gap)
        dc.rounded_rectangle([x, base - h, x + bw, base + h], radius=5, fill=couleur_onde)
    img = ImageChops.add(img, calque.filter(ImageFilter.GaussianBlur(8)))
    img = ImageChops.add(img, calque)
    d = ImageDraw.Draw(img)

    # Collines
    p1, p2, p3 = rnd.uniform(0, 6), rnd.uniform(0, 6), rnd.uniform(140, 200)
    d.polygon([(0, VH)] + [(x, 585 + 28 * math.sin(x / p3 + p1) + 16 * math.sin(x / 61 + p2))
                           for x in range(0, VW + 10, 10)] + [(VW, VH)], fill=loin)
    d.polygon([(0, VH)] + [(x, 640 + 20 * math.sin(x / 120 + p2))
                           for x in range(0, VW + 10, 10)] + [(VW, VH)], fill=proche)

    # Abreviation du livre (« Ps ») en silhouette a droite, comme les vignettes
    # de la Bible audio (demande de BC, 8 nov. 2026). Teinte des collines,
    # lueur du soleil : elle reste derriere le texte sans le gener.
    if titre is None:
        masque = Image.new("L", (VW, VH), 0)
        md = ImageDraw.Draw(masque)
        f_ab = ImageFont.truetype(FONT_SERIF_BOLD, 330)
        for size in range(330, 160, -10):
            f_ab = ImageFont.truetype(FONT_SERIF_BOLD, size)
            bb0 = md.textbbox((0, 0), "Ps", font=f_ab)
            if bb0[2] - bb0[0] <= VW * 0.25:
                break
        bb = md.textbbox((0, 0), "Ps", font=f_ab)
        md.text((VW - 70 - bb[2], 120 - bb[1]), "Ps", font=f_ab, fill=255)
        img.paste(soleil, (0, 0), masque.filter(ImageFilter.GaussianBlur(16)).point(lambda v: int(v * 0.22)))
        img.paste(loin, (0, 0), masque.point(lambda v: int(v * 0.5)))
        d = ImageDraw.Draw(img)

    def texte_ombre(xy, texte, police, couleur, flou, force):
        m = Image.new("L", (VW, VH), 0)
        ImageDraw.Draw(m).text(xy, texte, font=police, fill=255)
        img.paste((0, 0, 0), (0, 0), m.filter(ImageFilter.GaussianBlur(flou)).point(lambda v: int(v * force)))
        ImageDraw.Draw(img).text(xy, texte, font=police, fill=couleur)

    # Titre (plus etroit pour un Psaume : la silhouette « Ps » occupe la droite)
    largeur_titre = VW * (0.58 if titre is None else 0.66)
    titre = titre or f"Psaume {num}"
    f_titre = ImageFont.truetype(FONT_SERIF_BOLD, 80)
    for size in range(170, 80, -6):
        f = ImageFont.truetype(FONT_SERIF_BOLD, size)
        if d.textlength(titre, font=f) <= largeur_titre:
            f_titre = f
            break
    texte_ombre((80, 210), titre, f_titre, (255, 250, 240), 12, 0.6)

    # Theme
    theme = sous_titre or get_psaume_theme(num) or "Bible Louis Segond 1910"
    if part_label:
        theme = f"{theme} ({part_label})"
    f_theme = ImageFont.truetype(FONT_SERIF, 28)
    for size in range(50, 28, -2):
        f = ImageFont.truetype(FONT_SERIF, size)
        if d.textlength(theme, font=f) <= VW - 170:
            f_theme = f
            break
    texte_ombre((84, 210 + f_titre.size + 26), theme, f_theme, (255, 240, 214), 8, 0.5)
    d = ImageDraw.Draw(img)

    # Bandeau LECTURE AUDIO avec casque
    clair = (255, 250, 240)
    f_band = ImageFont.truetype(FONT_SANS_BOLD, 40)
    label = "LECTURE AUDIO"
    bx, by, bh = 80, 96, 76
    bwid = int(d.textlength(label, font=f_band) + 120)
    d.rounded_rectangle([bx, by, bx + bwid, by + bh], radius=38, fill=proche)
    hx, hy, hs, hw = bx + 26, by + 16, 40, 6
    d.arc([hx, hy, hx + hs, hy + hs], start=180, end=360, fill=clair, width=hw)
    d.rounded_rectangle([hx - hw // 2, hy + hs // 2 - 2, hx + hs * 0.26, hy + hs * 0.95], radius=hs // 10, fill=clair)
    d.rounded_rectangle([hx + hs * 0.74, hy + hs // 2 - 2, hx + hs + hw // 2, hy + hs * 0.95], radius=hs // 10, fill=clair)
    tb = d.textbbox((0, 0), label, font=f_band)
    d.text((bx + 86, by + (bh - (tb[3] - tb[1])) // 2 - tb[1]), label, font=f_band, fill=clair)

    # Pied
    f_pied = ImageFont.truetype(FONT_SANS, 24)
    gris = (200, 192, 182)
    d.text((80, VH - 50), "Bible Louis Segond 1910", font=f_pied, fill=gris)
    d.text((VW - 60 - d.textlength(WATERMARK, font=f_pied), VH - 50), WATERMARK, font=f_pied, fill=gris)

    img.save(out, "PNG")
    return out


def _meditation_head(num, part_label=None):
    """Cabeçalho legível p/ captions: 'Psaume N : Thème (part)' com fallback.
    Sem travessão (decisão de BC, 2 de novembro de 2026)."""
    theme = get_psaume_theme(num)
    head = f"Psaume {num}" + (f" : {theme}" if theme else "")
    if part_label:
        head += f" ({part_label})"
    return head


def _video_title(num, part_label=None):
    """Título YouTube: 'Psaume N : Thème (part) | Lecture Audio | Bible LSG1910'."""
    theme = get_psaume_theme(num)
    title = f"Psaume {num}" + (f" : {theme}" if theme else "")
    if part_label:
        title += f" ({part_label})"
    title += f" | {TITLE_SUFFIX}"
    if len(title) > 100:
        title = title[:97] + "..."
    return title


def post_to_telegram(video_path, num, part_label=None):
    """Publica a meditação no canal Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHANNEL:
        signaler_echec("Telegram méditation", "TELEGRAM_BOT_TOKEN ou TELEGRAM_CHANNEL vide")
        return
    head = _meditation_head(num, part_label)
    chapter_url = f"{APP_URL}/lsg/psaumes/{num}"
    # UNE seule cloture. PSAUME_CTA se terminait par « Partagez-le 🙏 » — la
    # formule retiree partout ailleurs — et se retrouvait empilee avec la
    # cloture tournante. On garde la phrase de fond, la cloture varie.
    # Les hashtags restent : la legende est recopiee a la main vers TikTok.
    # Meme titre que sur YouTube (demande de BC, 2 novembre 2026).
    titre = _video_title(num, part_label).replace("&", "&amp;").replace("<", "&lt;")
    caption = (
        f"🎙️ <b>{titre}</b>\n\n"
        f"{_strip_share_clause(PSAUME_CTA)} "
        f"{_rotate(TG_CLOSERS, f'psaume-{num}')}\n"
        f"📖 {chapter_url}\n\n"
        f"#LaBibleApp #Psaumes #Méditation #LSG1910"
    )
    # Le bouton ouvre la Mini App directement sur le Psaume publie.
    reply_markup = telegram_markup(f"Psaumes {num}")
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
            signaler_echec("Telegram méditation", f"HTTP {r.status_code} — {r.text[:200]}")
    except Exception as e:
        signaler_echec("Telegram méditation", f"{type(e).__name__} : {e}")


def post_to_facebook(video_id, num, part_label=None):
    """Publica na página Facebook um post com o link do vídeo YouTube.

    O vídeo em si não vai para o Facebook : /videos pede publish_video, que a
    app já não oferece, e os Reels limitam-se a 90 s. Um Salmo narrado dura
    vários minutos. O post de link só pede pages_manage_posts."""
    if not FB_PAGE_TOKEN or not FB_PAGE_ID:
        signaler_echec("Facebook méditation", "FB_PAGE_TOKEN ou FB_PAGE_ID vide")
        return
    if not video_id:
        signaler_echec("Facebook méditation", "pas de vidéo YouTube : rien à partager")
        return
    head = _meditation_head(num, part_label)
    chapter_url = f"{APP_URL}/lsg/psaumes/{num}"
    message = (
        f"🎙️ {head}\n"
        f"Lecture à voix haute · Bible Louis Segond 1910\n\n"
        f"{_strip_share_clause(PSAUME_CTA)}\n\n"
        f"📖 Lisez le psaume complet gratuitement → {chapter_url}\n\n"
        f"#LaBibleApp #Psaumes #Méditation #Bible #LSG1910 #ParoleDeDieu"
    )
    r = requests.post(
        f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/feed",
        data={"message": message,
              "link": f"https://www.youtube.com/watch?v={video_id}",
              "access_token": FB_PAGE_TOKEN},
        timeout=60,
    )
    if r.status_code == 200:
        print(f"✅ Facebook publié — {r.json().get('id')}")
    else:
        # Nunca o URL do pedido : leva o token.
        signaler_echec("Facebook méditation", f"HTTP {r.status_code} — {r.text[:200]}")


def _hms(t, srt=False):
    t = max(0.0, t)
    h, m, sec = int(t // 3600), int(t % 3600 // 60), t % 60
    if srt:
        return f"{h:02d}:{m:02d}:{int(sec):02d},{int(round((sec % 1) * 1000)) % 1000:03d}"
    return f"{h}:{m:02d}:{int(sec):02d}" if h else f"{m}:{int(sec):02d}"


def _debut_verset(texte, n=6):
    mots = texte_a_lire(clean_text(strip_rubric(texte))).rstrip(".").split()
    return " ".join(mots[:n]) + ("…" if len(mots) > n else "")


def chapitres_youtube():
    """Capítulos (« moments clés » no YouTube e no Google). Regras do YouTube :
    o primeiro em 0:00, pelo menos 3, cada um com 10 s ou mais. Os versículos
    duram menos : juntam-se versículos seguidos até ~15 s."""
    if not TIMELINE:
        return ""
    debuts, durees, versets = TIMELINE["debuts"], TIMELINE["durees"], TIMELINE["versets"]
    groupes, cur = [], None
    for i, (d0, du) in enumerate(zip(debuts, durees)):
        if cur is None:
            cur = [i, i, 0.0 if not groupes else d0]
        cur[1] = i
        if d0 + du - cur[2] >= 15:
            groupes.append(cur)
            cur = None
    if cur is not None:
        if groupes and (TIMELINE["total"] - cur[2]) < 10:
            groupes[-1][1] = cur[1]          # trop court : fusion avec le précédent
        else:
            groupes.append(cur)
    if len(groupes) < 3:
        return ""
    lignes = []
    for a, b, t0 in groupes:
        va, vb = versets[a][0], versets[b][0]
        ref = f"v. {va}" if va == vb else f"v. {va}-{vb}"
        lignes.append(f"{_hms(t0)} {ref} · {_debut_verset(versets[a][1])}")
    return "\n".join(lignes)


def sous_titres_srt(path):
    """Legendas com o texto exato de cada versículo, sincronizadas com a voz.
    O YouTube indexa este texto : é o que mais pesa na pesquisa."""
    if not TIMELINE:
        return None
    blocs = []
    for i, ((vnum, vtext), d0, du) in enumerate(
            zip(TIMELINE["versets"], TIMELINE["debuts"], TIMELINE["durees"]), 1):
        txt = texte_a_lire(clean_text(strip_rubric(vtext)))
        blocs.append(f"{i}\n{_hms(d0 + LEAD - 0.2, True)} --> {_hms(d0 + du - FADE_DURATION, True)}\n{txt}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(blocs))
    return path


def _extras_youtube(youtube, video_id, num):
    """Legendas e playlist. Pedem o âmbito OAuth youtube.force-ssl : com o
    token atual (youtube.upload) dão 403. NÃO é uma avaria : aviso no log,
    o vídeo fica publicado e a run fica verde."""
    from googleapiclient.http import MediaFileUpload
    try:
        srt = sous_titres_srt("psaume.srt")
        if srt:
            youtube.captions().insert(
                part="snippet",
                body={"snippet": {"videoId": video_id, "language": "fr",
                                  "name": "Français", "isDraft": False}},
                media_body=MediaFileUpload(srt, mimetype="application/octet-stream"),
            ).execute()
            print("✅ Legendas YouTube enviadas")
    except Exception as e:
        print(f"⚠️  Legendas não enviadas (âmbito OAuth ?) : {str(e)[:160]}")
    try:
        pl_id = None
        req = youtube.playlists().list(part="snippet", mine=True, maxResults=50)
        while req is not None and pl_id is None:
            res = req.execute()
            for it in res.get("items", []):
                if it["snippet"]["title"] == PLAYLIST_NARREE:
                    pl_id = it["id"]
                    break
            req = youtube.playlists().list_next(req, res)
        if pl_id is None:
            pl_id = youtube.playlists().insert(
                part="snippet,status",
                body={"snippet": {"title": PLAYLIST_NARREE, "description": PLAYLIST_DESC,
                                  "defaultLanguage": "fr"},
                      "status": {"privacyStatus": "public"}},
            ).execute()["id"]
            print(f"✅ Playlist criada : {PLAYLIST_NARREE}")
        youtube.playlistItems().insert(
            part="snippet",
            body={"snippet": {"playlistId": pl_id,
                              "resourceId": {"kind": "youtube#video", "videoId": video_id}}},
        ).execute()
        print("✅ Vídeo adicionado à playlist")
    except Exception as e:
        print(f"⚠️  Playlist não atualizada (âmbito OAuth ?) : {str(e)[:160]}")


def upload_to_youtube(video_path, num, verses_with_idx, part_label=None):
    """Upload do vídeo para YouTube como vídeo normal (não Short)."""
    if not YT_CLIENT_ID or not YT_CLIENT_SECRET or not YT_REFRESH_TOKEN:
        signaler_echec("YouTube méditation", "identifiants OAuth YouTube vides ou absents")
        return None

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.auth.transport.requests import Request

    creds = Credentials(
        token=None, refresh_token=YT_REFRESH_TOKEN, client_id=YT_CLIENT_ID,
        client_secret=YT_CLIENT_SECRET, token_uri="https://oauth2.googleapis.com/token",
        scopes=None,
    )
    creds.refresh(Request())
    youtube = build("youtube", "v3", credentials=creds)
    from youtube_garde import verifier_chaine
    verifier_chaine(youtube)

    title = _video_title(num, part_label)

    # Lista de versículos para descrição
    verses_text = "\n".join(
        f"Psaume {num}:{vnum} · {clean_text(strip_rubric(vtext)).rstrip('.')}."
        for vnum, vtext in verses_with_idx
    )

    head = _meditation_head(num, part_label)
    chapter_url = f"{APP_URL}/lsg/psaumes/{num}"
    theme = get_psaume_theme(num)
    chapitres = chapitres_youtube()
    # Les deux premières lignes sont celles que YouTube et Google affichent :
    # le nom du Psaume, ce que c'est, la traduction. Les 3 premiers hashtags
    # s'affichent au-dessus du titre.
    description = (
        f"Psaume {num} lu à voix haute, en entier"
        + (f" : {theme}" if theme else "") + ".\n"
        f"Bible Louis Segond 1910 (LSG 1910), texte intégral, sans commentaire. "
        f"Voix de synthèse, musique douce.\n\n"
        f"📖 Lire le Psaume {num} gratuitement : {chapter_url}\n"
        f"🎧 Toute la Bible audio : {APP_URL}/bible-audio\n"
        f"🎙️ Tous les Psaumes lus à voix haute : la playlist « {PLAYLIST_NARREE} »\n\n"
        + (f"━━━━━━━━━━━━━━━━━━━━━\n{chapitres}\n\n" if chapitres else "")
        + f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{verses_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{PSAUME_CTA}\n"
        f"🔔 Abonnez-vous : un Psaume chaque jour.\n"
        f"🔗 {APP_URL}/liens\n\n"
        f"#Psaume{num} #Psaumes #Bible #LSG1910 #ParoleDeDieu #BibleAudio #LaBibleApp"
    )
    # YouTube limita descrição a 5000 chars : corta-se na lista de versículos,
    # nunca nos capítulos nem nas primeiras linhas.
    if len(description) > 5000:
        excesso = len(description) - 5000 + 40
        corte = verses_text[:max(0, len(verses_text) - excesso)]
        corte = corte[:corte.rfind("\n")] if "\n" in corte else corte
        description = description.replace(
            verses_text, corte + f"\n… (suite : {chapter_url})")
        description = description[:5000]

    tags = [
        f"Psaume {num}", f"Psaume {num} lecture", f"Psaume {num} audio",
        f"Psaume {num} Louis Segond", f"Psaume {num} lu",
    ]
    if theme:
        tags.append(theme)
    tags += ["Psaumes", "Psaumes audio", "Bible audio", "Bible audio français",
             "Bible Louis Segond 1910", "LSG 1910", "lecture de la Bible",
             "Parole de Dieu", "méditation biblique", "Bible en français"]
    # Limite YouTube : 500 caractères pour l'ensemble des tags.
    while len(",".join(tags)) > 480:
        tags.pop()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "22",
            "defaultLanguage": "fr",
            "defaultAudioLanguage": "fr",
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

    # Vignette : contrairement aux Shorts, une video longue affiche partout
    # la vignette definie. Echec sans consequence : la video reste publiee.
    try:
        thumb = vignette_audio(num, part_label, out="thumb_psaume.png")
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumb, mimetype="image/png"),
        ).execute()
        print("✅ Vignette YouTube definie")
    except Exception as e:
        print(f"⚠️  Vignette non definie : {str(e)[:200]}")

    _extras_youtube(youtube, video_id, num)
    import yt_commentaire
    yt_commentaire.commenter(youtube, video_id, f"{APP_URL}/lsg/psaumes/{num}",
                             titre=f"Psaume {num}", audio=True)
    return video_id


def _next_psaume(progress):
    """
    Ordre sequentiel : 1, 2, 3 ... 150, puis retour a 1.
    Le Psaume 119 se publie d'un seul tenant (176 versets), il n'est plus
    decoupe en parties.
    """
    num = int(progress.get("next_psaume", 1) or 1)

    # Cycle termine : on ne republie pas, on s'arrete et on echoue
    # volontairement pour declencher l'e-mail automatique de GitHub Actions.
    # Pour repartir : remettre "next_psaume" a 1 dans progress_meditation.json.
    if num > 150:
        print("🏁 Les 150 Psaumes ont ete publies — le cycle est termine.")
        print("   Aucune publication aujourd'hui.")
        print("   Pour recommencer : remettre \"next_psaume\": 1 "
              "dans progress_meditation.json.")
        sys.exit(1)

    if num < 1:
        num = 1

    suivant = num + 1
    if suivant > 150:
        print("🏁 Psaume 150 : dernier du cycle. "
              "Les prochaines executions s'arreteront jusqu'a remise a 1.")

    progress["next_psaume"] = suivant
    # Nettoyage des cles issues de la version melangee (abandonnee).
    for obsolete in ("order", "idx", "published", "queue", "psaume_119_part"):
        progress.pop(obsolete, None)

    return num


def main():
    # ─── Parse args ───
    args = sys.argv[1:]
    # Rempli uniquement en mode automatique. La progression n'est ecrite
    # qu'apres une publication reussie (voir la fin de main()) : une execution
    # qui echoue ne « brule » plus le Psaume du jour.
    progress = None
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
        # Sem repetição dentro do ciclo (ordem embaralhada dos 150 Salmos).
        # Salmo 119 publica-se sempre inteiro (176 versículos), como qualquer outro.
        if os.path.exists(PROGRESS_FILE):
            progress = load_json(PROGRESS_FILE)
        else:
            progress = {}

        num = _next_psaume(progress)
        part_label = None
        vfrom = vto = None

    print(f"🎵 Méditation — {_meditation_head(num, part_label)}")

    # ─── Carregar versículos ───
    verses = fetch_psaume_verses(num, vfrom, vto)
    if not verses:
        signaler_echec("Méditation", f"aucun verset trouvé pour le Psaume {num}")
        finaliser("méditation psaume")
        sys.exit(1)

    # Remover rubricas demasiado curtas (linhas como "De David")
    filtered = [(vn, vt) for vn, vt in verses if not is_rubric(vt)]
    if filtered:
        verses = filtered

    print(f"📖 {len(verses)} versículos")

    # ─── Gerar vídeo ───
    # Sem vídeo (voz ou ffmpeg em falha) nada é publicado e a progressão não
    # avança : o mesmo Salmo volta a ser tentado amanhã.
    try:
        video_path = make_meditation_video(num, verses, part_label)
    except Exception as e:
        signaler_echec("Méditation (vidéo)", f"{type(e).__name__} : {e}")
        finaliser("méditation psaume")
        sys.exit(1)

    if ESSAI:
        os.makedirs("echantillons", exist_ok=True)
        shutil.copy(video_path, os.path.join("echantillons", os.path.basename(video_path)))
        sous_titres_srt(os.path.join("echantillons", f"psaume_{num}.srt"))
        with open(os.path.join("echantillons", f"psaume_{num}_chapitres.txt"), "w", encoding="utf-8") as f:
            f.write(_video_title(num, part_label) + "\n\n" + chapitres_youtube() + "\n")
        print("🧪 ESSAI : vidéo dans echantillons/, rien n'est publié.")
        return

    # ─── Upload YouTube ───
    # publier() isole chaque plateforme : une panne reseau sur l'une ne
    # peut plus empecher les autres ni la sauvegarde de la progression.
    video_id = publier("YouTube méditation", upload_to_youtube, video_path, num, verses, part_label)
    # Pour la page https://labible.app/bible-audio : {"23": "<id>", "119:1-22": "<id>"}
    if video_id:
        vf = "videos_psaumes_audio.json"
        videos = load_json(vf) if os.path.exists(vf) else {}
        videos[f"{num}:{part_label}" if part_label else str(num)] = video_id
        save_json(vf, videos)

    # ─── Telegram + Facebook (lien vers la vidéo YouTube) ───
    publier("Telegram méditation", post_to_telegram, video_path, num, part_label)
    publier("Facebook méditation", post_to_facebook, video_id, num, part_label)

    # ─── Progression (uniquement apres publication reussie) ───
    if progress is not None:
        save_json(PROGRESS_FILE, progress)
        print(f"💾 Progression enregistree — prochain Psaume : "
              f"{progress.get('next_psaume')}")

    print("✅ Terminé (méditation).")
    # Sans echec : silence, run vert. Avec echecs : alerte privee + exit 1.
    # La progression est deja ecrite ; le workflow commite avec
    # `if: ${{ !cancelled() }}`, donc rien ne se reperd.
    finaliser("méditation psaume")


if __name__ == "__main__":
    main()
