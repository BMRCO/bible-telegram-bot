"""organiser_playlists.py : range les videos lues a voix haute dans leurs playlists.

Lit videos_bible_audio.json et videos_psaumes_audio.json, puis :
  - Bible audio : chaque chapitre dans « 📖 Livre | Bible audio LSG 1910 »
    (creee si absente) et dans « 🎧 Bible audio complete | Louis Segond 1910 » ;
  - Psaumes narres : chaque Psaume dans « 🎙️ Les Psaumes lus à voix haute ».
Ajoute ce qui manque dans l'ordre de lecture, retire les doublons, ne touche
a aucune autre playlist ni a aucune video. Affiche l'inventaire des playlists.
N'affiche jamais le jeton ni aucun secret.
"""
import json
import os
import sys

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bible_audio as ba  # noqa: E402  (ordre des livres, noms affiches)
from youtube_garde import verifier_chaine  # noqa: E402

PL_COMPLETE = ba.PLAYLIST_COMPLETE
PL_PSAUMES = "🎙️ Les Psaumes lus à voix haute"
DESC_PSAUMES = (
    "Les 150 Psaumes lus à voix haute, en entier, dans le texte de la Bible "
    "Louis Segond 1910 (domaine public), sans commentaire ajouté. Un Psaume "
    "chaque jour. Le texte complet est accessible gratuitement, hors ligne et "
    "sans publicité sur LaBible.app."
)


def charger(nom):
    try:
        return json.load(open(nom, encoding="utf-8"))
    except FileNotFoundError:
        return {}


def mes_playlists(yt):
    out, req = {}, yt.playlists().list(part="snippet,contentDetails", mine=True, maxResults=50)
    while req is not None:
        res = req.execute()
        for it in res.get("items", []):
            out.setdefault(it["snippet"]["title"], (it["id"], it["contentDetails"]["itemCount"]))
        req = yt.playlists().list_next(req, res)
    return out


def contenu(yt, pl_id):
    items, req = [], yt.playlistItems().list(part="snippet", playlistId=pl_id, maxResults=50)
    while req is not None:
        res = req.execute()
        items += [(it["id"], it["snippet"]["resourceId"]["videoId"]) for it in res.get("items", [])]
        req = yt.playlistItems().list_next(req, res)
    return items


def creer(yt, titre, desc):
    pid = yt.playlists().insert(part="snippet,status", body={
        "snippet": {"title": titre, "description": desc, "defaultLanguage": "fr"},
        "status": {"privacyStatus": "public"}}).execute()["id"]
    print(f"➕ Playlist créée : {titre}")
    return pid


def ranger(yt, titre, pid, videos):
    """videos : liste ordonnee d'identifiants. Retire les doublons, ajoute les manquants."""
    deja, vus, retires = contenu(yt, pid), set(), 0
    for item_id, vid in deja:
        if vid in vus:
            yt.playlistItems().delete(id=item_id).execute()
            retires += 1
        vus.add(vid)
    ajoutes = 0
    for vid in videos:
        if vid in vus:
            continue
        yt.playlistItems().insert(part="snippet", body={"snippet": {
            "playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
        vus.add(vid)
        ajoutes += 1
    print(f"✅ {titre} : {ajoutes} ajoutée(s), {retires} doublon(s) retiré(s), {len(vus)} vidéo(s)")


def main():
    creds = Credentials(token=None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
                        client_id=os.environ["YOUTUBE_CLIENT_ID"],
                        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token", scopes=None)
    creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds)
    verifier_chaine(yt)
    pls = mes_playlists(yt)

    # ── Bible audio, dans l'ordre de lecture ──
    bible = charger("videos_bible_audio.json")
    # Meme cle que bible_audio.py : slugify_book(nom_affiche(livre)) + "/" + chapitre.
    slugs = {ba.slugify_book(ba.nom_affiche(livre)): livre for livre in ba.ORDRE}

    def cle_ordre(cle):
        s, ch = cle.rsplit("/", 1)
        livre = slugs.get(s)
        return (ba.ORDRE.index(livre) if livre else 999, int(ch))

    complets, par_livre = [], {}
    for cle in sorted(bible, key=cle_ordre):
        s = cle.rsplit("/", 1)[0]
        livre = slugs.get(s)
        if not livre:
            print(f"::warning::Livre inconnu pour « {cle} », ignoré")
            continue
        complets.append(bible[cle])
        par_livre.setdefault(livre, []).append(bible[cle])
    if complets:
        pid = pls[PL_COMPLETE][0] if PL_COMPLETE in pls else creer(
            yt, PL_COMPLETE, "Toute la Bible Louis Segond 1910 lue à voix haute, chapitre après "
                             "chapitre, sans commentaire ajouté. Le texte complet est accessible "
                             "gratuitement, hors ligne et sans publicité sur LaBible.app.")
        ranger(yt, PL_COMPLETE, pid, complets)
    for livre, vids in par_livre.items():
        titre = f"📖 {ba.nom_affiche(livre)} | Bible audio LSG 1910"
        pid = pls[titre][0] if titre in pls else creer(
            yt, titre, f"{ba.nom_complet(livre)}, lu à voix haute, chapitre après chapitre, dans le "
                       f"texte de la Bible Louis Segond 1910 (domaine public), sans commentaire "
                       f"ajouté. Le texte complet est accessible gratuitement, hors ligne et sans "
                       f"publicité sur LaBible.app.")
        ranger(yt, titre, pid, vids)

    # ── Psaumes narres ──
    psaumes = charger("videos_psaumes_audio.json")
    if psaumes:
        vids = [psaumes[k] for k in sorted(psaumes, key=int)]
        pid = pls[PL_PSAUMES][0] if PL_PSAUMES in pls else creer(yt, PL_PSAUMES, DESC_PSAUMES)
        ranger(yt, PL_PSAUMES, pid, vids)

    print("::group::Playlists de la chaîne")
    for titre, (pid, n) in sorted(mes_playlists(yt).items()):
        print(f"{n:5d}  {titre}")
    print("::endgroup::")


if __name__ == "__main__":
    main()
