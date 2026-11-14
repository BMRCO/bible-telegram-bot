"""deja_publie.py : versets deja publies, serie par serie.

Regle de BC (14 novembre 2026) : un verset ne sort jamais deux fois dans la
MEME serie (Promesses, Paroles de Jesus, Sagesse, Propheties, Protection,
Psaume du soir, Les derniers temps...). Il peut sortir dans une autre serie :
le theme est different.

Fichier : versets_publies.json = {serie: ["psaumes|23|1", ...]} (livre
normalise sans accents, un verset par entree ; une plage compte pour chacun
de ses versets). Rempli au depart depuis les titres de la chaine YouTube
(scripts/registre_versets.py), puis a chaque publication.
"""
import json
import os

from yt_themes import versets_de

FICHIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "versets_publies.json")
_etat = None


def _charger():
    global _etat
    if _etat is None:
        try:
            _etat = json.load(open(FICHIER, encoding="utf-8"))
        except FileNotFoundError:
            _etat = {}
    return _etat


def cles(ref):
    return [f"{b}|{c}|{v}" for b, c, v in versets_de(ref)]


def deja(serie, ref):
    """True si un des versets de `ref` est deja sorti dans cette serie."""
    vus = set(_charger().get(serie, []))
    return any(k in vus for k in cles(ref))


def noter(serie, ref):
    etat = _charger()
    vus = set(etat.get(serie, []))
    vus.update(cles(ref))
    etat[serie] = sorted(vus)
    with open(FICHIER, "w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False, indent=0, sort_keys=True)
        f.write("\n")
