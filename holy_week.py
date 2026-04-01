"""
holy_week.py — Publications spéciales Semaine Sainte 2026
Publie images + reels en extra (en plus des publications normales)
"""
import os, json, datetime, hashlib, math, subprocess, requests, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ── Secrets ──
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

# ── Programme Semaine Sainte 2026 ──
HOLY_WEEK = {
    "2026-03-29": {
        "theme":   "Dimanche des Rameaux",
        "emoji":   "🌿",
        "tag":     "#DimancheDesRameaux",
        "verse":   "Et ceux qui précédaient et ceux qui suivaient criaient : Hosanna ! Béni soit celui qui vient au nom du Seigneur !",
        "ref":     "Marc 11:9",
        "palette": "bordeaux",
        "deco":    "branches",
    },
    "2026-03-30": {
        "theme":   "Lundi Saint — Le Temple purifié",
        "emoji":   "🕊️",
        "tag":     "#SemaineSainte",
        "verse":   "Il leur dit : Il est écrit : Ma maison sera appelée une maison de prière. Mais vous, vous en faites une caverne de voleurs.",
        "ref":     "Matthieu 21:13",
        "palette": "bordeaux",
        "deco":    "temple",
    },
    "2026-03-31": {
        "theme":   "Mardi Saint — Les derniers enseignements",
        "emoji":   "✝️",
        "tag":     "#SemaineSainte",
        "verse":   "Jésus lui dit : Je suis le chemin, la vérité, et la vie. Nul ne vient au Père que par moi.",
        "ref":     "Jean 14:6",
        "palette": "bordeaux",
        "deco":    "path",
    },
    "2026-04-01": {
        "theme":   "Mercredi Saint — Le Lavement des Pieds",
        "emoji":   "🙏",
        "tag":     "#SemaineSainte",
        "verse":   "Si donc je vous ai lavé les pieds, moi, le Seigneur et le Maître, vous devez aussi vous laver les pieds les uns aux autres.",
        "ref":     "Jean 13:14",
        "palette": "sombre",
        "deco":    "washing",
    },
    "2026-04-02": {
        "theme":   "Jeudi Saint — La Cène",
        "emoji":   "🍞",
        "tag":     "#JeudiSaint",
        "verse":   "Il prit du pain ; et, après avoir rendu grâces, il le rompit, et le leur donna, en disant : Ceci est mon corps, qui est donné pour vous.",
        "ref":     "Luc 22:19",
        "palette": "or",
        "deco":    "bread_cup",
    },
    "2026-04-03": {
        "theme":   "Vendredi Saint — La Crucifixion",
        "emoji":   "⛪",
        "tag":     "#VendrediSaint",
        "verse":   "Car Dieu a tant aimé le monde qu'il a donné son Fils unique, afin que quiconque croit en lui ne périsse point, mais qu'il ait la vie éternelle.",
        "ref":     "Jean 3:16",
        "palette": "sombre",
        "deco":    "calvary",
    },
    "2026-04-04": {
        "theme":   "Samedi Saint",
        "emoji":   "🙏",
        "tag":     "#SamediSaint",
        "verse":   "Tu ne laisseras pas mon âme au séjour des morts, tu ne permettras pas que ton bien-aimé voie la corruption.",
        "ref":     "Psaume 16:10",
        "palette": "violet",
        "deco":    "tomb_closed",
    },
    "2026-04-05": {
        "theme":   "Pâques — Il est Ressuscité !",
        "emoji":   "🌅",
        "tag":     "#Paques #Resurrection",
        "verse":   "Il n'est point ici, mais il est ressuscité. Souvenez-vous de quelle manière il vous a parlé, lorsqu'il était encore en Galilée.",
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


# ── Éléments décoratifs ──

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
    """Silhouette subtile du temple — colonnes et arche"""
    cx, base_y = W//2, H - 80
    col_w, col_h = 28, 320
    gap = 100
    for offset in [-gap*1.5, -gap*0.5, gap*0.5, gap*1.5]:
        x = int(cx + offset)
        draw.rectangle([x-col_w//2, base_y-col_h, x+col_w//2, base_y], fill=(*color, alpha))
        draw.rectangle([x-col_w, base_y-col_h, x+col_w, base_y-col_h+18], fill=(*color, alpha))
    draw.rectangle([cx-int(gap*2.2), base_y-col_h-10, cx+int(gap*2.2), base_y-col_h+8], fill=(*color, alpha))
    arch_w = int(gap*0.9)
    arch_bbox = [cx-arch_w, base_y-col_h-arch_w, cx+arch_w, base_y-col_h+arch_w//2]
    draw.arc(arch_bbox, start=180, end=0, fill=(*color, alpha), width=4)
    for i in range(4):
        step_w = int(gap*2.2) + i*30
        draw.rectangle([cx-step_w, base_y+i*14, cx+step_w, base_y+(i+1)*14], fill=(*color, alpha-4))

def draw_path(draw, W, H, color, alpha=18):
    """Route en perspective convergeant vers un point de fuite"""
    vp_x, vp_y = W//2, H//3
    for side in [-1, 1]:
        base_x = W//2 + side * W//2
        draw.line([(base_x, H), (vp_x, vp_y)], fill=(*color, alpha), width=3)
    for i in range(1, 8):
        t = i / 8
        y = int(vp_y + t * (H - vp_y))
        half_w = int(t * W//2 * 0.85)
        draw.line([(vp_x - half_w, y), (vp_x + half_w, y)], fill=(*color, alpha-6), width=1)
    for side in [-1, 1]:
        for i in range(2, 6):
            t = i / 7
            tx = int(vp_x + side * t * W * 0.42)
            ty = int(vp_y + t * (H - vp_y))
            th = int(t * 80)
            draw.line([(tx, ty), (tx, ty-th)], fill=(*color, alpha-4), width=max(1, int(t*3)))
            draw.ellipse([tx-int(th*0.4), ty-th-int(th*0.5), tx+int(th*0.4), ty-th+int(th*0.3)],
                         fill=(*color, alpha-8))
    draw_cross(draw, vp_x, vp_y - 60, 40, color, alpha-4)

def draw_washing(draw, W, H, color, alpha=18):
    """Deux mains et eau qui coule"""
    cx, cy = W//2, H//2 + 80
    hw, hh = 55, 90
    lx = cx - 140
    draw.rounded_rectangle([lx-hw//2, cy-hh, lx+hw//2, cy], radius=20,
                             outline=(*color, alpha), width=3)
    for i in range(4):
        fx = lx - hw//2 + 12 + i*13
        draw.rounded_rectangle([fx, cy-hh-35, fx+9, cy-hh+5], radius=5,
                                 outline=(*color, alpha-4), width=2)
    rx = cx + 120
    draw.rounded_rectangle([rx-hw//2, cy-hh//2, rx+hw//2, cy+hh//2], radius=20,
                             outline=(*color, alpha), width=3)
    for i in range(4):
        fx = rx - hw//2 + 8 + i*13
        draw.rounded_rectangle([fx-5, cy+hh//2-5, fx+5, cy+hh//2+30], radius=5,
                                 outline=(*color, alpha-4), width=2)
    for i, (dx, dy) in enumerate([(cx-60, cy-60),(cx-30, cy-40),(cx, cy-55),(cx+30, cy-45)]):
        r = 5 + i % 3
        draw.ellipse([dx-r, dy-r*2, dx+r, dy+r], fill=(*color, alpha-6))
        draw.line([(dx, dy+r), (dx-3, dy+r+12)], fill=(*color, alpha-8), width=2)
    draw.arc([cx-180, cy-200, cx+180, cy-20], start=200, end=340, fill=(*color, alpha-8), width=2)
    draw_cross(draw, cx, cy - 220, 35, color, alpha-6)

def draw_bread_cup(draw, W, H, color, alpha=18):
    """Pain rompu et calice"""
    cx, cy = W//2, H//2 + 60
    cup_w, cup_h = 80, 120
    draw.line([(cx, cy-cup_h//2), (cx, cy+cup_h//2)], fill=(*color, alpha), width=6)
    draw.rounded_rectangle([cx-cup_w//2, cy+cup_h//2-8, cx+cup_w//2, cy+cup_h//2+8],
                             radius=4, fill=(*color, alpha))
    draw.arc([cx-cup_w, cy-cup_h, cx+cup_w, cy-cup_h//4],
             start=200, end=340, fill=(*color, alpha), width=4)
    draw.line([(cx-cup_w, cy-cup_h*3//4), (cx-cup_w//2, cy-cup_h//4)], fill=(*color, alpha), width=4)
    draw.line([(cx+cup_w, cy-cup_h*3//4), (cx+cup_w//2, cy-cup_h//4)], fill=(*color, alpha), width=4)
    bx, by = cx - 200, cy - 20
    draw.rounded_rectangle([bx-70, by-35, bx+70, by+35], radius=25,
                             outline=(*color, alpha), width=3)
    draw.line([(bx-20, by-35), (bx+10, by+35)], fill=(*color, alpha-4), width=3)
    for mx, my in [(bx-30, by+45),(bx+10, by+50),(bx+40, by+42),(bx-50, by+48)]:
        draw.ellipse([mx-3, my-3, mx+3, my+3], fill=(*color, alpha-8))
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        r1, r2 = 50, 85
        x1 = cx + int(r1 * math.cos(rad)); y1 = (cy - cup_h//2) + int(r1 * math.sin(rad))
        x2 = cx + int(r2 * math.cos(rad)); y2 = (cy - cup_h//2) + int(r2 * math.sin(rad))
        draw.line([(x1,y1),(x2,y2)], fill=(*color, alpha-10), width=1)

def draw_calvary(draw, W, H, color, alpha=18):
    """Trois croix sur la colline du Calvaire"""
    cx, ground_y = W//2, H - 120
    hill_pts = []
    hill_w = W * 0.55
    for i in range(60):
        t = i / 59
        x = int(cx - hill_w//2 + t * hill_w)
        y = int(ground_y - math.sin(t * math.pi) * 220)
        hill_pts.append((x, y))
    hill_pts += [(cx + int(hill_w//2), H), (cx - int(hill_w//2), H)]
    draw.polygon(hill_pts, fill=(*color, alpha-10))
    for i in range(len(hill_pts)-3):
        draw.line([hill_pts[i], hill_pts[i+1]], fill=(*color, alpha-4), width=2)
    cross_positions = [(cx, ground_y - 200), (cx-180, ground_y-120), (cx+180, ground_y-120)]
    cross_sizes = [90, 65, 65]
    for (ccx, ccy), csz in zip(cross_positions, cross_sizes):
        thick = max(3, csz//8)
        arm_v = int(csz * 1.4)
        arm_h = csz
        horiz_y = ccy - arm_v//4
        draw.rectangle([ccx-thick, ccy-arm_v//2, ccx+thick, ccy+arm_v//2], fill=(*color, alpha))
        draw.rectangle([ccx-arm_h//2, horiz_y-thick, ccx+arm_h//2, horiz_y+thick], fill=(*color, alpha))
    for cx2, cy2, r in [(W//4, 120, 60), (W*3//4, 100, 50), (W//2, 80, 45)]:
        draw.ellipse([cx2-r, cy2-r//2, cx2+r, cy2+r//2], fill=(*color, alpha-10))

def draw_tomb_closed(draw, W, H, color, alpha=18):
    """Tombeau fermé — pierre ronde devant l'entrée"""
    cx, cy = W//2, H//2 + 100
    draw.rectangle([cx-300, cy+80, cx+300, cy+180], fill=(*color, alpha-10))
    for i in range(-280, 280, 60):
        draw.line([(cx+i, cy+80), (cx+i+30, cy+180)], fill=(*color, alpha-12), width=1)
    arch_w, arch_h = 160, 180
    draw.rectangle([cx-arch_w, cy-arch_h//2, cx+arch_w, cy+80], fill=(*color, alpha-6))
    draw.arc([cx-arch_w, cy-arch_h, cx+arch_w, cy-arch_h//2+arch_h],
             start=180, end=0, fill=(*color, alpha), width=4)
    draw.line([(cx-arch_w, cy-arch_h//2), (cx-arch_w, cy+80)], fill=(*color, alpha), width=4)
    draw.line([(cx+arch_w, cy-arch_h//2), (cx+arch_w, cy+80)], fill=(*color, alpha), width=4)
    stone_r = 110
    stone_cx = cx + arch_w - stone_r//2
    stone_cy = cy + 10
    draw.ellipse([stone_cx-stone_r, stone_cy-stone_r, stone_cx+stone_r, stone_cy+stone_r],
                 fill=(*color, alpha+5), outline=(*color, alpha+10), width=4)
    for angle in range(20, 180, 40):
        draw.arc([stone_cx-stone_r+15, stone_cy-stone_r+15,
                  stone_cx+stone_r-15, stone_cy+stone_r-15],
                 start=angle, end=angle+25, fill=(*color, alpha-8), width=2)
    for sx, sy in [(cx-250, 80),(cx-150, 50),(cx+100, 60),(cx+220, 90),(cx-50, 40),(cx+160, 45)]:
        r = 3
        draw.ellipse([sx-r, sy-r, sx+r, sy+r], fill=(*color, alpha))
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


# ── Helpers texte ──
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
    q_open = draw.textlength("« ", font=font)
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
        lines[0]  = "« " + lines[0]
        lines[-1] = lines[-1] + " »"
    return lines


# ── Génération image 1080×1080 ──
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
        chosen_lines[0]  = "« " + chosen_lines[0]
        chosen_lines[-1] = chosen_lines[-1] + " »"

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
    draw.text(((W-rw)//2, H-238), day_data["ref"], font=font_ref, fill=ACCENT)
    ww = draw.textlength(WATERMARK, font=font_sub)
    draw.text(((W-ww)//2, H-192), WATERMARK, font=font_sub, fill=ACCENT)

    out = "holy_week.png"
    img.save(out, "PNG")
    return out


# ── Génération reel 1080×1920 ──
def make_holy_week_reel(day_data, music_dir="music"):
    pal = PALETTES_HW[day_data["palette"]]
    BG, BG2, BORDER, TEXT, ACCENT = pal["bg"], pal["bg2"], pal["border"], pal["text"], pal["accent"]
    W, H = 1080, 1920
    FPS = 30; DURATION = 15; TOTAL = FPS * DURATION

    def blend(base, a, bg=BG):
        a = max(0,min(1,a))
        return tuple(int(bg[i]+(base[i]-bg[i])*a) for i in range(3))
    def ease(t): t=max(0,min(1,t)); return t*t*(3-2*t)

    tmp = Image.new("RGB",(10,10)); d = ImageDraw.Draw(tmp)
    BPAD = 100; CPAD = 100; MAX_TW = W-BPAD*2-CPAD*2
    size = 80
    while size > 30:
        fv = ImageFont.truetype(FONT_SERIF, size)
        lines = wrap_text_with_quotes(d, day_data["verse"], fv, MAX_TW)
        lh = size+22
        if lh*len(lines) <= int((H-BPAD*2)*0.52): break
        size -= 2

    fv = ImageFont.truetype(FONT_SERIF, size)
    d2 = ImageDraw.Draw(Image.new("RGB",(10,10)))
    verse_lines = wrap_text_with_quotes(d2, day_data["verse"], fv, MAX_TW)
    LINE_H = size+22

    fr = ImageFont.truetype(FONT_SERIF_BOLD, 40)
    ft = ImageFont.truetype(FONT_SANS, 28)
    fth = ImageFont.truetype(FONT_SANS, 24)

    CX1,CY1,CX2,CY2 = BPAD, BPAD, W-BPAD, H-BPAD

    rng = np.random.default_rng(99)
    N = 25
    px = rng.uniform(CX1+20, CX2-20, N)
    py = rng.uniform(CY1+20, CY2-20, N)
    ps = rng.uniform(0.2, 0.7, N)
    pr = rng.uniform(2, 5, N)
    pa = rng.uniform(0, 2*math.pi, N)

    start_y = int(CY1+(CY2-CY1)*0.44 - len(verse_lines)*LINE_H//2)
    FL = CY2-220; FT = CY2-195

    os.makedirs("hw_frames", exist_ok=True)

    for f in range(TOTAL):
        s = f/FPS
        alpha = ease(s/0.8) if s < 0.8 else (ease((DURATION-s)/1.5) if s > DURATION-1.5 else 1.0)

        img = Image.new("RGB",(W,H),BG)
        draw = ImageDraw.Draw(img)
        for y in range(0,H,4):
            t2 = y/H
            bg_y = tuple(max(0,int(BG[i]*(1-t2*0.35))) for i in range(3))
            draw.rectangle([(0,y),(W,min(y+4,H))], fill=bg_y)

        deco_layer = Image.new("RGBA",(W,H),(0,0,0,0))
        add_decorations(deco_layer, day_data["deco"], W, H, ACCENT, int(15*alpha))
        img = Image.alpha_composite(img.convert("RGBA"), deco_layer).convert("RGB")
        draw = ImageDraw.Draw(img)

        cl = Image.new("RGBA",(W,H),(0,0,0,0))
        cd = ImageDraw.Draw(cl)
        cd.rounded_rectangle([CX1,CY1,CX2,CY2], radius=40, fill=(*BG,int(alpha*230)))
        img = Image.alpha_composite(img.convert("RGBA"), cl).convert("RGB")
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([CX1,CY1,CX2,CY2], radius=40, outline=blend(BORDER,alpha), width=5)
        draw.rounded_rectangle([CX1+12,CY1+12,CX2-12,CY2-12], radius=34, outline=blend(BORDER,alpha*0.3), width=1)

        th_a = min(1.0,s/0.5)*alpha
        theme_text = day_data["emoji"] + "  " + day_data["theme"].upper()
        tw = draw.textlength(theme_text, font=fth)
        draw.text(((W-tw)//2, CY1+30), theme_text, font=fth, fill=blend(ACCENT,th_a))
        draw.line([(CX1+60,CY1+65),(CX2-60,CY1+65)], fill=blend(BORDER,th_a*0.6), width=1)

        pl = Image.new("RGBA",(W,H),(0,0,0,0))
        pd = ImageDraw.Draw(pl)
        for i in range(N):
            tp = s*ps[i]
            cx = int((px[i]+math.sin(tp*0.5+pa[i])*18)%W)
            cy = int((py[i]-s*ps[i]*10)%H)
            r  = int(pr[i])
            bright = (math.sin(tp+pa[i])+1)/2*0.3+0.1
            a_p = int(bright*alpha*80)
            gc = blend(ACCENT,bright*0.5)
            pd.ellipse([(cx-r,cy-r),(cx+r,cy+r)], fill=(*gc,a_p))
        img = Image.alpha_composite(img.convert("RGBA"), pl).convert("RGB")
        draw = ImageDraw.Draw(img)

        for i,line in enumerate(verse_lines):
            ls = 0.6+i*0.18; le = ls+0.5
            la = (0 if s<ls else (ease((s-ls)/(le-ls)) if s<le else 1.0))*alpha
            bbox = draw.textbbox((0,0),line,font=fv); tw2 = bbox[2]-bbox[0]
            x = (W-tw2)//2; y = start_y+i*LINE_H
            draw.text((x+2,y+2), line, font=fv, fill=blend((0,0,0),la*0.5))
            draw.text((x,y),     line, font=fv, fill=blend(TEXT,la))

        fs = 0.6+len(verse_lines)*0.18+0.3
        fa = (0 if s<fs else (ease((s-fs)/0.6) if s<fs+0.6 else 1.0))*alpha
        lx1=CX1+CPAD; lx2=CX2-CPAD
        draw.line([(lx1,FL),(lx2,FL)], fill=blend(BORDER,fa*0.8), width=2)
        rw = draw.textlength(day_data["ref"], font=fr)
        draw.text(((W-rw)//2,FT), day_data["ref"], font=fr, fill=blend(ACCENT,fa))
        ww = draw.textlength(WATERMARK, font=ft)
        draw.text(((W-ww)//2,FT+50), WATERMARK, font=ft, fill=blend(ACCENT,fa*0.7))

        img.save(f"hw_frames/frame_{f:04d}.png")

    import glob, random as _random
    output = "holy_reel.mp4"
    music_files = glob.glob(f"{music_dir}/*.mp3") + glob.glob(f"{music_dir}/*.m4a")
    if music_files:
        music = _random.choice(music_files)
        subprocess.run([
            'ffmpeg','-framerate','30','-i','hw_frames/frame_%04d.png',
            '-ss','2','-i', music,
            '-c:v','libx264','-profile:v','baseline','-level','3.1',
            '-pix_fmt','yuv420p','-crf','22',
            '-c:a','aac','-b:a','128k','-ar','44100',
            '-movflags','+faststart','-shortest',
            output,'-y'
        ], capture_output=True)
    else:
        subprocess.run([
            'ffmpeg','-framerate','30','-i','hw_frames/frame_%04d.png',
            '-c:v','libx264','-profile:v','baseline','-level','3.1',
            '-pix_fmt','yuv420p','-crf','22',
            '-movflags','+faststart',
            output,'-y'
        ], capture_output=True)

    shutil.rmtree("hw_frames", ignore_errors=True)
    return output


# ── Upload / Publication ──
def upload_to_cloudinary(path, resource="image"):
    import time as _t
    if not CLOUDINARY_CLOUD_NAME: return upload_to_imgbb(path)
    timestamp = str(int(_t.time()))
    sig = hashlib.sha1(f"timestamp={timestamp}{CLOUDINARY_API_SECRET.strip()}".encode()).hexdigest()
    with open(path,"rb") as f:
        r = requests.post(
            f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/{resource}/upload",
            data={"api_key":CLOUDINARY_API_KEY,"timestamp":timestamp,"signature":sig},
            files={"file":f}, timeout=180
        )
    if r.status_code == 200:
        _t.sleep(3 if resource=="image" else 5)
        return r.json()["secure_url"]
    return upload_to_imgbb(path) if resource=="image" else None

def upload_to_imgbb(path):
    if not IMGBB_API_KEY: return None
    import time
    with open(path,"rb") as f:
        r = requests.post("https://api.imgbb.com/1/upload",
                          params={"key":IMGBB_API_KEY}, files={"image":f}, timeout=60)
    if r.status_code == 200:
        time.sleep(5); return r.json()["data"]["url"]
    return None

def post_telegram_photo(path, caption):
    markup = json.dumps({"inline_keyboard":[[{"text":"📖 Lire dans LaBible.app","url":MINI_APP_URL}]]})
    with open(path,"rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                          data={"chat_id":CHANNEL,"caption":caption,"parse_mode":"HTML","reply_markup":markup},
                          files={"photo":f}, timeout=30)
    r.raise_for_status(); print("✅ Telegram image publié")

def post_telegram_video(path, caption):
    markup = json.dumps({"inline_keyboard":[[{"text":"📖 Lire dans LaBible.app","url":MINI_APP_URL}]]})
    with open(path,"rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendVideo",
                          data={"chat_id":CHANNEL,"caption":caption,"parse_mode":"HTML","reply_markup":markup},
                          files={"video":f}, timeout=60)
    r.raise_for_status(); print("✅ Telegram vidéo publié")

def post_facebook_photo(path, caption):
    if not FB_PAGE_TOKEN: return
    with open(path,"rb") as f:
        r = requests.post(f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/photos",
                          data={"message":caption,"access_token":FB_PAGE_TOKEN},
                          files={"source":f}, timeout=60)
    print(f"✅ Facebook image — {r.json().get('id','?')}" if r.status_code==200 else f"❌ Facebook ({r.status_code}): {r.text}")

def post_facebook_reel(path, caption):
    if not FB_PAGE_TOKEN: return
    with open(path,"rb") as f:
        r = requests.post(f"https://graph.facebook.com/v25.0/{FB_PAGE_ID}/videos",
                          data={"description":caption,"access_token":FB_PAGE_TOKEN},
                          files={"source":f}, timeout=120)
    print(f"✅ Facebook reel — {r.json().get('id','?')}" if r.status_code==200 else f"❌ Facebook reel ({r.status_code}): {r.text}")

def post_instagram_image(path, caption):
    if not FB_PAGE_TOKEN: return
    url = upload_to_cloudinary(path, "image")
    if not url: return
    if "cloudinary.com" in url: url = url.replace("/upload/","/upload/f_jpg/")
    r = requests.post(f"https://graph.facebook.com/v25.0/{IG_ACCOUNT_ID}/media",
                      data={"image_url":url,"caption":caption,"access_token":FB_PAGE_TOKEN}, timeout=60)
    if r.status_code!=200: print(f"❌ IG container ({r.status_code}): {r.text}"); return
    cid = r.json().get("id")
    import time
    for _ in range(8):
        time.sleep(10)
        rs = requests.get(f"https://graph.facebook.com/v25.0/{cid}",
                          params={"fields":"status_code","access_token":FB_PAGE_TOKEN}, timeout=30)
        s = rs.json().get("status_code","")
        if s=="FINISHED": break
        if s=="ERROR": print("❌ IG ERROR"); return
    r2 = requests.post(f"https://graph.facebook.com/v25.0/{IG_ACCOUNT_ID}/media_publish",
                       data={"creation_id":cid,"access_token":FB_PAGE_TOKEN}, timeout=60)
    print(f"✅ Instagram image — {r2.json().get('id','?')}" if r2.status_code==200 else f"❌ IG publish ({r2.status_code}): {r2.text}")

def post_instagram_reel(path, caption):
    if not FB_PAGE_TOKEN: return
    video_url = upload_to_cloudinary(path, "video")
    if not video_url: return
    r = requests.post(f"https://graph.facebook.com/v25.0/{IG_ACCOUNT_ID}/media",
                      data={"media_type":"REELS","video_url":video_url,"caption":caption,
                            "access_token":FB_PAGE_TOKEN,"thumb_offset":"7500"}, timeout=60)
    if r.status_code!=200: print(f"❌ IG reel container ({r.status_code}): {r.text}"); return
    cid = r.json().get("id"); print(f"✅ Container reel IG: {cid}")
    import time
    for attempt in range(10):
        time.sleep(15)
        rs = requests.get(f"https://graph.facebook.com/v25.0/{cid}",
                          params={"fields":"status_code","access_token":FB_PAGE_TOKEN}, timeout=30)
        s = rs.json().get("status_code","")
        print(f"  ⏳ {s} (tentative {attempt+1})")
        if s=="FINISHED": break
        if s=="ERROR": print("❌ IG reel ERROR"); return
    r2 = requests.post(f"https://graph.facebook.com/v25.0/{IG_ACCOUNT_ID}/media_publish",
                       data={"creation_id":cid,"access_token":FB_PAGE_TOKEN}, timeout=60)
    print(f"✅ Instagram reel — {r2.json().get('id','?')}" if r2.status_code==200 else f"❌ IG reel publish ({r2.status_code}): {r2.text}")

def post_threads(path, caption):
    if not THREADS_ACCESS_TOKEN: return
    url = upload_to_cloudinary(path, "image")
    if not url: return
    if "cloudinary.com" in url: url = url.replace("/upload/","/upload/f_jpg/")
    r = requests.post("https://graph.threads.net/v1.0/me/threads",
                      data={"media_type":"IMAGE","image_url":url,"text":caption,"access_token":THREADS_ACCESS_TOKEN}, timeout=60)
    if r.status_code!=200: print(f"❌ Threads ({r.status_code}): {r.text}"); return
    import time; time.sleep(5)
    r2 = requests.post("https://graph.threads.net/v1.0/me/threads_publish",
                       data={"creation_id":r.json().get("id"),"access_token":THREADS_ACCESS_TOKEN}, timeout=60)
    print(f"✅ Threads — {r2.json().get('id','?')}" if r2.status_code==200 else f"❌ Threads publish ({r2.status_code}): {r2.text}")

def post_youtube(path, day_data):
    if not YT_CLIENT_ID: return
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.auth.transport.requests import Request
        creds = Credentials(token=None, refresh_token=YT_REFRESH_TOKEN,
                            client_id=YT_CLIENT_ID, client_secret=YT_CLIENT_SECRET,
                            token_uri="https://oauth2.googleapis.com/token",
                            scopes=["https://www.googleapis.com/auth/youtube.upload"])
        creds.refresh(Request())
        yt = build("youtube","v3",credentials=creds)
        title = f"{day_data['emoji']} {day_data['ref']} — {day_data['theme']}"
        desc  = (f"{day_data['emoji']} {day_data['theme']}\n\n"
                 f"« {day_data['verse']} »\n\n— {day_data['ref']} (LSG 1910)\n\n"
                 f"📖 {APP_URL}\n\n#Shorts #SemaineSainte #Bible #Paques #JésusChrist #LSG1910 #BibleFrancaise")
        body = {"snippet":{"title":title,"description":desc,"categoryId":"22",
                           "tags":["SemaineSainte","Bible","Paques","LSG1910","Shorts"]},
                "status":{"privacyStatus":"public","selfDeclaredMadeForKids":False}}
        req = yt.videos().insert(part="snippet,status", body=body,
                                  media_body=MediaFileUpload(path,mimetype="video/mp4",resumable=True))
        response = None
        while response is None:
            _, response = req.next_chunk()
        print(f"✅ YouTube — https://youtube.com/shorts/{response.get('id','?')}")
    except Exception as e:
        print(f"❌ YouTube: {e}")


# ── MAIN ──
def main():
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    day   = HOLY_WEEK.get(today)

    if not day:
        print(f"📅 {today} — pas de publication Semaine Sainte.")
        return

    print(f"\n✝️  Semaine Sainte — {day['theme']}\n")

    hashtags = f"#SemaineSainte #Paques #Bible #BibleFrancaise #Jésus #JésusChrist {day['tag']} #LSG1910 #LaBible #Foi"

    caption_tg = (f"{day['emoji']} <b>{day['theme']}</b>\n\n"
                  f"« {day['verse']} »\n\n— <b>{day['ref']}</b> (LSG 1910)\n\n"
                  f"#SemaineSainte {day['tag']}")

    caption_social = (f"{day['emoji']} {day['theme']}\n\n"
                      f"« {day['verse']} »\n\n— {day['ref']} (LSG 1910)\n\n"
                      f"📖 Bible complète gratuite sur {APP_URL}\n\n"
                      f"👇 Partage ce verset avec quelqu'un qui en a besoin 🙏\n\n"
                      f"{hashtags}")

    # ── IMAGE ──
    print("🖼️  Génération image...")
    img = make_holy_week_image(day)
    post_telegram_photo(img, caption_tg)
    post_facebook_photo(img, caption_social)
    post_instagram_image(img, caption_social)
    post_threads(img, caption_social)

    # ── REEL ──
    print("\n🎬 Génération reel...")
    reel = make_holy_week_reel(day)
    post_telegram_video(reel, caption_tg)
    post_facebook_reel(reel, caption_social)
    post_instagram_reel(reel, caption_social)
    post_youtube(reel, day)

    print(f"\n✅ Semaine Sainte complète — {day['theme']}")


if __name__ == "__main__":
    main()
