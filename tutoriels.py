"""tutoriels.py : serie « Decouvrir LaBible.app », 10 Shorts tutoriels.

Decision de BC (18 novembre 2026) : la serie est publiee sur tous les reseaux,
un episode par jour, avec une playlist YouTube a elle. Les videos sont deja
faites (captures reelles de l'application, montage hors du bot) et rangees
dans tutoriels/NN.mp4 ; leurs textes sont dans tutoriels/episodes.json.

Un passage = l'episode suivant de progress_tutoriels.json. Apres le dixieme,
le workflow tutoriels.yml se desactive lui-meme.

Usage : python tutoriels.py            (episode suivant)
        python tutoriels.py 3          (episode 3, sans toucher a la progression)
Variables : ESSAI=1 (rien n'est publie), SANS_YOUTUBE=1, ONLY_PLATFORM."""
import json
import os
import subprocess
import sys
import time

from bot import APP_URL, publier, signaler_echec, finaliser, load_json, save_json
import bot

DOSSIER = "tutoriels"
EPISODES = os.path.join(DOSSIER, "episodes.json")
PROGRESS_FILE = "progress_tutoriels.json"
VIDEOS_FILE = "videos_tutoriels.json"
ESSAI = os.environ.get("ESSAI") == "1"
SERIE = "Découvrir LaBible.app"
PLAYLIST = "🎓 Découvrir LaBible.app | Tutoriels"
PLAYLIST_DESC = ("Découvrir LaBible.app en dix courtes vidéos : lire la Bible, toucher un verset, "
                 "rechercher, le verset du jour, le plan de lecture, la Bibliothèque, les versets par "
                 "thème, la Bible audio, le quiz biblique et l'installation. La Bible Louis Segond 1910, "
                 "gratuite, sans publicité, même hors ligne : https://labible.app")
HASHTAGS = "#LaBibleApp #Bible #LSG1910 #ApplicationBible #BibleGratuite #ParoleDeDieu"


def episode(n):
    for e in load_json(EPISODES):
        if e["n"] == n:
            return e
    raise KeyError(n)


def total():
    return len(load_json(EPISODES))


# ─── Legendes ───────────────────────────────────────────────────────────────
def tete(e):
    return f"📱 {SERIE} · {e['n']}/{total()}\n{e['titre']}\n\n{e['resume']}"


def legende(e, reseau):
    if reseau == "ig":
        return f"{tete(e)}\n\n👉 LaBible.app : lien en bio.\n\n{HASHTAGS}"
    if reseau == "threads":
        return f"{tete(e)}\n\n👉 {APP_URL}"
    return f"{tete(e)}\n\n👉 {APP_URL}\n\n{HASHTAGS}"


def legende_telegram(e):
    return (f"📱 <b>{SERIE} · {e['n']}/{total()}</b>\n\n<b>{e['titre']}</b>\n\n"
            f"{e['resume']}\n\n👉 {APP_URL}")


def titre_youtube(e):
    return f"{e['titre']} | {SERIE} {e['n']}/{total()}"[:100]


def description_youtube(e):
    return (f"{SERIE}, épisode {e['n']} sur {total()} : {e['titre'].lower()}.\n"
            f"{e['resume']}\n\n"
            f"📱 LaBible.app : la Bible Louis Segond 1910, gratuite, sans publicité, même hors ligne.\n"
            f"👉 {APP_URL}\n"
            f"🎓 Toute la série : la playlist « {PLAYLIST} »\n\n"
            f"#Shorts {HASHTAGS}")


# ─── Reseaux ────────────────────────────────────────────────────────────────
def publier_autres_reseaux(video, e):
    # bot.py construit ses legendes par social_caption : on la remplace pour
    # ce passage par celle de la serie.
    bot.social_caption = lambda r, t, c, cn, url=None, reseau="fb": legende(e, reseau)
    cat = {"emoji": "📱", "tag": "#LaBibleApp"}
    publier("Telegram", bot.send_video, video, legende_telegram(e), e["titre"])
    publier("Facebook reel", bot.post_reel_to_facebook, video, e["titre"], e["resume"], cat, "jesus", APP_URL)
    publier("Instagram reel", bot.post_reel_to_instagram, video, e["titre"], e["resume"], cat, "jesus", APP_URL)
    publier("Threads reel", bot.post_reel_to_threads, video, e["titre"], e["resume"], cat, "jesus", APP_URL)
    publier("Pinterest", epingle, video, e)


def epingle(video, e):
    if not bot.should_post("pinterest"):
        print("⏭️  Pinterest skip (filtro)")
        return
    if not bot.PINTEREST_ACCESS_TOKEN:
        signaler_echec("Pinterest", "PINTEREST_ACCESS_TOKEN vide ou absent")
        return
    image = "tutoriel_pin.jpg"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "5", "-i", video,
                    "-frames:v", "1", "-q:v", "3", image], check=True)
    url = bot.heberger_image(image, "Pinterest")
    if not url:
        return
    import requests
    r = requests.post("https://api.pinterest.com/v5/pins",
                      headers={"Authorization": f"Bearer {bot.PINTEREST_ACCESS_TOKEN}",
                               "Content-Type": "application/json"},
                      json={"board_id": bot.PINTEREST_BOARD_ID,
                            "title": f"{e['titre']} | {SERIE}"[:100],
                            "description": (f"{e['resume']}\n\nLaBible.app : la Bible Louis Segond 1910, "
                                            f"gratuite, sans publicité, même hors ligne.")[:800],
                            "link": APP_URL,
                            "media_source": {"source_type": "image_url", "url": url}}, timeout=60)
    if r.status_code in (200, 201):
        print(f"✅ Pinterest publié — {r.json().get('id')}")
    else:
        signaler_echec("Pinterest", f"HTTP {r.status_code} — {r.text[:200]}")


# ─── YouTube ────────────────────────────────────────────────────────────────
def youtube():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from youtube_garde import verifier_chaine
    creds = Credentials(token=None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
                        client_id=os.environ["YOUTUBE_CLIENT_ID"],
                        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token", scopes=None)
    creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds)
    verifier_chaine(yt)
    return yt


def playlist(yt, progress):
    """La playlist de la serie : retrouvee par son titre, ou creee une fois."""
    if progress.get("playlist"):
        return progress["playlist"]
    req, trouve = yt.playlists().list(part="snippet", mine=True, maxResults=50), None
    while req is not None and not trouve:
        rep = req.execute()
        for it in rep.get("items", []):
            if it["snippet"]["title"] == PLAYLIST:
                trouve = it["id"]
        req = yt.playlists().list_next(req, rep)
    pid = trouve or yt.playlists().insert(part="snippet,status", body={
        "snippet": {"title": PLAYLIST, "description": PLAYLIST_DESC, "defaultLanguage": "fr"},
        "status": {"privacyStatus": "public"}}).execute()["id"]
    progress["playlist"] = pid
    print(f"➕ Playlist {'retrouvée' if trouve else 'créée'} : {PLAYLIST}")
    time.sleep(8)   # une playlist toute neuve n'est pas lisible tout de suite
    return pid


def upload(video, e, progress):
    from googleapiclient.http import MediaFileUpload
    import yt_commentaire
    yt = youtube()
    body = {"snippet": {"title": titre_youtube(e), "description": description_youtube(e),
                        "tags": ["LaBible.app", "Bible", "application Bible", "Bible gratuite", "tutoriel",
                                 "Louis Segond", "LSG1910", "Shorts"],
                        "categoryId": "22", "defaultLanguage": "fr"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    vid = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(video, mimetype="video/mp4", resumable=True)
                             ).execute()["id"]
    print(f"✅ YouTube : https://youtube.com/watch?v={vid}")
    try:
        pid = playlist(yt, progress)
        yt.playlistItems().insert(part="snippet", body={"snippet": {
            "playlistId": pid, "position": max(0, e["n"] - 1),
            "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
        print(f"✅ Ajoutée à la playlist « {PLAYLIST} »")
    except Exception as ex:
        print(f"⚠️  Playlist non mise à jour : {str(ex)[:200]}")
    yt_commentaire.commenter(yt, vid, APP_URL, titre=e["titre"])
    return vid


def arreter_workflow():
    """Desactive tutoriels.yml une fois la serie terminee (API GitHub)."""
    import requests
    depot, jeton = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GH_TOKEN")
    if not depot or not jeton:
        print("⚠️  Hors GitHub Actions : workflow non désactivé.")
        return
    r = requests.put(f"https://api.github.com/repos/{depot}/actions/workflows/tutoriels.yml/disable",
                     headers={"Authorization": f"Bearer {jeton}", "Accept": "application/vnd.github+json"},
                     timeout=30)
    print("::notice::Série tutoriels terminée : workflow désactivé." if r.status_code == 204
          else f"::warning::Workflow non désactivé (HTTP {r.status_code})")


def main():
    progress = load_json(PROGRESS_FILE) if os.path.exists(PROGRESS_FILE) else {}
    manuel = len(sys.argv) > 1 and sys.argv[1].isdigit()
    n = int(sys.argv[1]) if manuel else int(progress.get("prochain", 1) or 1)
    if n > total():
        print("🏁 Les dix épisodes ont été publiés.")
        arreter_workflow()
        return
    e = episode(n)
    video = os.path.join(DOSSIER, f"{n:02d}.mp4")
    print(f"🎓 {SERIE} {n}/{total()} : {e['titre']}")
    if ESSAI:
        print(titre_youtube(e) + "\n\n" + description_youtube(e) + "\n\n" + legende(e, "fb"))
        print("🧪 ESSAI : rien n'est publié.")
        return
    vid = None
    if os.environ.get("SANS_YOUTUBE") != "1":
        vid = publier("YouTube Tutoriel", upload, video, e, progress)
    publier_autres_reseaux(video, e)
    if vid:
        videos = load_json(VIDEOS_FILE) if os.path.exists(VIDEOS_FILE) else {}
        videos[str(n)] = vid
        save_json(VIDEOS_FILE, videos)
    if not manuel and (vid or os.environ.get("SANS_YOUTUBE") == "1"):
        progress["prochain"] = n + 1
    save_json(PROGRESS_FILE, progress)
    finaliser("tutoriel")


if __name__ == "__main__":
    main()
