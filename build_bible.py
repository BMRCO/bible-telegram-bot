import io
import os
import json
import zipfile
import requests
import xml.etree.ElementTree as ET

USFX_ZIP_URL = "https://ebible.org/Scriptures/fraLSG_usfx.zip"
OUT_DIR = "bible"

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
    import re
    t = name.lower()
    repl = (("é","e"),("è","e"),("ê","e"),("ë","e"),("à","a"),("â","a"),
            ("î","i"),("ï","i"),("ô","o"),("ù","u"),("û","u"),
            ("ç","c"),("œ","oe"))
    for a, b in repl:
        t = t.replace(a, b)
    t = re.sub(r"[^a-z0-9]+", "_", t).strip("_")
    return t

def download_zip(url: str) -> bytes:
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    return r.content

def parse_usfx_book_id(root: ET.Element) -> str | None:
    # Procura um elemento <book id="GEN" ...> (ou variantes)
    for el in root.iter():
        tag = el.tag.lower()
        if tag.endswith("book"):
            bid = el.attrib.get("id") or el.attrib.get("code") or el.attrib.get("book")
            if bid:
                return bid.strip()
    return None

def parse_usfx_chapters(root: ET.Element) -> dict:
    # saída: { "1": { "1": "texto", ... }, ... }
    chapters = {}
    current_ch = None
    current_vs = None
    buf = []

    def flush():
        nonlocal buf, current_ch, current_vs
        if current_ch and current_vs and buf:
            text = " ".join("".join(buf).split())
            chapters.setdefault(current_ch, {})[current_vs] = text
        buf = []

    for el in root.iter():
        tag = el.tag.lower()

        if tag.endswith("c") and el.attrib.get("id"):
            flush()
            current_ch = el.attrib["id"]
            current_vs = None

        if tag.endswith("v") and el.attrib.get("id"):
            flush()
            current_vs = el.attrib["id"]

        if current_ch and current_vs:
            if el.text:
                buf.append(el.text)
            if el.tail:
                buf.append(el.tail)

    flush()
    return chapters

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    zip_bytes = download_zip(USFX_ZIP_URL)
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))

    created = 0

    for name in z.namelist():
        low = name.lower()
        if not (low.endswith(".usfx") or low.endswith(".xml")):
            continue

        content = z.read(name)

        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            continue

        book_id = parse_usfx_book_id(root)
        if not book_id or book_id not in BOOK_MAP:
            continue

        book_name = BOOK_MAP[book_id]
        chapters = parse_usfx_chapters(root)

        out_path = os.path.join(OUT_DIR, safe_filename(book_name) + ".json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({book_name: chapters}, f, ensure_ascii=False)

        created += 1

    if created < 60:
        raise RuntimeError(f"Foram gerados só {created} livros. Algo mudou no zip/formato.")
    print(f"OK: {created} livros gerados em {OUT_DIR}/")

if __name__ == "__main__":
    main()
