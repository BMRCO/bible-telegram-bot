#!/usr/bin/env python3
"""
test_voix.py : genere un echantillon audio d'un Psaume avec une voix Piper,
une piste par locuteur de la voix, pour l'ecouter avant de choisir.

Ne publie rien. Ne modifie pas bible/lsg1910.json : le texte est lu tel quel ;
seuls le pied-de-mouche (¶) et les espaces typographiques sont retires de
l'entree donnee a la synthese, qui ne sait pas les lire.

Usage : python scripts/test_voix.py MODELE.onnx PSAUME DOSSIER_SORTIE
"""

import json
import os
import subprocess
import sys
import wave

from piper import PiperVoice, SynthesisConfig

BIBLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bible", "lsg1910.json")
PAUSE_TITRE = 1.0      # secondes apres « Psaume N. »
PAUSE_VERSET = 0.38    # secondes entre deux versets
TILDE = "̃"       # nasales francaises : sans ce symbole, la voix les avale


def versets(num):
    data = json.load(open(BIBLE, encoding="utf-8"))["verses"]
    out = [v for v in data if v["book_name"] in ("Psaume", "Psaumes") and int(v["chapter"]) == num]
    out.sort(key=lambda v: int(v["verse"]))
    if not out:
        sys.exit(f"Psaume {num} introuvable dans {BIBLE}")
    return [v["text"] for v in out]


def entree_synthese(texte):
    """Ce que la synthese recoit. Le texte biblique lui-meme n'est pas modifie."""
    t = texte.replace("¶", "")
    for esp in (" ", " ", " ", " ", " "):
        t = t.replace(esp, " ")
    t = t.replace("’", "'")
    return " ".join(t.split())


def phonemes_perdus(voice, texte):
    """Compte les phonemes que le modele ne connait pas : ils seraient
    supprimes en silence (defaut du 29 septembre 2026, voix gilles)."""
    carte = voice.config.phoneme_id_map
    perdus = 0
    for phrase in voice.phonemize(texte):
        perdus += sum(1 for p in phrase if p not in carte)
    return perdus


def silence(wav_out, secondes, rate):
    wav_out.writeframes(b"\x00\x00" * int(rate * secondes))


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    modele, num, sortie = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    os.makedirs(sortie, exist_ok=True)

    voice = PiperVoice.load(modele)
    carte = voice.config.phoneme_id_map
    if TILDE not in carte:
        sys.exit("ECHEC : cette voix n'a pas le tilde combinant (U+0303) : "
                 "elle avalerait les nasales du francais. Voix inutilisable.")

    textes = [f"Psaume {num}."] + [entree_synthese(t) for t in versets(num)]
    perdus = sum(phonemes_perdus(voice, t) for t in textes)
    print(f"Phonemes inconnus du modele : {perdus}")
    if perdus:
        sys.exit("ECHEC : des phonemes seraient supprimes en silence.")

    nb = voice.config.num_speakers or 1
    noms = {v: k for k, v in (voice.config.speaker_id_map or {}).items()}
    rate = voice.config.sample_rate
    nom_modele = os.path.basename(modele).replace(".onnx", "")

    for sid in range(nb):
        nom = noms.get(sid, f"locuteur{sid}")
        wav_path = os.path.join(sortie, f"{nom_modele}_{nom}_psaume{num}.wav")
        cfg = SynthesisConfig(speaker_id=sid if nb > 1 else None, length_scale=1.0)
        with wave.open(wav_path, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(rate)
            for i, t in enumerate(textes):
                for chunk in voice.synthesize(t, syn_config=cfg):
                    out.writeframes(chunk.audio_int16_bytes)
                silence(out, PAUSE_TITRE if i == 0 else PAUSE_VERSET, rate)
        mp3 = wav_path[:-4] + ".mp3"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav_path,
                        "-ac", "1", "-ar", "22050", "-b:a", "64k", mp3], check=True)
        os.remove(wav_path)
        print(f"OK {mp3}")


if __name__ == "__main__":
    main()
