#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Banc d'essai des accroches — LaBible.app

POURQUOI CE FICHIER EXISTE
--------------------------
Entre le 7 et le 10 septembre 2026, six defauts d'accroche ont ete trouves.
Tous les six de la meme facon : BC lisant le canal, une publication a la fois.
Au rythme de 7 accroches par jour, decouvrir un defaut qui touche 1 verset sur
50 demande une semaine ; un defaut sur 200, plus d'un mois. Et chaque defaut
est deja parti sur six plateformes quand on le voit.

Ce script inverse le sens : il genere N accroches d'un coup, hors publication,
et les met sous les yeux avant qu'une seule ne sorte. Une session de vingt
minutes vaut trois mois de canal.

CE QU'IL NE FAIT PAS : publier. Il n'appelle aucune API de reseau social.
Il lit la Bible, appelle Anthropic, applique les filtres, affiche. Rien d'autre.

UTILISATION
-----------
    export ANTHROPIC_API_KEY=sk-...
    python3 test_accroches.py                 # 30 versets au hasard
    python3 test_accroches.py 100             # 100 versets
    python3 test_accroches.py 40 psaume       # 40 versets d'une categorie
    python3 test_accroches.py --prompt        # montre le prompt, n'appelle rien

COUT : ~1200 tokens d'entree par accroche, modele haiku. 100 accroches
coutent environ 0,12 $. Ce n'est jamais l'argent qui limite, c'est la lecture.

COMMENT LIRE LE RESULTAT
------------------------
Les lignes REJETEE sont une bonne nouvelle : le filtre a fait son travail, le
repli fixe serait sorti. Ce sont les lignes « ok » qu'il faut lire une par une,
avec les trois questions du cahier :

  1. Est-ce le sujet du verset, ou une partie de lui ?
     (s'il y a un « Mais », le sujet est apres)
  2. Est-ce que ca dit quelque chose que le verset ne dit pas deja ?
  3. Chaque fait affirme est-il dans le chapitre — surtout QUI fait l'action ?
"""
import os
import sys
import json
import random
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "-")
os.environ.setdefault("TELEGRAM_CHANNEL", "-")

import bot  # noqa: E402


def passages(categorie=None):
    """Tous les passages publiables, avec leur texte nettoye."""
    out = []
    for cat_name, cat in bot.CATEGORIES.items():
        if categorie and cat_name != categorie:
            continue
        try:
            entrees = json.load(open(cat["file"], encoding="utf-8"))
        except Exception as e:
            print(f"⚠️  {cat['file']} illisible : {e}")
            continue
        for it in entrees:
            book, ch = it[0], it[1]
            vs = list(range(it[2], it[3] + 1)) if len(it) == 4 else [it[2]]
            try:
                brut = " ".join(bot.load_verse(book, ch, v) for v in vs)
            except Exception:
                continue
            texte = bot.clean_text(bot.strip_rubric(brut))
            if not texte.strip():
                continue
            ref = f"{book} {ch}:{vs[0]}" + (f"-{vs[-1]}" if len(vs) > 1 else "")
            out.append((ref, texte, cat_name))
    return out


def raison_du_rejet(hook, verse_text):
    """Le filtre qui rejetterait cette accroche, ou None. Meme ordre que
    generate_hook_ai, pour que le banc d'essai dise la meme chose que la
    production."""
    if not hook:
        return "vide"
    if len(hook) > 120 or len(hook.split()) > 18:
        return "longueur"
    for nom, rx in (("formule interdite", bot._HOOK_INTERDIT),
                    ("contexte incertain", bot._HOOK_HESITE),
                    ("cadre de tradition", bot._HOOK_TRADITION),
                    ("duree inventee", bot._HOOK_DUREE)):
        if rx.search(hook):
            return nom
    taux = bot.taux_de_recopie(hook, verse_text)
    if taux >= bot.HOOK_RECOPIE_MAX:
        return f"recopie {taux:.0%}"
    return None


def main():
    args = [a for a in sys.argv[1:]]
    if "--prompt" in args:
        ref, texte, cat = random.choice(passages())
        print(f"=== prompt reel pour {ref} ({cat}) ===\n")
        ctx = bot.contexte_du_chapitre(ref)
        print(f"[contexte du chapitre : {len(ctx)} caracteres]")
        print(ctx[:1200] + ("\n[...]" if len(ctx) > 1200 else ""))
        print(f"\n[verset] « {texte} »")
        return

    n = 30
    categorie = None
    for a in args:
        if a.isdigit():
            n = int(a)
        elif a in bot.CATEGORIES:
            categorie = a

    if not bot.ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY absente. export ANTHROPIC_API_KEY=sk-...")
        sys.exit(1)

    tous = passages(categorie)
    if not tous:
        print("❌ aucun passage trouve — lancer depuis la racine du depot.")
        sys.exit(1)
    random.shuffle(tous)
    echantillon = tous[:n]

    print(f"Banc d'essai : {len(echantillon)} accroches"
          f"{' — categorie ' + categorie if categorie else ''}")
    print(f"modele {bot.ANTHROPIC_MODEL} · seuil de recopie "
          f"{bot.HOOK_RECOPIE_MAX:.0%} · contexte du chapitre actif\n")

    rejets = collections.Counter()
    retenues = []
    for i, (ref, texte, cat) in enumerate(echantillon, 1):
        bot._HOOK_CACHE.clear()
        hook = bot.generate_hook_ai(texte, ref, cat)
        raison = raison_du_rejet(hook, texte)
        if hook and not raison:
            retenues.append((ref, cat, hook, texte))
            print(f"{i:>3}. ✓  {ref:<22} {hook}")
        else:
            rejets[raison or "appel echoue"] += 1
            court = (hook or "")[:64]
            print(f"{i:>3}. ✗  {ref:<22} [{raison or 'appel echoue'}] {court}")

    total = len(echantillon)
    print(f"\n{'='*74}")
    print(f"retenues : {len(retenues)}/{total}   "
          f"repli fixe : {total - len(retenues)}/{total}")
    if rejets:
        print("\nmotifs :")
        for motif, k in rejets.most_common():
            print(f"  {k:>3}  {motif}")

    if retenues:
        print(f"\n{'='*74}")
        print("A RELIRE UNE PAR UNE — ce sont celles qui seraient publiees.")
        print("Pour chacune : est-ce le sujet du verset ? dit-elle du neuf ?")
        print("chaque fait est-il dans le chapitre — surtout QUI agit ?\n")
        for ref, cat, hook, texte in retenues:
            print(f"— {ref}  [{cat}]")
            print(f"  accroche : {hook}")
            print(f"  verset   : {texte[:150]}{'…' if len(texte) > 150 else ''}\n")


if __name__ == "__main__":
    main()
