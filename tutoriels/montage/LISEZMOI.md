# Montage de la serie « Astuces LaBible.app » (18-19 novembre 2026)

Hors du bot : refaire les videos seulement si l'application change.

1. Servir le depot labible.app en local : `python3 -m http.server 8767` (racine du depot).
2. Polices du telephone : Roboto et Noto Serif (@fontsource, converties en TTF dans ~/.fonts)
   avec un fontconfig qui fait de serif, Georgia, sans-serif, system-ui et Arial ces polices.
3. `python3 capture_serie.py` : 34 captures reelles (Chromium, 390x844 x3, mode sombre) et
   leurs positions dans cap/serie.json.
4. `python3 serie.py [n ...]` : les Shorts 1080x1920 (fondus enchaines 0,5 s, une couleur par
   episode). Voix Tom de Piper (fr_FR-tom-medium, choix de BC le 19 nov. 2026) dans
   voix/epNN_<i>.mp3 (WAV du workflow narration_tutoriels.yml, voix
   piper:fr/fr_FR/tom/medium/fr_FR-tom-medium, convertis en MP3) (texte : tutoriels/narration.json, la phrase 0 du titre reste vide).
   Musique : music/igorlisul-sweet-dreams-relaxing-guitar-music-480281.mp3, copiee en
   musique.mp3, baissee sous la voix. `--images` : planches de controle seulement.
5. Copier tuto_NN.mp4 en tutoriels/NN.mp4.

6. `python3 pres2.py` : la video de presentation en sept parties (texte : narration.json,
   cle 12). `pres.py` (cle 11) est l'ancienne version.
