"""dernieres_publications.py : affiche les dernieres publications de chaque reseau
(Facebook, Instagram, Threads, Pinterest), pour verifier ce qui est parti.
Lecture seule. N'affiche jamais de jeton."""
import os
import requests

N = int(os.environ.get("N") or 6)
FB_ID, FB_TOK = os.environ.get("FB_PAGE_ID", ""), os.environ.get("FB_PAGE_TOKEN", "")
IG_ID = os.environ.get("IG_ACCOUNT_ID", "")
TH_TOK = os.environ.get("THREADS_ACCESS_TOKEN", "")
PIN_TOK, PIN_BOARD = os.environ.get("PINTEREST_ACCESS_TOKEN", ""), os.environ.get("PINTEREST_BOARD_ID", "")


def court(t):
    return " ".join((t or "").split())[:90]


def bloc(nom, f):
    print(f"\n===== {nom} =====")
    try:
        f()
    except Exception as e:
        print(f"(lecture impossible : {type(e).__name__} {str(e)[:150]})")


def fb():
    for k in ("posts", "video_reels"):
        r = requests.get(f"https://graph.facebook.com/v25.0/{FB_ID}/{k}",
                         params={"fields": "id,created_time,message,description", "limit": N,
                                 "access_token": FB_TOK}, timeout=30).json()
        print(f"-- {k}")
        for p in r.get("data", []):
            print(p.get("created_time", ""), "|", court(p.get("message") or p.get("description")))
        if "error" in r:
            print("erreur :", r["error"].get("message", "")[:120])


def ig():
    r = requests.get(f"https://graph.facebook.com/v25.0/{IG_ID}/media",
                     params={"fields": "id,timestamp,caption,media_type", "limit": N,
                             "access_token": FB_TOK}, timeout=30).json()
    for p in r.get("data", []):
        print(p.get("timestamp", ""), p.get("media_type", ""), "|", court(p.get("caption")))
    if "error" in r:
        print("erreur :", r["error"].get("message", "")[:120])


def threads():
    r = requests.get("https://graph.threads.net/v1.0/me/threads",
                     params={"fields": "id,timestamp,text,media_type", "limit": N,
                             "access_token": TH_TOK}, timeout=30).json()
    for p in r.get("data", []):
        print(p.get("timestamp", ""), p.get("media_type", ""), "|", court(p.get("text")))


def pinterest():
    r = requests.get(f"https://api.pinterest.com/v5/boards/{PIN_BOARD}/pins",
                     headers={"Authorization": f"Bearer {PIN_TOK}"}, params={"page_size": N}, timeout=30).json()
    for p in r.get("items", []):
        print(p.get("created_at", ""), "|", court(p.get("title")))


bloc("Facebook", fb)
bloc("Instagram", ig)
bloc("Threads", threads)
bloc("Pinterest", pinterest)
