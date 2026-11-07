# -*- coding: utf-8 -*-
"""Rangement automatique des videos dans les playlists de la chaine.

Jusqu'au 5 octobre 2026 aucun script ne rangeait les videos : les playlists
etaient remplies a la main dans YouTube Studio. Depuis le 7 novembre 2026 le
jeton YouTube a le scope youtube.force-ssl, qui permet playlistItems.insert :
chaque script appelle ranger() juste apres l'envoi de la video.

    import yt_playlists
    yt_playlists.ranger(youtube, video_id, "protection")

`youtube` est le client deja construit par le script appelant. L'appel ne
leve jamais d'exception : un echec de rangement n'interrompt pas la
publication, il est seulement ecrit dans le journal.

Les series lues a voix haute (Bible audio, Psaumes narres) ont leur propre
rangement dans bible_audio.py et psaume_meditation.py.
"""

# Titres EXACTS des playlists sur la chaine, emoji compris. Une playlist
# absente de la chaine n'est pas creee : elle est signalee et ignoree.
PLAYLISTS = {
    # Shorts « verset du jour » : bot.py
    "promise":        "\U0001f33f Promesses de Dieu",
    "jesus":          "✝️ Paroles de Jésus",
    "proverbe":       "\U0001f4a1 Sagesse Biblique",
    "prophetie":      "\U0001f4ef  Prophéties Bibliques",
    "protection":     "\U0001f6e1️ Protection Divine",
    "psaume_soir":    "\U0001f319 Psaume du Soir",
    # Pas de playlist « Psaume du Matin » sur la chaine.
    "psaume_matin":   None,
    # Paraboles : ce sont les paroles de Jesus, elles vont dans sa playlist.
    "parabole":       "✝️ Paroles de Jésus",
    # Quiz quotidien : quiz_post.py
    "quiz":           "\U0001f9e9 Quiz Biblique",
    # Semaine Sainte : holy_week.py
    "semaine_sainte": "✝️ Semaine Sainte / Pâques",
}

# Serie « Versets bibliques » : thematic_meditation.py, cle = theme_key.
# Les themes sans playlist sont a None : ils sont ignores sans bruit.
PLAYLISTS_THEMATIQUES = {
    "protection": "\U0001f6e1️ Protection Divine",
    "promesses":  "\U0001f33f Promesses de Dieu",
    "sagesse":    "\U0001f4a1 Sagesse Biblique",
    "jesus":      "✝️ Paroles de Jésus",
    "propheties": "\U0001f4ef  Prophéties Bibliques",
    "psaumes":    "\U0001f3b5 Les Psaumes — Lectures Bibliques | Bible LSG1910",
    "priere":     "\U0001f64f La Prière",
    "pardon":     "\U0001f90d Le Pardon de Dieu",
    "guerison":   "\U0001f49a La Guérison de Dieu",
    "deuil":      "\U0001f56f️ Le Réconfort dans le Deuil",
    "peur":       "\U0001f499 Face à la Peur et l'Angoisse",
    # Sans playlist pour l'instant :
    "paix": None, "amour": None, "esperance": None, "confiance": None,
    "force": None, "gratitude": None, "combat": None, "solitude": None,
    "famille": None,
}

_index = None


def _norm(titre):
    """Compare les titres sans tenir compte des espaces doubles."""
    return " ".join(titre.split())


def cle_pour_categorie(cat_name, hour_utc=None):
    """Cle de playlist pour une categorie de bot.py (meme logique que category_label)."""
    if cat_name == "psaume":
        return "psaume_matin" if hour_utc == 5 else "psaume_soir"
    return cat_name


def _charger_index(youtube):
    global _index
    if _index is not None:
        return _index
    index, req = {}, youtube.playlists().list(part="snippet", mine=True, maxResults=50)
    while req is not None:
        rep = req.execute()
        for item in rep.get("items", []):
            index[_norm(item["snippet"]["title"])] = item["id"]
        req = youtube.playlists().list_next(req, rep)
    _index = index
    return index


def _deja_dedans(youtube, playlist_id, video_id):
    try:
        rep = youtube.playlistItems().list(part="id", playlistId=playlist_id,
                                           videoId=video_id, maxResults=1).execute()
        return bool(rep.get("items"))
    except Exception:
        return False


def ranger(youtube, video_id, cle, thematique=False):
    """Ajoute la video a la playlist de sa serie. Ne leve jamais."""
    if not video_id:
        return
    titre = (PLAYLISTS_THEMATIQUES if thematique else PLAYLISTS).get(cle)
    if not titre:
        print(f"ℹ️  Playlist : aucune playlist pour « {cle} », rangement ignoré")
        return
    try:
        playlist_id = _charger_index(youtube).get(_norm(titre))
        if not playlist_id:
            print(f"⚠️  Playlist « {titre} » absente de la chaîne, rangement ignoré")
            return
        if _deja_dedans(youtube, playlist_id, video_id):
            print(f"ℹ️  Déjà dans « {titre} »")
            return
        youtube.playlistItems().insert(part="snippet", body={"snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).execute()
        print(f"✅ Ajoutée à la playlist « {titre} »")
    except Exception as e:
        print(f"⚠️  Playlist non rangée : {str(e)[:200]}")
