import os
import json
import random
import re
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL = os.environ["TELEGRAM_CHANNEL"]

PROGRESS_FILE = "progress.json"
PROMISES_LIST = "promesses_curated.json"
JESUS_LIST = "jesus_curated.json"
BIBLE_DIR = "bible"

FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

WATERMARK = "@appbible"
FIXED_HASHTAGS = "#LaBible #LSG1910 #versetdujour"


# ---------------------------------------------------
# CLEAN + FRENCH TYPOGRAPHY
# ---------------------------------------------------
def clean_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"\\\+?w\b", "", text)
    text = re.sub(r'strong="[^"]+"', "", text)
    text = re.sub(r"\|[^ \t]+", "", text)
    text = re.sub(r"\\[a-zA-Z0-9]+\*?", "", text)
    text = text.replace("\\", "")

    text = re.sub(r"\s+", " ", text).strip()

    # Corrige A → À no início de frase
    text = re.sub(r"(^|\. )A ", r"\1À ", text)

    # Espaçamento francês
    text = re.sub(r"\s*([;:?!])", r" \1", text)

    # Garante ponto final
    if not text.endswith((".", "!", "?", "»")):
        text += "."

    # Aspas françaises
    if not text.startswith("«"):
        text = f"« {text} »"

    return text


# ---------------------------------------------------
def safe_filename(name: str) -> str:
    t = name.lower()
    repl = (("é","e"),("è","e"),("ê","e"),("ë","e"),
            ("à","a"),("â","a"),
            ("î","i"),("ï","i"),
            ("ô","o"),
            ("ù","u"),("û","u"),
            ("ç","c"),("œ","oe"))
    for a,b in repl:
        t = t.replace(a,b)
    t = re.sub(r"[^a-z0-9]+","_",t).strip("_")
    return t


def load_json(path):
    with open(path,"r",encoding="utf-8") as f:
        return json.load(f)


def save_json(path,data):
    with open(path,"w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2)


def load_book(book_name):
    path = f"{BIBLE_DIR}/{safe_filename(book_name)}.json"
    data = load_json(path)
    return data[book_name]


def send_photo(path,caption):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(path,"rb") as f:
        r = requests.post(
            url,
            data={
                "chat_id":CHANNEL,
                "caption":caption,
                "parse_mode":"HTML"
            },
            files={"photo":f},
            timeout=30
        )
    r.raise_for_status()


# ---------------------------------------------------
# SIGNATURE DESIGN
# ---------------------------------------------------
def make_background(W,H):
    img = Image.new("RGB",(W,H))
    draw = ImageDraw.Draw(img)

    # Gradiente suave
    for y in range(H):
        t = y / H
        r = int(12 + t*15)
        g = int(12 + t*15)
        b = int(18 + t*20)
        draw.line([(0,y),(W,y)],fill=(r,g,b))

    # Blur leve para efeito cinematográfico
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    return img


def draw_glow_border(draw,W,H):
    gold = (195,165,90)
    glow = (120,100,60)

    margin = 60

    # glow
    for i in range(8):
        draw.rounded_rectangle(
            [margin-i,margin-i,W-margin+i,H-margin+i],
            radius=32,
            outline=glow,
            width=1
        )

    draw.rounded_rectangle(
        [margin,margin,W-margin,H-margin],
        radius=30,
        outline=gold,
        width=6
    )


def wrap_text(draw,text,font,max_w):
    words=text.split()
    lines=[]
    current=words[0]
    for w in words[1:]:
        if draw.textlength(current+" "+w,font=font)<=max_w:
            current+=" "+w
        else:
            lines.append(current)
            current=w
    lines.append(current)
    return lines


def make_image(text,ref):
    W,H=1080,1080
    img=make_background(W,H)
    draw=ImageDraw.Draw(img)

    draw_glow_border(draw,W,H)

    pad_x=130
    top=200
    bottom=320

    max_w=W-2*pad_x
    max_h=H-top-bottom

    font_size=64
    font=ImageFont.truetype(FONT_SERIF,font_size)

    lines=wrap_text(draw,text,font,max_w)
    line_h=int(font_size*1.35)

    total_h=line_h*len(lines)
    y=top+(max_h-total_h)//2

    text_color=(245,245,245)
    shadow=(0,0,0)

    for line in lines:
        draw.text((pad_x+2,y+2),line,font=font,fill=shadow)
        draw.text((pad_x,y),line,font=font,fill=text_color)
        y+=line_h

    # Ref + version
    small=ImageFont.truetype(FONT_SANS,36)
    tiny=ImageFont.truetype(FONT_SANS,28)

    draw.line([(pad_x,H-260),(W-pad_x,H-260)],fill=(150,130,70),width=2)

    draw.text((pad_x,H-220),ref,font=small,fill=(220,220,230))
    draw.text((pad_x,H-180),"LSG 1910",font=tiny,fill=(170,170,180))

    wm_w=draw.textlength(WATERMARK,font=tiny)
    draw.text((W-pad_x-wm_w,H-180),WATERMARK,font=tiny,fill=(150,150,160))

    out="verse.png"
    img.save(out)
    return out


# ---------------------------------------------------
def load_list(path):
    arr=load_json(path)
    if not arr:
        raise RuntimeError("Lista vazia")
    return arr


def reshuffle_if_needed(path,index):
    arr=load_list(path)
    if index>=len(arr):
        random.shuffle(arr)
        save_json(path,arr)
        index=0
    return arr,index


def pick_from_curated(path,key,progress):
    index=progress.get(key,0)
    arr,index=reshuffle_if_needed(path,index)
    book,ch,v=arr[index]
    progress[key]=index+1
    return book,ch,v


def main():
    progress=load_json(PROGRESS_FILE)
    next_kind=progress.get("next","promise")

    if next_kind=="promise":
        book,ch,v=pick_from_curated(PROMISES_LIST,"i_promise",progress)
        progress["next"]="jesus"
    else:
        book,ch,v=pick_from_curated(JESUS_LIST,"i_jesus",progress)
        progress["next"]="promise"

    book_data=load_book(book)
    raw_text=book_data[str(ch)][str(v)]
    text=clean_text(raw_text)

    ref=f"{book} {ch}:{v}"

    img=make_image(text,ref)
    caption=f"📖 <b>{ref}</b>\n{FIXED_HASHTAGS}"

    send_photo(img,caption)
    save_json(PROGRESS_FILE,progress)


if __name__=="__main__":
    main()