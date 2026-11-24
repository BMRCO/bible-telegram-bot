"""Audit des playlists YouTube (lecture seule, ne modifie rien).

Pour chaque playlist de la chaine : titre, nombre de videos, couverture posee ou non,
date de la derniere video ajoutee. Puis, pour chaque serie suivie par un registre
videos_*.json, les videos publiees qui manquent dans sa playlist.
Ecrit le resultat en JSON entre AUDIT-DEBUT et AUDIT-FIN. N'affiche aucun secret.
(Demande de BC, 24 nov. 2026 : « verifica se as playlists do youtube e as capas
estao atualizadas ».)
"""
import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

creds = Credentials(token=None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
                    client_id=os.environ["YOUTUBE_CLIENT_ID"],
                    client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
                    token_uri="https://oauth2.googleapis.com/token", scopes=None)
creds.refresh(Request())
yt = build("youtube", "v3", credentials=creds)


def toutes(req_fn, **kw):
    req = req_fn(**kw)
    while req is not None:
        rep = req.execute()
        yield from rep.get("items", [])
        req = req_fn.__self__.list_next(req, rep)


def contenu(pid):
    ids, derniere = [], ""
    for it in toutes(yt.playlistItems().list, part="contentDetails,snippet", playlistId=pid, maxResults=50):
        ids.append(it["contentDetails"]["videoId"])
        derniere = max(derniere, it["snippet"].get("publishedAt", ""))
    return ids, derniere[:10]


playlists = []
par_titre = {}
for p in toutes(yt.playlists().list, part="snippet,contentDetails,status", mine=True, maxResults=50):
    pid = p["id"]
    try:
        couv = bool(yt.playlistImages().list(part="snippet", parent=pid).execute().get("items"))
    except Exception as e:
        couv = f"? {str(e)[:60]}"
    ids, derniere = contenu(pid)
    t = " ".join(p["snippet"]["title"].split())
    par_titre[t] = set(ids)
    playlists.append({"titre": t, "videos": p["contentDetails"]["itemCount"], "couverture": couv,
                      "derniere_ajout": derniere, "visibilite": p["status"]["privacyStatus"]})

# Series suivies par un registre : playlist attendue (debut de titre) -> fichier
SERIES = {
    "⏳ Les derniers temps": "videos_derniers_temps.json",
    "💡 Astuces LaBible.app": "videos_tutoriels.json",
    "🎧 Lectures pour méditer": "videos_compilations.json",
    "🎙️ Les Psaumes lus à voix haute": "videos_psaumes_audio.json",
    "🎧 Bible audio complète": "videos_bible_audio.json",
}
manquants = {}
for debut, fichier in SERIES.items():
    if not os.path.exists(fichier):
        continue
    reg = json.load(open(fichier, encoding="utf-8"))
    vids = set(v for v in (reg.values() if isinstance(reg, dict) else reg) if isinstance(v, str))
    pl = next((ids for t, ids in par_titre.items() if t.startswith(debut)), None)
    if pl is None:
        manquants[debut] = "PLAYLIST INTROUVABLE"
        continue
    manque = sorted(vids - pl)
    manquants[debut] = {"registre": len(vids), "dans_playlist": len(vids & pl), "manquent": manque[:30]}

print("AUDIT-DEBUT")
print(json.dumps({"playlists": playlists, "series": manquants}, ensure_ascii=False))
print("AUDIT-FIN")
