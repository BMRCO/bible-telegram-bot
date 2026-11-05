"""
annonce.py
==========
Publie une annonce (video animee ou image) sur toutes les plateformes, avec
un texte propre a chacune. Ne touche a aucune progression.

Usage : python annonce.py bible_audio anime
        python annonce.py bible_audio statique

Les medias sont dans assets/annonces/, les textes dans ANNONCES ci-dessous.
"""

import os
import sys
import time

import requests

from bot import (
    publier, finaliser, signaler_echec, publier_reel_facebook,
    upload_video_public, heberger_image, _threads_publish,
    FB_PAGE_ID, FB_PAGE_TOKEN, IG_ACCOUNT_ID, THREADS_ACCESS_TOKEN,
    PINTEREST_ACCESS_TOKEN, PINTEREST_BOARD_ID,
)

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "")
YT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "")
YT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YT_REFRESH = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

CHAINE = "https://www.youtube.com/@LaBible-app"

ANNONCES = {
    "bible_audio": {
        "anime": "assets/annonces/bible_audio_anime.mp4",
        "statique": "assets/annonces/bible_audio_statique.jpg",
        "telegram": (
            "🎧 <b>La Bible entière, lue à voix haute</b>\n\n"
            "La Bible Louis Segond 1910 est maintenant disponible en lecture audio sur YouTube, "
            "chapitre après chapitre, avec le texte à l'écran.\n\n"
            "Pour écouter la Parole en chemin, au travail, avant de dormir.\n\n"
            f"▶️ {CHAINE}"
        ),
        "facebook": (
            "🎧 La Bible entière, lue à voix haute, est maintenant disponible sur YouTube.\n\n"
            "Chapitre après chapitre, le texte de la Bible Louis Segond 1910, lu et affiché à l'écran. "
            "Gratuit, sans commentaire ajouté : la Parole seule.\n\n"
            f"▶️ {CHAINE}\n\n"
            "#BibleAudio #LSG1910 #ParoleDeDieu #LaBibleApp"
        ),
        "instagram": (
            "🎧 La Bible entière, lue à voix haute.\n\n"
            "Maintenant disponible sur YouTube : chapitre après chapitre, le texte Louis Segond 1910 "
            "à l'écran. Gratuit. La Parole seule.\n\n"
            "▶️ Lien dans la bio\n\n"
            "#BibleAudio #Bible #LSG1910 #ParoleDeDieu #Évangile #LaBibleApp"
        ),
        "threads": (
            "La Bible entière, lue à voix haute, chapitre après chapitre. Maintenant disponible "
            "sur YouTube, texte Louis Segond 1910 à l'écran.\n\n"
            f"{CHAINE}"
        ),
        "pinterest_titre": "La Bible entière, lue à voix haute | Bible audio Louis Segond 1910",
        "pinterest": (
            "La Bible Louis Segond 1910 lue à voix haute, chapitre après chapitre, avec le texte "
            "à l'écran. Bible audio en français, gratuite et sans commentaire ajouté, sur la "
            "chaîne YouTube de LaBible.app."
        ),
        "youtube_titre": "La Bible entière, lue à voix haute | Bible audio LSG 1910 #Shorts",
        "youtube": (
            "La Bible Louis Segond 1910 lue à voix haute, chapitre après chapitre, avec le texte "
            "à l'écran. Retrouvez tous les chapitres sur la chaîne.\n\n"
            "📖 Lire la Bible gratuitement : https://labible.app\n\n"
            "#BibleAudio #Bible #LSG1910 #ParoleDeDieu #LaBibleApp"
        ),
    },
}


# ─── Telegram ───
def telegram(media, texte, video):
    if not TG_TOKEN or not TG_CHANNEL:
        raise RuntimeError("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHANNEL vide")
    methode, champ = ("sendVideo", "video") if video else ("sendPhoto", "photo")
    with open(media, "rb") as f:
        data = {"chat_id": TG_CHANNEL, "caption": texte, "parse_mode": "HTML"}
        if video:
            data["supports_streaming"] = "true"
        r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/{methode}",
                          data=data, files={champ: f}, timeout=180)
    if r.status_code != 200 or not r.json().get("ok"):
        # Jamais l'URL : elle contient le jeton.
        raise RuntimeError(f"HTTP {r.status_code} — {r.text[:200]}")
    print("✅ Telegram publié")


# ─── Facebook ───
def facebook(media, texte, video):
    if video:
        if not publier_reel_facebook(media, texte, "Facebook"):
            raise RuntimeError("reel non publié (voir l'alerte ci-dessus)")
        return
    with open(media, "rb") as f:
        r = requests.post(f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/photos",
                          data={"message": texte, "access_token": FB_PAGE_TOKEN},
                          files={"source": f}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} — {r.text[:200]}")
    print("✅ Facebook publié")


def _attendre_meta(container_id, url_base, token, champ, essais, pause):
    for _ in range(essais):
        time.sleep(pause)
        st = requests.get(f"{url_base}/{container_id}", params={"fields": champ, "access_token": token},
                          timeout=30).json().get(champ, "")
        print(f"  ⏳ {st}")
        if st == "FINISHED":
            return
        if st == "ERROR":
            raise RuntimeError("container en ERROR côté Meta")
    raise RuntimeError("container jamais prêt")


# ─── Instagram ───
def instagram(media, texte, video):
    if video:
        url = upload_video_public(media)
        data = {"media_type": "REELS", "video_url": url, "caption": texte, "access_token": FB_PAGE_TOKEN}
    else:
        url = heberger_image(media, "Instagram")
        data = {"image_url": url, "caption": texte, "access_token": FB_PAGE_TOKEN}
    if not url:
        raise RuntimeError("hébergement du média échoué")
    r = requests.post(f"https://graph.facebook.com/v25.0/{IG_ACCOUNT_ID}/media", data=data, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"container — HTTP {r.status_code} — {r.text[:200]}")
    cid = r.json()["id"]
    _attendre_meta(cid, "https://graph.facebook.com/v25.0", FB_PAGE_TOKEN, "status_code",
                   12 if video else 8, 15 if video else 8)
    r = requests.post(f"https://graph.facebook.com/v25.0/{IG_ACCOUNT_ID}/media_publish",
                      data={"creation_id": cid, "access_token": FB_PAGE_TOKEN}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"publication — HTTP {r.status_code} — {r.text[:200]}")
    print("✅ Instagram publié")


# ─── Threads ───
def threads(media, texte, video):
    url = upload_video_public(media) if video else heberger_image(media, "Threads")
    if not url:
        raise RuntimeError("hébergement du média échoué")
    data = {"media_type": "VIDEO" if video else "IMAGE", "text": texte, "access_token": THREADS_ACCESS_TOKEN,
            ("video_url" if video else "image_url"): url}
    r = requests.post("https://graph.threads.net/v1.0/me/threads", data=data, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"container — HTTP {r.status_code} — {r.text[:200]}")
    cid = r.json()["id"]
    if video:
        _attendre_meta(cid, "https://graph.threads.net/v1.0", THREADS_ACCESS_TOKEN, "status", 12, 6)
    _threads_publish(cid)


# ─── Pinterest (image seulement) ───
def pinterest(media, a):
    url = heberger_image(media, "Pinterest")
    if not url:
        raise RuntimeError("hébergement de l'image échoué")
    r = requests.post("https://api.pinterest.com/v5/pins",
                      headers={"Authorization": f"Bearer {PINTEREST_ACCESS_TOKEN}", "Content-Type": "application/json"},
                      json={"board_id": PINTEREST_BOARD_ID, "title": a["pinterest_titre"][:100],
                            "description": a["pinterest"][:800], "link": CHAINE,
                            "media_source": {"source_type": "image_url", "url": url}}, timeout=60)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"HTTP {r.status_code} — {r.text[:200]}")
    print("✅ Pinterest publié")


# ─── YouTube Short (video seulement) ───
def youtube(media, a):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from google.auth.transport.requests import Request
    creds = Credentials(token=None, refresh_token=YT_REFRESH, client_id=YT_ID, client_secret=YT_SECRET,
                        token_uri="https://oauth2.googleapis.com/token",
                        scopes=["https://www.googleapis.com/auth/youtube.upload"])
    creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds)
    resp = yt.videos().insert(part="snippet,status", body={
        "snippet": {"title": a["youtube_titre"], "description": a["youtube"], "categoryId": "22",
                    "tags": ["Bible audio", "Bible audio français", "Louis Segond 1910", "LaBible.app"],
                    "defaultLanguage": "fr", "defaultAudioLanguage": "fr"},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }, media_body=MediaFileUpload(media, mimetype="video/mp4")).execute()
    print(f"✅ YouTube Short — {resp['id']}")


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ANNONCES or sys.argv[2] not in ("anime", "statique"):
        sys.exit(__doc__)
    a = ANNONCES[sys.argv[1]]
    video = sys.argv[2] == "anime"
    media = a[sys.argv[2]]
    print(f"📣 Annonce {sys.argv[1]} ({sys.argv[2]})")
    publier("Telegram annonce", telegram, media, a["telegram"], video)
    publier("Facebook annonce", facebook, media, a["facebook"], video)
    publier("Instagram annonce", instagram, media, a["instagram"], video)
    publier("Threads annonce", threads, media, a["threads"], video)
    if video:
        publier("YouTube annonce", youtube, media, a)
    else:
        publier("Pinterest annonce", pinterest, media, a)
    finaliser("annonce")


if __name__ == "__main__":
    main()
