#!/usr/bin/env python3
"""
test_voix_edge.py : echantillon d'un Psaume avec les voix neuronales Microsoft
(celles de « Lecture a voix haute » d'Edge), via le paquet edge-tts.

Ne publie rien. Ne modifie pas bible/lsg1910.json : seuls le pied-de-mouche (¶)
et les espaces typographiques sont retires de l'entree donnee a la synthese.
Les references (« 23:1 ») ne sont jamais lues : edge-tts les prend pour des heures.

Usage : python scripts/test_voix_edge.py PSAUME DOSSIER_SORTIE VOIX [VOIX...]
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile

import edge_tts
import edge_tts.communicate as _comm

# edge-tts ecrit xml:lang='en-US' en dur dans le SSML. Les voix multilingues
# (Remy, Vivienne) s'en servent pour deviner la langue : elles commencent alors
# en anglais ou en espagnol avant de passer au francais. On force le francais.
# (La balise <lang> n'est pas acceptee par ce point d'acces : pas d'audio.)
def _mkssml_fr(tc, escaped_text):
    if isinstance(escaped_text, bytes):
        escaped_text = escaped_text.decode("utf-8")
    return (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='fr-FR'>"
        f"<voice name='{tc.voice}'>"
        f"<prosody pitch='{tc.pitch}' rate='{tc.rate}' volume='{tc.volume}'>"
        f"{escaped_text}"
        "</prosody></voice></speak>"
    )

_comm.mkssml = _mkssml_fr

BIBLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bible", "lsg1910.json")
PAUSE_TITRE = 1.0
PAUSE_VERSET = 0.5
DEBIT = "-8%"   # un peu plus lent que la normale : lecture, pas annonce


def versets(num):
    data = json.load(open(BIBLE, encoding="utf-8"))["verses"]
    out = [v for v in data if v["book_name"] in ("Psaume", "Psaumes") and int(v["chapter"]) == num]
    out.sort(key=lambda v: int(v["verse"]))
    if not out:
        sys.exit(f"Psaume {num} introuvable")
    return [v["text"] for v in out]


def entree_synthese(texte):
    t = texte.replace("¶", "")
    for esp in (" ", " ", " ", " ", " "):
        t = t.replace(esp, " ")
    return " ".join(t.split())


async def segment(texte, voix, chemin, debit=DEBIT, hauteur="+0Hz"):
    await edge_tts.Communicate(texte, voix, rate=debit, pitch=hauteur).save(chemin)


def silence(chemin, secondes):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "anullsrc=r=24000:cl=mono", "-t", str(secondes), chemin], check=True)


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    num, sortie, voix_liste = int(sys.argv[1]), sys.argv[2], sys.argv[3:]
    os.makedirs(sortie, exist_ok=True)
    textes = [f"Psaume {num}."] + [entree_synthese(t) for t in versets(num)]
    tmp = tempfile.mkdtemp()
    p_titre, p_verset = os.path.join(tmp, "s1.wav"), os.path.join(tmp, "s2.wav")
    silence(p_titre, PAUSE_TITRE)
    silence(p_verset, PAUSE_VERSET)

    for spec in voix_liste:
        # « Voix » ou « Voix@debit@hauteur », par ex. fr-FR-RemyMultilingualNeural@-15%@-6Hz
        voix, debit, hauteur = (spec.split("@") + [DEBIT, "+0Hz"])[:3]
        morceaux = []
        if "Multilingual" in voix:
            # Une voix multilingue devine la langue sur chaque requete. Sur un
            # morceau court (« Psaume 23. ») elle se trompe : anglais, espagnol.
            # On lui donne donc tout le Psaume d'un seul bloc, en francais.
            mp3 = os.path.join(tmp, f"{spec}_bloc.mp3")
            asyncio.run(segment(" ".join(textes), voix, mp3, debit, hauteur))
            textes_v = []
            morceaux = [mp3]
        else:
            textes_v = textes
        for i, t in enumerate(textes_v):
            mp3 = os.path.join(tmp, f"{spec}_{i}.mp3")
            asyncio.run(segment(t, voix, mp3, debit, hauteur))
            wav = mp3[:-4] + ".wav"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3,
                            "-ar", "24000", "-ac", "1", wav], check=True)
            morceaux += [wav, p_titre if i == 0 else p_verset]
        liste = os.path.join(tmp, f"liste_{len(os.listdir(tmp))}.txt")
        with open(liste, "w") as f:
            f.writelines(f"file '{m}'\n" for m in morceaux)
        nom = voix.split("-")[-1].replace("Neural", "") + ("" if spec == voix else "_lent_grave")
        out = os.path.join(sortie, f"edge_{nom}_psaume{num}.mp3")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", liste, "-ac", "1", "-b:a", "64k", out], check=True)
        print(f"OK {out}")


if __name__ == "__main__":
    main()
