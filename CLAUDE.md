# LaBible.app — bot de publication

Publie chaque jour des versets et méditations LSG 1910 sur Telegram, Facebook, Instagram,
YouTube, Pinterest et Threads, via GitHub Actions.

## Règle absolue

**Ne JAMAIS modifier le contenu biblique.** `bible/lsg1910.json` ne se réécrit pas.
`clean_text()` et `strip_rubric()` mettent le texte en forme **à la publication** :
ne rien y ajouter ni retirer sans accord explicite.

## Règles techniques

- Toute modification de `clean_text` / `strip_rubric` : valider sur les 31 102 versets
  (zéro verset vide, zéro verset mutilé).
- **Une seule `BOOK_NAME_MAP`, dans `bot.py`** : les autres scripts l'importent.
- Écrire la progression **après** publication ; le pas « Commit progress » garde
  `if: ${{ !cancelled() }}`.
- Chaque plateforme passe par `publier()` ; tout échec passe par `signaler_echec()`.
  Pour désactiver une plateforme : `ONLY_PLATFORM`, jamais effacer un secret.
- Chaque secret lu par un script doit être passé dans le `env:` de son workflow.
- Workflows épinglés en `ubuntu-24.04` : ne pas remettre `ubuntu-latest` sans test.
- **Aucun message technique sur un canal public.** Les échecs : e-mail GitHub et annotations du run.
- Le dépôt est **public** : aucun `chat_id`, secret, adresse e-mail ou nom personnel dans un fichier.
- Musique : uniquement des pistes libres de Content ID.
- Commits avec l'adresse `noreply` de BMRCO. Après chaque push, vérifier sur le dépôt distant.
