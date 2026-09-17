"""Deterministic, original fallback cartoon for editions with no usable web image."""
import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")

def _font(name, size):
    """Try repo fonts first, then fall back to system DejaVu."""
    for base in (_FONT_DIR, "/usr/share/fonts/truetype/dejavu", "/System/Library/Fonts/Supplemental"):
        for candidate in (name, name.replace("Bold", "Regular")):
            path = os.path.join(base, candidate + ".ttf")
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)

def original_daily_cartoon(language="pt"):
    im=Image.new("RGB",(1000,820),"white"); d=ImageDraw.Draw(im)
    font=_font("PlayfairDisplay-Regular", 25)
    bold=_font("PlayfairDisplay-Bold", 22)
    captions=("EU FIZ UMA LISTA DE PRIORIDADES.","E A PRIORIDADE NÚMERO UM?", "PARAR DE REORGANIZAR A LISTA.") if str(language).startswith("pt") else ("I MADE A PRIORITY LIST.","AND PRIORITY NUMBER ONE?","STOP REORGANIZING THE LIST.")
    for i,c in enumerate(captions):
        x=20+i*326; d.rectangle((x,20,x+306,800),outline="black",width=3)

        import textwrap
        wrapped="\n".join(textwrap.wrap(c,width=19))
        d.multiline_text((x+14,42),wrapped,fill="black",font=bold,spacing=5)
        # simple original desk scene
        d.ellipse((x+105,330,x+200,425),outline="black",width=4); d.line((x+152,425,x+152,620),fill="black",width=5)
        d.line((x+152,475,x+85,535),fill="black",width=4); d.line((x+152,475,x+235,525),fill="black",width=4)
        d.rectangle((x+55,610,x+255,730),outline="black",width=4)
        if i==0:
            for j in range(4): d.line((x+75,638+j*18,x+210,638+j*18),fill="black",width=2)
        elif i==1: d.text((x+110,650),"1?",fill="black",font=bold)
        else:
            d.line((x+78,655,x+230,655),fill="black",width=5); d.line((x+95,680,x+215,680),fill="black",width=3)
    b=BytesIO(); im.save(b,"PNG"); return {"title":"Uma lista muito organizada","source":"text-me original","line":"A prioridade de hoje não precisa de uma nova lista.","image":b.getvalue()}
