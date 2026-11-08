# -*- coding: utf-8 -*-
"""Playlists YouTube par theme biblique, alignees sur les pages /versets du site.

Le site LaBible.app a 44 pages de themes (labible.app/versets/<theme>), chacune
avec sa liste de versets (data/versets_themes.json du depot du site). Chaque
theme a une playlist sur la chaine. Une video dont la reference figure dans la
liste d'un theme entre dans la playlist de ce theme.

    import yt_themes
    yt_themes.ranger_reference(youtube, video_id, "Psaumes 145:18-19")

Ne leve jamais d'exception : un echec de rangement n'interrompt pas la
publication. Les identifiants des playlists sont dans playlists_themes.json,
ecrit par scripts/playlists_themes.py.
"""
import json
import os
import re
import unicodedata

import requests

THEMES_URL = "https://raw.githubusercontent.com/BMRCO/labible.app/main/data/versets_themes.json"
ETAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "playlists_themes.json")

# Themes qui avaient deja une playlist avant le 8 novembre 2026 : on la garde.
EXISTANTES = {
    "protection": "\U0001f6e1️ Protection Divine",
    "paix": "\U0001f54a️ La Paix de Dieu",
    "amour": "❤️ L'Amour de Dieu",
    "esperance": "\U0001f305 L'Espérance en Dieu",
    "priere": "\U0001f64f La Prière",
    "promesses": "\U0001f33f Promesses de Dieu",
    "deuil": "\U0001f56f️ Le Réconfort dans le Deuil",
    "pardon": "\U0001f90d Le Pardon de Dieu",
    "guerison": "\U0001f49a La Guérison de Dieu",
    "peur": "\U0001f499 Face à la Peur et l'Angoisse",
    "confiance": "⚓ La Confiance en Dieu",
    "force": "\U0001f981 La Force et le Courage",
    "famille": "\U0001f3e1 La Famille selon Dieu",
    "gratitude": "\U0001f64c La Gratitude",
    "combat": "⚔️ Le Combat Spirituel",
    "solitude": "\U0001f463 La Présence de Dieu",
    "sagesse": "\U0001f4a1 Sagesse Biblique",
    "paroles-de-jesus": "✝️ Paroles de Jésus",
    "propheties": "\U0001f4ef Prophéties Bibliques",
}

# Themes crees le 8 novembre 2026 : emoji devant le libelle de la page du site.
EMOJIS = {
    "foi": "⛰️", "encouragement": "\U0001f4aa", "joie": "☀️", "benediction": "✨",
    "mariage": "\U0001f48d", "enfants": "\U0001f476", "amitie": "\U0001f91d", "travail": "\U0001f6e0️",
    "tristesse": "\U0001f4a7", "salut": "✝️", "saint-esprit": "\U0001f525", "nouvel-an": "\U0001f4c5",
    "naissance-de-jesus": "⭐", "resurrection": "\U0001f304", "grace": "\U0001f49b", "patience": "⏳",
    "humilite": "\U0001f33e", "colere": "⚖️", "argent": "\U0001f4b0", "mere": "\U0001f469‍\U0001f467",
    "pere": "\U0001f468‍\U0001f467", "jeunes": "\U0001f331", "femmes": "\U0001f338", "matin": "\U0001f324️",
    "soir": "\U0001f319", "repentance": "\U0001f647", "vie-eternelle": "♾️",
    "psaumes": "\U0001f3b5",
}

_themes = None
_par_verset = None


def norm_livre(b):
    b = unicodedata.normalize("NFD", b).encode("ascii", "ignore").decode().lower()
    b = " ".join(b.replace("’", "'").split())
    return {"psaume": "psaumes", "cantique des cantiqu": "cantique des cantiques",
            "cantique": "cantique des cantiques"}.get(b, b)


def versets_de(ref):
    """« Psaumes 145:18-19 » -> [("psaumes", 145, 18), ("psaumes", 145, 19)]. [] si illisible."""
    m = re.match(r"^\s*((?:[1-3]\s)?[^\d:]+?)\s+(\d+):(\d+)(?:\s*-\s*(\d+))?", ref or "")
    if not m:
        return []
    b, c, a = norm_livre(m.group(1)), int(m.group(2)), int(m.group(3))
    z = int(m.group(4) or a)
    if z < a or z - a > 30:
        z = a
    return [(b, c, v) for v in range(a, z + 1)]


def themes():
    """Les themes du site ({slug: {label, refs…}}), lus une fois par execution."""
    global _themes, _par_verset
    if _themes is None:
        r = requests.get(THEMES_URL, timeout=30)
        r.raise_for_status()
        _themes = r.json()
        _par_verset = {}
        for slug, t in _themes.items():
            for b, c, v in t["refs"]:
                _par_verset.setdefault((norm_livre(b), int(c), int(v)), set()).add(slug)
    return _themes


def themes_de(ref):
    themes()
    out = set()
    for cle in versets_de(ref):
        out |= _par_verset.get(cle, set())
    return sorted(out)


def titre_playlist(slug):
    if slug in EXISTANTES:
        return EXISTANTES[slug]
    return f"{EMOJIS.get(slug, '📖')} {themes()[slug]['label']} | Bible Louis Segond 1910"


def lien(slug):
    return f"https://labible.app/versets/{slug}"


def description(slug):
    label = themes()[slug]["label"]
    return (f"{label} dans la Bible Louis Segond 1910, en vidéo. Chaque verset est donné tel qu’il "
            f"est écrit, sans commentaire ajouté : le texte est du domaine public.\n\n"
            f"📖 Tous les versets de ce thème : {lien(slug)}\n"
            f"📱 La Bible complète, gratuite, hors ligne et sans publicité : https://labible.app")


def etat():
    try:
        return json.load(open(ETAT, encoding="utf-8"))
    except FileNotFoundError:
        return {}


def ranger_reference(youtube, video_id, ref):
    """Ajoute la video aux playlists des themes dont la liste contient ce verset. Ne leve jamais."""
    if not video_id or not ref:
        return
    try:
        slugs = themes_de(ref)
        if not slugs:
            return
        ids = etat()
        for slug in slugs:
            pid = (ids.get(slug) or {}).get("id")
            if not pid:
                continue
            deja = youtube.playlistItems().list(part="id", playlistId=pid, videoId=video_id,
                                                maxResults=1).execute().get("items")
            if deja:
                continue
            youtube.playlistItems().insert(part="snippet", body={"snippet": {
                "playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).execute()
            print(f"✅ Ajoutée à la playlist du thème « {slug} »")
    except Exception as e:
        print(f"⚠️  Playlist de thème non rangée : {str(e)[:200]}")
