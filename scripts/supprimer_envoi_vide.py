"""supprimer_envoi_vide.py : supprime un envoi YouTube rate (video jamais traitee).

Refuse de supprimer une video traitee ou vue : seul un envoi interrompu,
bloque sur « Le traitement va bientot commencer », peut partir.

    VIDEO_ID=xxxxxxxxxxx python scripts/supprimer_envoi_vide.py
"""
import os
import sys

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from youtube_garde import verifier_chaine  # noqa: E402


def main():
    vid = os.environ.get("VIDEO_ID", "").strip()
    if not vid:
        sys.exit("::error::VIDEO_ID absent")
    creds = Credentials(token=None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
                        client_id=os.environ["YOUTUBE_CLIENT_ID"],
                        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token", scopes=None)
    creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds)
    verifier_chaine(yt)

    items = yt.videos().list(part="snippet,statistics,processingDetails,status",
                             id=vid).execute().get("items", [])
    if not items:
        sys.exit(f"::error::Video {vid} introuvable sur la chaine")
    v = items[0]
    titre = v["snippet"]["title"]
    vues = int(v.get("statistics", {}).get("viewCount", 0))
    traitement = v.get("processingDetails", {}).get("processingStatus", "?")
    envoi = v.get("status", {}).get("uploadStatus", "?")
    print(f"Video : {titre}")
    print(f"Envoi : {envoi} · traitement : {traitement} · vues : {vues}")
    if vues > 0 or envoi == "processed" or traitement == "succeeded":
        sys.exit("::error::Video traitee ou deja vue : suppression refusee")
    yt.videos().delete(id=vid).execute()
    print(f"::notice::Envoi rate supprime : {vid} ({titre})")


if __name__ == "__main__":
    main()
