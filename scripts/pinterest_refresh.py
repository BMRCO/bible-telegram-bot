#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pinterest — renouvellement automatique de l'access token.

Utilise le refresh token (permanent) pour obtenir un nouvel access token et
le reecrit dans les GitHub Secrets. Lance chaque semaine : l'access token
vivant 30 jours, une marge large est conservee en cas d'echec ponctuel.

Variables d'environnement attendues :
    PINTEREST_CLIENT_ID, PINTEREST_CLIENT_SECRET, PINTEREST_REFRESH_TOKEN,
    GH_PAT_SECRETS, REPO
"""

import base64
import os
import sys

import requests
from nacl import encoding, public

TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"
GH_API = "https://api.github.com"


def alert(msg: str) -> None:
    """Previent sur Telegram : sans cela, une panne passe inapercue
    pendant des semaines. Silencieux si les identifiants sont absents."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHANNEL_ALERT", "").strip() or os.environ.get(
        "TELEGRAM_CHANNEL", ""
    ).strip()
    if not token or not chat:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat, "text": msg, "disable_notification": False},
            timeout=30,
        )
    except Exception:
        pass


def die(msg: str) -> None:
    print(msg)
    alert(f"\u26a0\ufe0f LaBible.app \u2014 Pinterest\n\n{msg}")
    sys.exit(1)


def need(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        sys.exit(f"❌ Variable manquante : {name}")
    return val


def refresh_token(client_id: str, client_secret: str, refresh: str) -> dict:
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    r = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "refresh_on": "true",
        },
        timeout=60,
    )
    if r.status_code != 200:
        die(
            f"❌ Renouvellement du jeton refuse ({r.status_code}).\n"
            f"{r.text[:300]}\n\n"
            "Si le refresh token a expire, relancer le workflow "
            "« Pinterest — capture OAuth »."
        )
    return r.json()


def put_secret(repo: str, pat: str, name: str, value: str) -> None:
    h = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}

    k = requests.get(f"{GH_API}/repos/{repo}/actions/secrets/public-key", headers=h, timeout=30)
    if k.status_code != 200:
        die(f"❌ Cle publique GitHub inaccessible ({k.status_code}).\n{k.text[:300]}")
    key = k.json()

    sealed = public.SealedBox(public.PublicKey(key["key"].encode(), encoding.Base64Encoder))
    encrypted = base64.b64encode(sealed.encrypt(value.encode())).decode()

    w = requests.put(
        f"{GH_API}/repos/{repo}/actions/secrets/{name}",
        headers=h,
        json={"encrypted_value": encrypted, "key_id": key["key_id"]},
        timeout=30,
    )
    if w.status_code not in (201, 204):
        die(f"❌ Ecriture du secret {name} refusee ({w.status_code}).\n{w.text[:300]}")
    print(f"✅ Secret mis a jour : {name}")


def main() -> None:
    client_id = need("PINTEREST_CLIENT_ID")
    client_secret = need("PINTEREST_CLIENT_SECRET")
    refresh = need("PINTEREST_REFRESH_TOKEN")
    pat = need("GH_PAT_SECRETS")
    repo = need("REPO")

    print("→ Renouvellement de l'access token…")
    data = refresh_token(client_id, client_secret, refresh)

    access = data.get("access_token", "")
    if not access:
        sys.exit(f"❌ Reponse sans access_token : {list(data.keys())}")

    rexp = data.get("refresh_token_expires_in")
    print(f"   access valable  : {data.get('expires_in', '?')} s")
    if rexp:
        print(f"   refresh valable : {rexp} s (~{int(rexp) // 86400} jours)")
    put_secret(repo, pat, "PINTEREST_ACCESS_TOKEN", access)

    # Certains flux renvoient aussi un nouveau refresh token : on le conserve.
    new_refresh = data.get("refresh_token", "")
    if new_refresh and new_refresh != refresh:
        put_secret(repo, pat, "PINTEREST_REFRESH_TOKEN", new_refresh)

    print("\n✅ Access token renouvele.")


if __name__ == "__main__":
    main()
