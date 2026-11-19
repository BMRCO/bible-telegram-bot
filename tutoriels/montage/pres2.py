"""Presentation de LaBible.app en sept parties (Short 1080x1920, voix Tom de Piper).
Titres et rubriques a la maniere de la maquette de BC, captures reelles de l'application.
Voix : voix/ep12_<partie>.mp3 (narration.json, cle 12). Usage : python3 pres2.py"""
import math, os, subprocess
from PIL import Image, ImageDraw
import serie
from serie import F, GAR, ROB, CREME, W, H, FPS, CAP, fond, centre, arrondi, eclaircir

D = os.path.dirname(os.path.abspath(__file__))
ITA = GAR.replace("Regular", "Italic")
OR = (214, 178, 106)
ICONE = "/home/claude/labible.app/icons/icon-192x192.png"
XF = 0.6

# rubrique, titre, sous-titre (italique doree si « ital »)
PARTIES = [
    ("MÉDITER", "Un verset. Chaque jour.", "La Parole qui nourrit", True),
    ("LE PROJET", "La Parole de Dieu", "à portée de main.", True),
    ("LECTURE", "Lire à son rythme", "La Bible Louis Segond 1910", False),
    ("RECHERCHE", "Retrouver un passage", "Par mot ou par référence", False),
    ("AU QUOTIDIEN", "Un peu chaque jour", "Le verset du jour · Le plan sur 365 jours", False),
    ("ÉCOUTER ET PARTAGER", "La Parole partagée", "Bible audio · Thèmes · Images", False),
    ("COMMENCEZ VOTRE LECTURE", "LaBible.app", "Gratuite · Sans publicité · Sans compte", False),
]

# plans : (partie, duree minimale, type, parametres)
#   ecran : capture, centre vertical (px CSS), largeur visible (px CSS)
PLANS = [
    (0, 3.2, "image", ("j3_image.jpg",)),
    (1, 3.4, "ecran", ("l1_haut", 300, 390)),
    (2, 2.6, "ecran", ("l3_texte", 520, 330)),
    (2, 2.6, "ecran", ("l5_clair", 520, 330)),
    (3, 2.6, "ecran", ("r1_ref", 280, 390)),
    (3, 2.6, "ecran", ("r4_resultats", 420, 330)),
    (4, 2.8, "ecran", ("j2_ouvert", 420, 330)),
    (4, 2.8, "ecran", ("p1_plan", 330, 360)),
    (5, 2.4, "ecran", ("a1_audio", 340, 360)),
    (5, 2.4, "ecran", ("v2_theme", 380, 360)),
    (5, 2.4, "image", ("t5_image.jpg",)),
    (6, 3.6, "ecran", ("i1_bouton", 300, 390)),
]

FOND = fond(OR)
_imgs = {}


def img(nom):
    if nom not in _imgs:
        _imgs[nom] = Image.open(os.path.join(CAP, nom)).convert("RGB")
    return _imgs[nom]


def badge(im):
    d = ImageDraw.Draw(im)
    bw, bh, y = 400, 118, 110
    x = (W - bw) // 2
    d.rounded_rectangle([x, y, x + bw, y + bh], 22, fill=(244, 238, 224))
    ic = Image.open(ICONE).convert("RGBA").resize((70, 70))
    im.paste(ic, (x + 34, y + 24), ic)
    d.text((x + 128, y + 22), "LaBible", font=F(ROB % 700, 42), fill=(40, 34, 26))
    lw = d.textlength("LaBible", font=F(ROB % 700, 42))
    d.text((x + 128 + lw, y + 22), ".app", font=F(ROB % 700, 42), fill=(176, 132, 52))
    d.text((x + 130, y + 72), "L S G   1 9 1 0", font=F(ROB % 500, 22), fill=(120, 110, 96))


BASE = FOND.copy(); badge(BASE)
d0 = ImageDraw.Draw(BASE)
d0.line([(110, 1712), (W - 110, 1712)], fill=(90, 78, 58), width=2)

# telephone
PX, PY, PW, PH = 190, 560, 700, 1080        # ecran
BZ = 22                                     # bord


def telephone(ecran):
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(c)
    d.rounded_rectangle([PX - BZ + 10, PY - BZ + 24, PX + PW + BZ + 10, PY + PH + BZ + 24], 70, fill=(0, 0, 0, 120))
    d.rounded_rectangle([PX - BZ, PY - BZ, PX + PW + BZ, PY + PH + BZ], 66, fill=(18, 17, 16, 255),
                        outline=(70, 64, 54, 255), width=3)
    c.paste(ecran, (PX, PY), arrondi((PW, PH), 46))
    d.rounded_rectangle([W // 2 - 60, PY + 12, W // 2 + 60, PY + 22], 5, fill=(0, 0, 0, 160))
    return c


def ecran(nom, cy, larg, u):
    src = img(nom + ".jpg")
    k = 1 + 0.04 * u                        # lente avancee
    cw = larg * 3 / k
    ch = cw * PH / PW
    cx = src.size[0] / 2
    top = max(0, min(src.size[1] - ch, cy * 3 - ch / 2))
    left = max(0, min(src.size[0] - cw, cx - cw / 2))
    return src.crop((int(left), int(top), int(left + cw), int(top + ch))).resize((PW, PH), Image.BILINEAR)


def image_seule(nom, u):
    src = img(nom)
    t = int(760 * (1 + 0.03 * u))
    im = src.resize((t, int(t * src.size[1] / src.size[0])), Image.BILINEAR)
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(c)
    x, y = (W - im.size[0]) // 2, 1110 - im.size[1] // 2
    d.rounded_rectangle([x + 10, y + 24, x + im.size[0] + 10, y + im.size[1] + 24], 40, fill=(0, 0, 0, 110))
    c.paste(im, (x, y), arrondi(im.size, 36))
    return c


def calque(i, u):
    _, dur, typ, par = PLANS[i]
    u = u / max(dur, 0.01)
    if typ == "image":
        return image_seule(par[0], u)
    return telephone(ecran(par[0], par[1], par[2], u))


def textes(p, a):
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if a <= 0:
        return c
    d = ImageDraw.Draw(c)
    rub, tit, sous, ital = PARTIES[p]
    A = int(255 * a)
    t = 100 if p < 6 else 128
    while d.textlength(tit, font=F(GAR, t)) > 960: t -= 4
    centre(d, tit, 300, F(GAR, t), CREME + (A,))
    fs = F(ITA, 64) if ital else F(ROB % 400, 40)
    centre(d, sous, 430 if ital else 440, fs, (OR if ital else eclaircir(OR, 0.1)) + (A,))
    txt = "   ".join(" ".join(m) for m in rub.split())     # lettres espacees
    centre(d, txt, 1750, F(ROB % 500, 28), OR + (A,))
    return c


def calendrier(voix):
    """Durees des plans allongees a la voix de leur partie ; debuts des parties."""
    durs = [p[1] for p in PLANS]
    for p in range(len(PARTIES)):
        idx = [i for i, pl in enumerate(PLANS) if pl[0] == p]
        besoin = 0.5 + voix[p] + 0.9 if voix.get(p) else 0
        tot = sum(durs[i] for i in idx) - XF * (len(idx) - 1)
        if besoin > tot:
            for i in idx:
                durs[i] += (besoin - tot) / len(idx)
    debuts, t = [], 0.0
    for dd in durs:
        debuts.append(t); t += dd - XF
    return durs, debuts, t + XF


def _duree(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f],
                                capture_output=True, text=True).stdout)


def main():
    fic = {p: os.path.join(D, "voix", f"ep12_{p}.mp3") for p in range(len(PARTIES))}
    voix = {p: _duree(f) for p, f in fic.items() if os.path.exists(f)}
    durs, debuts, tot = calendrier(voix)
    PLANS[:] = [(pl[0], durs[i], pl[2], pl[3]) for i, pl in enumerate(PLANS)]
    deb_p = {p: min(debuts[i] for i, pl in enumerate(PLANS) if pl[0] == p) for p in range(len(PARTIES))}
    fin_p = {p: (deb_p[p + 1] + XF / 2 if p + 1 in deb_p else tot) for p in deb_p}
    n = int(tot * FPS)
    tmp = os.path.join(D, "presentation2.video.tmp.mp4")
    pr = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "19", "-preset", "veryfast",
                           "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    for k in range(n):
        t = k / FPS
        i = max(j for j in range(len(PLANS)) if debuts[j] <= t)
        u = t - debuts[i]
        lay = calque(i, u)
        if i > 0 and u < XF:                       # fondu depuis le plan precedent
            prev = calque(i - 1, t - debuts[i - 1])
            lay = Image.blend(prev, lay, 0.5 - 0.5 * math.cos(math.pi * u / XF))
        im = Image.alpha_composite(BASE.convert("RGBA"), lay)
        dep = {q: (0 if q == 0 else deb_p[q] + XF / 2) for q in deb_p}
        p = max(q for q in dep if dep[q] <= t)
        a = min(1, (t - dep[p]) / 0.4)
        if p + 1 in dep:
            a = min(a, (dep[p + 1] - 0.08 - t) / 0.35)
        im = Image.alpha_composite(im, textes(p, max(0, a))).convert("RGB")
        if k < 12: im = Image.blend(Image.new("RGB", (W, H), (6, 6, 7)), im, k / 12)
        if k >= n - 18: im = Image.blend(Image.new("RGB", (W, H), (6, 6, 7)), im, (n - k) / 18)
        pr.stdin.write(im.tobytes())
    pr.stdin.close()
    assert pr.wait() == 0
    sortie = os.path.join(D, "presentation_labible.mp4"); tmp2 = sortie + ".tmp.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-ss", "8", "-i", os.path.join(D, "musique.mp3")]
    clips = [(deb_p[p] + 0.5, fic[p]) for p in sorted(voix)]
    for _, f in clips: cmd += ["-i", f]
    fc = f"[1:a]volume=0.32,afade=t=in:d=1.5,afade=t=out:st={tot - 2.5:.2f}:d=2.5,aformat=channel_layouts=stereo:sample_rates=44100[m];"
    for j, (t0, _) in enumerate(clips):
        ms = int(t0 * 1000)
        fc += f"[{j + 2}:a]aformat=channel_layouts=stereo:sample_rates=44100,adelay={ms}|{ms}[v{j}];"
    fc += "".join(f"[v{j}]" for j in range(len(clips))) + f"amix=inputs={len(clips)}:normalize=0[voix];"
    fc += "[voix]asplit[v1][v2];[m][v1]sidechaincompress=threshold=0.015:ratio=6:attack=30:release=800:makeup=1[md];"
    fc += "[md][v2]amix=inputs=2:normalize=0,loudnorm=I=-15:TP=-1.5:LRA=11[a]"
    cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-ar", "44100", "-t", f"{tot:.2f}", tmp2]
    subprocess.run(cmd, check=True)
    os.replace(tmp2, sortie); os.remove(tmp)
    print(f"ok presentation {tot:.1f}s")


def apercu():
    import sys
    durs, debuts, tot = calendrier({})
    for k, i in enumerate([0, 1, 2, 4, 6, 9, 11]):
        p = PLANS[i][0]
        im = Image.alpha_composite(Image.alpha_composite(BASE.convert("RGBA"), calque(i, 1.0)), textes(p, 1)).convert("RGB")
        im.save(f"/tmp/p2_{k}.jpg", quality=88)


if __name__ == "__main__":
    import sys
    apercu() if "--images" in sys.argv else main()
