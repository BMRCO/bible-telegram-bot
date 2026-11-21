"""reel_scene.py : le reel des versets du jour, au visuel de la serie « Les derniers temps ».

Demande de BC (21 novembre 2026) : « Melhora o visual dos reels como os ultimos
temas ». Meme langage que derniers_temps.py : un ciel qui change lentement
pendant toute la video, en tete un pictogramme dore et le nom de la serie en
capitales espacees, le verset en EB Garamond creme, la reference en italique or,
puis le carton de cloture. Chaque categorie a son ciel et son pictogramme ;
le Psaume du soir est un crepuscule (la lumiere baisse), les autres une aube.

Rien n'est ajoute au texte biblique : le verset, sa reference, le nom de la serie.
Temps (regle du cahier, §5.10) : le verset s'efface a 10,2 s, le carton entre a
10,7 s et reste lisible de 11,2 s a 14,55 s.

    faire_reel(texte, ref, cat_name, sortie, musique=None)
"""
import hashlib
import math
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
DUREE = 15.0
FONT = "fonts/EBGaramond-Regular.ttf"
FONT_IT = "fonts/EBGaramond-Italic.ttf"
CREME = (244, 236, 218)

# ciel haut, ciel bas, lumiere de l'horizon, or, or pale, etoiles, pictogramme, soir ?
THEMES = {
    "protection": dict(titre="PROTECTION DIVINE", haut=(4, 8, 22), bas=(12, 22, 48),
                       lumiere=(224, 176, 104), etoiles=110, picto="bouclier", soir=False),
    "jesus":      dict(titre="PAROLES DE JÉSUS", haut=(16, 4, 8), bas=(40, 12, 20),
                       lumiere=(236, 160, 110), etoiles=70, picto="croix", soir=False),
    "psaume":     dict(titre="PSAUME DU SOIR", haut=(6, 4, 18), bas=(30, 16, 46),
                       lumiere=(214, 132, 120), etoiles=190, picto="lune", soir=True),
    "promise":    dict(titre="PROMESSES", haut=(3, 14, 16), bas=(10, 36, 38),
                       lumiere=(226, 198, 120), etoiles=80, picto="arc", soir=False),
    "proverbe":   dict(titre="SAGESSE BIBLIQUE", haut=(12, 10, 4), bas=(36, 28, 12),
                       lumiere=(232, 178, 92), etoiles=60, picto="lampe", soir=False),
    "prophetie":  dict(titre="PROPHÉTIES BIBLIQUES", haut=(4, 6, 20), bas=(18, 18, 48),
                       lumiere=(228, 186, 112), etoiles=140, picto="rouleau", soir=False),
}
THEME_DEFAUT = dict(titre="VERSET BIBLIQUE", haut=(6, 6, 14), bas=(20, 20, 36),
                    lumiere=(226, 190, 118), etoiles=90, picto="croix", soir=False)

OR = (226, 190, 118)
OR_PALE = (200, 172, 120)


def _font(path, size):
    return ImageFont.truetype(path, size)


def _texte_espace(d, cx, y, txt, font, fill, espace):
    largeurs = [d.textlength(c, font=font) for c in txt]
    x = cx - (sum(largeurs) + espace * (len(txt) - 1)) / 2
    for c, w in zip(txt, largeurs):
        d.text((x, y), c, font=font, fill=fill)
        x += w + espace


# ─── Pictogrammes (traits dores, 64 px de haut) ─────────────────────────────
def _picto(d, nom, cx, cy, h, c, lw=3):
    w = h * 0.7
    if nom == "bouclier":
        droite = [(cx, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy - h * 0.05)]
        for i in range(1, 13):
            t = i / 12
            droite.append((cx + w / 2 * math.cos(t * math.pi / 2), cy - h * 0.05 + h * 0.55 * math.sin(t * math.pi / 2)))
        gauche = [(2 * cx - x, y) for x, y in reversed(droite)]
        d.line(droite + gauche[1:], fill=c, width=lw, joint="curve")
        d.line([(cx, cy - h * 0.3), (cx, cy + h * 0.25)], fill=c, width=lw)
        d.line([(cx - w * 0.22, cy - h * 0.08), (cx + w * 0.22, cy - h * 0.08)], fill=c, width=lw)
    elif nom == "croix":
        d.line([(cx, cy - h / 2), (cx, cy + h / 2)], fill=c, width=lw + 1)
        d.line([(cx - w * 0.42, cy - h * 0.18), (cx + w * 0.42, cy - h * 0.18)], fill=c, width=lw + 1)
    elif nom == "lune":
        r = h * 0.46
        d.arc([cx - r, cy - r, cx + r, cy + r], 70, 290, fill=c, width=lw)
        r2 = r * 0.82
        ox = r * 0.42
        d.arc([cx - r2 + ox, cy - r2, cx + r2 + ox, cy + r2], 108, 252, fill=c, width=lw)
        for dx, dy, s in ((r * 1.25, -r * 0.7, 5), (r * 1.6, r * 0.1, 3)):
            d.line([(cx + dx - s, cy + dy), (cx + dx + s, cy + dy)], fill=c, width=2)
            d.line([(cx + dx, cy + dy - s), (cx + dx, cy + dy + s)], fill=c, width=2)
    elif nom == "arc":
        for k, r in enumerate((h * 0.55, h * 0.42, h * 0.29)):
            d.arc([cx - r, cy - r + h * 0.25, cx + r, cy + r + h * 0.25], 180, 360, fill=c, width=lw)
        d.line([(cx - h * 0.7, cy + h * 0.25), (cx + h * 0.7, cy + h * 0.25)], fill=c, width=2)
    elif nom == "lampe":
        # lampe a huile : corps en amande, bec, anse, flamme
        d.arc([cx - w * 0.55, cy - h * 0.05, cx + w * 0.45, cy + h * 0.45], 0, 180, fill=c, width=lw)
        d.line([(cx - w * 0.55, cy + h * 0.2), (cx + w * 0.45, cy + h * 0.2)], fill=c, width=lw)
        d.line([(cx + w * 0.45, cy + h * 0.2), (cx + w * 0.78, cy + h * 0.06)], fill=c, width=lw)
        d.arc([cx - w * 0.85, cy + h * 0.05, cx - w * 0.45, cy + h * 0.35], 90, 270, fill=c, width=lw)
        f = [(cx + w * 0.8, cy - h * 0.42), (cx + w * 0.92, cy - h * 0.12), (cx + w * 0.8, cy + h * 0.0),
             (cx + w * 0.68, cy - h * 0.12)]
        d.polygon(f, outline=c, fill=c)
    elif nom == "rouleau":
        d.rectangle([cx - w * 0.5, cy - h * 0.32, cx + w * 0.5, cy + h * 0.32], outline=c, width=lw)
        for s in (-1, 1):
            d.ellipse([cx + s * w * 0.5 - h * 0.09, cy - h * 0.42, cx + s * w * 0.5 + h * 0.09, cy + h * 0.42],
                      outline=c, width=lw)
        for k in (-0.12, 0.02, 0.16):
            d.line([(cx - w * 0.3, cy + h * k), (cx + w * 0.3, cy + h * k)], fill=c, width=2)


# ─── Calques ────────────────────────────────────────────────────────────────
def calque_tete(th):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    _picto(d, th["picto"], W / 2, 236, 64, OR)
    t = 46
    while t > 30 and sum(d.textlength(ch, font=_font(FONT, t)) for ch in th["titre"]) + 9 * len(th["titre"]) > W - 160:
        t -= 2
    _texte_espace(d, W / 2, 300, th["titre"], _font(FONT, t), OR, 9)
    d.line([(W / 2 - 150, 384), (W / 2 + 150, 384)], fill=OR_PALE + (150,), width=2)
    return img


def calque_verset(texte, ref, wrap):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    marge, taille = 120, 74
    while taille > 36:
        f = _font(FONT, taille)
        lignes = wrap(d, texte, f, W - 2 * marge)
        lh = int(taille * 1.32)
        if lh * len(lignes) <= 860:
            break
        taille -= 2
    f = _font(FONT, taille)
    lignes = wrap(d, texte, f, W - 2 * marge)
    lh = int(taille * 1.32)
    fr = _font(FONT_IT, 50)
    hauteur = lh * len(lignes) + 46 + 60
    y = 470 + (900 - hauteur) / 2
    for l in lignes:
        d.text(((W - d.textlength(l, font=f)) / 2, y), l, font=f, fill=CREME)
        y += lh
    y += 46
    d.text(((W - d.textlength(ref, font=fr)) / 2, y), ref, font=fr, fill=OR)
    fs = _font(FONT, 34)
    sig = "LaBible.app · LSG 1910"
    d.text(((W - d.textlength(sig, font=fs)) / 2, 1500), sig, font=fs, fill=OR_PALE)
    return img


def calque_fin(ligne):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f1, f2, f3 = _font(FONT_IT, 44), _font(FONT, 92), _font(FONT, 38)
    for txt, f, y, c in ((ligne, f1, 760, CREME), ("LaBible.app", f2, 830, OR),
                         ("Gratuit · Sans publicité · LSG 1910", f3, 968, OR_PALE)):
        d.text(((W - d.textlength(txt, font=f)) / 2, y), txt, font=f, fill=c)
    return img


def _np(img):
    a = np.asarray(img, dtype=np.float32)
    return a[..., :3], a[..., 3:4] / 255.0


def _composer(cadre, calque, a):
    if a <= 0:
        return
    rgb, al = calque
    k = al * a
    cadre *= (1 - k)
    cadre += rgb * k


def _alpha(t, debut, fin, fondu=0.7):
    if t < debut or t > fin:
        return 0.0
    return min(1.0, (t - debut) / fondu, (fin - t) / fondu)


def _ciel(th, seed):
    rng = np.random.default_rng(seed)
    haut, bas = np.array(th["haut"], float), np.array(th["bas"], float)
    y = np.linspace(0, 1, H)[:, None, None]
    base = np.repeat(haut * (1 - y) + bas * y, W, axis=1)
    yy, xx = np.mgrid[0:H, 0:W]
    dx = (xx - W / 2) / (W * 0.9)
    dy = (yy - H * 0.90) / (H * 0.30)
    lueur = np.clip(1 - np.sqrt(dx ** 2 + dy ** 2), 0, 1) ** 2.2
    lueur[yy > H * 0.90] *= 0.55
    ligne = np.exp(-((yy - H * 0.90) / 3.0) ** 2) * np.clip(1 - np.abs(dx), 0, 1)
    n = th["etoiles"]
    etoiles = (rng.uniform(0, W, n).astype(int), (rng.uniform(0, 0.82, n) ** 1.3 * H).astype(int),
               rng.uniform(0.35, 1.0, n), rng.uniform(0, 2 * math.pi, n), rng.uniform(0.6, 1.6, n))
    return base.astype(np.float32), lueur[..., None].astype(np.float32), ligne[..., None].astype(np.float32), etoiles


def faire_reel(texte, ref, cat_name, sortie, musique=None, ligne_fin="Lisez le chapitre entier sur",
               wrap=None):
    """Ecrit la video dans `sortie` et la renvoie. `wrap` : bot.wrap_text_with_quotes."""
    if wrap is None:
        from bot import wrap_text_with_quotes as wrap
    th = THEMES.get(cat_name, THEME_DEFAUT)
    seed = int(hashlib.md5(ref.encode("utf-8")).hexdigest(), 16) % (2 ** 31)
    base, lueur, ligne, (sx, sy, sb, sp, sv) = _ciel(th, seed)
    lum = np.array(th["lumiere"], np.float32)
    tete, vers, fin = _np(calque_tete(th)), _np(calque_verset(texte.rstrip("."), ref, wrap)), _np(calque_fin(ligne_fin))

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if musique:
        cmd += ["-ss", "2", "-i", musique, "-filter_complex",
                f"[1:a]volume=0.6,afade=t=in:d=1,afade=t=out:st={DUREE - 2}:d=2[a]",
                "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-t", str(DUREE), "-movflags", "+faststart", sortie]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(DUREE * FPS)):
        t = i / FPS
        u = t / DUREE
        # aube qui monte, ou crepuscule qui descend (Psaume du soir)
        jour = (0.62 - 0.45 * u ** 1.2) if th["soir"] else (0.10 + 0.55 * u ** 1.4)
        cadre = base + lueur * (lum * jour) + ligne * (lum * min(1.0, 0.25 + jour))
        pali = (0.4 + 0.6 * u) if th["soir"] else (1 - 0.6 * u)     # les etoiles naissent le soir
        eclat = sb * (0.65 + 0.35 * np.sin(sp + t * sv * 2.2)) * pali
        cadre[sy, sx] = np.maximum(cadre[sy, sx], eclat[:, None] * 255)
        _composer(cadre, tete, _alpha(t, 0.2, DUREE - 0.4, 1.0))
        _composer(cadre, vers, _alpha(t, 0.8, 10.2, 0.8))
        _composer(cadre, fin, _alpha(t, 10.7, DUREE + 1, 0.5))
        if t > DUREE - 0.45:
            cadre *= max(0.0, (DUREE - t) / 0.45)
        p.stdin.write(np.clip(cadre, 0, 255).astype(np.uint8).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError("ffmpeg a échoué")
    return sortie


def apercu(texte, ref, cat_name, chemin, t=6.0, wrap=None):
    """Une image fixe a l'instant t (planche de controle)."""
    if wrap is None:
        from bot import wrap_text_with_quotes as wrap
    th = THEMES.get(cat_name, THEME_DEFAUT)
    seed = int(hashlib.md5(ref.encode("utf-8")).hexdigest(), 16) % (2 ** 31)
    base, lueur, ligne, (sx, sy, sb, sp, sv) = _ciel(th, seed)
    lum = np.array(th["lumiere"], np.float32)
    u = t / DUREE
    jour = (0.62 - 0.45 * u ** 1.2) if th["soir"] else (0.10 + 0.55 * u ** 1.4)
    cadre = base + lueur * (lum * jour) + ligne * (lum * min(1.0, 0.25 + jour))
    pali = (0.4 + 0.6 * u) if th["soir"] else (1 - 0.6 * u)
    cadre[sy, sx] = np.maximum(cadre[sy, sx], (sb * pali)[:, None] * 255)
    _composer(cadre, _np(calque_tete(th)), 1)
    _composer(cadre, _np(calque_verset(texte.rstrip("."), ref, wrap)), 1)
    Image.fromarray(np.clip(cadre, 0, 255).astype(np.uint8)).save(chemin, quality=90)
