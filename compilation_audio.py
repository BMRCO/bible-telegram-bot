"""compilation_audio.py : lectures longues pour ecouter (YouTube, 16:9).

Decision de BC (21 novembre 2026) : des videos longues de 20 a 60 min a ecouter,
« Psaumes pour la nuit », « L'Evangile de Jean »... Le texte biblique est lu tel
quel (voix du Henri, celle des Psaumes narres), verset apres verset, sur une
musique libre de Content ID qui baisse sous la voix. Rien n'est ajoute au texte :
le titre de la compilation, la reference de chaque verset, rien d'autre.

Compilations : compilations_audio.json (dans l'ordre de publication). Chaque
passage est « Livre N » (chapitre entier), « theme:<slug> » (versets d'un theme
du site) ou « liste:<fichier.json> » (liste de references). Jamais deux fois la
meme compilation : progress_compilations.json ({"faites": [...]}).

Video : une image fixe par verset (verset, reference), assemblee par ffmpeg,
donc rapide meme pour une heure. Chapitres YouTube dans la description.

    python compilation_audio.py                 -> compilation suivante
    python compilation_audio.py psaumes-nuit    -> compilation precise
    ESSAI=1 LIMITE=12 python compilation_audio.py psaumes-nuit
                                                -> echantillons/, rien n'est publie

N'affiche jamais de jeton ni de secret.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import bot
from bot import (APP_URL, clean_text, strip_rubric, is_rubric, load_json, save_json, publier,
                 signaler_echec, finaliser, slugify_book, get_bible_index, BOOK_NAME_MAP)
import psaume_meditation as pm
import yt_themes
from musique_revendiquee import libres

COMPILATIONS = "compilations_audio.json"
PROGRESS_FILE = "progress_compilations.json"
VIDEOS_FILE = "videos_compilations.json"
ESSAI = os.environ.get("ESSAI") == "1"
LIMITE = int(os.environ.get("LIMITE", "0") or 0)       # essai court : N versets seulement

W, H = 1920, 1080
SR = pm.SR
GAR = "fonts/EBGaramond-Regular.ttf"
GAR_IT = "fonts/EBGaramond-Italic.ttf"
OR = (214, 178, 106)
OR_CLAIR = (236, 210, 150)
CREME = (244, 236, 218)
GRIS = (150, 140, 124)
FOND_HAUT, FOND_BAS = (12, 11, 16), (34, 28, 22)

AVANT, APRES = 0.5, 1.6          # silence avant / apres chaque verset (s)
TITRE_DUREE_MIN = 10.5     # un chapitre YouTube dure au moins 10 s
FIN_DUREE = 8.0
PLAYLIST = "🎧 Lectures pour méditer | Louis Segond 1910"
PLAYLIST_DESC = ("Des lectures longues de la Bible Louis Segond 1910, à écouter : Psaumes, "
                 "Évangiles, versets par thème. Le texte seul, lu calmement. "
                 "LaBible.app, gratuite et sans publicité : https://labible.app")
HASHTAGS = "#Bible #LouisSegond #LSG1910 #ParoleDeDieu #BibleAudio #LaBibleApp"


# ─── Contenu ────────────────────────────────────────────────────────────────
def nom_livre(livre):
    return BOOK_NAME_MAP.get(livre, livre)


def chapitre(livre, ch):
    idx = get_bible_index()
    reel = nom_livre(livre)
    if reel not in idx:
        reel = next((k for k in idx if k.lower() == reel.lower()), reel)
    vs = idx[reel][str(ch)]
    return [(int(v), vs[v]) for v in sorted(vs, key=int)]


def tete(livre, ch):
    return f"Psaume {ch}" if livre == "Psaumes" else f"{livre} {ch}"


def segments(comp):
    """[(titre du segment ou None, [(reference affichee, texte), ...])]"""
    out = []
    for p in comp["passages"]:
        if p.startswith("theme:"):
            refs = [(b, int(c), int(v)) for b, c, v in yt_themes.themes()[p[6:]]["refs"]]
            out.append((None, [(f"{b} {c}:{v}", bot.load_verse(b, c, v)) for b, c, v in refs]))
        elif p.startswith("liste:"):
            items = []
            for r in load_json(p[6:]):
                # « Livre C:V » ou une plage « Livre C:V-W » (derniers temps, 22 nov. 2026)
                m = re.match(r"^(.+?)\s+(\d+):(\d+)(?:-(\d+))?$", r)
                livre, ch, v = m.group(1), int(m.group(2)), int(m.group(3))
                for n in range(v, int(m.group(4) or v) + 1):
                    items.append((f"{livre} {ch}:{n}", bot.load_verse(livre, ch, n)))
            out.append((None, items))
        elif p.startswith("plage:"):
            # « plage:Titre|Livre C:V-W » : un passage titre (paraboles, 25 nov. 2026)
            titre_p, r = p[6:].split("|", 1)
            m = re.match(r"^(.+?)\s+(\d+):(\d+)(?:-(\d+))?$", r.strip())
            livre, ch, v = m.group(1), int(m.group(2)), int(m.group(3))
            out.append((titre_p.strip(), [(f"{livre} {ch}:{n}", bot.load_verse(livre, ch, n))
                                          for n in range(v, int(m.group(4) or v) + 1)]))
        else:
            m = re.match(r"^(.+?)\s+(\d+)$", p)
            livre, ch = m.group(1), int(m.group(2))
            vs = [(n, t) for n, t in chapitre(livre, ch) if not (n == 1 and is_rubric(t))]
            out.append((tete(livre, ch), [(f"{tete(livre, ch)}:{n}" if livre != "Psaumes"
                                           else f"Psaume {ch}:{n}", t) for n, t in vs]))
    # pas deux fois le meme verset dans une compilation
    vus, propre = set(), []
    for titre, items in out:
        garde = []
        for ref, t in items:
            if ref not in vus:
                vus.add(ref); garde.append((ref, t))
        if garde:
            propre.append((titre, garde))
    return propre


# ─── Images ─────────────────────────────────────────────────────────────────
def _f(path, size):
    return ImageFont.truetype(path, size)


def fond():
    a = np.linspace(0, 1, H)[:, None, None]
    g = (np.array(FOND_HAUT) * (1 - a) + np.array(FOND_BAS) * a) * np.ones((1, W, 1))
    y, x = np.ogrid[:H, :W]
    halo = np.exp(-(((x - W / 2) / (W * 0.45)) ** 2 + ((y - H * 0.48) / (H * 0.5)) ** 2))
    g = g + halo[..., None] * np.array([26, 20, 10])
    return Image.fromarray(np.clip(g, 0, 255).astype(np.uint8))


FOND = None
NATURE = None      # chemin de la boucle video de nature (series « pour dormir »)

# Fonds de nature (Pixabay, licence Pixabay, sans Content ID), choisis par BC le
# 27 nov. 2026. Telecharges a la fabrication, jamais gardes dans le depot.
NATURE_VIDEOS = {
    "pluie-feuilles": "https://cdn.pixabay.com/video/2021/09/04/87476-601149398_large.mp4",
    "foret-rayons": "https://cdn.pixabay.com/video/2025/10/20/311049_large.mp4",
    "foret-brume": "https://cdn.pixabay.com/video/2026/10/14/382582_large.mp4",
    "brume-matin": "https://cdn.pixabay.com/video/2022/10/23/136182-764387455_large.mp4",
}


def boucle_nature(nom, dossier):
    """Telecharge la video et en fait une boucle sans raccord visible : la fin se
    fond dans le debut (fondu de 1,5 s). 1920x1080, 24 i/s, sans son."""
    import requests
    brut = os.path.join(dossier, f"nature_{nom}.mp4")
    r = requests.get(NATURE_VIDEOS[nom], timeout=180, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    open(brut, "wb").write(r.content)
    d = min(bot.duree_media(brut) or 20.0, 40.0)
    boucle = os.path.join(dossier, f"boucle_{nom}.mp4")
    f = 1.5
    fc = (f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=24,"
          f"format=yuv420p,split=2[a][b];"
          f"[a]trim={f}:{d},setpts=PTS-STARTPTS[corps];[b]trim=0:{f},setpts=PTS-STARTPTS[debut];"
          f"[corps][debut]xfade=transition=fade:duration={f}:offset={d - 2 * f:.3f}[v]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-nostdin", "-i", brut, "-filter_complex", fc,
                    "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", boucle],
                   check=True)
    return boucle


def _lignes(d, texte, font, largeur):
    mots, lignes, cur = texte.split(), [], ""
    for m in mots:
        t = (cur + " " + m).strip()
        if d.textlength(t, font=font) <= largeur:
            cur = t
        else:
            if cur:
                lignes.append(cur)
            cur = m
    if cur:
        lignes.append(cur)
    return lignes


def _centre(d, y, txt, font, fill):
    x = (W - d.textlength(txt, font=font)) / 2
    if NATURE:
        d.text((x + 3, y + 3), txt, font=font, fill=(0, 0, 0, 170))
    d.text((x, y), txt, font=font, fill=fill)


def cadre(titre_comp):
    if NATURE:
        # calque transparent pose sur la video : un voile sombre pour la lecture
        im = Image.new("RGBA", (W, H), (0, 0, 0, 150))
    else:
        im = FOND.copy()
    d = ImageDraw.Draw(im)
    _centre(d, 54, "LaBible.app  ·  Bible Louis Segond 1910", _f(GAR, 34), GRIS)
    d.line([(W / 2 - 60, 124), (W / 2 + 60, 124)], fill=OR, width=2)
    _centre(d, H - 92, titre_comp, _f(GAR_IT, 36), GRIS)
    return im, d


def image_verset(titre_comp, ref, texte, chemin):
    im, d = cadre(titre_comp)
    txt = f"« {texte} »"
    for taille in range(70 if NATURE else 62, 33, -2):
        f = _f(GAR, taille)
        lg = _lignes(d, txt, f, W - 360)
        hl = int(taille * 1.42)
        if len(lg) * hl <= 640:
            break
    bloc = len(lg) * hl + 40 + 50
    y = (H - bloc) // 2 + 10
    for l in lg:
        _centre(d, y, l, f, CREME)
        y += hl
    _centre(d, y + 34, ref, _f(GAR, 46), OR_CLAIR)
    im.save(chemin, quality=92)


def image_titre(comp, chemin, minutes=None):
    im, d = cadre("")
    _centre(d, 380, comp["titre"], _f(GAR, 96), CREME)
    _centre(d, 520, comp["sous_titre"], _f(GAR_IT, 54), OR_CLAIR)
    if minutes and minutes >= 60:
        # sans la duree en dessous d'une heure (comme le titre et la miniature)
        h_, m_ = divmod(minutes, 60)
        _centre(d, 640, f"{h_} h" + (f" {m_:02d}" if m_ else ""), _f(GAR, 40), GRIS)
    im.save(chemin, quality=92)


def image_segment(titre_comp, titre_seg, chemin):
    im, d = cadre(titre_comp)
    _centre(d, 470, titre_seg, _f(GAR, 110), OR_CLAIR)
    im.save(chemin, quality=92)


def image_fin(chemin):
    im, d = cadre("")
    _centre(d, 420, "LaBible.app", _f(GAR, 110), CREME)
    _centre(d, 570, "La Bible Louis Segond 1910, gratuite et sans publicité", _f(GAR_IT, 48), OR_CLAIR)
    im.save(chemin, quality=92)


def miniature(comp, minutes, chemin):
    w, h = 1280, 720
    if NATURE:
        image = chemin + ".nature.jpg"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-nostdin", "-ss", "3", "-i", NATURE,
                        "-frames:v", "1", "-vf", f"scale={w}:{h}", image], check=True)
        im = Image.open(image).convert("RGB")
        im = Image.blend(im, Image.new("RGB", (w, h), (0, 0, 0)), 0.5)
        return miniature_nature(comp, minutes, im, chemin)
    im = FOND.resize((w, h))
    d = ImageDraw.Draw(im)
    for taille in range(112, 50, -4):
        f = _f(GAR, taille)
        lg = _lignes(d, comp["titre"], f, w - 140)
        if len(lg) <= 2:
            break
    hl = int(taille * 1.12)
    f2 = _f(GAR_IT, 50)
    # Sans la duree (BC, 24 nov. 2026 : « tira os minutos da capa ») ; YouTube
    # l'affiche deja. Seule une lecture d'une heure ou plus la porte.
    if minutes >= 60:
        h_, m_ = divmod(minutes, 60)
        t2 = f"{h_} h" + (f" {m_:02d}" if m_ else "") + " · Bible Louis Segond 1910"
    else:
        t2 = "Bible Louis Segond 1910"
    bloc = len(lg) * hl + 50 + 60
    y = (h - bloc) // 2
    bas = y
    for l in lg:
        x = (w - d.textlength(l, font=f)) / 2
        d.text((x, y), l, font=f, fill=CREME)
        bas = d.textbbox((x, y), l, font=f)[3]
        y += hl
    y = bas + 30
    d.line([(w / 2 - 70, y), (w / 2 + 70, y)], fill=OR, width=3)
    d.text(((w - d.textlength(t2, font=f2)) / 2, y + 24), t2, font=f2, fill=OR_CLAIR)
    im.save(chemin, quality=92)


def miniature_nature(comp, minutes, im, chemin):
    """Grandes lettres dorees en capitales, lisibles sur un telephone."""
    from PIL import ImageFilter
    w, h = im.size
    titre = comp["titre"].upper()
    calque = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(calque)
    for taille in range(150, 60, -6):
        f = _f(GAR, taille)
        lg = _lignes(d, titre, f, w - 120)
        if len(lg) <= 2:
            break
    hl = int(taille * 1.02)
    if minutes >= 60:
        h_, m_ = divmod(minutes, 60)
        t2 = f"{h_} h" + (f" {m_:02d}" if m_ else "") + " · Bible Louis Segond 1910"
    else:
        t2 = "Bible Louis Segond 1910"
    f2 = _f(GAR_IT, 56)
    y = (h - (len(lg) * hl + 90)) // 2
    for l in lg:
        d.text(((w - d.textlength(l, font=f)) / 2, y), l, font=f, fill=OR_CLAIR + (255,))
        y += hl
    d.text(((w - d.textlength(t2, font=f2)) / 2, y + 26), t2, font=f2, fill=CREME + (255,))
    ombre = calque.split()[3].filter(ImageFilter.GaussianBlur(10)).point(lambda v: min(255, int(v * 1.4)))
    base = im.convert("RGBA")
    base.paste(Image.new("RGBA", (w, h), (0, 0, 0, 255)), (4, 6), ombre)
    base.alpha_composite(calque)
    base.convert("RGB").save(chemin, quality=92)


# ─── Montage ────────────────────────────────────────────────────────────────
def hms(s):
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def musique_longue(duree, dossier):
    pistes = sorted(os.path.join("music_meditation", f) for f in os.listdir("music_meditation")
                    if f.lower().endswith((".mp3", ".m4a", ".ogg", ".wav")))
    pistes = libres(pistes) or []
    if not pistes:
        return None
    import random
    random.Random(int(duree)).shuffle(pistes)
    total, choix = 0.0, []
    while total < duree + 10:
        for p in pistes:
            choix.append(p)
            # bot.duree_media : marche aussi sans ffprobe (secours imageio-ffmpeg) ;
            # une piste illisible compte pour 2 min, pour ne jamais boucler sans fin
            total += bot.duree_media(p) or 120.0
            if total >= duree + 10:
                break
    liste = os.path.join(dossier, "musique.txt")
    with open(liste, "w") as f:
        for p in choix:
            f.write(f"file '{os.path.abspath(p)}'\n")
    sortie = os.path.join(dossier, "musique.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", liste,
                    "-ar", "48000", "-ac", "2", sortie], check=True)
    return sortie


def fabriquer(comp):
    global FOND, NATURE
    FOND = fond()
    dossier = "compilation_tmp"
    shutil.rmtree(dossier, ignore_errors=True)
    os.makedirs(dossier)
    NATURE = None
    if comp.get("nature"):
        try:
            NATURE = boucle_nature(comp["nature"], dossier)
            print(f"🌿 Fond de nature : {comp['nature']}")
        except Exception as e:
            print(f"⚠️  Fond de nature indisponible ({str(e)[:120]}) : fond habituel")
    EXT = ".png" if NATURE else ".jpg"
    segs = segments(comp)
    if LIMITE:
        reste, court = LIMITE, []
        for t, items in segs:
            if reste <= 0:
                break
            court.append((t, items[:reste])); reste -= len(items[:reste])
        segs = court
    n_total = sum(len(i) for _, i in segs)
    print(f"📖 {comp['titre']} : {len(segs)} passage(s), {n_total} versets")

    plans, pistes, chapitres = [], [], []    # plans : (image, duree)
    t = 0.0
    k = 0

    def ajouter(img, audio, avant, apres, minimum=0.0):
        nonlocal t
        d = max(minimum, avant + (len(audio) / SR if audio is not None else 0) + apres)
        if audio is not None:
            pistes.append((t + avant, audio))
        plans.append((img, d))
        t += d

    # titre (sans voix : la musique s'installe)
    img = os.path.join(dossier, "titre" + EXT)
    image_titre(comp, img)
    chapitres.append((0, comp["titre"]))
    ajouter(img, None, 0, 0, TITRE_DUREE_MIN)

    for titre_seg, items in segs:
        if titre_seg:
            chapitres.append((t, titre_seg))
            img = os.path.join(dossier, f"s{k:04d}{EXT}"); k += 1
            image_segment(comp["titre"], titre_seg, img)
            ajouter(img, pm.synthese(f"{titre_seg}.", os.path.join(dossier, f"a{k:04d}")), 0.8, 1.6)
        for ref, texte in items:
            propre = clean_text(strip_rubric(texte)).rstrip(".")
            img = os.path.join(dossier, f"v{k:04d}{EXT}"); k += 1
            image_verset(comp["titre"], ref, propre, img)
            ajouter(img, pm.synthese(pm.texte_a_lire(propre), os.path.join(dossier, f"a{k:04d}")), AVANT, APRES)
            print(f"  🎙️  {k}/{n_total + len(segs)}", end="\r")
    print()
    img = os.path.join(dossier, "fin" + EXT)
    image_fin(img)
    ajouter(img, None, 0, 0, FIN_DUREE)
    total = t
    minutes = max(1, round(total / 60))
    image_titre(comp, os.path.join(dossier, "titre" + EXT), minutes)   # avec la duree

    # voix
    voix = np.zeros(int(total * SR) + SR, dtype=np.float32)
    for t0, a in pistes:
        i0 = int(t0 * SR)
        voix[i0:i0 + len(a)] += a
    voix = voix[:int(total * SR)]
    wav = os.path.join(dossier, "voix.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(voix, -1, 1) * 32767).astype(np.int16).tobytes())

    # images -> video (concat : chaque image tient sa duree)
    liste = os.path.join(dossier, "images.txt")
    with open(liste, "w") as f:
        for img, d in plans:
            f.write(f"file '{os.path.abspath(img)}'\nduration {d:.3f}\n")
        f.write(f"file '{os.path.abspath(plans[-1][0])}'\n")
    musique = musique_longue(total, dossier)
    sortie = f"compilation_{comp['id']}.mp4"
    tmp = sortie + ".tmp.mp4"
    # Avec un fond de nature, la boucle video passe en entree 0 et les images
    # (transparentes) se posent dessus ; les entrees audio decalent d'un rang.
    o = 1 if NATURE else 0
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-nostdin"]
    if NATURE:
        cmd += ["-stream_loop", "-1", "-i", NATURE]
    cmd += ["-f", "concat", "-safe", "0", "-i", liste, "-i", wav]
    if musique:
        cmd += ["-i", musique]
        fc = (f"[{1 + o}:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[v][sc];"
              f"[{2 + o}:a]volume=0.14,afade=t=in:d=3,afade=t=out:st={max(0, total - 6):.2f}:d=6[m0];"
              f"[m0][sc]sidechaincompress={pm.DUCKING}[m];"
              f"[v][m]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]")
    else:
        fc = f"[{1 + o}:a]aformat=sample_rates=48000:channel_layouts=stereo,loudnorm=I=-16:TP=-1.5:LRA=11[a]"
    if NATURE:
        fc += ";[0:v]fps=24[fond];[1:v]fps=24,format=rgba[cal];[fond][cal]overlay=format=auto,format=yuv420p[vid]"
        cmd += ["-filter_complex", fc, "-map", "[vid]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23"]
    else:
        cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[a]",
                "-vf", "fps=24,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
                "-crf", "22"]
    cmd += ["-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", "-movflags", "+faststart", tmp]
    subprocess.run(cmd, check=True)
    os.replace(tmp, sortie)
    vignette = f"compilation_{comp['id']}.jpg"
    miniature(comp, minutes, vignette)
    print(f"✅ Vidéo : {sortie} ({hms(total)})")
    return sortie, vignette, minutes, chapitres


# ─── YouTube ────────────────────────────────────────────────────────────────
def titre_video(comp, minutes):
    """Sans la duree (BC, 22 nov. 2026 : le YouTube l'affiche deja sur la miniature).
    Seule une lecture d'une heure ou plus la porte, car c'est elle qu'on cherche."""
    if minutes >= 60:
        h, m = divmod(minutes, 60)
        duree = f"{h} h" + (f" {m:02d}" if m else "")
        return f"{comp['titre']} | {duree} | Bible Louis Segond 1910"[:100]
    return f"{comp['titre']} | Bible Louis Segond 1910"[:100]


def poser_miniature(yt, vid, vignette, essais=3):
    """Reessayee : une video encore en traitement refuse parfois sa miniature (403)."""
    import time
    from googleapiclient.http import MediaFileUpload
    for n in range(essais):
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(vignette, mimetype="image/jpeg")).execute()
            print("✅ Miniature")
            return True
        except Exception as e:
            if n == essais - 1:
                print(f"⚠️  Miniature non posée : {str(e)[:200]}")
                return False
            time.sleep(60 * (n + 1))


def remettre_miniatures():
    """compilation = « --vignettes » : refait la miniature des lectures longues deja
    publiees (format actuel, sans la duree). Ne publie rien."""
    global FOND, NATURE
    FOND = fond()
    NATURE = None
    comps = {c["id"]: c for c in load_json(COMPILATIONS)}
    videos = load_json(VIDEOS_FILE) if os.path.exists(VIDEOS_FILE) else {}
    yt = youtube()
    for cle, vid in videos.items():
        item = yt.videos().list(part="contentDetails", id=vid).execute()["items"][0]
        d = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", item["contentDetails"]["duration"])
        minutes = int(d.group(1) or 0) * 60 + int(d.group(2) or 0)
        chemin = f"miniature_{cle}.jpg"
        miniature(comps[cle], minutes, chemin)
        if poser_miniature(yt, vid, chemin):
            print(f"🖼️  {cle}")


def retitrer():
    """compilation = « --titres » : remet au format actuel le titre des lectures
    longues deja publiees (videos_compilations.json). Ne publie rien."""
    comps = {c["id"]: c for c in load_json(COMPILATIONS)}
    videos = load_json(VIDEOS_FILE) if os.path.exists(VIDEOS_FILE) else {}
    yt = youtube()
    for cle, vid in videos.items():
        item = yt.videos().list(part="snippet,contentDetails", id=vid).execute()["items"][0]
        sn = item["snippet"]
        d = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", item["contentDetails"]["duration"])
        minutes = int(d.group(1) or 0) * 60 + int(d.group(2) or 0)
        nouveau = titre_video(comps[cle], minutes)
        if sn["title"] == nouveau:
            print(f"= {cle} : {nouveau}")
            continue
        corps = {"id": vid, "snippet": {"title": nouveau, "description": sn.get("description", ""),
                                        "categoryId": sn["categoryId"], "tags": sn.get("tags", []),
                                        "defaultLanguage": sn.get("defaultLanguage", "fr"),
                                        "defaultAudioLanguage": sn.get("defaultAudioLanguage", "fr")}}
        yt.videos().update(part="snippet", body=corps).execute()
        print(f"✅ {cle} : {sn['title']} -> {nouveau}")


def description(comp, chapitres):
    lignes = [f"{comp['titre']}. {comp['sous_titre']}.",
              "Le texte de la Bible Louis Segond 1910, lu verset après verset.", ""]
    if len(chapitres) >= 3:
        lignes += [f"{hms(t)} {nom}" for t, nom in chapitres] + [""]
    lignes += [f"📖 Lire la Bible : {APP_URL}",
               f"🎧 Toutes les lectures : la playlist « {PLAYLIST} »", "", HASHTAGS]
    return "\n".join(lignes)[:4900]


def youtube():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from youtube_garde import verifier_chaine
    creds = Credentials(token=None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
                        client_id=os.environ["YOUTUBE_CLIENT_ID"],
                        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token", scopes=None)
    creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds)
    verifier_chaine(yt)
    return yt


def playlist(yt, progress):
    if progress.get("playlist"):
        return progress["playlist"]
    req = yt.playlists().list(part="snippet", mine=True, maxResults=50)
    while req is not None:
        rep = req.execute()
        for p in rep.get("items", []):
            if p["snippet"]["title"] == PLAYLIST:
                progress["playlist"] = p["id"]
                return p["id"]
        req = yt.playlists().list_next(req, rep)
    pid = yt.playlists().insert(part="snippet,status", body={
        "snippet": {"title": PLAYLIST, "description": PLAYLIST_DESC, "defaultLanguage": "fr"},
        "status": {"privacyStatus": "public"}}).execute()["id"]
    print(f"✅ Playlist créée : {PLAYLIST}")
    progress["playlist"] = pid
    return pid


def ajouter_playlist(yt, vid, progress, essais=4):
    """Une playlist tout juste creee repond parfois 409 « The operation was aborted »
    (22 nov. 2026, premiere lecture longue) : on reessaie apres une pause."""
    import time
    for n in range(essais):
        try:
            yt.playlistItems().insert(part="snippet", body={"snippet": {
                "playlistId": playlist(yt, progress),
                "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
            print(f"✅ Ajoutée à « {PLAYLIST} »")
            return True
        except Exception as e:
            if n == essais - 1:
                print(f"⚠️  Playlist non mise à jour : {str(e)[:200]}")
                return False
            time.sleep(10 * (n + 1))


def rattraper_playlist():
    """compilation = « --playlist » : remet dans la playlist les lectures longues
    deja publiees qui n'y sont pas (videos_compilations.json). Ne publie rien."""
    progress = load_json(PROGRESS_FILE) if os.path.exists(PROGRESS_FILE) else {}
    videos = load_json(VIDEOS_FILE) if os.path.exists(VIDEOS_FILE) else {}
    yt = youtube()
    pid = playlist(yt, progress)
    deja, req = set(), yt.playlistItems().list(part="contentDetails", playlistId=pid, maxResults=50)
    while req is not None:
        rep_ = req.execute()
        deja |= {i["contentDetails"]["videoId"] for i in rep_.get("items", [])}
        req = yt.playlistItems().list_next(req, rep_)
    for cle, vid in videos.items():
        if vid in deja:
            print(f"= {cle} déjà dans la playlist")
        else:
            ajouter_playlist(yt, vid, progress)
    save_json(PROGRESS_FILE, progress)


def upload(video, vignette, comp, minutes, chapitres, progress):
    from googleapiclient.http import MediaFileUpload
    import yt_commentaire
    yt = youtube()
    body = {"snippet": {"title": titre_video(comp, minutes), "description": description(comp, chapitres),
                        "tags": ["Bible", "Bible audio", "lecture de la Bible", "Louis Segond", "LSG1910",
                                 "Parole de Dieu", comp["titre"]],
                        "categoryId": "22", "defaultLanguage": "fr", "defaultAudioLanguage": "fr"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    vid = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(video, mimetype="video/mp4", resumable=True,
                                                        chunksize=50 * 1024 * 1024)).execute()["id"]
    print(f"✅ YouTube : https://youtube.com/watch?v={vid}")
    poser_miniature(yt, vid, vignette)
    ajouter_playlist(yt, vid, progress)
    yt_commentaire.commenter(yt, vid, APP_URL, titre=comp["titre"], audio=True)
    return vid


# ─────────────────────────────────────────────────────────────────────────────
def main():
    comps = load_json(COMPILATIONS)
    progress = load_json(PROGRESS_FILE) if os.path.exists(PROGRESS_FILE) else {}
    faites = progress.setdefault("faites", [])
    if len(sys.argv) > 1 and sys.argv[1].strip() == "--vignettes":
        remettre_miniatures()
        return
    if len(sys.argv) > 1 and sys.argv[1].strip() == "--titres":
        retitrer()
        return
    if len(sys.argv) > 1 and sys.argv[1].strip() == "--playlist":
        rattraper_playlist()
        return
    if len(sys.argv) > 1 and sys.argv[1].strip():
        comp = next((c for c in comps if c["id"] == sys.argv[1].strip()), None)
        if not comp:
            sys.exit(f"compilation inconnue : {sys.argv[1]}")
    else:
        comp = next((c for c in comps if c["id"] not in faites), None)
        if not comp:
            print("🏁 Toutes les compilations ont été publiées : ajouter des entrées à compilations_audio.json.")
            return
    try:
        video, vignette, minutes, chapitres = fabriquer(comp)
    except Exception as e:
        signaler_echec("Compilation (vidéo)", f"{type(e).__name__} : {e}")
        finaliser("compilation")
        sys.exit(1)
    if ESSAI:
        os.makedirs("echantillons", exist_ok=True)
        for f in (video, vignette):
            shutil.copy(f, "echantillons/")
        with open("echantillons/compilation.txt", "w", encoding="utf-8") as f:
            f.write(titre_video(comp, minutes) + "\n\n" + description(comp, chapitres))
        print("🧪 ESSAI : rien n'est publié.")
        return
    vid = publier("YouTube compilation", upload, video, vignette, comp, minutes, chapitres, progress)
    if vid:
        faites.append(comp["id"])
        videos = load_json(VIDEOS_FILE) if os.path.exists(VIDEOS_FILE) else {}
        videos[comp["id"]] = vid
        save_json(VIDEOS_FILE, videos)
        save_json(PROGRESS_FILE, progress)
    finaliser("compilation")


if __name__ == "__main__":
    main()
