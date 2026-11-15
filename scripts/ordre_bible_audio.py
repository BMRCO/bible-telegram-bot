"""ordre_bible_audio.py : remet la playlist « 🎧 Bible audio complète | Louis
Segond 1910 » dans l'ordre de la Bible (Genese 1 ... Apocalypse 22) et lui pose
sa couverture (assets/playlists/bible-audio.jpg). Demande de BC, 15 nov. 2026.

Les nouveaux chapitres s'inserent deja a leur place (bible_audio.py) ; ce
script range ce qui a ete publie avant et peut etre relance sans risque :
il ne deplace que les videos mal placees. A lancer a la main."""
import os
import sys

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
os.chdir(RACINE)
import bible_audio as ba  # noqa: E402
from bot import load_json  # noqa: E402
from youtube_garde import verifier_chaine  # noqa: E402

COUVERTURE = os.path.join("assets", "playlists", "bible-audio.jpg")


def main():
    creds = Credentials(token=None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
                        client_id=os.environ["YOUTUBE_CLIENT_ID"],
                        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token", scopes=None)
    creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds)
    verifier_chaine(yt)

    pid, req = None, yt.playlists().list(part="snippet", mine=True, maxResults=50)
    while req is not None and not pid:
        rep = req.execute()
        for it in rep.get("items", []):
            if it["snippet"]["title"] == ba.PLAYLIST_COMPLETE:
                pid = it["id"]
        req = yt.playlists().list_next(req, rep)
    if not pid:
        sys.exit(f"Playlist introuvable : {ba.PLAYLIST_COMPLETE}")

    # Couverture (un seul type accepte : « hero » ; update refuse, donc on
    # retire l'ancienne image puis on pose la nouvelle).
    if os.environ.get("SANS_COUVERTURE") != "1":
        for img in yt.playlistImages().list(part="snippet", parent=pid).execute().get("items", []):
            yt.playlistImages().delete(id=img["id"]).execute()
        yt.playlistImages().insert(part="snippet", body={"snippet": {"playlistId": pid, "type": "hero"}},
                                   media_body=MediaFileUpload(COUVERTURE, mimetype="image/jpeg")).execute()
        print("✅ Couverture posée")

    videos = load_json(ba.VIDEOS_FILE)
    cles = {v: k for k, v in videos.items()}

    # Rattrapage : chaque chapitre publie doit etre dans la playlist de son
    # livre et dans la Bible complete (15 nov. 2026 : Apocalypse 1 manquait
    # dans la playlist du livre).
    titres, req = {}, yt.playlists().list(part="snippet", mine=True, maxResults=50)
    while req is not None:
        rep = req.execute()
        for it in rep.get("items", []):
            titres.setdefault(it["snippet"]["title"], it["id"])
        req = yt.playlists().list_next(req, rep)
    contenu = {}
    for cle, vid in sorted(videos.items(), key=lambda kv: ba.rang_canonique(kv[0])):
        i, _ = ba.rang_canonique(cle)
        if i >= len(ba.CANON):
            continue
        nom_pl = f"📖 {ba.nom_affiche(ba.CANON[i])} | Bible audio LSG 1910"
        for p in (titres.get(nom_pl), pid):
            if not p:
                continue
            if p not in contenu:
                contenu[p] = {v for _, v in ba.elements_playlist(yt, p)}
            if vid not in contenu[p]:
                yt.playlistItems().insert(part="snippet", body={"snippet": {
                    "playlistId": p, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
                contenu[p].add(vid)
                print(f"✅ {cle} ajouté à « {nom_pl if p != pid else ba.PLAYLIST_COMPLETE} »")

    actuel = ba.elements_playlist(yt, pid)
    voulu = sorted(actuel, key=lambda e: ba.rang_canonique(cles.get(e[1], "?/0")))
    moves = 0
    for i, (eid, vid) in enumerate(voulu):
        if actuel[i][0] == eid:
            continue
        yt.playlistItems().update(part="snippet", body={"id": eid, "snippet": {
            "playlistId": pid, "position": i,
            "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
        actuel.remove((eid, vid))
        actuel.insert(i, (eid, vid))
        moves += 1
    print(f"::notice::{len(voulu)} vidéos, {moves} déplacées ; ordre : "
          + ", ".join(cles.get(v, "?") for _, v in voulu))


if __name__ == "__main__":
    main()
