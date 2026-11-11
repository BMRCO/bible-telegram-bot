"""musique_revendiquee.py : pistes du dossier music_meditation/ a ne plus utiliser.

Regle du projet : seulement de la musique libre de Content ID. Releve du
11 novembre 2026 dans YouTube Studio (filtre « Revendications », ~124 videos) :
toutes les pistes de l'artiste « Harmony of Heaven » sont revendiquees
(« God Is My Calm », « God Is My Strength », « God Will Lead Me », « God Holds
My Tomorrow »...), ainsi que « Heaven's Whisper » (Ruwin) et « Flute Meditation
Music 8 ». Les fichiers restent dans le dossier (les anciennes videos les
utilisent) mais ne servent plus aux nouvelles publications.

Restees sans revendication a cette date : « Flute Meditation Music 15 », les deux
« Fundo musical relaxante », « Meditation ». Les pistes jessequinn*, nickpanek*
et onetent-relaxing-meditation-music-2 n'avaient pas encore ete utilisees :
si l'une d'elles est revendiquee, ajouter son nom a MOTS.

Un seul endroit pour cette liste : psaume_meditation.py (donc bible_audio.py),
thematic_meditation.py et quiz_post.py l'importent.
"""
import os
import re

# Compare sur le nom reduit aux lettres et chiffres : « Heaven’s Whisper »,
# « heavens-whisper » et « Heavens Whisper » donnent tous « heavenswhisper ».
# (Avant le 11 nov. 2026, l'apostrophe courbe et les tirets faisaient manquer
# deux des trois pistes de l'ancienne liste.)
MOTS = ("harmonyofheaven", "heavenswhisper", "flutemeditationmusic8")


def _norme(chemin):
    nom = os.path.splitext(os.path.basename(chemin))[0].lower()
    return re.sub(r"[^a-z0-9]", "", nom)


def est_revendiquee(chemin):
    n = _norme(chemin)
    if any(m in n for m in MOTS):
        return True
    # Serie Harmony of Heaven telechargee sous son titre de page :
    # « Christian instrumental music for prayer (...) - Royalty-free Music »,
    # « Instrumental Christian music for prayer (12-56) - Royalty-free Music »...
    return n.endswith("royaltyfreemusic") and n.startswith(("christian", "instrumentalchristian"))


def libres(chemins):
    """Les pistes non revendiquees ; s'il n'en reste aucune, None (pas de musique
    plutot qu'une piste revendiquee)."""
    return [c for c in chemins if not est_revendiquee(c)]
