"""
holy_week.py \u2014 Publications sp\u00e9ciales Semaine Sainte 2026
Publie images + reels en extra (en plus des publications normales)
"""
import os, json, datetime, hashlib, math, subprocess, requests, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# \u2500\u2500 Secrets \u2500\u2500
TOKEN                 = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL               = os.environ["TELEGRAM_CHANNEL"]
FB_PAGE_ID            = os.environ.get("FB_PAGE_ID", "1018605031335601")
FB_PAGE_TOKEN         = os.environ.get("FB_PAGE_TOKEN", "")
IG_ACCOUNT_ID         = os.environ.get("IG_ACCOUNT_ID", "17841447648424267")
IMGBB_API_KEY         = os.environ.get("IMGBB_API_KEY", "")
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY    = os.environ.get("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")
THREADS_ACCESS_TOKEN  = os.environ.get("THREADS_ACCESS_TOKEN", "")
YT_CLIENT_ID          = os.environ.get("YOUTUBE_CLIENT_ID", "")
YT_CLIENT_SECRET      = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YT_REFRESH_TOKEN      = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

FONT_SERIF      = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_SERIF_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
FONT_SANS       = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
WATERMARK       = "LaBible.app"
MINI_APP_URL    = "https://t.me/BIBLE_APP_BOT/labible"
APP_URL         = "https://labible.app"

# \u2500\u2500 Programme Semaine Sainte 2026 \u2500\u2500
HOLY_WEEK = {
    "2026-03-29": {
        "theme":   "Dimanche des Rameaux",
        "emoji":   "\ud83c\udf3f",
        "tag":     "#DimancheDesRameaux",
        "verse":   "Et ceux qui pr\u00e9c\u00e9daient et ceux qui suivaient criaient : Hosanna ! B\u00e9ni soit celui qui vient au nom du Seigneur !",
        "ref":     "Marc 11:9",
        "palette": "bordeaux",
        "deco":    "branches",
    },
    "2026-03-30": {
        "theme":   "Lundi Saint \u2014 Le Temple purifi\u00e9",
        "emoji":   "\ud83d\udd4a\ufe0f",
        "tag":     "#SemaineSainte",
        "verse":   "Il leur dit : Il est \u00e9crit : Ma maison sera appel\u00e9e une maison de pri\u00e8re. Mais vous, vous en faites une caverne de voleurs.",
        "ref":     "Matthieu 21:13",
        "palette": "bordeaux",
        "deco":    "temple",
    },
    "2026-03-31": {
        "theme":   "Mardi Saint \u2014 Les derniers enseignements",
        "emoji":   "\u271d\ufe0f",
        "tag":     "#SemaineSainte",
        "verse":   "J\u00e9sus lui dit : Je suis le chemin, la v\u00e9rit\u00e9, et la vie. Nul ne vient au P\u00e8re que par moi.",
        "ref":     "Jean 14:6",
        "palette": "bordeaux",
        "deco":    "path",
    },
    "2026-04-01": {
        "theme":   "Mercredi Saint \u2014 Le Lavement des Pieds",
        "emoji":   "\ud83d\ude4f",
        "tag":     "#SemaineSainte",
        "verse":   "Si donc je vous ai lav\u00e9 les pieds, moi, le Seigneur et le Ma\u00eetre, vous devez aussi vous laver les pieds les uns aux autres.",
        "ref":     "Jean 13:14",
        "palette": "sombre",
        "deco":    "washing",
    },
    "2026-04-02": {
        "theme":   "Jeudi Saint \u2014 La C\u00e8ne",
        "emoji":   "\ud83c\udf5e",
        "tag":     "#JeudiSaint",
        "verse":   "Il prit du pain ; et, apr\u00e8s avoir rendu gr\u00e2ces, il le rompit, et le leur donna, en disant : Ceci est mon corps, qui est donn\u00e9 pour vous.",
        "ref":     "Luc 22:19",
        "palette": "or",
        "deco":    "bread_cup",
    },
    "2026-04-03": {
        "theme":   "Vendredi Saint \u2014 La Crucifixion",
        "emoji":   "\u26ea",
        "tag":     "#VendrediSaint",
        "verse":   "Car Dieu a tant aim\u00e9 le monde qu'il a donn\u00e9 son Fils unique, afin que quiconque croit en lui ne p\u00e9risse point, mais qu'il ait la vie \u00e9ternelle.",
        "ref":     "Jean 3:16",
        "palette": "sombre",
        "deco":    "calvary",
    },
    "2026-04-04": {
        "theme":   "Samedi Saint",
        "emoji":   "\ud83d\ude4f",
        "tag":     "#SamediSaint",
        "verse":   "Tu ne laisseras pas mon \u00e2me au s\u00e9jour des morts, tu ne permettras pas que ton bien-aim\u00e9 voie la corruption.",
        "ref":     "Psaume 16:10",
        "palette": "violet",
        "deco":    "tomb_closed",
    },
    "2026-04-05": {
        "theme":   "P\u00e2ques \u2014 Il est Ressuscit\u00e9 !",
        "emoji":   "\ud83c\udf05",
        "tag":     "#Paques #Resurrection",
        "verse":   "Il n'est point ici, mais il est ressuscit\u00e9. Souvenez-vous de quelle mani\u00e8re il vous a parl\u00e9, lorsqu'il \u00e9tait encore en Galil\u00e9e.",
        "ref":     "Luc 24:6",
        "palette": "lumiere",
        "deco":    "tomb_rays",
    },
}

PALETTES_HW = {
    "bordeaux": {"bg": (28,4,8),    "bg2": (16,2,5),   "border": (180,130,60), "text": (240,225,195), "accent": (200,150,70)},
    "sombre":   {"bg": (8,8,14),    "bg2": (4,4,8),    "border": (120,100,60), "text": (220,210,190), "accent": (150,120,60)},
    "or":       {"bg": (20,14,4),   "bg2": (12,8,2),   "border": (210,175,80), "text": (255,245,220), "accent": (220,185,90)},
    "lumiere":  {"bg": (10,20,40),  "bg2": (6,12,25),  "border": (200,175,100),"text": (255,250,230), "accent": (210,185,110)},
    "violet":   {"bg": (18,8,30),   "bg2": (10,4,18),  "border": (160,120,200),"text": (235,225,255), "accent": (180,140,220)},
}


# \u2500\u2500 \u00c9l\u00e9ments d\u00e9coratifs \u2500\u2500

def draw_cross(draw, cx, cy, size, color, alpha=22):
    thick = max(2, size//8)
    arm_v = int(size*1.4)
    arm_h = size
    horiz_y = cy - arm_v//4
    draw.rectangle([cx-thick, cy-arm_v//2, cx+thick, cy+arm_v//2], fill=(*color, alpha))
    draw.rectangle([cx-arm_h//2, horiz_y-thick, cx+arm_h//2, horiz_y+thick], fill=(*color, alpha))

def draw_branch(draw, x, y, length, angle, color, alpha=20, depth=4):
    if depth == 0 or length < 8: return
    end_x = x + int(length * math.cos(math.radians(angle)))
    end_y = y - int(length * math.sin(math.radians(angle)))
    draw.line([(x,y),(end_x,end_y)], fill=(*color, alpha), width=max(1, depth-1))
    for sub_angle, factor in [(-38, 0.5), (38, 0.5), (0, 0.68)]:
        draw_branch(draw, end_x, end_y, length*factor, angle+sub_angle, color, alpha, depth-1)

def draw_tomb_open(draw, cx, cy, size, color, alpha=22):
    bbox = [cx-size, cy-size, cx+size, cy+int(size*0.3)]
    draw.arc(bbox, start=180, end=0, fill=(*color, alpha), width=3)
    draw.line([(cx-size, cy-size//2),(cx-size, cy+size//2)], fill=(*color, alpha), width=3)
    draw.line([(cx+size, cy-size//2),(cx+size, cy+size//2)], fill=(*color, alpha), width=3)
    draw.line([(cx-size-15, cy+size//2),(cx+size+15+size//2, cy+size//2)], fill=(*color, alpha), width=2)
    r = size//2
    draw.ellipse([cx+size+8, cy-r//2, cx+size+8+r, cy+r//2], outline=(*color, alpha), width=2)

def draw_rays(draw, cx, cy, size, color, alpha=18):
    for angle in range(0, 360, 25):
        rad = math.radians(angle)
        x1 = cx + int(size*0.28 * math.cos(rad))
        y1 = cy + int(size*0.28 * math.sin(rad))
        x2 = cx + int(size * math.cos(rad))
        y2 = cy + int(size * math.sin(rad))
        draw.line([(x1,y1),(x2,y2)], fill=(*color, alpha), width=2)

def draw_temple(draw, W, H, color, alpha=18):
    """Silhouette subtile du temple \u2014 colonnes et arche"""
    cx, base_y = W//2, H - 80
    col_w, col_h = 28, 320
    gap = 100
    for offset in [-gap*1.5, -gap*0.5, gap*0.5, gap*1.5]:
        x = int(cx + offset)
        draw.rectangle([x-col_w//2, base_y-col_h, x+col_w//2, base_y], fill=(*color, alpha))
        # chapiteau
        draw.rectangle([x-col_w, base_y-col_h, x+col_w, base_y-col_h+18], fill=(*color, alpha))
    # entablement
    draw.rectangle([cx-int(gap*2.2), base_y-col_h-10, cx+int(gap*2.2), base_y-col_h+8], fill=(*color, alpha))
    # arche centrale
    arch_w = int(gap*0.9)
    arch_bbox = [cx-arch_w, base_y-col_h-arch_w, cx+arch_w, base_y-col_h+arch_w//2]
    draw.arc(arch_bbox, start=180, end=0, fill=(*color, alpha), width=4)
    # escaliers
    for i in range(4):
        step_w = int(gap*2.2) + i*30
        draw.rectangle([cx-step_w, base_y+i*14, cx+step_w, base_y+(i+1)*14], fill=(*color, alpha-4))

def draw_path(draw, W, H, color, alpha=18):
    """Route en perspective convergeant vers un point de fuite"""
    vp_x, vp_y = W//2, H//3  # point de fuite
    # Bords de la route
    for side in [-1, 1]:
        base_x = W//2 + side * W//2
        draw.line([(base_x, H), (vp_x, vp_y)], fill=(*color, alpha), width=3)
    # Lignes de perspective (pointill\u00e9s)
    for i in range(1, 8):
        t = i / 8
        y = int(vp_y + t * (H - vp_y))
        half_w = int(t * W//2 * 0.85)
        draw.line([(vp_x - half_w, y), (vp_x + half_w, y)], fill=(*color, alpha-6), width=1)
    # Arbres stylis\u00e9s sur les c\u00f4t\u00e9s
    for side in [-1, 1]:
        for i in range(2, 6):
            t = i / 7
            tx = int(vp_x + side * t * W * 0.42)
            ty = int(vp_y + t * (H - vp_y))
            th = int(t * 80)
            draw.line([(tx, ty), (tx, ty-th)], fill=(*color, alpha-4), width=max(1, int(t*3)))
            draw.ellipse([tx-int(th*0.4), ty-th-int(th*0.5), tx+int(th*0.4), ty-th+int(th*0.3)],
                         fill=(*color, alpha-8))
    # Croix au point de fuite
    draw_cross(draw, vp_x, vp_y - 60, 40, color, alpha-4)

def draw_washing(draw, W, H, color, alpha=18):
    """Deux mains et eau qui coule \u2014 lavement des pieds"""
    cx, cy = W//2, H//2 + 80
    # Main gauche (qui verse l'eau)
    hw, hh = 55, 90
    lx = cx - 140
    draw.rounded_rectangle([lx-hw//2, cy-hh, lx+hw//2, cy], radius=20,
                             outline=(*color, alpha), width=3)
    # Doigts main gauche
    for i in range(4):
        fx = lx - hw//2 + 12 + i*13
        draw.rounded_rectangle([fx, cy-hh-35, fx+9, cy-hh+5], radius=5,
                                 outline=(*color, alpha-4), width=2)
    # Main droite (pied / main re\u00e7oit)
    rx = cx + 120
    draw.rounded_rectangle([rx-hw//2, cy-hh//2, rx+hw//2, cy+hh//2], radius=20,
                             outline=(*color, alpha), width=3)
    # Doigts main droite
    for i in range(4):
        fx = rx - hw//2 + 8 + i*13
        draw.rounded_rectangle([fx-5, cy+hh//2-5, fx+5, cy+hh//2+30], radius=5,
                                 outline=(*color, alpha-4), width=2)
    # Gouttes d'eau entre les deux mains
    for i, (dx, dy) in enumerate([(cx-60, cy-60),(cx-30, cy-40),(cx, cy-55),(cx+30, cy-45)]):
        r = 5 + i % 3
        draw.ellipse([dx-r, dy-r*2, dx+r, dy+r], fill=(*color, alpha-6))
        draw.line([(dx, dy+r), (dx-3, dy+r+12)], fill=(*color, alpha-8), width=2)
    # Arc au-dessus
    draw.arc([cx-180, cy-200, cx+180, cy-20], start=200, end=340, fill=(*color, alpha-8), width=2)
    # Petite croix
    draw_cross(draw, cx, cy - 220, 35, color, alpha-6)

def draw_bread_cup(draw, W, H, color, alpha=18):
    """Pain rompu et calice \u2014 La C\u00e8ne"""
    cx, cy = W//2, H//2 + 60
    # Calice
    cup_w, cup_h = 80, 120
    # Tige
    draw.line([(cx, cy-cup_h//2), (cx, cy+cup_h//2)], fill=(*color, alpha), width=6)
    # Base
    draw.rounded_rectangle([cx-cup_w//2, cy+cup_h//2-8, cx+cup_w//2, cy+cup_h//2+8],
                             radius=4, fill=(*color, alpha))
    # Coupe
    draw.arc([cx-cup_w, cy-cup_h, cx+cup_w, cy-cup_h//4],
             start=200, end=340, fill=(*color, alpha), width=4)
    draw.line([(cx-cup_w, cy-cup_h*3//4), (cx-cup_w//2, cy-cup_h//4)],
              fill=(*color, alpha), width=4)
    draw.line([(cx+cup_w, cy-cup_h*3//4), (cx+cup_w//2, cy-cup_h//4)],
              fill=(*color, alpha), width=4)
    # Pain \u00e0 gauche
    bx, by = cx - 200, cy - 20
    draw.rounded_rectangle([bx-70, by-35, bx+70, by+35], radius=25,
                             outline=(*color, alpha), width=3)
    # Ligne de rupture du pain
    draw.line([(bx-20, by-35), (bx+10, by+35)], fill=(*color, alpha-4), width=3)
    # Miettes
    for mx, my in [(bx-30, by+45),(bx+10, by+50),(bx+40, by+42),(bx-50, by+48)]:
        draw.ellipse([mx-3, my-3, mx+3, my+3], fill=(*color, alpha-8))
    # Rayons autour du calice
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        r1, r2 = 50, 85
        x1 = cx + int(r1 * math.cos(rad))
        y1 = (cy - cup_h//2) + int(r1 * math.sin(rad))
        x2 = cx + int(r2 * math.cos(rad))
        y2 = (cy - cup_h//2) + int(r2 * math.sin(rad))
        draw.line([(x1,y1),(x2,y2)], fill=(*color, alpha-10), width=1)

def draw_calvary(draw, W, H, color, alpha=18):
    """Trois croix sur la colline du Calvaire"""
    cx, ground_y = W//2, H - 120
    # Colline
    hill_pts = []
    hill_w = W * 0.55
    for i in range(60):
        t = i / 59
        x = int(cx - hill_w//2 + t * hill_w)
        y = int(ground_y - math.sin(t * math.pi) * 220)
        hill_pts.append((x, y))
    hill_pts += [(cx + int(hill_w//2), H), (cx - int(hill_w//2), H)]
    draw.polygon(hill_pts, fill=(*color, alpha-10))
    # Contour colline
    for i in range(len(hill_pts)-3):
        draw.line([hill_pts[i], hill_pts[i+1]], fill=(*color, alpha-4), width=2)

    # Trois croix
    cross_positions = [(cx, ground_y - 200), (cx-180, ground_y-120), (cx+180, ground_y-120)]
    cross_sizes = [90, 65, 65]
    for (ccx, ccy), csz in zip(cross_positions, cross_sizes):
        thick = max(3, csz//8)
        arm_v = int(csz * 1.4)
        arm_h = csz
        horiz_y = ccy - arm_v//4
        draw.rectangle([ccx-thick, ccy-arm_v//2, ccx+thick, ccy+arm_v//2],
                        fill=(*color, alpha))
        draw.rectangle([ccx-arm_h//2, horiz_y-thick, ccx+arm_h//2, horiz_y+thick],
                        fill=(*color, alpha))
    # Nuages sombres
    for cx2, cy2, r in [(W//4, 120, 60), (W*3//4, 100, 50), (W//2, 80, 45)]:
        draw.ellipse([cx2-r, cy2-r//2, cx2+r, cy2+r//2], fill=(*color, alpha-10))

def draw_tomb_closed(draw, W, H, color, alpha=18):
    """Tombeau ferm\u00e9 \u2014 pierre ronde devant l'entr\u00e9e"""
    cx, cy = W//2, H//2 + 100
    # Sol rocheux
    draw.rectangle([cx-300, cy+80, cx+300, cy+180], fill=(*color, alpha-10))
    for i in range(-280, 280, 60):
        draw.line([(cx+i, cy+80), (cx+i+30, cy+180)], fill=(*color, alpha-12), width=1)
    # Entr\u00e9e du tombeau (arche taill\u00e9e dans le roc)
    arch_w, arch_h = 160, 180
    draw.rectangle([cx-arch_w, cy-arch_h//2, cx+arch_w, cy+80], fill=(*color, alpha-6))
    draw.arc([cx-arch_w, cy-arch_h, cx+arch_w, cy-arch_h//2+arch_h],
             start=180, end=0, fill=(*color, alpha), width=4)
    draw.line([(cx-arch_w, cy-arch_h//2), (cx-arch_w, cy+80)], fill=(*color, alpha), width=4)
    draw.line([(cx+arch_w, cy-arch_h//2), (cx+arch_w, cy+80)], fill=(*color, alpha), width=4)
    # Pierre ronde fermant le tombeau
    stone_r = 110
    stone_cx = cx + arch_w - stone_r//2
    stone_cy = cy + 10
    draw.ellipse([stone_cx-stone_r, stone_cy-stone_r, stone_cx+stone_r, stone_cy+stone_r],
                 fill=(*color, alpha+5), outline=(*color, alpha+10), width=4)
    # Texture pierre
    for angle in range(20, 180, 40):
        rad = math.radians(angle)
        draw.arc([stone_cx-stone_r+15, stone_cy-stone_r+15,
                  stone_cx+stone_r-15, stone_cy+stone_r-15],
                 start=angle, end=angle+25, fill=(*color, alpha-8), width=2)
    # \u00c9toiles dans le ciel (nuit du samedi)
    for sx, sy in [(cx-250, 80),(cx-150, 50),(cx+100, 60),(cx+220, 90),(cx-50, 40),(cx+160, 45)]:
        r = 3
        draw.ellipse([sx-r, sy-r, sx+r, sy+r], fill=(*color, alpha))
    # Croix discr\u00e8te au loin
    draw_cross(draw, cx - 280, cy - 100, 30, color, alpha-8)


def add_decorations(layer, deco_type, W, H, accent, alpha_base=22):
    d = ImageDraw.Draw(layer)
    if deco_type == "branches":
        draw_branch(d, 80, H-80, 220, 65, accent, alpha_base, 4)
        draw_branch(d, W-80, H-80, 220, 115, accent, alpha_base, 4)
        draw_branch(d, W//2, H-60, 180, 90, accent, alpha_base-5, 3)
        draw_cross(d, W//2, 120, 50, accent, alpha_base-5)
    elif deco_type == "temple":
        draw_temple(d, W, H, accent, alpha_base)
        draw_cross(d, W//2, 100, 40, accent, alpha_base-6)
    elif deco_type == "path":
        draw_path(d, W, H, accent, alpha_base)
    elif deco_type == "washing":
        draw_washing(d, W, H, accent, alpha_base)
    elif deco_type == "bread_cup":
        draw_bread_cup(d, W, H, accent, alpha_base)
    elif deco_type == "calvary":
        draw_calvary(d, W, H, accent, alpha_base)
    elif deco_type == "tomb_closed":
        draw_tomb_closed(d, W, H, accent, alpha_base)
    elif deco_type == "tomb_rays":
        draw_tomb_open(d, W//4, H*3//4, 80, accent, alpha_base)
        draw_rays(d, W*2//3, H//3, 200, accent, alpha_base-5)
        draw_cross(d, W*3//4, H//4, 60, accent, alpha_base-8)


# \u2500\u2500 Helpers texte \u2500\u2500
def wrap_text(draw, text, font, max_w):
    words = text.split()
    if not words: return [""]
    lines, current = [], words[0]
    for w in words[1:]:
        test = current + " " + w
        if draw.textlength(test, font=font) <= max_w:
            current = test
        else:
            lines.append(current)
            current = w
    lines.append(current)
    if len(lines) >= 2 and len(lines[-1].strip()) <= 2:
        lines[-2] += " " + lines.pop()
    return lines

def wrap_text_with_quotes(draw, text, font, max_w):
    words = text.split()
    if not words: return [""]
    q_open = draw.textlength("\u00ab ", font=font)
    lines, current = [], words[0]
    for w in words[1:]:
        test = current + " " + w
        margin = q_open if len(lines) == 0 else 0
        if draw.textlength(test, font=font) + margin <= max_w:
            current = test
        else:
            lines.append(current)
            current = w
    lines.append(current)
    if lines:
        lines[0]  = "\u00ab " + lines[0]
        lines[-1] = lines[-1] + " \u00bb"
    return lines


# \u2500\u2500 G\u00e9n\u00e9ration image 1080\u00d71080 \u2500\u2500
def make_holy_week_image(day_data):
    pal = PALETTES_HW[day_data["palette"]]
    BG, BG2, BORDER, TEXT, ACCENT = pal["bg"], pal["bg2"], pal["border"], pal["text"], pal["accent"]
    W, H = 1080, 1080

    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y/H
        c = tuple(int(BG[i] + t*(BG2[i]-BG[i])) for i in range(3))
        draw.line([(0,y),(W,y)], fill=c)

    deco_layer = Image.new("RGBA", (W, H), (0,0,0,0))
    add_decorations(deco_layer, day_data["deco"], W, H, ACCENT, 22)
    img = Image.alpha_composite(img.convert("RGBA"), deco_layer).convert("RGB")
    draw = ImageDraw.Draw(img)

    m = 55
    draw.rounded_rectangle([m,m,W-m,H-m], radius=32, outline=BORDER, width=6)
    draw.rounded_rectangle([m+14,m+14,W-m-14,H-m-14], radius=26, outline=(*BORDER,80), width=1)
    draw.line([(m+40,m+40),(W-m-40,m+40)], fill=BORDER, width=1)

    font_theme = ImageFont.truetype(FONT_SANS, 22)
    theme_text = day_data["emoji"] + "  " + day_data["theme"].upper()
    tw = draw.textlength(theme_text, font=font_theme)
    draw.text(((W-tw)//2, m+52), theme_text, font=font_theme, fill=ACCENT)
    draw.line([(m+40,m+88),(W-m-40,m+88)], fill=(*BORDER,100), width=1)

    pad_x, top, bottom = 130, 200, 300
    max_w, max_h = W-2*pad_x, H-top-bottom

    chosen_font = chosen_lines = chosen_lh = None
    for size in range(62, 30, -2):
        font = ImageFont.truetype(FONT_SERIF, size)
        lines = wrap_text(draw, day_data["verse"], font, max_w)
        lh = int(size*1.42)
        if lh*len(lines) <= max_h:
            chosen_font, chosen_lines, chosen_lh = font, lines, lh
            break
    if chosen_font is None:
        chosen_font = ImageFont.truetype(FONT_SERIF, 30)
        chosen_lines = wrap_text(draw, day_data["verse"], chosen_font, max_w)
        chosen_lh = int(30*1.42)

    if chosen_lines:
        chosen_lines[0]  = "\u00ab " + chosen_lines[0]
        chosen_lines[-1] = chosen_lines[-1] + " \u00bb"

    total_h = chosen_lh * len(chosen_lines)
    y = top + max(0, (max_h-total_h)//2)
    for line in chosen_lines:
        lw = draw.textlength(line, font=chosen_font)
        x = (W-lw)//2
        draw.text((x+2,y+2), line, font=chosen_font, fill=(0,0,0))
        draw.text((x,y),     line, font=chosen_font, fill=TEXT)
        y += chosen_lh

    draw.line([(pad_x,H-260),(W-pad_x,H-260)], fill=BORDER, width=2)
    font_ref = ImageFont.truetype(FONT_SERIF_BOLD, 38)
    font_sub = ImageFont.truetype(FONT_SANS, 26)
    rw = draw.textlength(day_data["ref"], font=font_ref)
    draw.text(((W-rw)//2, H-238), day_data["ref"], font