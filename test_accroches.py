#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Banc d'essai des accroches — LaBible.app

POURQUOI CE FICHIER EXISTE
--------------------------
Entre le 7 et le 11 septembre 2026, neuf defauts d'accroche ont ete trouves.
Tous les neuf de la meme facon : BC lisant le canal, une publication a la fois.
Au rythme de 7 accroches par jour, decouvrir un defaut qui touche 1 verset sur
50 demande une semaine ; un defaut sur 200, plus d'un mois. Et chaque defaut
est deja parti sur six plateformes quand on le voit.

Ce script inverse le sens : il genere N accroches d'un coup, hors publication,
et les met sous les yeux avant qu'une seule ne sorte. Une session de vingt
minutes vaut trois mois de canal.

CE QU'IL NE FAIT PAS : publier. Il n'appelle aucune API de reseau social.
Il lit la Bible, appelle Anthropic, observe bot.py travailler, affiche.

CE QU'IL NE COPIE PAS — et c'est la regle du fichier
---------------------------------------------------
Ce banc ne reimplemente AUCUN filtre. La version precedente en gardait une
liste a la main : elle n'en connaissait que cinq sur neuf, et affichait donc
« ok » pour des accroches que la production aurait refusees. Un banc d'essai
qui ment est pire que pas de banc du tout.

Ici, on met un mouchard sur bot._verifier_hook et sur bot.requests.post. Les
filtres appliques sont ceux de bot.py, dans l'ordre de bot.py, pour toujours.
Ajouter un dixieme filtre a bot.py ne demande pas de toucher a ce fichier.

UTILISATION
-----------
    export ANTHROPIC_API_KEY=sk-...
    python3 test_accroches.py                 # 30 versets au hasard
    python3 test_accroches.py 100             # 100 versets
    python3 test_accroches.py 40 psaume       # 40 versets d'une categorie
    python3 test_accroches.py --prompt        # montre le prompt REEL, 0 appel

COUT : ~1200 tokens d'entree par accroche, modele haiku. 100 accroches
coutent environ 0,12 $. Ce n'est jamais l'argent qui limite, c'est la lecture.

COMMENT LIRE LE RESULTAT
------------------------
Trois blocs, et le deuxieme est le plus utile :

1. Les lignes ✗ sont une bonne nouvelle : le filtre a fait son travail.
2. Les lignes ⟳ sont la matiere premiere. Une accroche refusee au premier
   essai puis acceptee au second montre ce que le modele fait quand on ne
   l'arrete pas. Un meme motif qui revient souvent en ⟳ veut dire qu'une
   regle du prompt ne passe pas — c'est au prompt qu'il faut toucher, pas au
   filtre. Un meme motif qui revient souvent en ✗ veut dire l'inverse : le
   filtre est trop serre et envoie tout au repli fixe.
3. Les lignes ✓ sont a relire une par une, avec les trois questions :
     a. Est-ce le sujet du verset, ou seulement sa premiere clause ?
        (s'il y a un « Mais », le sujet est apres)
     b. La ligne APPORT dit-elle vrai ? Est-ce vraiment ce que la phrase
        ajoute, ou une justification qui sonne bien ?
     c. Chaque fait affirme est-il dans le chapitre — surtout QUI agit ?
"""
import os
import sys
import io
import json
import random
import contextlib
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "-")
os.environ.setdefault("TELEGRAM_CHANNEL", "-")

import bot  # noqa: E402


# --------------------------------------------------------------- le mouchard
#
# bot.generate_hook_ai() avale tout : il applique les neuf defenses, reessaie
# une fois, et rend soit une phrase, soit None. Vu du dehors, une panne d'API
# et un filtre qui se declenche sont indiscernables — et le motif du refus,
# qui est toute l'information, est perdu.
#
# On enveloppe donc _verifier_hook sans le remplacer : chaque appel est
# enregistre, puis delegue a la vraie fonction. Le banc voit exactement ce que
# la production voit, sans en copier une ligne.
JOURNAL = []
_verifier_reel = bot._verifier_hook


def _verifier_espion(hook, verse_text, contexte="", apport=None):
    motif = _verifier_reel(hook, verse_text, contexte, apport)
    JOURNAL.append({"hook": hook, "apport": apport, "motif": motif})
    return motif


bot._verifier_hook = _verifier_espion


def generer(texte, ref, cat):
    """Une generation, et ce qu'elle a coute en tentatives.

    bot.py ecrit ses propres lignes ⚠️ / ✅ sur la sortie standard : utiles
    dans les journaux de GitHub Actions, ici elles tripleraient la longueur du
    rapport puisque le banc reimprime tout, en plus complet. On les avale —
    sauf l'avertissement du chapitre indisponible, qui est un vrai probleme."""
    JOURNAL.clear()
    bot._HOOK_CACHE.clear()
    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon):
        hook = bot.generate_hook_ai(texte, ref, cat)
    for ligne in tampon.getvalue().splitlines():
        if "Contexte du chapitre indisponible" in ligne:
            print(f"     {ligne.strip()}")
    return hook, list(JOURNAL)


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


def montrer_le_prompt():
    """Affiche le prompt REEL envoye a l'API, sans depenser un seul token.

    On intercepte requests.post, on garde le corps du message, et on rend une
    reponse valide pour que generate_hook_ai se termine proprement."""
    ref, texte, cat = random.choice(passages())
    capture = {}

    class _Reponse:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"content": [{"type": "text", "text":
                                 "ACCROCHE : (interception)\n"
                                 "APPORT : (aucun appel n'a ete fait)"}]}

    def _poste(url, headers=None, json=None, timeout=None):
        capture.setdefault("corps", json["messages"][0]["content"])
        return _Reponse()

    reel, bot.requests.post = bot.requests.post, _poste
    try:
        generer(texte, ref, cat)
    finally:
        bot.requests.post = reel

    corps = capture.get("corps", "")
    print(f"=== prompt reel pour {ref} ({cat}) — {len(corps)} caracteres ===\n")
    print(corps)
    print(f"\n=== fin · aucun appel facture ===")


def main():
    args = list(sys.argv[1:])
    if "--prompt" in args:
        montrer_le_prompt()
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
          f"{bot.HOOK_RECOPIE_MAX:.0%} · contexte du chapitre actif · "
          f"deux tentatives\n")

    retenues, repliees, rattrapees = [], [], []
    motifs_1, motifs_2 = collections.Counter(), collections.Counter()
    pannes = 0

    for i, (ref, texte, cat) in enumerate(echantillon, 1):
        hook, essais = generer(texte, ref, cat)

        if hook is None and not essais:
            pannes += 1
            print(f"{i:>3}. ⚠  {ref:<22} [appel API echoue]")
            continue

        # le dernier essai porte l'apport de l'accroche finalement retenue
        apport = essais[-1]["apport"] if essais else None
        premier = essais[0] if essais else None

        if hook and len(essais) == 1:
            retenues.append((ref, cat, hook, apport, texte))
            print(f"{i:>3}. ✓  {ref:<22} {hook}")
        elif hook:
            motifs_1[premier["motif"]] += 1
            rattrapees.append((ref, cat, premier, hook, apport, texte))
            print(f"{i:>3}. ⟳  {ref:<22} {hook}")
            print(f"     refusee d'abord : {(premier['hook'] or '')[:62]}")
            print(f"     motif           : {premier['motif']}")
        else:
            motifs_1[essais[0]["motif"]] += 1
            if len(essais) > 1:
                motifs_2[essais[1]["motif"]] += 1
            repliees.append((ref, cat, essais, texte))
            print(f"{i:>3}. ✗  {ref:<22} [repli fixe] "
                  f"{essais[-1]['motif'][:52]}")

    total = len(echantillon)
    ok = len(retenues) + len(rattrapees)
    print(f"\n{'=' * 74}")
    print(f"accroches IA publiees : {ok}/{total}"
          f"   dont rattrapees au 2e essai : {len(rattrapees)}")
    print(f"repli fixe            : {len(repliees)}/{total}")
    if pannes:
        print(f"appels echoues        : {pannes}/{total}")

    if motifs_1:
        print("\nmotifs au 1er essai — ce que le modele fait quand rien ne "
              "l'arrete :")
        for motif, k in motifs_1.most_common():
            print(f"  {k:>3}  {motif[:66]}")
    if motifs_2:
        print("\nmotifs au 2e essai — un motif frequent ici est un filtre "
              "trop serre :")
        for motif, k in motifs_2.most_common():
            print(f"  {k:>3}  {motif[:66]}")

    if repliees:
        print(f"\n{'=' * 74}")
        print("REFUSEES DEUX FOIS — ce sont elles qui ont coute une accroche.")
        print("Si le motif est le meme aux deux essais, le filtre ou la regle")
        print("correspondante merite d'etre relue.\n")
        for ref, cat, essais, texte in repliees:
            print(f"— {ref}  [{cat}]")
            for k, e in enumerate(essais, 1):
                print(f"  essai {k} : {(e['hook'] or '')[:66]}")
                print(f"           → {e['motif']}")
            print()

    if retenues or rattrapees:
        print(f"\n{'=' * 74}")
        print("A RELIRE UNE PAR UNE — ce sont celles qui seraient publiees.")
        print("Est-ce le sujet du verset ? la ligne APPORT dit-elle vrai ?")
        print("chaque fait est-il dans le chapitre — surtout QUI agit ?\n")
        for ref, cat, hook, apport, texte in retenues:
            print(f"— {ref}  [{cat}]")
            print(f"  accroche : {hook}")
            print(f"  apport   : {apport or '(non declare)'}")
            print(f"  verset   : {texte[:150]}{'…' if len(texte) > 150 else ''}\n")
        for ref, cat, premier, hook, apport, texte in rattrapees:
            print(f"— {ref}  [{cat}]  ⟳ 2e essai")
            print(f"  accroche : {hook}")
            print(f"  apport   : {apport or '(non declare)'}")
            print(f"  verset   : {texte[:150]}{'…' if len(texte) > 150 else ''}\n")


if __name__ == "__main__":
    main()
