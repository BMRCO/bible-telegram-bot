#!/usr/bin/env python3
"""Echantillons de musique douce pour les videos « pour dormir » (BC, 28 nov. 2026 :
« tem que procurar instrumental calmo suave »).

Uniquement des pistes CC0 (domaine public) d'OpenGameArt : aucune n'est dans la
Bibliotheque audio du YouTube, aucune licence a citer. Chaque echantillon fait
~50 s et se monte comme une vraie video : voix (Psaumes 23:1-3), pluie
enregistree, musique au volume et a l'attenuation de production."""
import os
import subprocess
import sys

import numpy as np
import requests

sys.path.insert(0, ".")
import compilation_audio as ca  # noqa: E402
import psaume_meditation as pm  # noqa: E402
from bot import clean_text  # noqa: E402

BASE = "https://opengameart.org/sites/default/files/"
PISTES = {
    "1_another_august": "013_Another_August.mp3",          # cynicmusic, CC0
    "2_calm_ambient_1": "001_Synthwave_4k.mp3",            # cynicmusic, CC0
    "3_calm_ambient_3": "006_lifeWave2k.mp3",              # cynicmusic, CC0
    "4_first_light": "first_light_particles.wav",          # Yoiyami, CC0
}
VERSETS = [
    "L'Éternel est mon berger : je ne manquerai de rien",
    "Il me fait reposer dans de verts pâturages, Il me dirige près des eaux paisibles",
    "Il restaure mon âme, Il me conduit dans les sentiers de la justice, à cause de son nom",
]
D = "travail_musique"
os.makedirs(D, exist_ok=True)
os.makedirs("echantillons", exist_ok=True)

# voix : lecture posee, comme en production
pm.DEBIT_VOIX = "-14%"
morceaux = [np.zeros(int(pm.SR * 1.0), np.float32)]
for i, v in enumerate(VERSETS):
    morceaux.append(ca.lecture_posee(pm.texte_a_lire(clean_text(v)), os.path.join(D, f"v{i}")))
    morceaux.append(np.zeros(int(pm.SR * 2.8), np.float32))
voix = np.concatenate(morceaux)
import wave
wav = os.path.join(D, "voix.wav")
with wave.open(wav, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(pm.SR)
    w.writeframes((np.clip(voix, -1, 1) * 32767).astype(np.int16).tobytes())
duree = len(voix) / pm.SR + 4
pluie = ca.pluie_enregistree(D)

for nom, fichier in PISTES.items():
    src = os.path.join(D, fichier)
    try:
        r = requests.get(BASE + fichier, timeout=180, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        open(src, "wb").write(r.content)
    except Exception as e:
        print(f"⚠️  {nom} : {e}")
        continue
    print(f"🎵 {nom} : {ca.bot.duree_media(src) or 0:.0f} s")
    sortie = f"echantillons/musique_{nom}.mp3"
    fc = (f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[v][sc];"
          f"[1:a]volume=0.14,afade=t=in:d=1,afade=t=out:st={duree - 4:.1f}:d=4[m0];"
          f"[m0][sc]sidechaincompress={pm.DUCKING}[m];"
          f"[v][m]amix=inputs=2:duration=longest:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a0];"
          f"[2:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.45,afade=t=in:d=1,"
          f"afade=t=out:st={duree - 4:.1f}:d=4[pl];[a0][pl]amix=inputs=2:duration=first:normalize=0[a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-ss", "20", "-stream_loop", "-1",
                    "-i", src, "-stream_loop", "-1", "-i", pluie, "-filter_complex", fc, "-map", "[a]",
                    "-t", f"{duree:.1f}", "-c:a", "libmp3lame", "-b:a", "160k", sortie], check=True)
    print(f"✅ {sortie}")
