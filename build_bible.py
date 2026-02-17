import io
import os
import re
import json
import zipfile
import requests

# Louis Segond 1910 (fraLSG) em USFM (domaine public)
USFM_ZIP_URL = "https://ebible.org/Scriptures/fraLSG_usfm.zip"
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

def download_zip(url: str) -> bytes:
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    return r.content

def clean_usfm_text(s: str) -> str:
    """
    Remove códigos comuns do USFM/footnotes/strong:
    - \w ... \w* (mantém só a palavra)
    - \x ... \x* (remove crossrefs)
    - |strong="Hxxxx" e outros pipes
    - outros marcadores \abc
    """
    if not s:
        return ""

    # 1) manter só o texto dentro de \w ...\w*
    # Ex: \w commencement|strong="H7225"\w*  -> commencement
    s = re.sub(r'\\w\s+([^\\]+?)\\w\*', r'\1', s)

    # 2) remover blocos de cross-reference \x ... \x*
    s = re.sub(r'\\x\s+.*?\\x\*', ' ', s)

    # 3) remover atributos após pipe, tipo |strong="H7225"
    s = re.sub(r'\|[^ \t]+', '', s)

    # 4) remover quaisquer marcadores restantes \abc ou \abc*
    s = re.sub(r'\\[a-zA-Z0-9]+\*?', '', s)

    # 5) limpar colchetes restantes que às vezes sobram
    s = s.replace("[", "").replace("]", "")

    # 6) normalizar espaços
    s = " ".join(s.split()).strip()
    return s

def parse_usfm_to_chapters(usfm_text: str):
    """
    Retorna (book_id, chapters)
    chapters: { "1": { "1": "texto", ... }, ... }
    """
    book_id = None
    chapters: dict[str, dict[str, str]] = {}
    current_c = None
    current_v = None

    lines = usfm_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    def append_to_current(extra: str):
        nonlocal chapters, current_c, current_v
        if current_c and current_v and extra.strip():
            extra_clean = clean_usfm_text(extra)
            if not extra_clean:
                return
            prev = chapters[current_c].get(current_v, "")
            joined = (prev + " " + extra_clean).strip()
            chapters[current_c][current_v] = " ".join(joined.split())

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # \id GEN ...
        if line.startswith("\\id "):
            parts = line.split()
            if len(parts) >= 2:
                book_id = parts[1].strip()
            continue

        # \c 1
        if line.startswith("\\c "):
            m = re.match(r"\\c\s+(\d+)", line)
            if m:
                current_c = m.group(1)
                chapters.setdefault(current_c, {})
                current_v = None
            continue

        # \v 1 texto...
        if line.startswith("\\v "):
            if current_c is None:
                continue
            # \v 1 ou \v 1-2
            m = re.match(r"\\v\s+([0-9]+)(?:-[0-9]+)?\s*(.*)", line)
            if m:
                current_v = m.group(1)
                text = m.group(2).strip()
                chapters[current_c][current_v] = clean_usfm_text(text)
            continue

        # Continuação do verso (linhas sem marcadores)
        if current_c and current_v and not line.startswith("\\"):
            append_to_current(line)

    # Limpeza final (segurança)
    for ch in list(chapters.keys()):
        for v in list(chapters[ch].keys()):
            chapters[ch][v] = clean_usfm_text(chapters[ch][v])

    return book_id, chapters

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    zip_bytes = download_zip(USFM_ZIP_URL)
    z = zipfile.ZipFile(io.BytesIO(zip_bytes))

    created = 0
    for name in z.namelist():
        low = name.lower()
        if not (low.endswith(".usfm") or low.endswith(".sfm") or low.endswith(".txt")):
            continue

        raw = z.read(name)

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")

        book_id, chapters = parse_usfm_to_chapters(text)
        if not book_id or book_id not in BOOK_MAP:
            continue
        if not chapters:
            continue

        book_name = BOOK_MAP[book_id]
        out_path = os.path.join(OUT_DIR, safe_filename(book_name) + ".json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({book_name: chapters}, f, ensure_ascii=False)

        created += 1

    if created < 60:
        raise RuntimeError(f"Foram gerados só {created} livros. Algo mudou no zip/formato.")
    print(f"OK: {created} livros gerados em {OUT_DIR}/")

if __name__ == "__main__":
    main()
