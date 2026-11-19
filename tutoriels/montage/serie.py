"""Serie « Decouvrir LaBible.app » : 10 Shorts tutoriels, captures reelles.
Usage : python3 serie.py [numero ...] [--images]"""
import json, math, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
D = os.path.dirname(os.path.abspath(__file__))
CAP = os.path.join(D, "cap")
POS = json.load(open(os.path.join(CAP, "serie.json")))
GAR = "/home/claude/bible-telegram-bot/fonts/EBGaramond-Regular.ttf"
ROB = os.path.expanduser("~/.fonts/roboto-latin-%d-normal.ttf")
CREME = (240, 232, 212)
XF = 0.5          # fondu enchaine entre deux plans (s)
SERIE = "Astuces LaBible.app"
_cache = {}

def F(chemin, t):
    k = (chemin, t)
    if k not in _cache: _cache[k] = ImageFont.truetype(chemin, t)
    return _cache[k]

def fond(acc):
    """Fond sombre avec deux halos de la couleur de l'episode."""
    import numpy as np
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    base = np.array([14, 13, 12], np.float32) * (1 - yy / H)[..., None] + np.array([6, 6, 7], np.float32) * (yy / H)[..., None]
    a = np.array(acc, np.float32)
    for cx, cy, r, f in ((W * 0.2, H * 0.08, 950, 0.42), (W * 0.85, H * 0.92, 1050, 0.32)):
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
        base += (np.clip(1 - d, 0, 1) ** 2 * f)[..., None] * a
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))

def centre(d, txt, y, f, coul):
    b = d.textbbox((0, 0), txt, font=f)
    d.text(((W - (b[2] - b[0])) / 2 - b[0], y - b[1]), txt, font=f, fill=coul)

def lignes(d, txt, f, largeur):
    out, cur = [], ""
    for m in txt.split():
        e = (cur + " " + m).strip()
        if d.textlength(e, font=f) <= largeur: cur = e
        else: out.append(cur); cur = m
    return out + [cur]

def arrondi(sz, r):
    m = Image.new("L", sz, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, sz[0] - 1, sz[1] - 1], r, fill=255)
    return m

def eclaircir(c, k): return tuple(int(v + (255 - v) * k) for v in c)

class Ep:
    def __init__(s, n, titre, acc, plans):
        s.n, s.titre, s.acc, s.plans = n, titre, acc, plans
        s.fond = fond(acc)
        s.tete = s._tete()

    def _tete(s):
        im = s.fond.copy(); d = ImageDraw.Draw(im)
        f = F(ROB % 500, 34)
        txt = SERIE
        w = d.textlength(txt, font=f)
        x0 = (W - w) / 2 - 28
        d.rounded_rectangle([x0, 86, x0 + w + 56, 146], 30, fill=tuple(int(v * 0.28) for v in s.acc), outline=s.acc, width=2)
        centre(d, txt, 100, f, eclaircir(s.acc, 0.35))
        t = 70
        while t > 44 and d.textlength(s.titre, font=F(GAR, t)) > 900: t -= 2
        centre(d, s.titre, 182 + (70 - t) // 3, F(GAR, t), CREME)
        return im

    # ---- plans
    def legende(s, im, txt, a=1.0):
        if not txt or a <= 0: return im
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
        f = F(ROB % 500, 54)
        ls = lignes(d, txt, f, 920)
        y = 1650 - (len(ls) - 1) * 37
        for l in ls:
            centre(d, l, y, f, CREME + (int(255 * a),)); y += 74
        return Image.alpha_composite(im.convert("RGBA"), c).convert("RGB")

    def anneau(s, im, x, y, r, a, point=True):
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
        d.ellipse([x - r, y - r, x + r, y + r], outline=s.acc + (int(255 * a),), width=7)
        if point: d.ellipse([x - 24, y - 24, x + 24, y + 24], fill=(255, 255, 255, int(130 * a)))
        return Image.alpha_composite(im.convert("RGBA"), c).convert("RGB")

    def fleche(s, im, x0, x1, y, a):
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(c)
        col = s.acc + (int(230 * a),)
        d.line([(x0, y), (x1, y)], fill=col, width=9)
        dx = -1 if x1 < x0 else 1
        d.polygon([(x1 + 30 * dx, y), (x1 - 10 * dx, y - 26), (x1 - 10 * dx, y + 26)], fill=col)
        return Image.alpha_composite(im.convert("RGBA"), c).convert("RGB")

FX, FY, FW, FH = 90, 290, 900, 1270

def fenetre(ep, nom, cy, t, dur, zoom=0.035):
    """Capture rognee autour de cy (px CSS), lente avancee (Ken Burns)."""
    src = Image.open(os.path.join(CAP, nom + ".jpg"))
    e0 = FW / src.size[0]
    k = 1 + zoom * (t / max(dur, 0.01))
    e = e0 * k
    cw, ch = FW / e, FH / e
    cx = src.size[0] / 2
    top = max(0, min(src.size[1] - ch, cy * 3 - ch / 2))
    left = max(0, min(src.size[0] - cw, cx - cw / 2))
    crop = src.crop((int(left), int(top), int(left + cw), int(top + ch))).resize((FW, FH), Image.BILINEAR)
    im = ep.tete.copy()
    im.paste(crop, (FX, FY), arrondi((FW, FH), 40))
    c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(c).rounded_rectangle([FX - 4, FY - 4, FX + FW + 4, FY + FH + 4], 44, outline=ep.acc + (170,), width=4)
    im = Image.alpha_composite(im.convert("RGBA"), c).convert("RGB")
    geo = lambda xc, yc: (FX + (xc * 3 - left) * e, FY + (yc * 3 - top) * e)
    return im, geo

def centre_de(b): return (b[0] + b[2] / 2, b[1] + b[3] / 2)

# ---------------------------------------------------------------- types de plans
def P_ecran(nom, cy, txt, tap=None, dur=3.2, fleche=None):
    def f(ep, t):
        im, geo = fenetre(ep, nom, cy, t, dur)
        if tap is not None and t > 0.9:
            u = (t - 0.9) / 0.7
            x, y = geo(*tap)
            im = ep.anneau(im, x, y, 30 + 42 * min(1, u), max(0, min(1, 2.2 - u)))
        if fleche is not None and t > 0.6:
            u = min(1, (t - 0.6) / 1.1)
            x0, x1, yc = fleche
            (ax, ay), (bx, _) = geo(x0, yc), geo(x1, yc)
            im = ep.fleche(im, ax, ax + (bx - ax) * u, ay, min(1, u * 2))
        return ep.legende(im, txt)
    return (dur, f)

def P_zoom(nom, region, points, per=1.45):
    """Gros plan sur une region (px CSS), anneau successif sur chaque point."""
    x0, y0, x1, y1 = region
    def f(ep, t):
        src = Image.open(os.path.join(CAP, nom + ".jpg"))
        zc = src.crop((int(x0 * 3), int(y0 * 3), int(x1 * 3), int(y1 * 3)))
        e = 1000 / zc.size[0]
        zc = zc.resize((1000, int(zc.size[1] * e)), Image.BILINEAR)
        zx, zy = 40, 920 - zc.size[1] // 2
        im = ep.tete.copy(); im.paste(zc, (zx, zy), arrondi(zc.size, 36))
        i = min(len(points) - 1, int(t / per)); u = (t - i * per) / per
        (px, py), txt = points[i]
        cx, cy = zx + (px * 3 - x0 * 3) * e, zy + (py * 3 - y0 * 3) * e
        im = ep.anneau(im, cx, cy, 62 + 6 * math.sin(u * math.pi), 1, point=False)
        a = min(1, u / 0.15, (1 - u) / 0.12) if i < len(points) - 1 else min(1, u / 0.15)
        return ep.legende(im, txt, a)
    return (per * len(points), f)

def P_image(fichier, txt, dur=3.2):
    def f(ep, t):
        img = Image.open(os.path.join(CAP, fichier))
        k = 860 * (1 + 0.03 * t / dur)
        img = img.resize((int(k), int(k)), Image.BILINEAR)
        im = ep.tete.copy(); x = (W - img.size[0]) // 2; y = 960 - img.size[1] // 2
        im.paste(img, (x, y), arrondi(img.size, 36))
        return ep.legende(im, txt)
    return (dur, f)

def P_titre(dur=2.6):
    def f(ep, t):
        im = ep.fond.copy(); d = ImageDraw.Draw(im)
        centre(d, "Astuce", 690, F(ROB % 500, 42), eclaircir(ep.acc, 0.25))
        ls = lignes(d, ep.titre, F(GAR, 116), 940)
        y = 790
        for l in ls: centre(d, l, y, F(GAR, 116), CREME); y += 130
        d.rounded_rectangle([W / 2 - 70, y + 40, W / 2 + 70, y + 46], 3, fill=ep.acc)
        centre(d, "La Bible Louis Segond 1910", y + 90, F(GAR, 52), eclaircir(ep.acc, 0.2))
        return im
    return (dur, f)

def P_fin(dur=3.4):
    def f(ep, t):
        im = ep.fond.copy(); d = ImageDraw.Draw(im)
        centre(d, "LaBible.app", 760, F(GAR, 124), CREME)
        centre(d, "La Bible Louis Segond 1910", 935, F(GAR, 56), eclaircir(ep.acc, 0.2))
        centre(d, "Gratuite, sans publicité, hors ligne.", 1035, F(ROB % 400, 44), (205, 198, 180))
        return im
    return (dur, f)

# ---------------------------------------------------------------- episodes
def B(nom, cle): return POS[nom][cle]

def episodes():
    E = []
    # 1 Lire
    l1 = POS["l1_haut"]
    E.append(Ep(1, "Lire la Bible confortablement", (226, 197, 122), [
        P_titre(),
        P_ecran("l1_haut", 270, "Choisissez le livre, le chapitre et le verset.", tap=centre_de(l1["livre"])),
        P_ecran("l1_haut", 270, "« Suivant » ouvre le chapitre d'après.", tap=centre_de(l1["suiv"]), dur=2.6),
        P_ecran("l2_suivant", 330, "Psaumes 24 : vous y êtes.", dur=2.6),
        P_ecran("l3_texte", 700, "Vous pouvez aussi glisser le doigt sur le texte.", fleche=(320, 80, 560), dur=3.4),
        P_ecran("l4_grand", 270, "A+ et A− changent la taille du texte.", tap=centre_de(B("l4_grand", "aplus"))),
        P_ecran("l5_clair", 270, "Le mode clair, pour lire en plein jour.", tap=centre_de(B("l5_clair", "theme"))),
        P_ecran("l5_clair", 270, "Ce bouton garde l'écran allumé pendant la lecture.", tap=centre_de(B("l5_clair", "wake")), dur=3.6),
        P_fin()]))
    # 2 Toucher un verset
    v = B("t1_lecture", "v16"); bar = B("t2_barre", "bar")
    btn = {b[0]: (b[1] + b[3] / 2, b[2] + b[4] / 2) for b in POS["t2_barre"]["btns"]}
    lib = [("Ajouter aux favoris", "Gardez le verset dans vos favoris."), ("Écouter", "Écoutez-le, lu à voix haute."),
           ("Copier", "Copiez le texte et sa référence."), ("Partager", "Partagez-le sur vos réseaux."),
           ("Créer une image", "Faites-en une image à partager."), ("Ajouter le verset suivant", "Ajoutez le verset suivant."),
           ("Références croisées", "Ouvrez les versets liés.")]
    E.append(Ep(2, "Tout faire depuis un verset", (240, 138, 60), [
        P_titre(),
        P_ecran("t1_lecture", v[1] + v[3] / 2, "Touchez un verset.", tap=(v[0] + v[2] * 0.55, v[1] + v[3] / 2)),
        P_ecran("t2_barre", bar[1], "Une barre s'ouvre sous le verset.", dur=2.8),
        P_zoom("t2_barre", (28, bar[1] - 150, 362, bar[1] + bar[3] + 40), [(btn[k], t) for k, t in lib]),
        P_ecran("t3_plus", B("t3_plus", "bar")[1] - 40, "Jusqu'à cinq versets à la suite."),
        P_ecran("t4_refs", 150 + 380, "Les références ouvrent d'autres passages."),
        P_image("t5_image.jpg", "Une image prête à partager."),
        P_fin()]))
    # 3 Rechercher
    E.append(Ep(3, "Retrouver un verset en un instant", (108, 155, 239), [
        P_titre(),
        P_ecran("r1_ref", 270, "Cherchez une référence…", tap=centre_de(B("r1_ref", "bouton"))),
        P_ecran("r1b_resultat", 270, "Touchez le résultat : le verset s'affiche.", tap=centre_de(B("r1b_resultat", "res")), dur=2.9),
        P_ecran("r1c_deplie", 270, "Touchez le texte…", tap=centre_de(B("r1c_deplie", "texte")), dur=2.6),
        P_ecran("r2_ouvert", B("r2_ouvert", "v16")[1], "… et le verset s'ouvre dans son chapitre."),
        P_ecran("r3_mot", 270, "Ou cherchez un mot.", tap=centre_de(B("r3_mot", "bouton"))),
        P_ecran("r4_resultats", 420, "Tous les versets qui le contiennent s'affichent.", dur=3.6),
        P_fin()]))
    # 4 Verset du jour
    bb = POS["b1_biblio"]
    vb = bb["vddbox"]
    E.append(Ep(4, "Recevoir un verset chaque jour", (229, 138, 168), [
        P_titre(),
        P_ecran("j1_bouton", 270, "Chaque jour, un nouveau verset.", tap=centre_de(B("j1_bouton", "vdd"))),
        P_ecran("j2_ouvert", 420, "Il s'ouvre dans son chapitre."),
        P_zoom("b1_biblio", (20, vb[1] - 70, 370, vb[1] + vb[3] + 70),
               [(centre_de(bb["vddbox"]), "Vous le retrouvez dans la Bibliothèque."),
                (centre_de(bb["copier"]), "Copiez-le…"), (centre_de(bb["image"]), "… ou faites-en une image.")], per=1.8),
        P_image("j3_image.jpg", "Un verset à partager chaque jour."),
        P_fin()]))
    # 5 Plan
    p1 = POS["p1_plan"]
    E.append(Ep(5, "Lire toute la Bible en un an", (111, 191, 115), [
        P_titre(),
        P_ecran("p1_plan", 330, "Lisez toute la Bible en un an."),
        P_ecran("p1_plan", 330, "Chaque jour, quelques chapitres.", tap=centre_de(p1["ouvrir"])),
        P_ecran("p2_lu", 330, "Marquez la lecture du jour.", tap=centre_de(B("p2_lu", "lu"))),
        P_ecran("p2_lu", 330, "Votre progression reste sur votre appareil.", dur=3.4),
        P_fin()]))
    # 6 Bibliotheque
    E.append(Ep(6, "Garder vos versets favoris", (155, 123, 234), [
        P_titre(),
        P_ecran("b1_biblio", 330, "Vos favoris et votre historique, au même endroit."),
        P_ecran("b2_biblio_bas", 520, "Rouvrez, copiez ou partagez en un geste.", dur=3.4),
        P_fin()]))
    # 7 Themes
    E.append(Ep(7, "Trouver des versets par thème", (63, 184, 160), [
        P_titre(),
        P_ecran("v1_themes", 420, "48 thèmes, près de 1 500 versets.", tap=centre_de(B("v1_themes", "protection"))),
        P_ecran("v2_theme", 380, "Les versets choisis pour chaque thème."),
        P_ecran("v3_theme_bas", 420, "Touchez un verset pour lire tout le chapitre.", dur=3.4),
        P_fin()]))
    # 8 Audio
    E.append(Ep(8, "Écouter la Bible", (91, 184, 232), [
        P_titre(),
        P_ecran("a1_audio", 340, "La Bible lue à voix haute, chapitre après chapitre.", dur=3.6),
        P_ecran("a2_livres", 420, "Choisissez un livre…", tap=centre_de(B("a2_livres", "genese"))),
        P_ecran("a3_chapitres", 560, "… puis le chapitre à écouter.", dur=3.4),
        P_fin()]))
    # 9 Quiz
    E.append(Ep(9, "Tester vos connaissances bibliques", (232, 121, 90), [
        P_titre(),
        P_ecran("q1_themes", 420, "Six thèmes pour tester vos connaissances.", tap=centre_de(B("q1_themes", "psaumes"))),
        P_ecran("q2_question", 380, "Retrouvez le début ou la suite du verset.", tap=centre_de(B("q2_question", "choix"))),
        P_ecran("q3_reponse", 420, "La réponse renvoie au chapitre.", dur=3.4),
        P_fin()]))
    # 10 Installer
    E.append(Ep(10, "Installer LaBible.app sur votre téléphone", (226, 197, 122), [
        P_titre(),
        P_ecran("i1_bouton", 270, "Installez l'app en un geste.", tap=centre_de(B("i1_bouton", "inst"))),
        P_ecran("i2_page", 400, "Gratuite, sur téléphone, tablette ou ordinateur."),
        P_ecran("i3_page_bas", 400, "Toute la Bible, même sans internet.", dur=3.4),
        P_fin()]))
    return E

# ---------------------------------------------------------------- rendu
def frame(ep, t):
    """Plans enchaines : fondu enchaine de XF secondes entre deux plans."""
    debut = 0
    for i, (dur, f) in enumerate(ep.plans):
        if t < debut + dur or i == len(ep.plans) - 1:
            u = t - debut
            im = f(ep, min(u, dur))
            if i + 1 < len(ep.plans) and u > dur - XF:
                k = (u - (dur - XF)) / XF
                nxt = ep.plans[i + 1][1](ep, u - (dur - XF))
                im = Image.blend(im, nxt, 0.5 - 0.5 * math.cos(math.pi * k))
            if i == 0 and u < 0.5:
                im = Image.blend(Image.new("RGB", (W, H), (6, 6, 7)), im, u / 0.5)
            return im
        debut += dur - XF
    return im

def duree(ep): return sum(d for d, _ in ep.plans) - XF * (len(ep.plans) - 1)

VOIX = os.path.join(D, "voix")
AVANT_VOIX, APRES_VOIX = 0.4, 1.0

def _duree_mp3(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f],
                                capture_output=True, text=True).stdout)

def narration(ep):
    """Allonge chaque plan au temps de sa phrase ; renvoie [(debut, fichier)]."""
    clips, debut, plans = [], 0.0, []
    for i, (dur, f) in enumerate(ep.plans):
        fic = os.path.join(VOIX, f"ep{ep.n:02d}_{i}.mp3")
        if os.path.exists(fic):
            dur = max(dur, AVANT_VOIX + _duree_mp3(fic) + APRES_VOIX + XF)
            clips.append((debut + AVANT_VOIX, fic))
        plans.append((dur, f))
        debut += dur - XF
    ep.plans = plans
    return clips

def rendre(ep, musique="musique.mp3"):
    clips = narration(ep)
    tot = duree(ep); n = int(tot * FPS)
    nom = f"tuto_{ep.n:02d}"
    tmp = os.path.join(D, nom + ".video.tmp.mp4")
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
                          "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    for i in range(n):
        im = frame(ep, i / FPS)
        if i >= n - 15: im = Image.blend(Image.new("RGB", (W, H), (6, 6, 7)), im, (n - i) / 15)
        p.stdin.write(im.tobytes())
    p.stdin.close()
    assert p.wait() == 0
    sortie = os.path.join(D, nom + ".mp4"); tmp2 = sortie + ".tmp.mp4"
    lg = _duree_mp3(musique)
    debut = (4 + 23 * ep.n) % max(1, int(lg - tot - 5))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-ss", str(debut), "-i", musique]
    for _, f in clips: cmd += ["-i", f]
    fc = f"[1:a]volume=0.32,afade=t=in:d=1,afade=t=out:st={tot - 2:.2f}:d=2,aformat=channel_layouts=stereo:sample_rates=44100[m];"
    if clips:
        for k, (t0, _) in enumerate(clips):
            ms = int(t0 * 1000)
            fc += f"[{k + 2}:a]aformat=channel_layouts=stereo:sample_rates=44100,adelay={ms}|{ms}[v{k}];"
        fc += "".join(f"[v{k}]" for k in range(len(clips))) + f"amix=inputs={len(clips)}:normalize=0[voix];"
        fc += "[voix]asplit[v1][v2];[m][v1]sidechaincompress=threshold=0.015:ratio=6:attack=30:release=800:makeup=1[md];"
        fc += "[md][v2]amix=inputs=2:normalize=0,loudnorm=I=-15:TP=-1.5:LRA=11[a]"
    else:
        fc += "[m]loudnorm=I=-15:TP=-1.5:LRA=11[a]"
    cmd += ["-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            "-ar", "44100", "-t", f"{tot:.2f}", tmp2]
    subprocess.run(cmd, check=True)
    os.replace(tmp2, sortie); os.remove(tmp)
    print(f"ok {nom} {tot:.1f}s")

if __name__ == "__main__":
    nums = [int(a) for a in sys.argv[1:] if a.isdigit()]
    eps = [e for e in episodes() if not nums or e.n in nums]
    if "--images" in sys.argv:
        for ep in eps:
            tot = duree(ep)
            ims = [frame(ep, t).resize((270, 480)) for t in [k * tot / 6 + 1.2 for k in range(6)]]
            m = Image.new("RGB", (6 * 280, 480), "white")
            for i, im in enumerate(ims): m.paste(im, (i * 280, 0))
            m.save(f"/tmp/ep{ep.n}.jpg", quality=85)
        sys.exit()
    for ep in eps: rendre(ep)
