"""stats_youtube.py : statistiques publiques de la chaine, par serie.

Lit les videos de la chaine (Data API : vues, j'aime, commentaires, duree,
date) et imprime un JSON entre deux balises, pour analyse. Ne modifie rien.
Cout : environ 60 unites de quota. N'affiche jamais le jeton ni aucun secret.
"""
import json
import os
import re
import sys

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from youtube_garde import verifier_chaine  # noqa: E402


def serie(titre):
    t = titre
    if "Lecture Audio" in t and t.startswith("Psaume"):
        return "Psaumes narrés"
    if "Bible audio" in t or "Bible Audio" in t or "BIBLE AUDIO" in t:
        return "Bible audio"
    if "Quiz biblique" in t or "Quiz Biblique" in t:
        return "Quiz"
    if "Versets bibliques" in t:
        return "Versets bibliques (thèmes)"
    if "Lecture Complète" in t and t.startswith("Psaume"):
        return "Psaumes lecture (série muette)"
    m = re.search(r"—\s*(.+?)\s*\|\s*Bible Louis Segond 1910", t)
    if m:
        return "Short " + m.group(1)
    if "Semaine" in t or "Pâques" in t or "Saint" in t or "Rameaux" in t:
        return "Semaine Sainte"
    if t.startswith("✝️") and "Bible LSG1910" in t:
        return "Paraboles"
    if "Pentec" in t:
        return "Pentecôte"
    return "Autres (anciens formats)"


def secondes(iso):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def main():
    creds = Credentials(token=None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
                        client_id=os.environ["YOUTUBE_CLIENT_ID"],
                        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token", scopes=None)
    creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds)
    verifier_chaine(yt)

    ch = yt.channels().list(part="snippet,statistics,contentDetails", mine=True).execute()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, req = [], yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50)
    while req is not None:
        rep = req.execute()
        ids += [it["contentDetails"]["videoId"] for it in rep.get("items", [])]
        req = yt.playlistItems().list_next(req, rep)

    videos = []
    for i in range(0, len(ids), 50):
        rep = yt.videos().list(part="snippet,statistics,contentDetails",
                               id=",".join(ids[i:i + 50])).execute()
        for v in rep.get("items", []):
            st = v.get("statistics", {})
            videos.append({
                "id": v["id"], "titre": v["snippet"]["title"],
                "date": v["snippet"]["publishedAt"][:10],
                "duree": secondes(v["contentDetails"].get("duration")),
                "vues": int(st.get("viewCount", 0)), "jaime": int(st.get("likeCount", 0)),
                "comm": int(st.get("commentCount", 0)),
                "serie": serie(v["snippet"]["title"]),
            })
    out = {"chaine": {"titre": ch["snippet"]["title"],
                      "abonnes": int(ch["statistics"].get("subscriberCount", 0)),
                      "vues": int(ch["statistics"].get("viewCount", 0)),
                      "videos": int(ch["statistics"].get("videoCount", 0))},
           "videos": videos}
    print("=====STATS-DEBUT=====")
    print(json.dumps(out, ensure_ascii=False))
    print("=====STATS-FIN=====")


if __name__ == "__main__":
    main()
