"""registre_thematiques.py : remplit versets_publies.json pour les meditations
thematiques (series « thematique_<theme> »), a partir :
  1. des descriptions des videos thematiques de la chaine YouTube
     (titre « <emoji> <theme> — Versets bibliques (LSG 1910) », une ligne
     « Ref — texte. » par verset) ;
  2. des offsets de progress_thematic.json (entrees deja passees de chaque liste).
Puis affiche, pour chaque theme, combien de versets restent jamais publies.
A lancer a la main. N'affiche aucun secret."""
import json
import os
import re
import sys

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
os.chdir(RACINE)
import deja_publie as dp  # noqa: E402
from youtube_garde import verifier_chaine  # noqa: E402

# Les memes cles et emojis que THEMES de thematic_meditation.py (lus dans le
# source pour ne pas importer bot.py, qui exige les secrets de publication).
SRC = open("thematic_meditation.py", encoding="utf-8").read()
BLOC = SRC[SRC.index("THEMES = {"):SRC.index("\n}\n", SRC.index("THEMES = {"))]
THEMES = {}
for cle, fichier, emoji in re.findall(
        r'"(\w+)":\s*dict\(\s*file="(\w+_curated\.json)".*?emoji="([^"]+)"', BLOC, re.S):
    THEMES[cle] = {"file": fichier,
                   "emoji": emoji.encode("latin-1", "backslashreplace").decode("unicode_escape")}
REF = re.compile(r"^\s*((?:[1-3]\s)?[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' ]*?)\s+(\d+):(\d+)(?:\s*-\s*(\d+))?\s+—")


def theme_de(titre):
    if "Versets bibliques (LSG 1910)" not in titre:
        return None
    t = titre.strip()
    for cle, th in THEMES.items():
        e = th["emoji"].replace("️", "")
        if t.replace("️", "").startswith(e):
            return cle
    return None


def main():
    creds = Credentials(token=None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
                        client_id=os.environ["YOUTUBE_CLIENT_ID"],
                        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token", scopes=None)
    creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds)
    verifier_chaine(yt)
    up = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0][
        "contentDetails"]["relatedPlaylists"]["uploads"]
    items, req = [], yt.playlistItems().list(part="snippet", playlistId=up, maxResults=50)
    while req is not None:
        rep = req.execute()
        items += rep.get("items", [])
        req = yt.playlistItems().list_next(req, rep)

    videos = notes = 0
    for it in items:
        sn = it["snippet"]
        cle = theme_de(sn.get("title", ""))
        if not cle:
            continue
        videos += 1
        for ligne in sn.get("description", "").splitlines():
            m = REF.match(ligne)
            if not m:
                continue
            ref = f"{m.group(1).strip()} {m.group(2)}:{m.group(3)}" + (f"-{m.group(4)}" if m.group(4) else "")
            if dp.cles(ref):
                dp.noter(f"thematique_{cle}", ref)
                notes += 1
    print(f"::notice::{len(items)} vidéos lues, {videos} méditations thématiques, {notes} versets notés")

    # Offsets : les entrees deja passees de chaque liste. Un offset revenu
    # a 0 avec des videos sur YouTube (guerison) est couvert par l'etape 1.
    offsets = json.load(open("progress_thematic.json", encoding="utf-8")).get("offsets", {})
    for cle, th in THEMES.items():
        L = json.load(open(th["file"], encoding="utf-8"))
        for e in L[:offsets.get(cle, 0)]:
            vs = e[2:] if len(e) > 2 else [1]
            ref = f"{e[0]} {e[1]}:{vs[0]}" + (f"-{vs[-1]}" if len(vs) > 1 else "")
            dp.noter(f"thematique_{cle}", ref)

    etat = json.load(open(dp.FICHIER, encoding="utf-8"))
    for cle, th in THEMES.items():
        L = json.load(open(th["file"], encoding="utf-8"))
        libres = 0
        for e in L:
            vs = e[2:] if len(e) > 2 else [1]
            ref = f"{e[0]} {e[1]}:{vs[0]}" + (f"-{vs[-1]}" if len(vs) > 1 else "")
            if not dp.deja(f"thematique_{cle}", ref):
                libres += 1
        print(f"{cle:11s} déjà publiés {len(etat.get('thematique_' + cle, [])):4d} | "
              f"liste {len(L):4d} | jamais publiés dans le thème : {libres}")


if __name__ == "__main__":
    main()
