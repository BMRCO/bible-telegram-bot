"""reel_scene.py : le reel des versets du jour.

EN PRODUCTION : faire_reel_doux() (en bas du fichier), au visuel des meditations
thematiques, choisi par BC le 21 nov. 2026. faire_reel() ci-dessous (visuel
« derniers temps ») a ete essaye puis refuse le meme jour ; il reste pour memoire.

Visuel « derniers temps » :

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
# Reels de versets (faire_reel_doux) : 21 s. Le verset entier reste ~9 s a l'ecran
# avant le carton (BC, 25 nov. 2026 : « deixa o versiculo inteiro mais tempo »).
DUREE_DOUX = 21.0
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


def _bande(img, y0, y1):
    """Calque reduit a une bande horizontale : composer 12 lignes par image reste rapide."""
    y0, y1 = max(0, y0), min(img.height, y1)
    a = np.asarray(img, dtype=np.float32)[y0:y1]
    return y0, y1, a[..., :3], a[..., 3:4] / 255.0


def _composer_bande(cadre, bande, a):
    if a <= 0:
        return
    y0, y1, rgb, al = bande
    k = al * a
    zone = cadre[y0:y1]
    zone *= (1 - k)
    zone += rgb * k


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


# ═════════════════════════════════════════════════════════════════════════════
# Version « douce », au visuel des meditations thematiques (choix de BC, 21 nov. 2026 :
# « era como os tematicos com a referencia do versiculo ao meio ») : fond en degrade
# doux de la couleur du theme, bordure fine, verset qui apparait en douceur au
# centre, ornement, reference centree et « LSG 1910 », LaBible.app en bas de la
# carte, particules qui scintillent (plus nombreuses le soir).
PALETTE_DOUCE = {"protection": "protection", "jesus": "jesus", "psaume": "psaumes",
                 "promise": "promesses", "proverbe": "sagesse", "prophetie": "propheties"}


def faire_reel_doux(texte, ref, cat_name, sortie, musique=None, ligne_fin="Lisez le chapitre entier sur",
                    soir=None):
    import thematic_meditation as tm
    from bot import FONT_SERIF, FONT_SERIF_BOLD, FONT_SANS
    pal = tm.THEMES[PALETTE_DOUCE.get(cat_name, "paix")]["palette"]
    TOP, BOT, ACC, ACC2, BLANC, SIL = pal
    if soir is None:
        soir = cat_name == "psaume"
    seed = int(hashlib.md5(ref.encode("utf-8")).hexdigest(), 16) % (2 ** 31)
    rng = np.random.default_rng(seed)
    BORD = 80

    fond = tm.gradient_bg(W, H, TOP, BOT)
    d = ImageDraw.Draw(fond)
    d.rounded_rectangle([BORD, BORD, W - BORD, H - BORD], radius=26,
                        outline=tuple(int(c * 0.7) for c in ACC), width=2)
    fond = np.asarray(fond, dtype=np.float32)

    # verset : une bande par ligne, qui apparait l'une apres l'autre au fil de la
    # video (22 nov. 2026, BC : le texte apparaissait trop vite, d'un bloc).
    mesure = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    fv, lignes, lh = tm.autosize_font(mesure, f"« {texte.rstrip('.')} »", W - 2 * (BORD + 120),
                                      int((H - 2 * BORD) * 0.55))
    y = BORD + (H - 2 * BORD) // 2 - lh * len(lignes) // 2 - 40
    bandes = []
    for l in lignes:
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        x = (W - d.textlength(l, font=fv)) // 2
        d.text((x + 2, y + 2), l, font=fv, fill=tuple(int(c * 0.5) for c in TOP) + (255,))
        d.text((x, y), l, font=fv, fill=BLANC + (255,))
        bandes.append(_bande(img, int(y - 10), int(y + lh + 20)))
        y += lh

    # pied de carte : ornement, reference, LSG 1910, LaBible.app
    vers = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(vers)
    cx, oy = W // 2, H - BORD - 290
    for i in range(150):
        k = 0.95 * (1 - i / 150) ** 1.2
        d.line([cx - 40 - i, oy - 1, cx - 40 - i, oy + 1], fill=ACC + (int(255 * k),))
        d.line([cx + 40 + i, oy - 1, cx + 40 + i, oy + 1], fill=ACC + (int(255 * k),))
    for dx, r in ((-22, 3), (0, 5), (22, 3)):
        d.ellipse([cx + dx - r, oy - r, cx + dx + r, oy + r], fill=ACC + (255,))
    for taille in range(44, 26, -2):
        fr = ImageFont.truetype(FONT_SERIF_BOLD, taille)
        if d.textlength(ref, font=fr) <= W - 2 * (BORD + 120):
            break
    d.text((cx, H - BORD - 232), ref, font=fr, fill=ACC + (255,), anchor="ms")
    d.text((cx, H - BORD - 190), "LSG 1910", font=ImageFont.truetype(FONT_SERIF, 28), fill=SIL + (255,), anchor="ms")
    d.text((cx, H - BORD - 56), "LaBible.app", font=ImageFont.truetype(FONT_SANS, 28), fill=ACC + (255,), anchor="ms")
    pied = _bande(vers, oy - 20, H - BORD - 20)

    # rythme : les lignes se succedent jusqu'a ~6,5 s, puis le pied de carte
    n_l = len(bandes)
    pas = min(0.9, 5.4 / max(1, n_l - 1))
    debuts = [0.3 + i * pas for i in range(n_l)]
    debut_pied = debuts[-1] + 0.6

    fin = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(fin)
    f1, f2, f3 = (ImageFont.truetype(FONT_SERIF, 42), ImageFont.truetype(FONT_SERIF_BOLD, 104),
                  ImageFont.truetype(FONT_SERIF, 36))
    d.text((cx, H // 2 - 100), ligne_fin, font=f1, fill=SIL + (255,), anchor="ms")
    d.text((cx + 3, H // 2 + 33), "LaBible.app", font=f2, fill=(0, 0, 0, 200), anchor="ms")
    d.text((cx, H // 2 + 30), "LaBible.app", font=f2, fill=ACC2 + (255,), anchor="ms")
    d.line([cx - 90, H // 2 + 70, cx + 90, H // 2 + 70], fill=ACC + (200,), width=2)
    d.text((cx, H // 2 + 130), "Gratuit · Sans publicité · LSG 1910", font=f3, fill=SIL + (255,), anchor="ms")
    fin = _np(fin)

    # particules : poussiere lumineuse qui monte lentement et scintille
    n = 90 if soir else 28
    px = rng.uniform(BORD + 10, W - BORD - 10, n)
    py = rng.uniform(BORD + 10, H - BORD - 10, n)
    vit = rng.uniform(4, 14, n)                     # px par seconde, vers le haut
    ph = rng.uniform(0, 2 * math.pi, n)
    fr_ = rng.uniform(0.5, 1.4, n)
    tai = rng.choice([1, 1, 1, 2], n)
    coul = np.array([255, 248, 230], np.float32) * 0.6 + np.array(ACC2, np.float32) * 0.4

    def ease(x):
        x = max(0.0, min(1.0, x))
        return x * x * (3 - 2 * x)

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if musique:
        cmd += ["-ss", "2", "-i", musique, "-filter_complex",
                f"[1:a]volume=0.6,afade=t=in:d=1,afade=t=out:st={DUREE_DOUX - 2}:d=2[a]",
                "-map", "0:v", "-map", "[a]", "-c:a", "aac", "-b:a", "160k"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-t", str(DUREE_DOUX), "-movflags", "+faststart", sortie]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(DUREE_DOUX * FPS)):
        t = i / FPS
        cadre = fond.copy()
        yy = (py - vit * t - BORD) % (H - 2 * BORD - 20) + BORD + 10
        ecl = 0.35 + 0.65 * (0.5 + 0.5 * np.sin(ph + t * fr_ * 2.4))
        for k in range(n):
            x0, y0, s = int(px[k]), int(yy[k]), int(tai[k])
            zone = cadre[y0:y0 + s + 1, x0:x0 + s + 1]
            zone += (coul - zone) * (ecl[k] * 0.85)
        sortie_v = 1.0 if t < 15.5 else ease((16.0 - t) / 0.5)
        for bd, t0 in zip(bandes, debuts):
            _composer_bande(cadre, bd, ease((t - t0) / 0.9) * sortie_v)
        _composer_bande(cadre, pied, ease((t - debut_pied) / 0.9) * sortie_v)
        _composer(cadre, fin, ease((t - 16.5) / 0.5))
        if t > DUREE_DOUX - 0.45:
            cadre *= max(0.0, (DUREE_DOUX - t) / 0.45)
        p.stdin.write(np.clip(cadre, 0, 255).astype(np.uint8).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError("ffmpeg a échoué")
    return sortie
