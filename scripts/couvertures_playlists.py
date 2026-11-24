"""Corrige les playlists relevees par l'audit du 24 nov. 2026 (scripts/audit_playlists.py),
a la demande de BC (« resolve os 3 ja ») :
1. retire le tiret long du titre « Les Psaumes — Lectures Bibliques » ;
2. pose une couverture sur chaque playlist qui n'en a pas (couvertures.FIXES et
   les playlists de livre de la Bible audio) ;
3. rend privee une playlist de theme vide (elle redevient publique a sa premiere
   video : scripts/playlists_themes.py).
Idempotent. N'affiche aucun secret.
"""
import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import couvertures  # noqa: E402

creds = Credentials(token=None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
                    client_id=os.environ["YOUTUBE_CLIENT_ID"],
                    client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
                    token_uri="https://oauth2.googleapis.com/token", scopes=None)
creds.refresh(Request())
yt = build("youtube", "v3", credentials=creds)

ANCIEN = "🎵 Les Psaumes — Lectures Bibliques | Bible LSG1910"
NOUVEAU = "🎵 Les Psaumes | Lectures Bibliques | Bible LSG1910"


def playlists():
    out, req = [], yt.playlists().list(part="snippet,status,contentDetails", mine=True, maxResults=50)
    while req is not None:
        rep = req.execute()
        out += rep.get("items", [])
        req = yt.playlists().list_next(req, rep)
    return out


def maj(p, titre=None, prive=None):
    sn = p["snippet"]
    body = {"id": p["id"], "snippet": {"title": titre or sn["title"], "description": sn.get("description", ""),
                                       "defaultLanguage": sn.get("defaultLanguage", "fr")}}
    part = "snippet"
    if prive is not None:
        body["status"] = {"privacyStatus": "private" if prive else "public"}
        part = "snippet,status"
    yt.playlists().update(part=part, body=body).execute()


for p in playlists():
    t = " ".join(p["snippet"]["title"].split())
    if t == " ".join(ANCIEN.split()):
        maj(p, titre=NOUVEAU)
        print(f"✏️  Renommée : {t} -> {NOUVEAU}")

os.makedirs("couvertures_tmp", exist_ok=True)
for p in playlists():
    t = " ".join(p["snippet"]["title"].split())
    a_couv = bool(yt.playlistImages().list(part="snippet", parent=p["id"]).execute().get("items"))
    if p["contentDetails"]["itemCount"] == 0:
        if p["status"]["privacyStatus"] == "public":
            maj(p, prive=True)
            print(f"🙈 Vide, rendue privée : {t}")
    if a_couv:
        continue
    chemin = None
    fixe = next((v for k, v in couvertures.FIXES.items() if " ".join(k.split()) == t), None)
    if fixe:
        f, titre, icone, palette, st = fixe
        chemin = couvertures.dessiner(f"couvertures_tmp/{f}.jpg", titre, icone, palette, st)
    elif t.startswith("📖 ") and t.endswith("| Bible audio LSG 1910"):
        livre = t[2:].split("|")[0].strip()
        chemin = couvertures.couverture_livre_audio(livre, f"couvertures_tmp/livre-{livre}.jpg")
    if chemin:
        couvertures.poser(yt, p["id"], chemin)
        print(f"🖼️  Couverture posée : {t}")
    else:
        print(f"::warning::Sans couverture et sans modèle : {t}")
