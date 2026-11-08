"""maj_vignettes_psaumes.py : remplace la vignette des Psaumes narres deja publies
par la vignette actuelle de psaume_meditation.vignette_audio().

Lit videos_psaumes_audio.json ({"numero": "id_video"}). Chaque remplacement
coute 50 unites du quota YouTube : MAX par passage (80 par defaut).
N'affiche jamais le jeton ni aucun secret.
"""
import json
import os
import sys

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import psaume_meditation as pm  # noqa: E402
from youtube_garde import verifier_chaine  # noqa: E402

MAX = int(os.environ.get("MAX") or 80)


def main():
    videos = json.load(open("videos_psaumes_audio.json", encoding="utf-8"))
    creds = Credentials(token=None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
                        client_id=os.environ["YOUTUBE_CLIENT_ID"],
                        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token", scopes=None)
    creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds)
    verifier_chaine(yt)

    faits = 0
    for cle in sorted(videos, key=lambda k: [int(x) if x.isdigit() else x for x in k.split("-")]):
        if faits >= MAX:
            print(f"::notice::Plafond de {MAX} atteint, relancer pour la suite")
            break
        num, _, part = cle.partition("-")
        if not num.isdigit():
            print(f"::warning::Clé « {cle} » ignorée")
            continue
        chemin = f"vignette_ps_{cle}.png"
        pm.vignette_audio(int(num), part_label=part or None, out=chemin)
        yt.thumbnails().set(videoId=videos[cle],
                            media_body=MediaFileUpload(chemin, mimetype="image/png")).execute()
        faits += 1
        print(f"✅ Psaume {cle} : vignette remplacée ({videos[cle]})")
    print(f"::notice::{faits} vignette(s) remplacée(s)")


if __name__ == "__main__":
    main()
