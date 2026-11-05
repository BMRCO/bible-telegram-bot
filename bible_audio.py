"""
bible_audio.py
==============
La Bible entiere lue a voix haute sur YouTube : un chapitre = une video.

Voix Henri (la meme que la serie des Psaumes, voir psaume_meditation.py),
musique douce sous la voix, texte du verset a l'ecran le temps de sa lecture.
Ordre : les quatre Evangiles (Marc, Matthieu, Luc, Jean), le reste du Nouveau
Testament, puis l'Ancien Testament. Les Psaumes sont exclus : la serie narree
quotidienne les couvre deja.

Ne publie que sur YouTube.

Usage :
    python bible_audio.py                 -> chapitre suivant (progression)
    python bible_audio.py Marc 1          -> chapitre precis (ne touche pas a la progression)
    ESSAI=1 python bible_audio.py Marc 1  -> video dans echantillons/, rien n'est publie

Etat : progress_bible_audio.json ({"index": N} = rang du prochain chapitre).
Le texte biblique n'est jamais modifie : seules des copies en memoire sont
nettoyees pour l'affichage et la synthese.
"""

import os
import sys
import random
import shutil
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from bot import (
    load_json, save_json, clean_text, slugify_book,
    BIBLE_FILE, APP_URL, WATERMARK,
    FONT_SERIF, FONT_SERIF_BOLD, FONT_SANS,
    signaler_echec, publier, finaliser,
)
from psaume_meditation import (
    synthese, texte_a_lire, gradient_bg, wrap, autosize_font, ease, lerp_color,
    pick_safe_music, vignette_audio, PSAUME_PALETTES,
    FPS, SR, LEAD, TAIL, SECS_VERSE_MIN, VOLUME_MUSIQUE,
)

YT_CLIENT_ID     = os.environ.get("YOUTUBE_CLIENT_ID", "")
YT_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YT_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

ESSAI = os.environ.get("ESSAI", "") == "1"
PROGRESS_FILE = "progress_bible_audio.json"

W, H = 1920, 1080
FADE = 0.8
SECS_INTRO_MIN = 5
SECS_OUTRO = 5
TITLE_SUFFIX = "Lecture Audio | Bible LSG1910"

# ─── Ordre de lecture (nom du livre tel qu'il est dans lsg1910.json) ───
NT = ["Marc", "Matthieu", "Luc", "Jean", "Actes", "Romains", "1 Corinthiens",
      "2 Corinthiens", "Galates", "Éphésiens", "Philippiens", "Colossiens",
      "1 Thessaloniciens", "2 Thessaloniciens", "1 Timothée", "2 Timothée",
      "Tite", "Philémon", "Hébreux", "Jacques", "1 Pierre", "2 Pierre",
      "1 Jean", "2 Jean", "3 Jean", "Jude", "Apocalypse"]
AT = ["Genèse", "Exode", "Lévitique", "Nombres", "Deutéronome", "Josué",
      "Juges", "Ruth", "1 Samuel", "2 Samuel", "1 Rois", "2 Rois",
      "1 Chroniques", "2 Chroniques", "Esdras", "Néhémie", "Esther", "Job",
      "Proverbes", "Ecclésiaste", "Cantique Des Cantiqu", "Ésaïe", "Jérémie",
      "Lamentations", "Ézéchiel", "Daniel", "Osée", "Joël", "Amos", "Abdias",
      "Jonas", "Michée", "Nahum", "Habacuc", "Sophonie", "Aggée", "Zacharie",
      "Malachie"]
ORDRE = NT + AT   # « Psaume » volontairement absent

# Nom affiche (titres, URL) quand il differe du fichier, qui tronque ce titre.
NOM_AFFICHE = {"Cantique Des Cantiqu": "Cantique des Cantiques"}

# Nom complet, lu par la voix et ecrit sous le titre de la vignette.
# Les livres numerotes doivent etre ecrits en toutes lettres, sinon la voix
# lit « un Corinthiens ».
NOM_COMPLET = {
    "Matthieu": "Évangile selon Matthieu", "Marc": "Évangile selon Marc",
    "Luc": "Évangile selon Luc", "Jean": "Évangile selon Jean",
    "Actes": "Actes des Apôtres",
    "Romains": "Épître aux Romains",
    "1 Corinthiens": "Première épître aux Corinthiens",
    "2 Corinthiens": "Deuxième épître aux Corinthiens",
    "Galates": "Épître aux Galates", "Éphésiens": "Épître aux Éphésiens",
    "Philippiens": "Épître aux Philippiens", "Colossiens": "Épître aux Colossiens",
    "1 Thessaloniciens": "Première épître aux Thessaloniciens",
    "2 Thessaloniciens": "Deuxième épître aux Thessaloniciens",
    "1 Timothée": "Première épître à Timothée",
    "2 Timothée": "Deuxième épître à Timothée",
    "Tite": "Épître à Tite", "Philémon": "Épître à Philémon",
    "Hébreux": "Épître aux Hébreux", "Jacques": "Épître de Jacques",
    "1 Pierre": "Première épître de Pierre", "2 Pierre": "Deuxième épître de Pierre",
    "1 Jean": "Première épître de Jean", "2 Jean": "Deuxième épître de Jean",
    "3 Jean": "Troisième épître de Jean", "Jude": "Épître de Jude",
    "Apocalypse": "Apocalypse",
    "1 Samuel": "Premier livre de Samuel", "2 Samuel": "Deuxième livre de Samuel",
    "1 Rois": "Premier livre des Rois", "2 Rois": "Deuxième livre des Rois",
    "1 Chroniques": "Premier livre des Chroniques",
    "2 Chroniques": "Deuxième livre des Chroniques",
    "Cantique Des Cantiqu": "Cantique des Cantiques",
}


def nom_affiche(livre):
    return NOM_AFFICHE.get(livre, livre)


def nom_complet(livre):
    return NOM_COMPLET.get(livre, nom_affiche(livre))


def chapter_url(livre, ch):
    return f"{APP_URL}/lsg/{slugify_book(nom_affiche(livre))}/{ch}"


def charger_bible():
    data = load_json(BIBLE_FILE)["verses"]
    par_chap = {}
    for v in data:
        par_chap.setdefault((v["book_name"], int(v["chapter"])), []).append(
            (int(v["verse"]), v["text"]))
    for k in par_chap:
        par_chap[k].sort()
    return par_chap


def liste_chapitres(par_chap):
    out = []
    for livre in ORDRE:
        chs = sorted(c for (b, c) in par_chap if b == livre)
        if not chs:
            raise RuntimeError(f"livre introuvable dans la Bible : {livre}")
        out += [(livre, c) for c in chs]
    return out


def texte_affiche(t):
    """Copie d'affichage : nettoyage typographique seulement (clean_text)."""
    return clean_text(t).rstrip(".")


# ─────────────────────────────────────────────────────────────────────────────
#  Video
# ─────────────────────────────────────────────────────────────────────────────
def faire_video(livre, ch, versets, rang):
    """Rend la video du chapitre. Retourne (chemin_mp4, timeline)."""
    BG_TOP, BG_BOTTOM, GOLD, GOLD_BRIGHT, WHITE, SIL = PSAUME_PALETTES[ORDRE.index(livre) % len(PSAUME_PALETTES)]
    n = len(versets)

    # ─── Narration : une synthese par verset ───
    os.makedirs("narration", exist_ok=True)
    intro_lue = f"{nom_complet(livre)}. Chapitre {ch}."
    voix_intro = synthese(intro_lue, "narration/intro")
    voix = []
    for i, (vn, vt) in enumerate(versets):
        voix.append(synthese(texte_a_lire(texte_affiche(vt)), f"narration/v{i:03d}"))
        print(f"  🎙️  {i + 1}/{n}", end="\r")
    print()

    T_INTRO = 1.0
    intro_secs = max(SECS_INTRO_MIN, T_INTRO + len(voix_intro) / SR + 1.5)
    durees = [max(SECS_VERSE_MIN, LEAD + len(a) / SR + TAIL) for a in voix]
    debuts, t = [], intro_secs
    for d in durees:
        debuts.append(t)
        t += d
    fin_versets = t
    total = fin_versets + SECS_OUTRO
    n_frames = int(round(total * FPS))

    piste = np.zeros(int(total * SR) + SR, dtype=np.float32)

    def poser(audio, a):
        i0 = int(a * SR)
        piste[i0:i0 + len(audio)] += audio

    poser(voix_intro, T_INTRO)
    for d0, a in zip(debuts, voix):
        poser(a, d0 + LEAD)
    piste = piste[:int(total * SR)]
    wav_path = "narration/narration.wav"
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(piste, -1, 1) * 32767).astype(np.int16).tobytes())

    # ─── Mise en page ───
    BORDER, CARD_PAD = 80, 120
    MAX_TW = W - BORDER * 2 - CARD_PAD * 2
    max_text_h = int((H - BORDER * 2) * 0.55)
    fond = gradient_bg(W, H, BG_TOP, BG_BOTTOM)
    ImageDraw.Draw(fond).rounded_rectangle(
        [BORDER, BORDER, W - BORDER, H - BORDER], radius=24,
        outline=tuple(int(c * 0.7) for c in GOLD), width=2)

    d_tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    layouts = []
    for vn, vt in versets:
        fv, lines, lh = autosize_font(d_tmp, f"« {texte_affiche(vt)} »", MAX_TW, max_text_h)
        layouts.append((vn, fv, lines, lh))

    f_livre  = ImageFont.truetype(FONT_SERIF_BOLD, 96)
    f_chap   = ImageFont.truetype(FONT_SERIF, 54)
    f_small  = ImageFont.truetype(FONT_SERIF, 34)
    f_vnum   = ImageFont.truetype(FONT_SERIF_BOLD, 48)
    f_ref    = ImageFont.truetype(FONT_SERIF, 42)
    f_wm     = ImageFont.truetype(FONT_SANS, 32)
    f_outro  = ImageFont.truetype(FONT_SERIF_BOLD, 110)
    f_osub   = ImageFont.truetype(FONT_SERIF, 38)

    titre_carte = nom_complet(livre)
    for size in range(96, 50, -4):
        f = ImageFont.truetype(FONT_SERIF_BOLD, size)
        if d_tmp.textlength(titre_carte, font=f) <= W - 2 * BORDER - 160:
            f_livre = f
            break

    def centre(draw, y, txt, font, col):
        bb = draw.textbbox((0, 0), txt, font=font)
        draw.text(((W - (bb[2] - bb[0])) // 2, y), txt, font=font, fill=col)

    # ─── Rendu : images brutes envoyees a ffmpeg par un tube ───
    out = f"bible_audio_{slugify_book(nom_affiche(livre))}_{ch}.mp4"
    music = pick_safe_music(rang + 1)
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", wav_path]
    if music:
        cmd += ["-stream_loop", "-1", "-i", music, "-filter_complex",
                f"[2:a]volume={VOLUME_MUSIQUE},afade=t=out:st={max(0.0, total - 3):.2f}:d=3[m];"
                f"[1:a][m]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
            "-pix_fmt", "yuv420p", "-crf", "22", "-c:a", "aac", "-b:a", "160k",
            "-shortest", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    cache = {}   # (etat, alpha arrondi) -> octets : les images fixes ne sont dessinees qu'une fois
    import bisect
    for f in range(n_frames):
        s = f / FPS
        if s < intro_secs:
            a = ease(s) if s < 1 else (ease(intro_secs - s) if s > intro_secs - 1 else 1.0)
            cle = ("intro", round(a, 2))
        elif s < fin_versets:
            i = min(bisect.bisect_right(debuts, s) - 1, n - 1)
            ls, du = s - debuts[i], durees[i]
            a = ease(ls / FADE) if ls < FADE else (ease((du - ls) / FADE) if ls > du - FADE else 1.0)
            cle = ("v", i, round(a, 2))
        else:
            a = ease(s - fin_versets) if s - fin_versets < 1 else 1.0
            cle = ("outro", round(a, 2))

        if cle not in cache:
            img = fond.copy()
            dr = ImageDraw.Draw(img)
            a = cle[-1]
            if cle[0] == "intro":
                y = H // 2 - 150
                centre(dr, y, titre_carte, f_livre, lerp_color(BG_TOP, GOLD_BRIGHT, a))
                y += f_livre.size + 34
                centre(dr, y, f"Chapitre {ch}", f_chap, lerp_color(BG_TOP, WHITE, a))
                y += f_chap.size + 50
                dr.line([((W - 360) // 2, y), ((W + 360) // 2, y)], fill=lerp_color(BG_TOP, SIL, a * 0.8), width=1)
                centre(dr, y + 24, "Bible Louis Segond 1910", f_small, lerp_color(BG_TOP, SIL, a * 0.8))
            elif cle[0] == "v":
                vn, fv, lines, lh = layouts[cle[1]]
                dr.text((BORDER + 60, BORDER + 50), str(vn), font=f_vnum, fill=lerp_color(BG_TOP, GOLD, a * 0.85))
                ty = BORDER + (H - BORDER * 2) // 2 - lh * len(lines) // 2
                c_txt = lerp_color(BG_TOP, WHITE, a)
                c_sh = tuple(int(BG_TOP[k] * (1 - a * 0.5)) for k in range(3))
                for line in lines:
                    bb = dr.textbbox((0, 0), line, font=fv)
                    x = (W - (bb[2] - bb[0])) // 2
                    dr.text((x + 2, ty + 2), line, font=fv, fill=c_sh)
                    dr.text((x, ty), line, font=fv, fill=c_txt)
                    ty += lh
                c_ref = lerp_color(BG_TOP, GOLD, a * 0.7)
                dr.text((BORDER + CARD_PAD, H - BORDER - 70), f"{nom_affiche(livre)} {ch}:{vn}", font=f_ref, fill=c_ref)
                wm = dr.textbbox((0, 0), WATERMARK, font=f_wm)
                dr.text((W - BORDER - CARD_PAD - (wm[2] - wm[0]), H - BORDER - 65), WATERMARK, font=f_wm, fill=c_ref)
            else:
                centre(dr, H // 2 - 130, "Méditez la Parole chaque jour", f_ref, lerp_color(BG_TOP, SIL, a * 0.7))
                centre(dr, H // 2 - 30, "LaBible.app", f_outro, lerp_color(BG_TOP, GOLD_BRIGHT, a))
                centre(dr, H // 2 + 110, "Gratuit · Sans publicité · LSG 1910", f_osub, lerp_color(BG_TOP, SIL, a * 0.7))
            if len(cache) > 400:
                cache.clear()
            cache[cle] = img.tobytes()
        proc.stdin.write(cache[cle])

    proc.stdin.close()
    err = proc.stderr.read().decode(errors="replace")
    proc.wait()
    shutil.rmtree("narration", ignore_errors=True)
    if proc.returncode != 0 or not os.path.exists(out):
        raise RuntimeError(f"ffmpeg : {err[-300:]}")
    print(f"✅ Vidéo : {out} ({total / 60:.1f} min)")
    return out, {"debuts": debuts, "durees": durees, "versets": versets, "total": total}


# ─────────────────────────────────────────────────────────────────────────────
#  Textes YouTube
# ─────────────────────────────────────────────────────────────────────────────
def _hms(t, srt=False):
    t = max(0.0, t)
    h, m, sec = int(t // 3600), int(t % 3600 // 60), t % 60
    if srt:
        return f"{h:02d}:{m:02d}:{int(sec):02d},{min(999, int(round((sec % 1) * 1000))):03d}"
    return f"{h}:{m:02d}:{int(sec):02d}" if h else f"{m}:{int(sec):02d}"


def chapitres(tl):
    """Chapitres YouTube : 0:00 d'abord, au moins 3, 10 s minimum chacun."""
    groupes, cur = [], None
    for i, (d0, du) in enumerate(zip(tl["debuts"], tl["durees"])):
        if cur is None:
            cur = [i, i, 0.0 if not groupes else d0]
        cur[1] = i
        if d0 + du - cur[2] >= 15:
            groupes.append(cur)
            cur = None
    if cur is not None:
        if groupes and tl["total"] - cur[2] < 10:
            groupes[-1][1] = cur[1]
        else:
            groupes.append(cur)
    if len(groupes) < 3:
        return ""
    lignes = []
    for a, b, t0 in groupes:
        va, vb = tl["versets"][a][0], tl["versets"][b][0]
        mots = texte_a_lire(texte_affiche(tl["versets"][a][1])).split()
        debut = " ".join(mots[:6]) + ("…" if len(mots) > 6 else "")
        lignes.append(f"{_hms(t0)} v. {va}" + ("" if va == vb else f"-{vb}") + f" · {debut}")
    return "\n".join(lignes)


def srt(tl, path):
    blocs = []
    for i, ((vn, vt), d0, du) in enumerate(zip(tl["versets"], tl["debuts"], tl["durees"]), 1):
        blocs.append(f"{i}\n{_hms(d0 + LEAD - 0.2, True)} --> {_hms(d0 + du - FADE, True)}\n"
                     f"{texte_a_lire(texte_affiche(vt))}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(blocs))
    return path


def titre_video(livre, ch):
    return f"{nom_affiche(livre)} {ch} | {TITLE_SUFFIX}"


def description(livre, ch, tl):
    url = chapter_url(livre, ch)
    nom = nom_affiche(livre)
    tag = "".join(c for c in nom.title() if c.isalnum())
    versets_txt = "\n".join(f"{nom} {ch}:{vn} · {texte_affiche(vt)}." for vn, vt in tl["versets"])
    ch_txt = chapitres(tl)
    desc = (
        f"{nom} chapitre {ch} lu à voix haute, en entier ({nom_complet(livre)}).\n"
        f"Bible Louis Segond 1910 (LSG 1910), texte intégral, sans commentaire. "
        f"Voix de synthèse, musique douce.\n\n"
        f"📖 Lire {nom} {ch} gratuitement : {url}\n\n"
        + (f"━━━━━━━━━━━━━━━━━━━━━\n{ch_txt}\n\n" if ch_txt else "")
        + f"━━━━━━━━━━━━━━━━━━━━━\n\n{versets_txt}\n\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔔 Abonnez-vous : la Bible entière, lue chapitre après chapitre.\n"
        f"🔗 {APP_URL}/liens\n\n"
        f"#{tag}{ch} #BibleAudio #Bible #LSG1910 #ParoleDeDieu #LaBibleApp"
    )
    if len(desc) > 5000:
        exces = len(desc) - 5000 + 40
        coupe = versets_txt[:max(0, len(versets_txt) - exces)]
        coupe = coupe[:coupe.rfind("\n")] if "\n" in coupe else coupe
        desc = desc.replace(versets_txt, coupe + f"\n… (suite : {url})")[:5000]
    return desc


def tags(livre, ch):
    nom = nom_affiche(livre)
    t = [f"{nom} {ch}", f"{nom} {ch} audio", f"{nom} {ch} lecture", f"{nom} chapitre {ch}",
         nom_complet(livre), f"{nom} Louis Segond", "Bible audio", "Bible audio français",
         "Bible Louis Segond 1910", "LSG 1910", "lecture de la Bible", "Parole de Dieu",
         "Bible en français"]
    while len(",".join(t)) > 480:
        t.pop()
    return t


# ─────────────────────────────────────────────────────────────────────────────
#  YouTube
# ─────────────────────────────────────────────────────────────────────────────
def upload(video, livre, ch, tl, rang):
    if not (YT_CLIENT_ID and YT_CLIENT_SECRET and YT_REFRESH_TOKEN):
        raise RuntimeError("identifiants OAuth YouTube vides ou absents")
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.auth.transport.requests import Request

    creds = Credentials(token=None, refresh_token=YT_REFRESH_TOKEN, client_id=YT_CLIENT_ID,
                        client_secret=YT_CLIENT_SECRET, token_uri="https://oauth2.googleapis.com/token",
                        scopes=["https://www.googleapis.com/auth/youtube.upload"])
    creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {"title": titre_video(livre, ch), "description": description(livre, ch, tl),
                    "tags": tags(livre, ch), "categoryId": "22",
                    "defaultLanguage": "fr", "defaultAudioLanguage": "fr"},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(video, mimetype="video/mp4",
                                                        resumable=True, chunksize=4 * 1024 * 1024))
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"  ⏳ Upload : {int(status.progress() * 100)}%")
    vid = resp["id"]
    print(f"✅ YouTube : https://youtube.com/watch?v={vid}")

    try:
        thumb = vignette_audio(rang + 1, out="thumb_bible.png",
                               titre=f"{nom_affiche(livre)} {ch}", sous_titre=nom_complet(livre))
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb, mimetype="image/png")).execute()
        print("✅ Vignette définie")
    except Exception as e:
        print(f"⚠️  Vignette non définie : {str(e)[:200]}")

    # Sous-titres et playlist du livre : demandent le scope youtube.force-ssl.
    # Avec le jeton actuel (youtube.upload) : 403, simple avertissement.
    try:
        yt.captions().insert(
            part="snippet",
            body={"snippet": {"videoId": vid, "language": "fr", "name": "Français", "isDraft": False}},
            media_body=MediaFileUpload(srt(tl, "chapitre.srt"), mimetype="application/octet-stream"),
        ).execute()
        print("✅ Sous-titres envoyés")
    except Exception as e:
        print(f"⚠️  Sous-titres non envoyés (scope OAuth ?) : {str(e)[:160]}")
    try:
        nom_pl = f"📖 {nom_affiche(livre)} | Bible audio LSG 1910"
        pl = None
        r = yt.playlists().list(part="snippet", mine=True, maxResults=50)
        while r is not None and pl is None:
            res = r.execute()
            pl = next((it["id"] for it in res.get("items", []) if it["snippet"]["title"] == nom_pl), None)
            r = yt.playlists().list_next(r, res)
        if pl is None:
            pl = yt.playlists().insert(part="snippet,status", body={
                "snippet": {"title": nom_pl, "defaultLanguage": "fr",
                            "description": f"{nom_complet(livre)}, lu à voix haute chapitre après chapitre, "
                                           f"dans le texte de la Bible Louis Segond 1910 (domaine public), "
                                           f"sans commentaire ajouté. Texte complet gratuit sur LaBible.app."},
                "status": {"privacyStatus": "public"}}).execute()["id"]
        yt.playlistItems().insert(part="snippet", body={"snippet": {
            "playlistId": pl, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
        print("✅ Ajoutée à la playlist du livre")
    except Exception as e:
        print(f"⚠️  Playlist non mise à jour (scope OAuth ?) : {str(e)[:160]}")
    return vid


# ─────────────────────────────────────────────────────────────────────────────
def main():
    par_chap = charger_bible()
    chapitres_ordre = liste_chapitres(par_chap)
    args = sys.argv[1:]
    progress = None
    if args:
        livre, ch = " ".join(args[:-1]), int(args[-1])
        livre = {v: k for k, v in NOM_AFFICHE.items()}.get(livre, livre)
        if (livre, ch) not in par_chap or livre not in ORDRE:
            sys.exit(f"Chapitre introuvable : {livre} {ch}")
        rang = chapitres_ordre.index((livre, ch))
    else:
        progress = load_json(PROGRESS_FILE) if os.path.exists(PROGRESS_FILE) else {}
        rang = int(progress.get("index", 0) or 0)
        if rang >= len(chapitres_ordre):
            print("🏁 Toute la Bible a été publiée.")
            return
        livre, ch = chapitres_ordre[rang]
    print(f"📖 {nom_affiche(livre)} {ch} ({rang + 1}/{len(chapitres_ordre)})")

    try:
        video, tl = faire_video(livre, ch, par_chap[(livre, ch)], rang)
    except Exception as e:
        signaler_echec("Bible audio (vidéo)", f"{type(e).__name__} : {e}")
        finaliser("bible audio")
        sys.exit(1)

    if ESSAI:
        os.makedirs("echantillons", exist_ok=True)
        shutil.copy(video, "echantillons/")
        srt(tl, f"echantillons/{os.path.splitext(os.path.basename(video))[0]}.srt")
        with open("echantillons/description.txt", "w", encoding="utf-8") as f:
            f.write(titre_video(livre, ch) + "\n\n" + description(livre, ch, tl))
        vignette_audio(rang + 1, out="echantillons/vignette.png",
                       titre=f"{nom_affiche(livre)} {ch}", sous_titre=nom_complet(livre))
        print("🧪 ESSAI : rien n'est publié.")
        return

    vid = publier("YouTube Bible audio", upload, video, livre, ch, tl, rang)
    # La progression n'avance que si la video est en ligne : sinon le meme
    # chapitre est retente au prochain passage (quota YouTube epuise, etc.).
    if vid and progress is not None:
        progress["index"] = rang + 1
        save_json(PROGRESS_FILE, progress)
        print(f"💾 Prochain chapitre : {rang + 2}/{len(chapitres_ordre)}")
    finaliser("bible audio")


if __name__ == "__main__":
    main()
