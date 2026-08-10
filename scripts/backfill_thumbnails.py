#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vignettes retroactives — applique une vignette aux videos deja publiees.

Le titre suffit a reconstruire la vignette : il contient la reference (ou le
numero du Psaume) et le libelle. Quatre formats coexistent sur la chaine,
selon l'epoque de publication — ils sont tous reconnus ci-dessous.

QUOTA : thumbnails().set() coute 50 unites, la quota journaliere est de
10 000. Environ 190 videos par jour au maximum. La progression est
enregistree dans backfill_progress.json : relancer le lendemain reprend ou
l'on s'etait arrete.

VIDEOS COURTES : sur un Short, YouTube affiche de toute facon une image du
film ; la vignette ne sert que dans les resultats Google. Par defaut on ne
traite donc que les videos longues (--mode long).

Usage :
    python scripts/backfill_thumbnails.py [--mode long|short|all]
                                          [--limit N] [--dry-run]
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import make_thumbnail, load_json, save_json  # noqa: E402

PROGRESS_FILE = "backfill_progress.json"
QUOTA_COST_SET = 50
QUOTA_DAILY = 10000
SAFE_MAX = (QUOTA_DAILY - 500) // QUOTA_COST_SET   # marge pour le reste du jour

# ── Formats de titre rencontres sur la chaine ────────────────────────────
RX_PSAUME = re.compile(r"^Psaume\s+(\d+)\s+—\s+(.+?)\s+\|\s+Lecture", re.I)
RX_THEME = re.compile(r"^(\S+)\s+(.+?)\s+—\s+Versets bibliques", re.U)
RX_REF_NEW = re.compile(
    r"^(.+?\s+\d+:\d+(?:-\d+)?)\s+—\s+(?:\S+\s+)?(.+?)\s+\|", re.U
)
RX_REF_OLD = re.compile(
    r"^(\S+)\s+(.+?)\s+—\s+(.+?\d+:\d+(?:-\d+)?)\s+\|", re.U
)


def parse_title(title):
    """(titre_vignette, sous_titre) ou None si le format est inconnu."""
    m = RX_PSAUME.match(title)
    if m:
        return f"Psaume {m.group(1)}", m.group(2).strip()

    m = RX_THEME.match(title)
    if m:
        return m.group(2).strip(), "Versets bibliques — LSG 1910"

    m = RX_REF_NEW.match(title)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    m = RX_REF_OLD.match(title)
    if m:
        return m.group(3).strip(), m.group(2).strip()

    return None


def get_youtube():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        None,
        refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YOUTUBE_CLIENT_ID"],
        client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
    )
    return build("youtube", "v3", credentials=creds)


def list_videos(youtube):
    """Toutes les videos de la chaine : (id, titre, duree_iso)."""
    ch = youtube.channels().list(part="contentDetails", mine=True).execute()
    uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    ids, page = [], None
    while True:
        r = youtube.playlistItems().list(
            part="contentDetails", playlistId=uploads, maxResults=50, pageToken=page
        ).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        page = r.get("nextPageToken")
        if not page:
            break

    out = []
    for i in range(0, len(ids), 50):
        r = youtube.videos().list(
            part="snippet,contentDetails", id=",".join(ids[i:i + 50])
        ).execute()
        for v in r["items"]:
            out.append((v["id"], v["snippet"]["title"],
                        v["contentDetails"]["duration"]))
    return out


def is_short(title, duration_iso):
    """Distingue Short et video longue.

    La duree seule ne suffit pas : le Psaume 75 dure 1 min 51 s et reste une
    video longue. Le titre est plus sur — les meditations et les paraboles
    portent une marque explicite. La duree ne sert qu'en dernier recours.
    """
    t = title.lower()
    if "lecture complète" in t or "lecture complete" in t:
        return False
    if "versets bibliques" in t:          # meditation thematique
        return False
    if "parabole" in t:
        return False

    m = re.match(r"^PT(?:(\d+)M)?(?:(\d+)S)?$", duration_iso)
    if not m:
        return False
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0) <= 180


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["long", "short", "all"], default="long")
    ap.add_argument("--limit", type=int, default=SAFE_MAX)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    limit = min(args.limit, SAFE_MAX)
    done = set(load_json(PROGRESS_FILE) or [])
    print(f"→ Deja traitees : {len(done)}")

    youtube = get_youtube()
    videos = list_videos(youtube)
    print(f"→ Videos sur la chaine : {len(videos)}")

    todo = []
    unknown = []
    for vid, title, dur in videos:
        if vid in done:
            continue
        short = is_short(title, dur)
        if args.mode == "long" and short:
            continue
        if args.mode == "short" and not short:
            continue
        parsed = parse_title(title)
        if not parsed:
            unknown.append(title)
            continue
        todo.append((vid, title, parsed))

    print(f"→ A traiter : {len(todo)}  (limite de ce passage : {limit})")
    if unknown:
        print(f"→ Titres non reconnus, ignores : {len(unknown)}")
        for t in unknown[:5]:
            print(f"     {t[:78]}")

    if args.dry_run:
        for vid, title, (t, s) in todo[:limit]:
            print(f"   [{vid}] {t}  /  {s}")
        print("\n(dry-run : rien n'a ete envoye)")
        return

    from googleapiclient.http import MediaFileUpload

    ok = fail = 0
    for vid, title, (thumb_title, subtitle) in todo[:limit]:
        try:
            path = make_thumbnail(thumb_title, subtitle=subtitle,
                                  out="thumb_backfill.png")
            youtube.thumbnails().set(
                videoId=vid, media_body=MediaFileUpload(path, mimetype="image/png")
            ).execute()
            done.add(vid)
            ok += 1
            print(f"   ✅ {thumb_title}")
        except Exception as e:
            fail += 1
            msg = str(e)[:160]
            print(f"   ❌ {thumb_title} — {msg}")
            if "quota" in msg.lower():
                print("   ⛔ Quota epuisee : relancer demain.")
                break

    save_json(PROGRESS_FILE, sorted(done))
    reste = len(todo) - ok
    print(f"\n✅ {ok} vignettes posees, {fail} echecs, {reste} restantes.")
    if reste > 0:
        print("   Relancer le workflow pour continuer.")


if __name__ == "__main__":
    main()
