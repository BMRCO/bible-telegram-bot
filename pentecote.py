"""
pentecote.py — Publicação especial Pentecôte (24 mai 2026)

Reusa todas as funções de bot.py.
Recebe argumento de slot (1-6) e publica o versículo correspondente.

Slots:
  1 = Protection (Jean 14:16) — image
  2 = Promesse (Actes 1:8) — reel
  3 = Sagesse (Galates 5:22-23) — image
  4 = Jésus (Jean 16:13) — reel
  5 = Prophétie (Actes 2:17) — image
  6 = Psaume (Psaumes 51:13) — reel
"""

import sys
import os
import requests
from bot import (
    load_json, save_json, load_verse, clean_text, make_image, make_reel_video,
    send_photo, send_video,
    post_to_facebook, post_to_instagram, post_to_pinterest, post_to_threads,
    post_reel_to_facebook, post_reel_to_instagram, post_reel_to_threads,
    post_to_youtube,
    PROGRESS_FILE, CATEGORIES,
)

# ----------------------------------------------------------------------
# Programa Pentecôte — 6 slots
# ----------------------------------------------------------------------
PENTECOTE_SLOTS = {
    "1": {
        "book": "Jean",
        "chapter": 14,
        "verse": 16,
        "cat_name": "protection",
        "mode": "image",
        "hour_utc": 5,
        "label": "🕊️ Pentecôte — Le Consolateur",
        "subline": "Aujourd'hui, l'Esprit Saint descend sur l'Église.\nIl demeure avec les siens — pour toujours.",
    },
    "2": {
        "book": "Actes",
        "chapter": 1,
        "verse": 8,
        "cat_name": "promise",
        "mode": "reel",
        "hour_utc": 7,
        "label": "🕊️ Pentecôte — La Promesse accomplie",
        "subline": "La promesse est accomplie.\nLa puissance d'en-haut nous est donnée.",
    },
    "3": {
        "book": "Galates",
        "chapter": 5,
        "verse": 22,
        "cat_name": "proverbe",
        "mode": "image",
        "hour_utc": 10,
        "label": "🕊️ Pentecôte — Le Fruit de l'Esprit",
        "subline": "L'Esprit produit en nous\nce que nous ne pouvons produire seuls.",
    },
    "4": {
        "book": "Jean",
        "chapter": 16,
        "verse": 13,
        "cat_name": "jesus",
        "mode": "reel",
        "hour_utc": 13,
        "label": "🕊️ Pentecôte — L'Esprit de vérité",
        "subline": "Jésus l'avait promis.\nL'Esprit guide ses disciples — hier, aujourd'hui, à jamais.",
    },
    "5": {
        "book": "Actes",
        "chapter": 2,
        "verse": 17,
        "cat_name": "prophetie",
        "mode": "image",
        "hour_utc": 17,
        "label": "🕊️ Pentecôte — La Prophétie accomplie",
        "subline": "La prophétie de Joël s'accomplit aujourd'hui.\nL'Esprit est répandu sur tous.",
    },
    "6": {
        "book": "Psaume",
        "chapter": 51,
        "verse": 13,
        "cat_name": "psaume",
        "mode": "reel",
        "hour_utc": 19,
        "label": "🌙 Pentecôte — Ne me retire pas ton Esprit",
        "subline": "Que ce Psaume vous accompagne ce soir.\nRestons sous la conduite de l'Esprit.",
    },
}


def build_pentecote_caption(slot, text, ref):
    """Caption especial Pentecôte com hashtag de Pentecôte."""
    cat = CATEGORIES[slot["cat_name"]]
    label = slot["label"]
    subline = slot["subline"]
    return (
        f"{label}\n"
        f"<b>{ref}</b>\n\n"
        f"« {text} »\n\n"
        f"{subline}\n\n"
        f"📖 labible.app\n\n"
        f"#LaBible #LSG1910 #Pentecôte #SaintEsprit {cat['tag']}"
    )


def main_pentecote():
    if len(sys.argv) < 2:
        print("❌ Uso: python pentecote.py <slot 1-6>")
        sys.exit(1)

    slot_id = sys.argv[1].strip()
    if slot_id not in PENTECOTE_SLOTS:
        print(f"❌ Slot inválido: {slot_id}. Use 1-6.")
        sys.exit(1)

    slot = PENTECOTE_SLOTS[slot_id]
    cat_name = slot["cat_name"]
    cat = CATEGORIES[cat_name]
    mode = slot["mode"]
    hour_utc = slot["hour_utc"]

    # Carregar verso
    text = load_verse(slot["book"], slot["chapter"], slot["verse"])
    if not text:
        print(f"❌ Verso não encontrado: {slot['book']} {slot['chapter']}:{slot['verse']}")
        sys.exit(1)
    text = clean_text(text)
    ref = f"{slot['book']} {slot['chapter']}:{slot['verse']}"

    print(f"🕊️ Pentecôte slot {slot_id} — {ref} [{mode}]")

    caption = build_pentecote_caption(slot, text, ref)

    progress = load_json(PROGRESS_FILE)

    if mode == "image":
        img = make_image(text, ref)
        send_photo(img, caption, ref)
        post_to_facebook(img, ref, text, cat, cat_name)
        post_to_instagram(img, ref, text, cat, cat_name)
        post_to_pinterest(img, ref, text, cat, cat_name)
        post_to_threads(img, ref, text, cat, cat_name)
    else:
        # Garantir logo
        if not os.path.exists("logo.png"):
            try:
                r = requests.get("https://labible.app/icons/icon-512x512.png", timeout=10)
                if r.status_code == 200:
                    with open("logo.png", "wb") as f:
                        f.write(r.content)
            except Exception as e:
                print(f"⚠️ Logo : {e}")
        video = make_reel_video(text, ref, progress)
        send_video(video, caption, ref)
        post_reel_to_facebook(video, ref, text, cat, cat_name)
        post_reel_to_instagram(video, ref, text, cat, cat_name)
        post_to_youtube(video, ref, text, cat, cat_name, hour_utc)
        post_reel_to_threads(video, ref, text, cat, cat_name)

    save_json(PROGRESS_FILE, progress)
    print(f"✅ Pentecôte slot {slot_id} terminé.")


if __name__ == "__main__":
    main_pentecote()
