import json
import os

# Ficheiros a corrigir
FILES = [
    "psaumes_curated.json",
    "promesses_curated.json",
    "jesus_curated.json",
    "proverbes_curated.json",
    "propheties_curated.json",
]

CORRECTIONS = {
    "Psaume": "Psaumes",
    "Cantique Des Cantiqu": "Cantique des Cantiques",
}

for filename in FILES:
    if not os.path.exists(filename):
        print(f"⚠️  {filename} non trouvé — ignoré.")
        continue

    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    count = 0
    for entry in data:
        if isinstance(entry, list) and len(entry) >= 1:
            for wrong, correct in CORRECTIONS.items():
                if entry[0] == wrong or str(entry[0]).startswith(wrong):
                    entry[0] = correct
                    count += 1
                    break

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ {filename} — {count} entrées corrigées.")

print("\n✅ Terminé.")
