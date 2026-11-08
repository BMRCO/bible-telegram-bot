"""commentaires_anciens.py : premier commentaire (lien vers le texte) sous les
videos publiees avant le 8 novembre 2026, date ou yt_commentaire.py a ete
branche sur les publications.

Les videos les plus recentes d'abord. MAX commentaires par passage (50 unites
de quota chacun), PAUSE secondes entre deux : des centaines de commentaires
avec lien d'un coup ressembleraient a du spam. Les videos traitees sont notees
dans commentaires_faits.json (commite par le workflow) : jamais deux fois.
Quiz et videos dont le titre ne donne pas de texte : ignores.
N'affiche jamais le jeton ni aucun secret.
"""
import json
import os
import re
import sys
import time

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
import bot  # noqa: E402  (parse_ref_to_chapter_url, APP_URL)
import yt_commentaire as ytc  # noqa: E402
import yt_themes as yth  # noqa: E402
from youtube_garde import verifier_chaine  # noqa: E402

MAX = int(os.environ.get("MAX") or 60)
PAUSE = int(os.environ.get("PAUSE") or 15)
AVANT = os.environ.get("AVANT", "2026-11-09")   # videos publiees avant cette date
FAITS = os.path.join(RACINE, "commentaires_faits.json")

REF = re.compile(r"((?:[1-3]\s)?[A-ZÉÈÀÂÎÔ][a-zà-ÿ]+(?:\s(?:des|de|du)\s[A-Z][a-zà-ÿ]+)?)\s(\d+):(\d+)(?:-(\d+))?")


def themes_titres():
    """Titre de theme de la serie « Versets bibliques » -> slug du site."""
    try:
        import thematic_meditation as tm
        return {v["title"].lower(): k for k, v in tm.THEMES.items()}
    except Exception:
        return {}


def cible(titre, site, th):
    """(url, ref, titre_lecture, audio) ou None."""
    if "Quiz" in titre or "quiz" in titre:
        return None
    m = re.match(r"^\s*Psaume (\d+)\b", titre)
    if m and ("Lecture Audio" in titre or "Lecture Complète" in titre):
        n = m.group(1)
        return f"{bot.APP_URL}/lsg/psaumes/{n}", None, f"Psaume {n}", "Lecture Audio" in titre
    if "Lecture Audio" in titre:      # chapitre de la Bible audio : « Marc 1 | Lecture Audio… »
        m = re.match(r"^\s*(.+?)\s(\d+)\s*\|", titre)
        if m:
            url = bot.parse_ref_to_chapter_url(f"{m.group(1)} {m.group(2)}:1")
            if url != bot.APP_URL:
                return url, None, f"{m.group(1)} {m.group(2)}", True
        return None
    if "Versets bibliques" in titre:
        tete = re.sub(r"^[^\wÀ-ÿ']+", "", titre.split("—")[0]).strip().lower()
        for t, k in th.items():
            if tete.startswith(t) and k in site:
                return f"{bot.APP_URL}/versets/{k}", None, None, False
        return None
    m = REF.search(titre)
    if m:
        ref = f"{m.group(1)} {m.group(2)}:{m.group(3)}" + (f"-{m.group(4)}" if m.group(4) else "")
        url = bot.parse_ref_to_chapter_url(ref)
        if url and url != bot.APP_URL:
            return url, ref, None, False
    return None


def main():
    creds = Credentials(token=None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
                        client_id=os.environ["YOUTUBE_CLIENT_ID"],
                        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token", scopes=None)
    creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds)
    verifier_chaine(yt)
    try:
        faits = set(json.load(open(FAITS, encoding="utf-8")))
    except FileNotFoundError:
        faits = set()

    ch = yt.channels().list(part="id,contentDetails", mine=True).execute()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    videos, req = [], yt.playlistItems().list(part="snippet,contentDetails", playlistId=uploads, maxResults=50)
    while req is not None:
        rep = req.execute()
        videos += [((it["contentDetails"].get("videoPublishedAt") or "")[:10],
                    it["contentDetails"]["videoId"], it["snippet"]["title"]) for it in rep.get("items", [])]
        req = yt.playlistItems().list_next(req, rep)
    videos.sort(reverse=True)   # les plus recentes d'abord

    site, th = yth.themes(), themes_titres()
    a_faire = []
    for date, vid, titre in videos:
        if vid in faits or date >= AVANT:
            continue
        c = cible(titre, site, th)
        if c:
            a_faire.append((vid, titre, c))
    print(f"::notice::{len(a_faire)} vidéo(s) sans commentaire de lien (avant {AVANT})")

    n = 0
    for vid, titre, (url, ref, lecture, audio) in a_faire:
        if n >= MAX:
            break
        corps = ytc.texte(vid, url, ref=ref, titre=lecture, audio=audio)
        try:
            yt.commentThreads().insert(part="snippet", body={"snippet": {
                "channelId": ch["id"], "videoId": vid,
                "topLevelComment": {"snippet": {"textOriginal": corps}}}}).execute()
        except HttpError as e:
            texte = (e.content or b"").decode("utf-8", "ignore")
            if e.resp.status == 403 and "quota" in texte.lower():
                print("::notice::Quota atteint : la suite au prochain passage")
                break
            if e.resp.status == 403 and "commentsDisabled" in texte:
                faits.add(vid)       # commentaires fermes : ne plus essayer
                continue
            print(f"::warning::{titre[:60]} : HTTP {e.resp.status} {texte[:160]}")
            continue
        faits.add(vid)
        n += 1
        print(f"✅ {titre[:60]} → {corps.splitlines()[0][:70]}")
        with open(FAITS, "w", encoding="utf-8") as f:
            json.dump(sorted(faits), f)
        time.sleep(PAUSE)
    with open(FAITS, "w", encoding="utf-8") as f:
        json.dump(sorted(faits), f)
    print(f"::notice::{n} commentaire(s) publié(s), {len(a_faire) - n} restant(s)")


if __name__ == "__main__":
    main()
