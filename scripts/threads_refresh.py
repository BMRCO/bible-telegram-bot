#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Threads — renouvellement automatique du jeton longue duree.

Un jeton Threads longue duree vit 60 jours. Il peut etre rafraichi des qu'il
a plus de 24 h et TANT QU'IL EST ENCORE VALIDE : une fois expire, aucun
rafraichissement n'est possible et il faut refaire tout le parcours OAuth
a la main sur Meta for Developers. D'ou un renouvellement hebdomadaire :
huit executions consecutives devraient echouer avant que le jeton ne meure.

Contrairement a Pinterest, aucun client_secret ni passage par le navigateur
n'est necessaire : le jeton courant suffit.

Variables d'environnement attendues :
    THREADS_ACCESS_TOKEN, GH_PAT_SECRETS, REPO

En cas d'echec le job sort en erreur : GitHub notifie par e-mail.
"""

import base64
import os
import sys

import requests
from nacl import encoding, public

REFRESH_URL = "https://graph.threads.net/refresh_access_token"
GH_API = "https://api.github.com"


def die(msg: str) -> None:
    """Sortie en erreur. Le job GitHub Actions echoue, ce qui declenche
    la notification par e-mail de GitHub — aucun envoi vers Telegram :
    le canal est public et diffuse les versets."""
    print(msg)
    sys.exit(1)


def need(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        die(f"❌ Variable manquante : {name}")
    return val


def refresh(token: str) -> dict:
    r = requests.get(
        REFRESH_URL,
        params={"grant_type": "th_refresh_token", "access_token": token},
        timeout=60,
    )
    if r.status_code != 200:
        die(
            f"❌ Renouvellement refuse ({r.status_code}).\n"
            f"{r.text[:300]}\n\n"
            "Si le jeton a expire, il n'est plus rafraichissable : refaire "
            "le parcours OAuth sur Meta for Developers, puis mettre a jour "
            "le secret THREADS_ACCESS_TOKEN."
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
    token = need("THREADS_ACCESS_TOKEN")
    pat = need("GH_PAT_SECRETS")
    repo = need("REPO")

    print("→ Renouvellement du jeton Threads…")
    data = refresh(token)

    new_token = data.get("access_token", "")
    if not new_token:
        die(f"❌ Reponse sans access_token : {list(data.keys())}")

    exp = data.get("expires_in")
    if exp:
        print(f"   valable : {exp} s (~{int(exp) // 86400} jours)")

    if new_token == token:
        print("ℹ️  Jeton inchange (deja renouvele recemment) — rien a ecrire.")
        return

    put_secret(repo, pat, "THREADS_ACCESS_TOKEN", new_token)
    print("\n✅ Jeton Threads renouvele.")


if __name__ == "__main__":
    main()
