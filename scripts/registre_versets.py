"""registre_versets.py : remplit versets_publies.json depuis les titres de la
chaine YouTube, puis affiche, pour chaque serie, combien de versets du vivier
n'ont encore jamais ete publies dans cette serie. N'affiche aucun secret."""
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

# Libelle du titre (« Ref — Libelle | Bible ... » ou « Ref | Libelle | Bible ... »)
LIBELLES = {
    "promesses de dieu": "promise", "promesses": "promise",
    "paroles de jésus": "jesus", "sagesse biblique": "proverbe",
    "prophéties bibliques": "prophetie", "protection divine": "protection",
    "psaume du soir": "psaume", "psaume du matin": "psaume", "psaumes bibliques": "psaume",
    "les derniers temps": "derniers_temps",
}
# Anciens titres : l'emoji de la categorie en tete
EMOJIS = {"🌿": "promise", "💡": "proverbe", "📯": "prophetie", "🛡": "protection",
          "🎵": "psaume", "🌙": "psaume"}
REF = re.compile(r"((?:[1-3]\s)?[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' ]*?)\s+(\d+):(\d+)(?:\s*-\s*(\d+))?")

VIVIERS = {"promise": "promesses_curated.json", "jesus": "jesus_curated.json",
           "proverbe": "proverbes_curated.json", "prophetie": "propheties_curated.json",
           "protection": "protection_curated.json", "psaume": "psaumes_curated.json"}


def serie_de(titre):
    t = titre.lower()
    for lib, s in LIBELLES.items():
        if re.search(r"[—|]\s*" + re.escape(lib) + r"\s*\|", t):
            return s
    tete = titre.strip()[:2]
    for e, s in EMOJIS.items():
        if tete.startswith(e):
            return s
    if titre.strip().startswith("✝") and "Lecture" not in titre:
        return "jesus"
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
    titres, req = [], yt.playlistItems().list(part="snippet", playlistId=up, maxResults=50)
    while req is not None:
        rep = req.execute()
        titres += [it["snippet"]["title"] for it in rep.get("items", [])]
        req = yt.playlistItems().list_next(req, rep)
    n = 0
    inconnus = []
    for t in titres:
        s = serie_de(t)
        if not s:
            continue
        m = REF.search(t)
        if not m:
            inconnus.append(t)
            continue
        ref = f"{m.group(1).strip()} {m.group(2)}:{m.group(3)}" + (f"-{m.group(4)}" if m.group(4) else "")
        if dp.cles(ref):
            dp.noter(s, ref)
            n += 1
    print(f"::notice::{len(titres)} vidéos lues, {n} Shorts de versets enregistrés")
    for t in inconnus[:15]:
        print("  sans référence lisible :", t)
    etat = json.load(open(dp.FICHIER, encoding="utf-8"))
    for s, f in VIVIERS.items():
        L = json.load(open(f, encoding="utf-8"))
        libres = 0
        for e in L:
            a = e[2]
            z = e[3] if len(e) >= 4 else a
            ref = f"{e[0]} {e[1]}:{a}" + (f"-{z}" if z != a else "")
            if not dp.deja(s, ref):
                libres += 1
        print(f"{s:12s} déjà publiés {len(etat.get(s, [])):4d} versets | vivier {len(L):4d} | jamais publiés dans la série : {libres}")
    print(f"derniers_temps déjà publiés {len(etat.get('derniers_temps', []))}")


if __name__ == "__main__":
    main()
