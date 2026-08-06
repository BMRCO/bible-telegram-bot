#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pinterest OAuth — capture initiale.

Echange le code d'autorisation contre un couple access_token / refresh_token,
en demandant `refresh_on=true` afin d'obtenir un refresh token permanent
(everlasting refresh). Les deux jetons sont ensuite ecrits directement dans
les GitHub Secrets du depot, via l'API, chiffres avec la cle publique du
depot : ils ne transitent jamais en clair dans les logs.

Variables d'environnement attendues :
    PINTEREST_CLIENT_ID, PINTEREST_CLIENT_SECRET, GH_PAT_SECRETS,
    OAUTH_CODE, REPO, REDIRECT_URI
"""

import base64
import os
import sys

import requests
from nacl import encoding, public

TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"
GH_API = "https://api.github.com"


def need(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        sys.exit(f"❌ Variable manquante : {name}")
    return val


def exchange_code(client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict:
    """Echange le code d'autorisation contre les jetons."""
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    r = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            # Refresh token permanent : plus de renouvellement manuel.
            "refresh_on": "true",
        },
        timeout=60,
    )
    if r.status_code != 200:
        sys.exit(f"❌ Pinterest ({r.status_code}) : {r.text[:400]}")
    return r.json()


def put_secret(repo: str, pat: str, name: str, value: str) -> None:
    """Ecrit un secret chiffre dans le depot GitHub."""
    h = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github+json"}

    k = requests.get(f"{GH_API}/repos/{repo}/actions/secrets/public-key", headers=h, timeout=30)
    if k.status_code != 200:
        sys.exit(f"❌ Cle publique GitHub ({k.status_code}) : {k.text[:300]}")
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
        sys.exit(f"❌ Ecriture du secret {name} ({w.status_code}) : {w.text[:300]}")
    print(f"✅ Secret ecrit : {name}")


def main() -> None:
    client_id = need("PINTEREST_CLIENT_ID")
    client_secret = need("PINTEREST_CLIENT_SECRET")
    pat = need("GH_PAT_SECRETS")
    code = need("OAUTH_CODE")
    repo = need("REPO")
    redirect_uri = os.environ.get("REDIRECT_URI", "https://labible.app/").strip()

    # Le code arrive parfois colle avec le reste de l'URL : on nettoie.
    if "code=" in code:
        code = code.split("code=", 1)[1]
    code = code.split("&")[0].split("#")[0].strip()

    print("→ Echange du code contre les jetons…")
    data = exchange_code(client_id, client_secret, code, redirect_uri)

    access = data.get("access_token", "")
    refresh = data.get("refresh_token", "")
    if not access or not refresh:
        sys.exit(f"❌ Reponse incomplete : {list(data.keys())}")

    print(f"   type de reponse   : {data.get('response_type', '?')}")
    print(f"   scopes            : {data.get('scope', '?')}")
    print(f"   access valable    : {data.get('expires_in', '?')} s")
    rexp = data.get("refresh_token_expires_in")
    if rexp:
        print(f"   refresh valable   : {rexp} s (~{int(rexp) // 86400} jours)")
    else:
        print("   refresh valable   : permanent")

    put_secret(repo, pat, "PINTEREST_ACCESS_TOKEN", access)
    put_secret(repo, pat, "PINTEREST_REFRESH_TOKEN", refresh)

    print("\n✅ Termine. Le renouvellement automatique peut desormais fonctionner.")
    if data.get("response_type") != "everlasting_refresh":
        jours = int(data.get("refresh_token_expires_in", 0)) // 86400 or "?"
        print(
            f"⚠️  Refresh NON permanent (valable {jours} jours).\n"
            "    Le renouvellement hebdomadaire prolonge ce delai a chaque\n"
            "    execution reussie. En revanche, si le workflow echoue sans\n"
            "    interruption pendant toute cette periode, le refresh token\n"
            "    expire et il faudra relancer cette capture OAuth."
        )


if __name__ == "__main__":
    main()
