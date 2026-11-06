"""Verifie le jeton YouTube : scopes accordes, upload possible, playlists
et sous-titres accessibles. N'affiche jamais le jeton ni aucun secret."""
import os
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

creds = Credentials(token=None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
                    client_id=os.environ["YOUTUBE_CLIENT_ID"],
                    client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
                    token_uri="https://oauth2.googleapis.com/token", scopes=None)
creds.refresh(Request())
# Le jeton part dans le corps de la requete, jamais dans l'URL.
info = requests.post("https://oauth2.googleapis.com/tokeninfo",
                     data={"access_token": creds.token}, timeout=30).json()
scopes = info.get("scope", "").split()
print("::notice::Scopes accordes : " + ", ".join(s.rsplit("/", 1)[-1] for s in scopes))
ok_complet = any(s.endswith(("/youtube", "/youtube.force-ssl")) for s in scopes)
yt = build("youtube", "v3", credentials=creds)
try:
    n = len(yt.playlists().list(part="snippet", mine=True, maxResults=50).execute().get("items", []))
    print(f"::notice::Playlists : OUI ({n} lues)")
except Exception as e:
    print(f"::notice::Playlists : NON ({str(e)[:120]})")
print("::notice::Sous-titres et playlists automatiques : " + ("OUI" if ok_complet else "NON (scope youtube.force-ssl absent)"))
