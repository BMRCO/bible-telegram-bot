#!/usr/bin/env python3
"""
test_voix_google.py : echantillon d'un Psaume avec les voix Google Chirp 3 HD.

Ne publie rien. Ne modifie pas bible/lsg1910.json : seuls le pied-de-mouche (¶)
et les espaces typographiques sont retires de l'entree donnee a la synthese.
La cle est lue dans GOOGLE_TTS_KEY et envoyee dans l'en-tete X-Goog-Api-Key,
jamais dans l'URL (elle finirait dans les journaux).

Usage : python scripts/test_voix_google.py PSAUME DOSSIER_SORTIE VOIX [VOIX...]
        VOIX = nom court (Charon) ou complet (fr-FR-Chirp3-HD-Charon),
        avec un debit optionnel : Charon@0.9
"""

import base64
import json
import os
import subprocess
import sys
import tempfile
import time

import requests

BIBLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bible", "lsg1910.json")
API = "https://texttospeech.googleapis.com/v1"
PAUSE_TITRE = 1.0
PAUSE_VERSET = 0.5
DEBIT = 0.92   # un peu plus lent que la normale : lecture, pas annonce


def erreur(msg):
    print(f"::error::{msg}")
    sys.exit(1)


def versets(num):
    data = json.load(open(BIBLE, encoding="utf-8"))["verses"]
    out = [v for v in data if v["book_name"] in ("Psaume", "Psaumes") and int(v["chapter"]) == num]
    out.sort(key=lambda v: int(v["verse"]))
    if not out:
        erreur(f"Psaume {num} introuvable")
    return [v["text"] for v in out]


def entree_synthese(texte):
    t = texte.replace("¶", "")
    for esp in (" ", " ", " ", " ", " "):
        t = t.replace(esp, " ")
    return " ".join(t.split())


def entetes(cle):
    return {"X-Goog-Api-Key": cle, "Content-Type": "application/json; charset=utf-8"}


def voix_disponibles(cle):
    r = requests.get(f"{API}/voices", params={"languageCode": "fr-FR"},
                     headers=entetes(cle), timeout=60)
    if r.status_code != 200:
        # Le corps d'erreur Google ne contient pas la cle.
        erreur(f"Liste des voix : HTTP {r.status_code} {r.text[:300]}")
    noms = sorted(v["name"] for v in r.json().get("voices", []) if "Chirp3-HD" in v["name"])
    print("::notice::Voix Chirp 3 HD fr-FR : " + ", ".join(n.split("-")[-1] for n in noms))
    return noms


def synthese(cle, texte, voix, debit, chemin):
    corps = {
        "input": {"text": texte},
        "voice": {"languageCode": "fr-FR", "name": voix},
        "audioConfig": {"audioEncoding": "MP3", "speakingRate": debit},
    }
    for essai in range(3):
        r = requests.post(f"{API}/text:synthesize", headers=entetes(cle),
                          data=json.dumps(corps), timeout=120)
        if r.status_code == 200:
            with open(chemin, "wb") as f:
                f.write(base64.b64decode(r.json()["audioContent"]))
            return
        if r.status_code in (429, 500, 503) and essai < 2:
            time.sleep(5 * (essai + 1))
            continue
        erreur(f"{voix} : HTTP {r.status_code} {r.text[:300]}")


def silence(chemin, secondes):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=24000:cl=mono", "-t", str(secondes), chemin], check=True)


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    cle = os.environ.get("GOOGLE_TTS_KEY", "").strip()
    if not cle:
        erreur("Secret GOOGLE_TTS_KEY absent ou vide")
    num, sortie, specs = int(sys.argv[1]), sys.argv[2], sys.argv[3:]
    os.makedirs(sortie, exist_ok=True)

    dispo = voix_disponibles(cle)
    textes = [f"Psaume {num}."] + [entree_synthese(t) for t in versets(num)]
    tmp = tempfile.mkdtemp()
    p_titre, p_verset = os.path.join(tmp, "s1.wav"), os.path.join(tmp, "s2.wav")
    silence(p_titre, PAUSE_TITRE)
    silence(p_verset, PAUSE_VERSET)

    for k, spec in enumerate(specs):
        nom, _, debit = spec.partition("@")
        debit = float(debit) if debit else DEBIT
        voix = nom if nom.startswith("fr-FR-") else f"fr-FR-Chirp3-HD-{nom}"
        if voix not in dispo:
            print(f"::warning::{voix} n'existe pas, ignoree")
            continue
        morceaux = []
        for i, t in enumerate(textes):
            mp3 = os.path.join(tmp, f"{k}_{i}.mp3")
            synthese(cle, t, voix, debit, mp3)
            wav = mp3[:-4] + ".wav"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3,
                            "-ar", "24000", "-ac", "1", wav], check=True)
            morceaux += [wav, p_titre if i == 0 else p_verset]
        liste = os.path.join(tmp, f"liste_{k}.txt")
        with open(liste, "w") as f:
            f.writelines(f"file '{m}'\n" for m in morceaux)
        court = voix.split("-")[-1]
        suffixe = "" if debit == DEBIT else f"_{str(debit).replace('.', '')}"
        out = os.path.join(sortie, f"chirp_{court}{suffixe}_psaume{num}.mp3")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", liste, "-ac", "1", "-b:a", "64k", out], check=True)
        print(f"OK {out}")

    if not any(f.endswith(".mp3") for f in os.listdir(sortie)):
        erreur("Aucun echantillon produit")


if __name__ == "__main__":
    main()
