"""playlists_themes.py : playlists YouTube des 44 themes du site (labible.app/versets).

    MODE=installer  cree les playlists manquantes, ecrit titre et description
                    (SEO, lien vers la page du theme), pose la couverture
                    assets/playlists/<theme>.jpg. Idempotent : ce qui est fait
                    est note dans playlists_themes.json et n'est pas refait.
    MODE=remplir    range dans chaque playlist de theme les videos deja publiees
                    dont le verset figure dans la liste du theme.

Le quota YouTube est partage avec les publications : chaque ecriture coute 50
unites, d'ou MAX ecritures par passage. Un quota epuise arrete proprement le
passage ; le suivant reprend la ou il s'est arrete.
N'affiche jamais le jeton ni aucun secret.
"""
import json
import os
import re
import sys

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, RACINE)
import yt_themes as yth  # noqa: E402
from youtube_garde import verifier_chaine  # noqa: E402

MODE = os.environ.get("MODE", "installer")
MAX = int(os.environ.get("MAX") or 60)
COUVERTURE = "v1"   # monter pour reposer toutes les couvertures


class Plafond(Exception):
    pass


ecritures = 0


def ecrire(req):
    """Execute une ecriture en comptant le plafond ; un quota epuise devient Plafond."""
    global ecritures
    if ecritures >= MAX:
        raise Plafond()
    try:
        r = req.execute()
    except HttpError as e:
        if e.resp.status == 403 and b"quota" in (e.content or b"").lower():
            raise Plafond()
        raise
    ecritures += 1
    return r


def sauver(etat):
    with open(yth.ETAT, "w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def mes_playlists(yt):
    out, req = {}, yt.playlists().list(part="snippet", mine=True, maxResults=50)
    while req is not None:
        rep = req.execute()
        for it in rep.get("items", []):
            out[" ".join(it["snippet"]["title"].split())] = it
        req = yt.playlists().list_next(req, rep)
    return out


def poser_couverture(yt, pid, chemin):
    existantes = yt.playlistImages().list(part="snippet", parent=pid).execute().get("items", [])
    media = MediaFileUpload(chemin, mimetype="image/jpeg")
    if existantes:
        img = existantes[0]
        ecrire(yt.playlistImages().update(part="snippet", body={
            "id": img["id"], "snippet": {"playlistId": pid, "type": img["snippet"].get("type", "hero")}},
            media_body=media))
        return
    derniere = None
    for typ in ("hero", "medium", "default"):
        try:
            ecrire(yt.playlistImages().insert(part="snippet", body={
                "snippet": {"playlistId": pid, "type": typ}}, media_body=media))
            return
        except HttpError as e:
            derniere = e
            if e.resp.status != 400:
                raise
    raise derniere


def installer(yt, etat):
    pls = mes_playlists(yt)
    for slug in yth.themes():
        e = etat.setdefault(slug, {})
        titre = yth.titre_playlist(slug)
        cle = " ".join(titre.split())
        if not e.get("id"):
            if cle in pls:
                e["id"] = pls[cle]["id"]
            else:
                e["id"] = ecrire(yt.playlists().insert(part="snippet,status", body={
                    "snippet": {"title": titre, "description": yth.description(slug), "defaultLanguage": "fr"},
                    "status": {"privacyStatus": "public"}}))["id"]
                e["seo"] = 1
                print(f"➕ Playlist créée : {titre}")
            sauver(etat)
        if not e.get("seo"):
            sn = pls.get(cle, {}).get("snippet", {})
            desc = sn.get("description", "")
            if yth.lien(slug) not in desc:
                desc = (desc.rstrip() + "\n\n" if desc.strip() else "") + yth.description(slug).split("\n\n", 1)[1]
            ecrire(yt.playlists().update(part="snippet", body={"id": e["id"], "snippet": {
                "title": sn.get("title", titre), "description": desc, "defaultLanguage": "fr"}}))
            e["seo"] = 1
            sauver(etat)
            print(f"✏️  Description : {titre}")
        if e.get("couverture") != COUVERTURE:
            chemin = os.path.join(RACINE, "assets", "playlists", f"{slug}.jpg")
            if os.path.exists(chemin):
                poser_couverture(yt, e["id"], chemin)
                e["couverture"] = COUVERTURE
                sauver(etat)
                print(f"🖼️  Couverture : {titre}")


def remplir(yt, etat):
    uploads = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0][
        "contentDetails"]["relatedPlaylists"]["uploads"]
    videos, req = [], yt.playlistItems().list(part="snippet,contentDetails", playlistId=uploads, maxResults=50)
    while req is not None:
        rep = req.execute()
        videos += [(it["contentDetails"].get("videoPublishedAt", ""), it["contentDetails"]["videoId"],
                    it["snippet"]["title"]) for it in rep.get("items", [])]
        req = yt.playlistItems().list_next(req, rep)
    videos.sort()   # les plus anciennes d'abord : l'ordre de la playlist suit la publication

    contenu = {}

    def dans(pid):
        if pid not in contenu:
            ids, r = set(), yt.playlistItems().list(part="contentDetails", playlistId=pid, maxResults=50)
            while r is not None:
                res = r.execute()
                ids |= {x["contentDetails"]["videoId"] for x in res.get("items", [])}
                r = yt.playlistItems().list_next(r, res)
            contenu[pid] = ids
        return contenu[pid]

    a_faire = []
    for _, vid, titre in videos:
        ref = re.split(r"\s[—|:]\s|\s—", titre, 1)[0]
        for slug in yth.themes_de(ref):
            pid = (etat.get(slug) or {}).get("id")
            if pid and vid not in dans(pid):
                a_faire.append((slug, pid, vid))
                dans(pid).add(vid)
    print(f"::notice::{len(a_faire)} vidéo(s) à ranger dans les playlists de thème")
    faits = 0
    for slug, pid, vid in a_faire:
        ecrire(yt.playlistItems().insert(part="snippet", body={"snippet": {
            "playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}))
        faits += 1
    print(f"::notice::{faits} rangée(s)")


def main():
    creds = Credentials(token=None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
                        client_id=os.environ["YOUTUBE_CLIENT_ID"],
                        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token", scopes=None)
    creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds)
    verifier_chaine(yt)
    etat = yth.etat()
    try:
        if MODE in ("installer", "tout"):
            installer(yt, etat)
        if MODE in ("remplir", "tout"):
            remplir(yt, etat)
    except Plafond:
        print(f"::notice::Plafond atteint ({ecritures} écritures) : la suite au prochain passage")
    finally:
        sauver(etat)
    print(f"::notice::{ecritures} écriture(s) YouTube")


if __name__ == "__main__":
    main()
