# -*- coding: utf-8 -*-
"""Premier commentaire de la chaine sous chaque video : le lien vers le texte.

Demande de BC (8 novembre 2026) : un commentaire du type « lisez la suite
sur… », pas toujours le meme. Les phrases tournent par _rotate() (meme video,
meme phrase : une reprise de run ne change rien). Elles disent ou se trouve
le texte, sans rien y ajouter : aucun commentaire sur le verset.

    import yt_commentaire
    yt_commentaire.commenter(youtube, video_id, url, ref="Jean 3:16")              # Short
    yt_commentaire.commenter(youtube, video_id, url, titre="Psaume 23", audio=True) # lecture

Ne leve jamais d'exception. 50 unites de quota par commentaire.
L'API ne permet pas d'epingler un commentaire : a faire a la main si voulu.
"""
import hashlib

# Interrupteur. Phrases validees par BC le 8 novembre 2026 (« Frases ok »).
ACTIF = True

COURTS = [
    "📖 Le chapitre entier : {url}",
    "Lisez {ref} dans son chapitre : {url}",
    "Le contexte de ce verset, dans la Bible Louis Segond 1910 : {url}",
    "📖 Tout le chapitre, gratuit et sans publicité : {url}",
    "La suite du texte : {url}",
    "Ce verset et tout son chapitre sur LaBible.app : {url}",
    "📖 Lisez le chapitre complet sur LaBible.app : {url}",
    "Le texte complet, hors ligne et sans compte : {url}",
]

LECTURES = [
    "📖 Le texte de {titre}, à lire pendant l’écoute : {url}",
    "Lisez {titre} sur LaBible.app : {url}",
    "Le texte complet de {titre}, Bible Louis Segond 1910 : {url}",
    "📖 {titre} à lire, gratuitement et sans publicité : {url}",
    "Suivez la lecture dans le texte : {url}",
]

THEMES = [
    "📖 Tous les versets de ce thème : {url}",
    "Les versets de ce thème, Bible Louis Segond 1910 : {url}",
    "📖 La liste complète des versets sur LaBible.app : {url}",
]

AUDIO = "🎧 Toute la Bible audio : https://labible.app/bible-audio"


def _rotate(pool, graine):
    h = int(hashlib.md5(graine.encode("utf-8")).hexdigest(), 16)
    return pool[h % len(pool)]


def texte(video_id, url, ref=None, titre=None, audio=False):
    if "/versets/" in url:
        return _rotate(THEMES, video_id).format(url=url)
    if titre:
        t = _rotate(LECTURES, video_id).format(titre=titre, url=url)
        return t + ("\n" + AUDIO if audio else "")
    return _rotate(COURTS, video_id).format(ref=ref or "ce verset", url=url)


def commenter(youtube, video_id, url, ref=None, titre=None, audio=False):
    if not ACTIF or not video_id or not url:
        return
    try:
        corps = texte(video_id, url, ref, titre, audio)
        ch = youtube.channels().list(part="id", mine=True).execute()["items"][0]["id"]
        youtube.commentThreads().insert(part="snippet", body={"snippet": {
            "channelId": ch, "videoId": video_id,
            "topLevelComment": {"snippet": {"textOriginal": corps}}}}).execute()
        print(f"✅ Commentaire publié : {corps.splitlines()[0][:80]}")
    except Exception as e:
        print(f"⚠️  Commentaire non publié : {str(e)[:200]}")
