"""derniers_temps.py : serie de Shorts « Les derniers temps » (YouTube seulement).

Decision de BC (14 novembre 2026) : une playlist de Shorts sur les prophéties
des derniers temps, et « essa serie tem que ser especial ». Elle a donc son
propre visuel, distinct des Shorts quotidiens de bot.py :

  - un ciel de nuit, presque noir, ou une aube d'or monte lentement sur
    l'horizon pendant toute la video (le jour qui vient) ;
  - en tete, un sablier et « LES DERNIERS TEMPS » en capitales espacees ;
  - le verset en EB Garamond, la reference en or ;
  - le carton de cloture habituel (LaBible.app, Gratuit · Sans publicite).

Rien n'est ajoute au texte biblique : seulement le verset, sa reference et le
nom de la serie. Aucune actualite, aucune date, aucun commentaire.

Versets : la liste du theme « derniers-temps » du site (data/versets_themes.json
du depot labible.app, page labible.app/versets/derniers-temps), dans l'ordre de
la page. Progression : progress_derniers_temps.json ({"index": N}).

Publication : YouTube seulement (Short), playlist « ⏳ Les derniers temps »
(creee si elle manque), playlists des autres themes qui contiennent le verset,
premier commentaire avec le lien. Les autres reseaux restent a 5 publications
par jour (decision du 8 novembre 2026) : cette serie n'y va pas.

    python derniers_temps.py                    -> verset suivant
    python derniers_temps.py "Matthieu 24:35"   -> verset precis (progression intacte)
    ESSAI=1 python derniers_temps.py            -> video dans echantillons/, rien n'est publie

N'affiche jamais de jeton ni de secret.
"""
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from bot import (APP_URL, clean_text, strip_rubric, load_verse, slugify_book, publier,
                 signaler_echec, finaliser, load_json, save_json, wrap_text_with_quotes)
from musique_revendiquee import libres
import yt_themes

SLUG = "derniers-temps"
PROGRESS_FILE = "progress_derniers_temps.json"
VIDEOS_FILE = "videos_derniers_temps.json"
ESSAI = os.environ.get("ESSAI") == "1"

W, H, FPS = 1080, 1920, 30
DUREE = 20.0
FONT = "fonts/EBGaramond-Regular.ttf"
FONT_IT = "fonts/EBGaramond-Italic.ttf"

# Couleurs de la serie
NUIT_HAUT = np.array([4, 5, 14], float)
NUIT_BAS = np.array([12, 12, 30], float)
AUBE = np.array([228, 168, 92], float)
OR = (226, 190, 118)
OR_PALE = (200, 172, 120)
CREME = (244, 236, 218)


# ─── Versets ────────────────────────────────────────────────────────────────
def refs_du_theme():
    t = yt_themes.themes()[SLUG]
    return [f"{b} {c}:{v}" for b, c, v in t["refs"]]


def lire_verset(ref):
    m = re.match(r"^(.+?)\s+(\d+):(\d+)$", ref.strip())
    if not m:
        raise ValueError(f"référence illisible : {ref}")
    livre, ch, v = m.group(1), int(m.group(2)), int(m.group(3))
    try:
        texte = load_verse(livre, ch, v)
    except KeyError:
        texte = None
    if not texte:
        raise ValueError(f"verset introuvable : {ref}")
    return livre, ch, v, clean_text(strip_rubric(texte)).rstrip(".")


def chapter_url(livre, ch):
    return f"{APP_URL}/lsg/{slugify_book(livre)}/{ch}"


# ─── Image ──────────────────────────────────────────────────────────────────
def _font(path, size):
    return ImageFont.truetype(path, size)


def _texte_espace(draw, xy_centre, txt, font, fill, espace):
    """Texte en capitales espacees, centre sur x."""
    largeurs = [draw.textlength(c, font=font) for c in txt]
    total = sum(largeurs) + espace * (len(txt) - 1)
    x = xy_centre[0] - total / 2
    for c, w in zip(txt, largeurs):
        draw.text((x, xy_centre[1]), c, font=font, fill=fill)
        x += w + espace


def _sablier(draw, cx, cy, h, fill, largeur=3):
    w = h * 0.62
    draw.line([(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2)], fill=fill, width=largeur)
    draw.line([(cx - w / 2, cy + h / 2), (cx + w / 2, cy + h / 2)], fill=fill, width=largeur)
    for s in (-1, 1):
        pts = []
        for i in range(21):
            t = i / 20
            y = cy - h / 2 + t * h
            x = cx + s * (w / 2 - 4) * (abs(1 - 2 * t) ** 0.8 * 0.92 + 0.08)
            pts.append((x, y))
        draw.line(pts, fill=fill, width=largeur)
    draw.polygon([(cx - w * 0.22, cy + h / 2 - 6), (cx + w * 0.22, cy + h / 2 - 6), (cx, cy + h * 0.12)],
                 fill=fill)


def calque_tete():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _sablier(d, W / 2, 236, 64, OR)
    _texte_espace(d, (W / 2, 300), "LES DERNIERS TEMPS", _font(FONT, 46), OR, 9)
    d.line([(W / 2 - 150, 384), (W / 2 + 150, 384)], fill=OR_PALE + (150,), width=2)
    return img


def calque_verset(texte, ref):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    marge = 120
    taille = 74
    while taille > 36:
        f = _font(FONT, taille)
        lignes = wrap_text_with_quotes(d, texte, f, W - 2 * marge)
        lh = int(taille * 1.32)
        if lh * len(lignes) <= 860:
            break
        taille -= 2
    f = _font(FONT, taille)
    lignes = wrap_text_with_quotes(d, texte, f, W - 2 * marge)
    lh = int(taille * 1.32)
    fr = _font(FONT_IT, 50)
    hauteur = lh * len(lignes) + 46 + 60
    y = 470 + (900 - hauteur) / 2
    for l in lignes:
        lw = d.textlength(l, font=f)
        d.text(((W - lw) / 2, y), l, font=f, fill=CREME)
        y += lh
    y += 46
    rw = d.textlength(ref, font=fr)
    d.text(((W - rw) / 2, y), ref, font=fr, fill=OR)
    # Signature discrete, au-dessus de la bande que l'interface des Shorts recouvre
    fs = _font(FONT, 34)
    sig = "LaBible.app · LSG 1910"
    d.text(((W - d.textlength(sig, font=fs)) / 2, 1500), sig, font=fs, fill=OR_PALE)
    return img


def calque_fin():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f1, f2, f3 = _font(FONT_IT, 44), _font(FONT, 92), _font(FONT, 38)
    for txt, f, y, c in (("Lisez le chapitre entier sur", f1, 760, CREME),
                         ("LaBible.app", f2, 830, OR),
                         ("Gratuit · Sans publicité · LSG 1910", f3, 968, OR_PALE)):
        d.text(((W - d.textlength(txt, font=f)) / 2, y), txt, font=f, fill=c)
    return img


def fond_et_etoiles(seed):
    rng = np.random.default_rng(seed)
    y = np.linspace(0, 1, H)[:, None]
    base = NUIT_HAUT * (1 - y[..., None]) + NUIT_BAS * y[..., None]
    base = np.repeat(base, W, axis=1)
    # Lueur d'aube : ellipse large posee sur l'horizon (y = 0.90 H)
    yy, xx = np.mgrid[0:H, 0:W]
    dx = (xx - W / 2) / (W * 0.9)
    dy = (yy - H * 0.90) / (H * 0.30)
    lueur = np.clip(1 - np.sqrt(dx ** 2 + dy ** 2), 0, 1) ** 2.2
    lueur[yy > H * 0.90] *= 0.55          # sous l'horizon, la terre reste sombre
    ligne = np.exp(-((yy - H * 0.90) / 3.0) ** 2) * np.clip(1 - np.abs(dx), 0, 1)
    n = 170
    sx = rng.uniform(0, W, n).astype(int)
    sy = (rng.uniform(0, 0.82, n) ** 1.3 * H).astype(int)
    sb = rng.uniform(0.35, 1.0, n)
    sp = rng.uniform(0, 2 * math.pi, n)
    sv = rng.uniform(0.6, 1.6, n)
    return base, lueur[..., None], ligne[..., None], (sx, sy, sb, sp, sv)


def _alpha(t, debut, fin, fondu=0.7):
    if t < debut or t > fin:
        return 0.0
    return min(1.0, (t - debut) / fondu, (fin - t) / fondu)


def _composer(cadre, calque_np, a):
    if a <= 0:
        return
    rgb, al = calque_np
    k = al * a
    cadre *= (1 - k)
    cadre += rgb * k


def faire_video(livre, ch, v, texte, ref, sortie):
    seed = sum(map(ord, ref))
    base, lueur, ligne, (sx, sy, sb, sp, sv) = fond_et_etoiles(seed)

    def np_calque(img):
        a = np.asarray(img, dtype=np.float32)
        return a[..., :3], a[..., 3:4] / 255.0

    tete = np_calque(calque_tete())
    vers = np_calque(calque_verset(texte, ref))
    fin = np_calque(calque_fin())

    musique = libres(sorted(
        os.path.join("music_meditation", f) for f in os.listdir("music_meditation")
        if f.lower().endswith((".mp3", ".m4a", ".ogg", ".wav")))) if os.path.isdir("music_meditation") else []
    piste = musique[seed % len(musique)] if musique else None
    print(f"🎵 Musique : {os.path.basename(piste) if piste else 'aucune'}")

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if piste:
        cmd += ["-ss", "8", "-i", piste, "-filter_complex",
                f"[1:a]volume=0.55,afade=t=in:d=1.5,afade=t=out:st={DUREE - 2.5}:d=2.5[a]",
                "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-t", str(DUREE), "-movflags", "+faststart", sortie]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(DUREE * FPS)
    for i in range(n):
        t = i / FPS
        aube = 0.10 + 0.55 * (t / DUREE) ** 1.4
        cadre = base + lueur * (AUBE * aube) + ligne * (AUBE * min(1.0, 0.25 + aube))
        # etoiles qui scintillent et palissent quand le jour monte
        eclat = sb * (0.65 + 0.35 * np.sin(sp + t * sv * 2.2)) * (1 - 0.6 * (t / DUREE))
        cadre[sy, sx] = np.maximum(cadre[sy, sx], (eclat[:, None] * 255))
        cadre = cadre.astype(np.float32)
        _composer(cadre, tete, _alpha(t, 0.2, DUREE - 0.4, 1.0))
        _composer(cadre, vers, _alpha(t, 1.0, 14.6, 1.0))
        _composer(cadre, fin, _alpha(t, 15.2, DUREE + 1, 0.6))
        if t > DUREE - 0.6:
            cadre *= max(0.0, (DUREE - t) / 0.6)
        p.stdin.write(np.clip(cadre, 0, 255).astype(np.uint8).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError("ffmpeg a échoué")
    return sortie


# ─── YouTube ────────────────────────────────────────────────────────────────
def titre_video(ref):
    return f"{ref} | Les derniers temps | Bible Louis Segond 1910"


def description(ref, texte, livre, ch):
    return (f"« {texte} »\n{ref} (Louis Segond 1910)\n\n"
            f"📖 Lire le chapitre : {chapter_url(livre, ch)}\n"
            f"⏳ Tous les versets sur les derniers temps : https://labible.app/versets/{SLUG}\n"
            f"📱 La Bible complète, gratuite et sans publicité : https://labible.app\n\n"
            f"#Shorts #DerniersTemps #RetourDeJésus #Bible #ParoleDeDieu #LSG1910")


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


def assurer_playlist(yt):
    """Cree la playlist de la serie si elle manque, et la note dans playlists_themes.json."""
    etat = yt_themes.etat()
    if (etat.get(SLUG) or {}).get("id"):
        return etat[SLUG]["id"]
    titre = yt_themes.titre_playlist(SLUG)
    req, trouve = yt.playlists().list(part="snippet", mine=True, maxResults=50), None
    while req is not None and not trouve:
        rep = req.execute()
        for it in rep.get("items", []):
            if " ".join(it["snippet"]["title"].split()) == " ".join(titre.split()):
                trouve = it["id"]
        req = yt.playlists().list_next(req, rep)
    pid = trouve or yt.playlists().insert(part="snippet,status", body={
        "snippet": {"title": titre, "description": yt_themes.description(SLUG), "defaultLanguage": "fr"},
        "status": {"privacyStatus": "public"}}).execute()["id"]
    etat[SLUG] = {"id": pid, "seo": 1}
    with open(yt_themes.ETAT, "w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print(f"➕ Playlist {'retrouvée' if trouve else 'créée'} : {titre}")
    return pid


def upload(video, ref, texte, livre, ch):
    from googleapiclient.http import MediaFileUpload
    import yt_commentaire
    yt = youtube()
    body = {"snippet": {"title": titre_video(ref), "description": description(ref, texte, livre, ch),
                        "tags": ["Bible", "derniers temps", "fin des temps", "retour de Jésus",
                                 "prophétie", "Apocalypse", "Louis Segond", "LSG1910", "Shorts"],
                        "categoryId": "22", "defaultLanguage": "fr"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    vid = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(video, mimetype="video/mp4", resumable=True)
                             ).execute()["id"]
    print(f"✅ YouTube : https://youtube.com/watch?v={vid}")
    try:
        assurer_playlist(yt)
    except Exception as e:
        print(f"⚠️  Playlist de la série non créée : {str(e)[:200]}")
    import time
    time.sleep(8)   # une playlist toute neuve n'est pas lisible tout de suite
    yt_themes.ranger_reference(yt, vid, ref)
    yt_commentaire.commenter(yt, vid, f"https://labible.app/versets/{SLUG}", ref=ref)
    return vid


# ─────────────────────────────────────────────────────────────────────────────
def main():
    refs = refs_du_theme()
    progress = None
    if len(sys.argv) > 1:
        ref = " ".join(sys.argv[1:])
    else:
        progress = load_json(PROGRESS_FILE) if os.path.exists(PROGRESS_FILE) else {}
        i = int(progress.get("index", 0) or 0) % len(refs)
        ref = refs[i]
        print(f"⏳ {i + 1}/{len(refs)}")
    try:
        livre, ch, v, texte = lire_verset(ref)
        print(f"📖 {ref} : {texte[:90]}")
        video = faire_video(livre, ch, v, texte, ref, "derniers_temps.mp4")
        print(f"✅ Vidéo : {video}")
    except Exception as e:
        signaler_echec("Derniers temps (vidéo)", f"{type(e).__name__} : {e}")
        finaliser("derniers temps")
        sys.exit(1)

    if ESSAI:
        os.makedirs("echantillons", exist_ok=True)
        shutil.copy(video, "echantillons/")
        with open("echantillons/description.txt", "w", encoding="utf-8") as f:
            f.write(titre_video(ref) + "\n\n" + description(ref, texte, livre, ch))
        print("🧪 ESSAI : rien n'est publié.")
        return

    vid = publier("YouTube Derniers temps", upload, video, ref, texte, livre, ch)
    if vid:
        videos = load_json(VIDEOS_FILE) if os.path.exists(VIDEOS_FILE) else {}
        videos[ref] = vid
        save_json(VIDEOS_FILE, videos)
        if progress is not None:
            progress["index"] = int(progress.get("index", 0) or 0) + 1
            save_json(PROGRESS_FILE, progress)
            print(f"💾 Prochain verset : {progress['index'] % len(refs) + 1}/{len(refs)}")
    finaliser("derniers temps")


if __name__ == "__main__":
    main()
