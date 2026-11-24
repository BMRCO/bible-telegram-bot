"""Couvertures carrees des playlists YouTube (1080 x 1080), dans le style des
couvertures de theme (assets/playlists/*.jpg) : fond sombre teinte avec un halo,
icone claire qui luit, titre en EB Garamond, sous-titre discret.

24 nov. 2026 (BC : « resolve os 3 ja ») : couvertures des playlists qui n'en avaient
pas, et couverture posee d'office quand bible_audio.py cree la playlist d'un livre.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

RACINE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(RACINE, "fonts", "EBGaramond-Regular.ttf")
TAILLE = 1080

# fond, halo, icone, texte (memes familles que les couvertures existantes)
PALETTES = {
    "nuit":   ((24, 28, 46), (92, 110, 160), (226, 232, 248), (236, 238, 246)),
    "marine": ((22, 26, 48), (70, 74, 110), (240, 232, 214), (240, 232, 214)),
    "vert":   ((30, 46, 34), (70, 130, 84), (170, 230, 186), (238, 242, 236)),
    "or":     ((46, 40, 30), (150, 128, 70), (240, 222, 170), (244, 238, 224)),
    "brun":   ((40, 34, 30), (130, 96, 70), (238, 214, 186), (244, 236, 226)),
    "pourpre": ((40, 28, 40), (120, 84, 120), (236, 216, 236), (244, 236, 244)),
}


# ── icones (dessinees dans un carre de 240 px centre en cx, cy) ──────────────
def _casque(d, cx, cy, c):
    d.arc((cx - 120, cy - 125, cx + 120, cy + 115), 180, 360, fill=c, width=30)
    for x in (cx - 128, cx + 76):
        d.rounded_rectangle((x, cy - 15, x + 52, cy + 105), 22, fill=c)


def _micro(d, cx, cy, c):
    d.rounded_rectangle((cx - 42, cy - 120, cx + 42, cy + 20), 42, fill=c)
    d.arc((cx - 80, cy - 60, cx + 80, cy + 60), 0, 180, fill=c, width=16)
    d.line((cx, cy + 60, cx, cy + 105), fill=c, width=16)
    d.line((cx - 50, cy + 105, cx + 50, cy + 105), fill=c, width=16)


def _question(d, cx, cy, c):
    d.ellipse((cx - 115, cy - 115, cx + 115, cy + 115), outline=c, width=16)
    f = ImageFont.truetype(FONT, 190)
    w = d.textlength("?", font=f)
    d.text((cx - w / 2, cy - 128), "?", font=f, fill=c)


def _lune(d, cx, cy, c, fond):
    d.ellipse((cx - 95, cy - 95, cx + 95, cy + 95), fill=c)
    d.ellipse((cx - 45, cy - 135, cx + 125, cy + 35), fill=fond)
    for (x, y, r) in ((cx + 70, cy - 70, 16),):
        d.polygon([(x, y - r * 2), (x + r * 0.5, y - r * 0.5), (x + r * 2, y), (x + r * 0.5, y + r * 0.5),
                   (x, y + r * 2), (x - r * 0.5, y + r * 0.5), (x - r * 2, y), (x - r * 0.5, y - r * 0.5)], fill=c)


def _arche(d, cx, cy, c):
    d.rounded_rectangle((cx - 70, cy - 110, cx + 70, cy + 80), 70, outline=c, width=16)
    for x in (cx - 25, cx, cx + 25):
        d.line((x, cy - 55, x, cy + 70), fill=c, width=11)
    d.line((cx - 95, cy + 95, cx + 95, cy + 95), fill=c, width=16)


def _ampoule(d, cx, cy, c):
    d.ellipse((cx - 85, cy - 125, cx + 85, cy + 45), outline=c, width=16)
    d.rectangle((cx - 38, cy + 40, cx + 38, cy + 62), fill=(0, 0, 0, 0))
    d.line((cx - 40, cy + 70, cx + 40, cy + 70), fill=c, width=16)
    d.line((cx - 30, cy + 98, cx + 30, cy + 98), fill=c, width=16)
    d.line((cx - 25, cy - 15, cx, cy + 20), fill=c, width=10)
    d.line((cx + 25, cy - 15, cx, cy + 20), fill=c, width=10)
    for a in (-60, -30, 0, 30, 60):
        r = math.radians(a - 90)
        d.line((cx + 120 * math.cos(r), cy - 40 + 120 * math.sin(r),
                cx + 145 * math.cos(r), cy - 40 + 145 * math.sin(r)), fill=c, width=10)


def _croix(d, cx, cy, c):
    d.rounded_rectangle((cx - 16, cy - 125, cx + 16, cy + 120), 8, fill=c)
    d.rounded_rectangle((cx - 80, cy - 70, cx + 80, cy - 38), 8, fill=c)


def _livre(d, cx, cy, c):
    d.polygon([(cx, cy - 70), (cx - 120, cy - 100), (cx - 120, cy + 80), (cx, cy + 110)], outline=c, width=14)
    d.polygon([(cx, cy - 70), (cx + 120, cy - 100), (cx + 120, cy + 80), (cx, cy + 110)], outline=c, width=14)
    d.line((cx, cy - 70, cx, cy + 110), fill=c, width=14)


ICONES = {"casque": _casque, "micro": _micro, "question": _question, "lune": _lune,
          "arche": _arche, "ampoule": _ampoule, "croix": _croix, "livre": _livre}


def _police(d, texte, taille, largeur_max):
    while taille > 40:
        f = ImageFont.truetype(FONT, taille)
        if d.textlength(texte, font=f) <= largeur_max:
            return f
        taille -= 4
    return ImageFont.truetype(FONT, taille)


def dessiner(chemin, titre, icone, palette="marine", sous_titre="", ligne_fin="Louis Segond 1910"):
    fond, halo, c_icone, c_texte = PALETTES[palette]
    S = TAILLE
    img = Image.new("RGB", (S, S), fond)
    # halo radial autour de l'icone
    lum = Image.new("L", (S, S), 0)
    ImageDraw.Draw(lum).ellipse((S / 2 - 330, 140, S / 2 + 330, 800), fill=255)
    lum = lum.filter(ImageFilter.GaussianBlur(170))
    img = Image.composite(Image.new("RGB", (S, S), halo), img, lum.point(lambda v: int(v * 0.55)))
    # icone qui luit
    calque = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    di = ImageDraw.Draw(calque)
    cy_ic = 330 if sous_titre else 380
    if icone == "lune":
        _lune(di, S // 2, cy_ic, c_icone + (255,), (0, 0, 0, 0))
    else:
        ICONES[icone](di, S // 2, cy_ic, c_icone + (255,))
    lueur = calque.filter(ImageFilter.GaussianBlur(26))
    img = img.convert("RGBA")
    img.alpha_composite(lueur)
    img.alpha_composite(lueur)
    img.alpha_composite(calque)
    d = ImageDraw.Draw(img)
    # titre, sous-titre, ligne de fin
    f = _police(d, titre, 150, S - 140)
    y = 560 if sous_titre else 610
    d.text(((S - d.textlength(titre, font=f)) / 2, y), titre, font=f, fill=c_texte)
    if sous_titre:
        fs = _police(d, sous_titre, 84, S - 200)
        d.text(((S - d.textlength(sous_titre, font=fs)) / 2, y + 175), sous_titre, font=fs, fill=c_texte)
    if ligne_fin:
        fl = ImageFont.truetype(FONT, 46)
        d.text(((S - d.textlength(ligne_fin, font=fl)) / 2, S - 150), ligne_fin, font=fl,
               fill=tuple(int(a * 0.75 + b * 0.25) for a, b in zip(c_texte, fond)))
    img.convert("RGB").save(chemin, "JPEG", quality=92)
    return chemin


def couverture_livre_audio(nom_livre, chemin):
    """Playlist « 📖 Livre | Bible audio LSG 1910 »."""
    return dessiner(chemin, nom_livre, "casque", "marine", sous_titre="Bible audio")


def poser(yt, pid, chemin):
    """Pose (ou remplace) la couverture d'une playlist. Meme methode que
    scripts/playlists_themes.py : l'API n'accepte que le type « hero »."""
    from googleapiclient.http import MediaFileUpload
    for img in yt.playlistImages().list(part="snippet", parent=pid).execute().get("items", []):
        yt.playlistImages().delete(id=img["id"]).execute()
    yt.playlistImages().insert(part="snippet", body={"snippet": {"playlistId": pid, "type": "hero"}},
                               media_body=MediaFileUpload(chemin, mimetype="image/jpeg")).execute()


# Couvertures des playlists qui n'en avaient pas (audit du 24 nov. 2026)
# titre de la playlist -> (fichier, titre, icone, palette, sous-titre)
FIXES = {
    "🌙 Psaume du Soir": ("psaume-du-soir", "Psaume du soir", "lune", "nuit", ""),
    "🎵 Les Psaumes | Lectures Bibliques | Bible LSG1910": ("psaumes-lectures", "Psaumes", "arche", "vert", "Lectures bibliques"),
    "🧩 Quiz Biblique": ("quiz", "Quiz biblique", "question", "or", ""),
    "🎙️ Les Psaumes lus à voix haute": ("psaumes-voix-haute", "Psaumes", "micro", "vert", "lus à voix haute"),
    "💡 Astuces LaBible.app": ("astuces", "Astuces", "ampoule", "or", "LaBible.app"),
    "🎧 Lectures pour méditer | Louis Segond 1910": ("lectures-mediter", "Lectures", "casque", "brun", "pour méditer"),
    "✝️ Semaine Sainte / Pâques": ("semaine-sainte", "Semaine sainte", "croix", "pourpre", ""),
}
