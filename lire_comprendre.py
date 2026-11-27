#!/usr/bin/env python3
"""
LaBible.app : serie « Lire et comprendre la Bible » (idee de BC, 27 nov. 2026).

Un episode de 60 a 90 s explique un detail concret du texte et montre ou il
se trouve, pour que la personne ouvre sa Bible et suive. Format vertical :
une image filmee en haut (Pixabay, choisie pour chaque verset), le texte en
bas, aligne a gauche, avec le passage commente en dore.

Le texte biblique vient toujours de bible/lsg1910.json (passe par clean_text,
« Éternel » accentue) ; il n'est jamais recopie a la main dans l'episode.
Chaque passage surligne doit se trouver dans le verset : sinon l'episode
s'arrete avant toute video.

Usage : python lire_comprendre.py <id episode>   (ESSAI=1 : rien n'est publie)
"""
import json
import os
import re
import subprocess
import sys
import unicodedata

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from bot import clean_text, strip_rubric, BOOK_NAME_MAP
import psaume_meditation as pm

W, H, FPS = 1080, 1920, 30
HAUT_IMAGE = 1120                     # hauteur de la zone filmee
MARGE = 84
FOND = (11, 17, 15)
OR = (235, 196, 96)
BLANC = (240, 236, 226)
GRIS = (150, 156, 150)
SERIF = "fonts/EBGaramond-Regular.ttf"
SERIF_IT = "fonts/EBGaramond-Italic.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANS_GRAS = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
EPISODES = "lire_comprendre.json"
SORTIE = "echantillons"
TEST_LOCAL = os.environ.get("TEST_LOCAL") == "1"   # sans voix ni reseau


def norm(s):
    s = s.replace("’", "'").replace(" ", " ").replace(" ", " ")
    return unicodedata.normalize("NFC", s).lower()


# ─── Texte biblique ──────────────────────────────────────────────────────────
_BIBLE = None


def verset(ref):
    """« Psaumes 23:4 » -> texte LSG 1910 mis en forme par clean_text."""
    global _BIBLE
    if _BIBLE is None:
        _BIBLE = json.load(open("bible/lsg1910.json", encoding="utf-8"))["verses"]
    m = re.match(r"^(.+?) (\d+):(\d+)$", ref)
    livre, ch, v = m.group(1), int(m.group(2)), int(m.group(3))
    livre = BOOK_NAME_MAP.get(livre, livre)
    for x in _BIBLE:
        if x["book_name"] == livre and x["chapter"] == ch and x["verse"] == v:
            return clean_text(strip_rubric(x["text"]))
    raise ValueError(f"verset introuvable : {ref}")


def spans(texte, passages):
    """Positions des passages a surligner ; erreur si l'un manque."""
    t = norm(texte)
    out = []
    for p in passages:
        i = t.find(norm(p))
        if i < 0:
            raise ValueError(f"« {p} » n'est pas dans : {texte}")
        out.append((i, i + len(p)))
    return out


# ─── Calques ─────────────────────────────────────────────────────────────────
def police(chemin, taille):
    return ImageFont.truetype(chemin, taille)


def mots_avec_or(texte, zones):
    """[(mot, en_or)] : un mot est dore s'il touche une zone surlignee."""
    out = []
    for m in re.finditer(r"\S+", texte):
        mot = m.group()
        dore = any(a < m.end() and m.start() < b for a, b in zones)
        # ponctuation francaise (« ; : ! ? ») jamais seule en debut de ligne,
        # guillemet ouvrant jamais seul en fin de ligne : espace insecable
        if out and re.fullmatch(r"[;:!?»]+", mot):
            out[-1] = (out[-1][0] + "\u00a0" + mot, out[-1][1])
            continue
        if out and out[-1][0] == "«":
            out[-1] = ("«\u00a0" + mot, dore)
            continue
        out.append((mot, dore))
    return out


def composer_lignes(d, mots, f, largeur):
    lignes, cur, lc = [], [], 0
    esp = d.textlength(" ", font=f)
    for mot, dore in mots:
        lm = d.textlength(mot, font=f)
        if cur and lc + esp + lm > largeur:
            lignes.append(cur)
            cur, lc = [], 0
        cur.append((mot, dore, lm))
        lc += (esp if len(cur) > 1 else 0) + lm
    if cur:
        lignes.append(cur)
    return lignes, esp


def calque(seg, ep):
    """Image RGBA plein cadre : degrade sous la video, bandeau, verset."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = np.zeros((H, W, 4), dtype=np.uint8)
    px[..., :3] = FOND
    # haut transparent, fondu vers le fond de 820 a HAUT_IMAGE, puis plein
    alpha = np.zeros(H, dtype=np.float32)
    y0 = HAUT_IMAGE - 300
    alpha[y0:HAUT_IMAGE] = np.linspace(0, 1, HAUT_IMAGE - y0) ** 1.4
    alpha[HAUT_IMAGE:] = 1
    alpha[:300] = np.maximum(alpha[:300], np.linspace(0.8, 0, 300) ** 0.8)   # lisibilite du bandeau
    px[..., 3] = (alpha[:, None] * 255).astype(np.uint8)
    im = Image.fromarray(px, "RGBA")
    d = ImageDraw.Draw(im)

    # bandeau de la serie, en haut a gauche
    for dx, dy, coul in ((2, 2, (0, 0, 0, 200)), (0, 0, None)):
        d.text((MARGE + dx, 92 + dy), "LIRE ET COMPRENDRE LA BIBLE", font=police(SANS_GRAS, 30),
               fill=coul or OR + (255,))
        d.text((MARGE + dx, 136 + dy), ep["titre_court"], font=police(SANS, 28),
               fill=coul or BLANC + (240,))

    y = HAUT_IMAGE - 120
    if seg.get("grand"):
        # une formule courte en grand (« il » → « tu »)
        f = police(SERIF, 132)
        d.text((MARGE, y + 150), seg["grand"], font=f, fill=OR + (255,))
        if seg.get("sous_grand"):
            d.text((MARGE, y + 340), seg["sous_grand"], font=police(SERIF_IT, 54), fill=BLANC + (255,))
    else:
        ref = seg["verset"]
        texte = verset(ref)
        zones = spans(texte, seg.get("surligne", []))
        d.text((MARGE, y), ref.upper(), font=police(SANS_GRAS, 32), fill=OR + (255,))
        d.line([MARGE, y + 52, MARGE + 90, y + 52], fill=OR + (200,), width=3)
        mots = mots_avec_or(f"« {texte} »", [(a + 2, b + 2) for a, b in zones])
        haut_dispo = H - 230 - (y + 100)
        for taille in range(74, 40, -2):
            f = police(SERIF, taille)
            lignes, esp = composer_lignes(d, mots, f, W - 2 * MARGE)
            pas = int(taille * 1.3)
            if len(lignes) * pas <= haut_dispo:
                break
        # bloc centre verticalement dans la zone du texte, aligne a gauche
        yy = y + 100 + max(0, (haut_dispo - len(lignes) * pas) // 3)
        for ligne in lignes:
            x = MARGE
            for k, (mot, dore, lm) in enumerate(ligne):
                d.text((x, yy), mot, font=f, fill=(OR if dore else BLANC) + (255,))
                if dore:
                    suite = k + 1 < len(ligne) and ligne[k + 1][1]
                    fin_trait = x + lm + (esp if suite else 0)
                    d.line([x, yy + int(taille * 1.08), fin_trait, yy + int(taille * 1.08)],
                           fill=OR + (150,), width=3)
                x += lm + esp
            yy += pas
    d.text((MARGE, H - 128), "LaBible.app", font=police(SANS_GRAS, 30), fill=OR + (230,))
    d.text((MARGE + 205, H - 126), "· Louis Segond 1910", font=police(SANS, 28), fill=GRIS + (255,))
    return im


def carte_finale(ep):
    im = Image.new("RGB", (W, H), FOND)
    d = ImageDraw.Draw(im)
    y = 700
    d.text((MARGE, y), ep["reference_finale"], font=police(SERIF, 96), fill=OR)
    d.text((MARGE, y + 140), "Louis Segond 1910", font=police(SERIF_IT, 58), fill=BLANC)
    d.line([MARGE, y + 250, MARGE + 120, y + 250], fill=OR, width=3)
    d.text((MARGE, y + 300), "LaBible.app", font=police(SERIF, 120), fill=OR)
    d.text((MARGE, y + 460), "La Bible gratuite, sans publicité", font=police(SANS, 34), fill=GRIS)
    return im


# ─── Son ─────────────────────────────────────────────────────────────────────
def voix(texte, base):
    if TEST_LOCAL:
        return np.zeros(int(pm.SR * max(1.5, len(texte.split()) * 0.36)), dtype=np.float32)
    return pm.synthese(pm.texte_a_lire(texte), base)


def ecrire_wav(sig, chemin):
    import wave
    with wave.open(chemin, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(pm.SR)
        w.writeframes((np.clip(sig, -1, 1) * 32767).astype(np.int16).tobytes())


# ─── Video ───────────────────────────────────────────────────────────────────
def telecharger(url, dossier):
    nom = os.path.join(dossier, "src_" + re.sub(r"[^0-9a-zA-Z_.]", "_", url.split("/")[-1]))
    if TEST_LOCAL:
        if not os.path.exists(nom):
            teinte = abs(hash(url)) % 360
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                            f"testsrc2=s=1920x1080:r=30:d=12,hue=h={teinte}", nom], check=True)
        return nom
    if not os.path.exists(nom):
        import requests
        r = requests.get(url, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        open(nom, "wb").write(r.content)
    return nom


def segment(i, seg, ep, dossier, duree):
    """Un fichier par segment : video recadree en haut, calque, fondu d'entree."""
    src = telecharger(seg["video"], dossier)
    cal = os.path.join(dossier, f"cal{i:02d}.png")
    calque(seg, ep).save(cal)
    tmp, out = os.path.join(dossier, f"seg{i:02d}.tmp.mp4"), os.path.join(dossier, f"seg{i:02d}.mp4")
    debut = float(seg.get("debut", 0))
    fc = (f"[0:v]scale={W}:{HAUT_IMAGE}:force_original_aspect_ratio=increase,"
          f"crop={W}:{HAUT_IMAGE},fps={FPS},setsar=1,"
          f"pad={W}:{H}:0:0:color=0x{FOND[0]:02x}{FOND[1]:02x}{FOND[2]:02x}[v];"
          f"[1:v]format=rgba,fade=t=in:st=0:d=0.45:alpha=1[c];"
          f"[v][c]overlay=0:0,fade=t=in:st=0:d=0.35:color=0x{FOND[0]:02x}{FOND[1]:02x}{FOND[2]:02x},"
          f"format=yuv420p[o]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-nostdin",
                    "-ss", str(debut), "-stream_loop", "-1", "-i", src, "-loop", "1", "-i", cal,
                    "-filter_complex", fc, "-map", "[o]", "-t", f"{duree:.3f}", "-an",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS), tmp],
                   check=True)
    os.replace(tmp, out)
    return out


def fin_video(ep, dossier, duree=4.0):
    png = os.path.join(dossier, "fin.png")
    carte_finale(ep).save(png)
    out = os.path.join(dossier, "seg99.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-nostdin", "-framerate", str(FPS),
                    "-i", png, "-vf", f"format=yuv420p,loop=-1:1,trim=duration={duree},fade=t=in:d=0.6",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS),
                    "-pix_fmt", "yuv420p", out], check=True)
    return out


def produire(ep):
    dossier = os.path.join("travail_lc", ep["id"])
    os.makedirs(dossier, exist_ok=True)
    # verifier tout le texte avant la moindre video
    for s in ep["segments"]:
        if not s.get("grand"):
            spans(verset(s["verset"]), s.get("surligne", []))
    pm.DEBIT_VOIX = ep.get("debit", "+0%")
    pistes, fichiers = [], []
    blanc_avant, blanc_apres = 0.25, 0.55
    for i, s in enumerate(ep["segments"]):
        v = voix(s["voix"], os.path.join(dossier, f"v{i:02d}"))
        sig = np.concatenate([np.zeros(int(pm.SR * blanc_avant), np.float32), v,
                              np.zeros(int(pm.SR * blanc_apres), np.float32)])
        n = int(round(len(sig) / pm.SR * FPS))           # duree calee sur une image entiere
        sig = np.pad(sig, (0, max(0, int(n / FPS * pm.SR) - len(sig))))[: int(n / FPS * pm.SR)]
        pistes.append(sig)
        fichiers.append(segment(i, s, ep, dossier, n / FPS))
        print(f"  segment {i + 1}/{len(ep['segments'])} : {n / FPS:.1f} s")
    fichiers.append(fin_video(ep, dossier))
    pistes.append(np.zeros(int(pm.SR * 4.0), np.float32))
    wav = os.path.join(dossier, "voix.wav")
    ecrire_wav(np.concatenate(pistes), wav)
    liste = os.path.join(dossier, "liste.txt")
    open(liste, "w").write("".join(f"file '{os.path.abspath(f)}'\n" for f in fichiers))
    muet = os.path.join(dossier, "muet.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", liste, "-c", "copy", muet], check=True)
    os.makedirs(SORTIE, exist_ok=True)
    final = os.path.join(SORTIE, f"lire_{ep['id']}.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", muet, "-i", wav,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                    "-af", "afade=t=out:st=0:d=0.01", "-shortest", "-movflags", "+faststart", final],
                   check=True)
    dur = len(np.concatenate(pistes)) / pm.SR
    print(f"✅ Episode {ep['id']} : {final} ({dur:.0f} s)")
    return final


def main():
    eps = json.load(open(EPISODES, encoding="utf-8"))
    cid = (sys.argv[1] if len(sys.argv) > 1 else "").strip() or eps[0]["id"]
    ep = next(e for e in eps if e["id"] == cid)
    final = produire(ep)
    # images de controle : milieu de chaque segment
    os.makedirs(SORTIE, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", final, "-vf",
                    "fps=1/6,scale=270:-1,tile=6x2", "-frames:v", "1",
                    os.path.join(SORTIE, f"lire_{ep['id']}_planche.jpg")], check=True)


if __name__ == "__main__":
    main()
