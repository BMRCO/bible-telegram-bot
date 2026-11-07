"""rattrapage_playlists.py : range dans leur playlist les videos publiees depuis
une date donnee qui n'y sont pas encore (le bot ne rangeait rien avant le
7 novembre 2026, faute de scope OAuth).

La serie est reconnue au titre de la video, avec les memes tables que
yt_playlists.py. Une video dont le titre n'est pas reconnu est listee et laissee
de cote. Rien n'est jamais retire d'une playlist.

    DEPUIS=2026-10-04 python scripts/rattrapage_playlists.py            # essai : n'ecrit rien
    DEPUIS=2026-10-04 APPLIQUER=1 python scripts/rattrapage_playlists.py

N'affiche jamais le jeton ni aucun secret.
"""
import os
import re
import sys
from collections import Counter, defaultdict

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import yt_playlists as ypl  # noqa: E402
from youtube_garde import verifier_chaine  # noqa: E402

DEPUIS = os.environ.get("DEPUIS", "2026-10-04")
# La serie « Versets bibliques » est rattrapee depuis son debut, quelle que soit
# DEPUIS : neuf de ses playlists de theme n'ont ete creees que le 7 novembre 2026.
# Les autres series avant le 4 octobre ont ete rangees a la main : on n'y touche pas.
DEPUIS_THEMES = "2026-01-01"
APPLIQUER = os.environ.get("APPLIQUER") == "1"
# Chaque ajout coute 50 unites du quota YouTube (10 000 par jour, partage avec les
# envois du bot) : on plafonne par passage, et on relance les jours suivants.
MAX = int(os.environ.get("MAX") or 80)

PL = ypl.PLAYLISTS
TH = ypl.PLAYLISTS_THEMATIQUES
PSAUMES_LECTURE = TH["psaumes"]

# Libelle du titre (bot.category_label) -> playlist
LIBELLES = {
    "Promesses de Dieu": PL["promise"],
    "Paroles de Jésus": PL["jesus"],
    "Sagesse Biblique": PL["proverbe"],
    "Prophéties Bibliques": PL["prophetie"],
    "Protection Divine": PL["protection"],
    "Psaume du Soir": PL["psaume_soir"],
}

# Titre de theme (thematic_meditation.THEMES[...]["title"]) -> cle
THEMES_TITRES = {
    "La protection de Dieu": "protection", "La paix de Dieu": "paix",
    "L'amour de Dieu": "amour", "La prière": "priere", "Le pardon de Dieu": "pardon",
    "La guérison de Dieu": "guerison", "Face à la peur": "peur", "Le deuil": "deuil",
}


def theme_de_titre(titre):
    """Cle de theme pour un titre « emoji Titre — Versets bibliques (LSG 1910) »."""
    try:
        import thematic_meditation as tm
        table = {v["title"].lower(): k for k, v in tm.THEMES.items()}
    except Exception:
        table = {k.lower(): v for k, v in THEMES_TITRES.items()}
    tete = titre.split("—")[0].split(" - ")[0]
    tete = re.sub(r"^[^\wÀ-ÿ']+", "", tete).strip().lower()
    for t, k in table.items():
        if tete.startswith(t):
            return k
    return None


def classer(titre):
    """Titre -> titre de playlist, None (serie sans playlist) ou '?' (inconnu)."""
    if "Lecture Audio" in titre or "Bible audio" in titre or "Bible Audio" in titre:
        return None  # series lues a voix haute : rangees par organiser_playlists.py
    if "Quiz biblique" in titre or "Quiz Biblique" in titre:
        return PL["quiz"]
    if "Versets bibliques" in titre:
        k = theme_de_titre(titre)
        return TH.get(k) if k else "?"
    if "Lecture Complète" in titre and titre.startswith("Psaume"):
        return PSAUMES_LECTURE
    m = re.search(r"—\s*(.+?)\s*\|\s*Bible Louis Segond 1910", titre)
    if m:
        lib = m.group(1)
        if lib == "Psaume du Matin":
            return None
        return LIBELLES.get(lib, "?")
    if titre.startswith("✝️") and "Bible LSG1910" in titre:
        return PL["parabole"]
    return "?"


def main():
    creds = Credentials(token=None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
                        client_id=os.environ["YOUTUBE_CLIENT_ID"],
                        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token", scopes=None)
    creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds)
    verifier_chaine(yt)

    uploads = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0][
        "contentDetails"]["relatedPlaylists"]["uploads"]
    videos, req = [], yt.playlistItems().list(part="snippet,contentDetails",
                                              playlistId=uploads, maxResults=50)
    while req is not None:
        rep = req.execute()
        stop = False
        for it in rep.get("items", []):
            date = it["contentDetails"].get("videoPublishedAt") or it["snippet"]["publishedAt"]
            if date[:10] < min(DEPUIS, DEPUIS_THEMES):
                stop = True
                continue
            if date[:10] < DEPUIS and "Versets bibliques" not in it["snippet"]["title"]:
                continue
            videos.append((date, it["contentDetails"]["videoId"], it["snippet"]["title"]))
        req = None if stop else yt.playlistItems().list_next(req, rep)
    videos.sort()
    print(f"::notice::{len(videos)} vidéo(s) retenue(s) (depuis le {DEPUIS}, « Versets bibliques » depuis le {DEPUIS_THEMES})")

    if APPLIQUER:
        ypl.creer_manquantes(yt)
    index = ypl._charger_index(yt)
    contenu = {}

    def dans(pid):
        if pid not in contenu:
            ids, r = set(), yt.playlistItems().list(part="contentDetails", playlistId=pid, maxResults=50)
            while r is not None:
                res = r.execute()
                ids |= {x["contentDetails"]["videoId"] for x in res.get("items", [])}
                r = yt.playlistItems().list_next(r, res)
            contenu[pid] = ids
        return contenu[pid]

    a_ajouter, inconnus, sans = defaultdict(list), [], Counter()
    for date, vid, titre in videos:
        cible = classer(titre)
        if cible == "?":
            inconnus.append((date[:10], titre))
            continue
        if cible is None:
            sans["série sans playlist ou rangée ailleurs"] += 1
            continue
        pid = index.get(ypl._norm(cible))
        if not pid:
            inconnus.append((date[:10], f"[playlist absente : {cible}] {titre}"))
            continue
        if vid not in dans(pid):
            a_ajouter[cible].append((vid, titre))

    total = sum(len(v) for v in a_ajouter.values())
    print(f"::notice::{total} vidéo(s) à ranger" + ("" if APPLIQUER else " (essai : rien n'est écrit)"))
    for cible, lst in a_ajouter.items():
        print(f"{len(lst):4d}  {cible}")
        for vid, titre in lst[:3]:
            print(f"        ex. {titre}")
    for k, n in sans.items():
        print(f"{n:4d}  ({k})")
    if inconnus:
        print(f"::warning::{len(inconnus)} titre(s) non reconnu(s), laissés de côté")
        for d, t in inconnus[:40]:
            print(f"        {d}  {t}")

    if APPLIQUER:
        faits = 0
        # Les petites playlists d'abord : elles sont completes des le premier passage.
        for cible, lst in sorted(a_ajouter.items(), key=lambda kv: len(kv[1])):
            pid = index[ypl._norm(cible)]
            for vid, _ in lst:
                if faits >= MAX:
                    break
                yt.playlistItems().insert(part="snippet", body={"snippet": {
                    "playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
                faits += 1
        print(f"::notice::{faits} vidéo(s) rangée(s), {total - faits} restante(s)"
              + (" : relancer demain" if total > faits else ""))


if __name__ == "__main__":
    main()
