import os, json, random, re

BIBLE_DIR = "bible"
OUT_FILE = "verses_index.json"

def safe_key_from_filename(fn: str) -> str:
    return fn.lower()

def main():
    refs = []
    for fn in sorted(os.listdir(BIBLE_DIR)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(BIBLE_DIR, fn)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        book = next(iter(data.keys()))
        chapters = data[book]

        for ch in sorted(chapters.keys(), key=lambda x: int(x)):
            verses = chapters[ch]
            for v in sorted(verses.keys(), key=lambda x: int(x)):
                refs.append([book, int(ch), int(v)])

    random.shuffle(refs)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(refs, f, ensure_ascii=False)

    print(f"OK: {len(refs)} versículos indexados em {OUT_FILE}")

if __name__ == "__main__":
    main()
