# Montage de la serie « Decouvrir LaBible.app » (18 novembre 2026)

Hors du bot : refaire les videos seulement si l'application change.

1. Servir le depot labible.app en local : `python3 -m http.server 8767` (racine du depot).
2. Polices du telephone : Roboto et Noto Serif (@fontsource, converties en TTF dans ~/.fonts)
   avec un fontconfig qui fait de serif, Georgia, sans-serif, system-ui et Arial ces polices.
3. `python3 capture_serie.py` : 34 captures reelles (Chromium, 390x844 x3, mode sombre) et
   leurs positions dans cap/serie.json.
4. `python3 serie.py [n ...]` : les Shorts 1080x1920 (fondus enchaines 0,5 s, une couleur par
   episode). Musique : music_meditation/« Meditation - Royalty-free Music.mp3 » (sans
   revendication), copiee en musique.mp3. `--images` : planches de controle seulement.
5. Copier tuto_NN.mp4 en tutoriels/NN.mp4.
