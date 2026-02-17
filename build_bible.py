import io
import os
import json
import zipfile
import requests
import xml.etree.ElementTree as ET

# Fonte: eBible.org (Louis Segond 1910 – domaine public)
USFX_ZIP_URL = "https://ebible.org/Scriptures/fraLSG_usfx.zip"

OUT_DIR = "bible"

# ID USFX -> Nome do livro em francês (LS1910)
BOOK_MAP = {
    "GEN":"Genèse","EXO":"Exode","LEV":"Lévitique","NUM":"Nombres","DEU":"Deutéronome",
    "JOS":"Josué","JDG":"Juges","RUT":"Ruth","1SA":"1 Samuel","2SA":"2 Samuel",
    "1KI":"1 Rois","2KI":"2 Rois","1CH":"1 Chroniques","2CH":"2 Chroniques",
    "EZR":"Esdras","NEH":"Néhémie","EST":"Esther","JOB":"Job","PSA":"Psaumes",
    "PRO":"Proverbes","ECC":"Ecclésiaste","SNG":"Cantique des Cantiques",
    "ISA":"Ésaïe","JER":"Jérémie","LAM":"Lamentations","EZK":"Ézéchiel","DAN":"Daniel",
    "HOS":"Osée","JOL":"Joël","AMO":"Amos","OBA":"Abdias","JON":"Jonas","MIC":"Michée",
    "NAM":"Nahum","HAB":"Habacuc","ZEP":"Sophonie","HAG":"Aggée","ZEC":"Zacharie","MAL":"Malachie",
    "MAT":"Matthieu","MRK":"Marc","LUK":"Luc","JHN":"Jean","ACT":"Actes",
    "ROM":"Romains","1CO":"1 Corinthiens","2CO":"2 Corinthiens","GAL":"Galates","EPH":"Éphésiens",
    "PHP":"Philippiens","COL":"Colossiens","1TH":"1 Thessaloniciens","2TH":"2 Thessaloniciens",
    "1TI":"1 Timothée","2TI":"2 Timothée","TIT":"Tite","PHM":"Philémon","HEB":"Hébreux",
    "JAS":"Jacques","1PE":"1 Pierre","2PE":"2 Pierre","1JN":"1 Jean","2JN":"2 Jean","3JN":"3 Jean",
    "JUD":"Jude","REV":"Apocalypse"
}

def safe_filename(name: str) -> str:
    # Remove acentos e caracteres problemáticos
    import re
    t = name.lower()
    repl = (("é","e"),("è","e"),("ê","e"),("ë","e"),("à","a"),("â","a"),("î","i"),("ï","i"),
            ("ô","o"),("ù","u"),("û","u"),("ç","c"),("œ","oe"))
    for a,b in repl:
        t = t.replace(a,b)
    t = re.sub(r"[^a-z0-9]+","_", t).strip("_")
    return t

def download_zip(url: str) -> bytes:
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content

def extract_usfx_files(zip_bytes: bytes) -> dict:
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))
    files = {}
    for name in z.namelist():
        if name.lower().endswith(".usfx") or name.lower().endswith(".xml"):
            files[name] = z.read(name)
    return files

def parse_usfx_book(xml_bytes: bytes, book_name: str) -> dict:
    # saída: { "1": { "1": "texto", "2": "texto"... }, "2": {...} }
    root = ET.fromstring(xml_bytes)

    chapters = {}
    current_ch = None
    current_vs = None
    buffer = []

    def flush_verse():
        nonlocal buffer, current_ch, current_vs
        if current_ch and current_vs and buffer:
            text = " ".join("".join(buffer).split())
            chapters.setdefault(current_ch, {})[current_vs] = text
        buffer = []

    for el in root.iter():
        tag = el.tag.lower()

        # USFX marca capítulos/versos normalmente com <c id="1"/> e <v id="1"/>
        if tag.endswith("c") and el.attrib.get("id"):
            flush_verse()
            current_ch = el.attrib["id"]
            current_vs = None
        elif tag.endswith("v") and el.attrib.get("id"):
            flush_verse()
            current_vs = el.attrib["id"]

        # texto
        if el.text and current_ch and current_vs:
            buffer.append(el.text)
        if el.tail and current_ch and current_vs:
            buffer.append(el.tail)

    flush_verse()
    return chapters

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    zip_bytes = download_zip(USFX_ZIP_URL)
    files = extract_usfx_files(zip_bytes)

    created = 0
    for fname, content in files.items():
        # tentar descobrir o ID do livro pelo nome do ficheiro (muitos vêm como GEN.usfx, MAT.usfx, etc.)
        base = os.path.basename(fname).split(".")[0].upper()
        book_id = base[:3] if base[:3] in BOOK_MAP else base  # fallback
        if book_id not in BOOK_MAP:
            continue

        book_name = BOOK_MAP[book_id]
        data = parse_usfx_book(content, book_name)

        out_name = safe_filename(book_name) + ".json"
        out_path = os.path.join(OUT_DIR, out_name)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({book_name: data}, f, ensure_ascii=False)

        created += 1

    if created < 10:
        raise RuntimeError("Poucos livros gerados — talvez mudou o formato do zip.")

    print(f"OK: {created} livros gerados em {OUT_DIR}/")

if __name__ == "__main__":
    main()
