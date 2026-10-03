#!/usr/bin/env python3
"""Gerador de GIFs quadrados para o Tenor — LaBible.app.

Este ficheiro gerou os trinta GIFs publicados no Tenor a 29/09/2026.
O gif_tenor.py original perdeu-se; este é o código de produção.

NÃO é chamado pelo bot. O Tenor não tem endpoint de upload na API, por
isso a publicação é sempre à mão. Isto é uma ferramenta avulsa, que vive
no repositório para não existir num sítio só.

640x640, boucle de 4 s, poeira de estrelas em movimento contínuo.
O texto NUNCA é escrito à mão: vem de bible/lsg1910.json pelas funções
do bot (load_verse -> strip_rubric -> clean_text), através do campo
"texte" do tenor_30.json.

Correr a partir da raiz do repositório:
    python3 gif_tenor.py --json tenor_30.json --out gifs
    python3 gif_tenor.py --json tenor_30.json --out gifs --only 1 14
"""
import os, sys, math, random, json, argparse
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W = H = 640
FPS = 10
DUR = 4.0
NFRAMES = int(FPS * DUR)          # 40
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

# Fundos observados nos cinco: azul-noite, negro, castanho, verde-escuro, violeta.
PALETTES = {
    "nuit":    ((10, 17, 48),  (4, 7, 22)),
    "noir":    ((20, 18, 16),  (6, 5, 5)),
    "terre":   ((32, 22, 14),  (10, 7, 5)),
    "foret":   ((10, 30, 22),  (4, 11, 9)),
    "violet":  ((26, 14, 40),  (9, 5, 15)),
}
ORDER = ["nuit", "noir", "terre", "foret", "violet"]

CREAM = (238, 233, 222)
GOLD  = (198, 163, 98)
GREY  = (128, 122, 112)


def _font(path, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, path), size)


def _background(pal):
    """Degradé radial suave, mais claro no centro."""
    top, bot = PALETTES[pal]
    small = 80
    img = Image.new("RGB", (small, small))
    px = img.load()
    cx = cy = (small - 1) / 2
    maxd = math.hypot(cx, cy)
    for y in range(small):
        for x in range(small):
            t = math.hypot(x - cx, y - cy) / maxd
            t = min(1.0, t ** 1.15)
            px[x, y] = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
    return img.resize((W, H), Image.BICUBIC)


def _stars(seed, n=100):
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        out.append({
            "x": rnd.uniform(0, W),
            "y": rnd.uniform(0, H),
            "r": rnd.choice([0.6, 0.8, 1.0, 1.0, 1.3, 1.7]),
            "base": rnd.uniform(0.25, 0.95),
            "phase": rnd.uniform(0, math.tau),
            "cycles": rnd.choice([1, 1, 2, 2, 3]),   # inteiro => boucle perfeita
            "dx": rnd.uniform(-10, 10),              # deriva total em 4 s
            "dy": rnd.uniform(-26, -8),
        })
    return out


def _wrap(draw, text, font, maxw):
    # split(" ") e não split(): o espaço inseparável (U+00A0) tem de colar
    # a pontuação francesa à palavra anterior e os guillemets ao texto.
    words, lines, cur = [w for w in text.split(" ") if w], [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= maxw:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


NBSP = "\u00a0"

# A EB Garamond NAO tem glifo para U+202F (narrow no-break space). O clean_text
# do bot aplica U+202F antes de ; ? ! — e esse caracter chega aqui dentro do
# campo "texte" do tenor_30.json. Desenhado tal e qual, sai um quadrado vazio na
# imagem. Normaliza-se para U+00A0, que a fonte tem. Ver _verificar_glifos.
ESPACOS_FINOS = ("\u202f", "\u2009", "\u200a", "\u2007")


def _nbsp(text):
    """Tipografia francesa: nunca começar uma linha por ! ? ; : ou », nem acabar em «."""
    for e in ESPACOS_FINOS:
        text = text.replace(e, NBSP)
    for p in ("!", "?", ";", ":", "»"):
        text = text.replace(" " + p, NBSP + p)
    return text.replace("« ", "«" + NBSP)


def _verificar_glifos(text, font_path="EBGaramond-Regular.ttf"):
    """Para o programa se a fonte nao souber desenhar algum caracter.

    Um caracter sem glifo nao levanta erro nenhum: a PIL desenha um quadrado
    vazio e segue. Foi assim que 12 dos 30 GIFs publicados a 29/09/2026 sairam
    com um quadrado antes do ponto de exclamacao, sem que nada o dissesse.
    Um defeito silencioso e um defeito que se decidiu nao ver.
    """
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return                      # verificacao opcional; nao bloqueia a geracao
    cmap = TTFont(os.path.join(FONT_DIR, font_path)).getBestCmap()
    faltam = sorted({c for c in text if ord(c) not in cmap and c != "\n"})
    if faltam:
        desc = ", ".join(f"U+{ord(c):04X} ({c!r})" for c in faltam)
        sys.exit(f"ERRO: a fonte {font_path} nao tem glifo para: {desc}\n"
                 f"      Texto: {text!r}")


def _layout(text, maxw, max_lines=6):
    """Escolhe o maior corpo de letra que ainda cabe."""
    probe = Image.new("RGB", (10, 10))
    d = ImageDraw.Draw(probe)
    for size in range(46, 25, -1):
        f = _font("EBGaramond-Regular.ttf", size)
        lines = _wrap(d, text, f, maxw)
        if len(lines) <= max_lines:
            return f, lines, size
    f = _font("EBGaramond-Regular.ttf", 26)
    return f, _wrap(d, text, f, maxw), 26


def _static_layer(text, ref):
    """Texto e assinatura — iguais em todos os fotogramas."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    maxw = W - 150
    citacao = _nbsp(f"« {text} »")
    _verificar_glifos(citacao)
    _verificar_glifos(ref)
    font, lines, size = _layout(citacao, maxw)
    lh = int(size * 1.46)
    total = lh * len(lines)
    y = (H - total) // 2 - 26
    for ln in lines:
        d.text((W // 2, y), ln, font=font, fill=CREAM + (255,), anchor="ma")
        y += lh

    # filete + referência (em baixo à esquerda), marca à direita
    fref = _font("EBGaramond-Regular.ttf", 19)
    flsg = _font("EBGaramond-Regular.ttf", 13)
    fmark = _font("EBGaramond-Italic.ttf", 14)
    bx, by = 58, H - 92
    d.line([(bx, by), (W - 58, by)], fill=GOLD + (70,), width=1)
    d.text((bx, by + 14), ref, font=fref, fill=GOLD + (255,))
    d.text((bx, by + 38), "LSG 1910", font=flsg, fill=GREY + (255,))
    d.text((W - 58, by + 34), "LaBible.app", font=fmark, fill=GREY + (190,), anchor="ra")
    return layer


def _palette(frame, pal, colors=80):
    """Paleta global: o primeiro fotograma + rampas garantidas para o texto."""
    ramp_h = 64
    src = Image.new("RGB", (W, H + ramp_h * 3))
    src.paste(frame, (0, 0))
    d = ImageDraw.Draw(src)
    base = PALETTES[pal][0]
    for k, col in enumerate((CREAM, GOLD, GREY)):
        for x in range(W):
            t = x / (W - 1)
            c = tuple(int(base[i] + (col[i] - base[i]) * t) for i in range(3))
            d.line([(x, H + k * ramp_h), (x, H + (k + 1) * ramp_h - 1)], fill=c)
    return src.quantize(colors=colors, method=Image.MEDIANCUT)


def make_gif(text, ref, out_path, pal="nuit", seed=0):
    bg = _background(pal)
    stars = _stars(seed)
    static = _static_layer(text, ref)
    frames = []
    for i in range(NFRAMES):
        t = i / NFRAMES                      # 0..1, boucle fechada
        star_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(star_layer)
        for s in stars:
            x = (s["x"] + s["dx"] * t) % W
            y = (s["y"] + s["dy"] * t) % H
            tw = 0.62 + 0.38 * math.sin(s["phase"] + math.tau * s["cycles"] * t)
            a = int(255 * s["base"] * tw)
            r = s["r"]
            sd.ellipse([x - r, y - r, x + r, y + r], fill=(255, 252, 240, a))
        star_layer = star_layer.filter(ImageFilter.GaussianBlur(0.45))
        fr = bg.copy().convert("RGBA")
        fr.alpha_composite(star_layer)
        fr.alpha_composite(static)
        frames.append(fr.convert("RGB"))
    # Paleta global unica: fotogramas muito mais parecidos => GIF muito mais leve.
    # A amostra inclui rampas fundo->creme/ouro/cinza para o texto nao perder a cor
    # (sem isto, no fundo "noir" a referencia saia cinzenta e granulada).
    pal_img = _palette(frames[0], pal)
    frames = [f.quantize(palette=pal_img, dither=Image.Dither.NONE) for f in frames]
    frames[0].save(out_path, save_all=True, append_images=frames[1:],
                   duration=int(1000 / FPS), loop=0, optimize=True, disposal=1)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True, help="tenor_30.json")
    ap.add_argument("--out", default="gifs")
    ap.add_argument("--only", type=int, nargs="*", help="gerar só estes números")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rows = json.load(open(a.json, encoding="utf-8"))
    for r in rows:
        if a.only and r["n"] not in a.only:
            continue
        pal = ORDER[(r["n"] - 1) % len(ORDER)]
        name = f"{r['n']:02d}_{r['ref'].replace(' ', '_').replace(':', '-')}.gif"
        p = make_gif(r["texte"], r["ref"], os.path.join(a.out, name), pal, seed=r["n"] * 97)
        print(f"{r['n']:2}  {pal:7} {os.path.getsize(p)/1024:6.0f} KB  {name}")


if __name__ == "__main__":
    main()
