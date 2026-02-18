import os, json, random, re

BIBLE_DIR = "bible"

GOSPELS = {"Matthieu", "Marc", "Luc", "Jean"}

# Promessas (palavras-chave)
PROMISE_PATTERNS = [
    r"\bje (?:te|vous) donnerai\b",
    r"\bje (?:te|vous) bénirai\b",
    r"\bje (?:suis|serai) avec (?:toi|vous)\b",
    r"\bne crains pas\b",
    r"\bn'ayez pas peur\b",
    r"\bje ferai\b",
    r"\bje te délivrerai\b",
    r"\bje vous délivrerai\b",
    r"\bje guérirai\b",
    r"\bje vous guérirai\b",
    r"\bje te fortifierai\b",
    r"\bje vous fortifierai\b",
    r"\bje te soutiendrai\b",
    r"\bje vous soutiendrai\b",
    r"\bje t'exaucerai\b",
    r"\bje vous exaucerai\b",
    r"\bje te sauverai\b",
    r"\bje vous sauverai\b",
    r"\bje t'aime\b",
    r"\bje vous aime\b",
]
PROMISE_RE = re.compile("|".join(PROMISE_PATTERNS), re.IGNORECASE)

# “Palavras de Jesus” (heurística): Evangelhos + aspas/«» OU "Jésus dit/leur dit"
JESUS_RE = re.compile(
    r"(?:«|»|\"|”|“|')|(?:j[eé]sus (?:dit|leur dit|lui dit|répondit))",
    re.IGNORECASE
)

def safe_filename(name: str) -> str:
    t = name.lower()
    repl = (("é","e"),("è","e"),("ê","e"),("ë","e"),
            ("à","a"),("â","a"),
            ("î","i"),("ï","i"),
            ("ô","o"),
            ("ù","u"),("û","u"),
            ("ç","c"),("œ","oe"))
    for a, b in repl:
        t = t.replace(a, b)
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return t

def load_book(book_name: str) -> dict:
    path = os.path.join(BIBLE_DIR, safe_filename(book_name) + ".json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data[book_name]

def list_books() -> list[str]:
    books = []
    for fn in os.listdir(BIBLE_DIR):
        if fn.endswith(".json"):
            # abrir para descobrir o nome exato do livro (chave)
            with open(os.path.join(BIBLE_DIR, fn), "r", encoding="utf-8") as f:
                d = json.load(f)
            books.append(next(iter(d.keys())))
    return books

def main():
    books = list_books()

    jesus_refs = []
    promise_refs = []

    for book in books:
        book_data = load_book(book)
        for ch in sorted(book_data.keys(), key=lambda x: int(x)):
            verses = book_data[ch]
            for v in sorted(verses.keys(), key=lambda x: int(x)):
                t = verses[v]

                # Promessas: em qualquer livro
                if PROMISE_RE.search(t):
                    promise_refs.append([book, int(ch), int(v)])

                # Palavras de Jesus: só nos 4 Evangelhos (heurística)
                if book in GOSPELS and JESUS_RE.search(t):
                    jesus_refs.append([book, int(ch), int(v)])

    random.shuffle(promise_refs)
    random.shuffle(jesus_refs)

    with open("promises_index.json", "w", encoding="utf-8") as f:
        json.dump(promise_refs, f, ensure_ascii=False)

    with open("jesus_index.json", "w", encoding="utf-8") as f:
        json.dump(jesus_refs, f, ensure_ascii=False)

    print(f"OK promises: {len(promise_refs)}")
    print(f"OK jesus: {len(jesus_refs)}")

if __name__ == "__main__":
    main()
