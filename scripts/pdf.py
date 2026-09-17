#!/usr/bin/env python3
"""Print-first newspaper renderer for the text-me daily report.

The report borrows the useful rules of Morning Paper (ink first, warm paper,
serif reading type, restrained labels and thin rules) and applies the compact
newspaper language chosen for text-me: blackletter masthead, narrow columns,
small-caps ledgers and a dedicated closing cartoon page.
"""
from __future__ import annotations

import argparse
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

A4=(1240,1754); M=58; BOTTOM=82
PAPER=(246,242,230); INK=(27,25,21); MUTED=(85,80,70); RULE=(55,51,43)
HERE=Path(__file__).resolve().parent
FONT_DIRS=(HERE.parent/'fonts',Path('/opt/matriz/fonts'),Path('/usr/share/fonts/opentype/urw-base35'),Path('/usr/share/fonts/truetype/dejavu'),Path('/usr/share/fonts/truetype/liberation'))
IMG_RE=re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def _first(*names):
    for folder in FONT_DIRS:
        for name in names:
            p=folder/name
            if p.exists(): return p
    return None

def _font(size,*names):
    p=_first(*names)
    return ImageFont.truetype(str(p),size) if p else ImageFont.load_default()

MAST=_font(73,'UnifrakturCook-Bold.ttf','PlayfairDisplay-Bold.ttf')
DEK=_font(35,'PlayfairDisplay-Bold.ttf','DejaVuSerif-Bold.ttf')
HED=_font(28,'PlayfairDisplay-Bold.ttf','DejaVuSerif-Bold.ttf')
BODY=_font(19,'PlayfairDisplay-Regular.ttf','NimbusRoman-Regular.otf','DejaVuSerif.ttf')
BODY_BOLD=_font(19,'PlayfairDisplay-Bold.ttf','NimbusRoman-Bold.otf','DejaVuSerif-Bold.ttf')
ITALIC=_font(16,'NimbusRoman-Italic.otf','DejaVuSerif-Italic.ttf','LiberationSerif-Italic.ttf')
SMALL=_font(16,'PlayfairDisplay-Regular.ttf','NimbusRoman-Regular.otf','DejaVuSerif.ttf')
LABEL=_font(13,'NimbusSansNarrow-Bold.otf','DejaVuSansCondensed-Bold.ttf','LiberationSans-Bold.ttf')
TIME=_font(17,'NimbusRoman-Bold.otf','DejaVuSerif-Bold.ttf')

class Block:
    def __init__(self,kind,text,image=None):
        self.kind=kind; self.text=text; self.image=image


def _wrap(draw,text,font,width):
    out=[]
    for paragraph in str(text).split('\n'):
        line=''
        for word in paragraph.split():
            trial=(line+' '+word).strip()
            if draw.textlength(trial,font=font)<=width: line=trial
            else:
                if line: out.append(line)
                line=word
        if line: out.append(line)
        if not paragraph.strip(): out.append('')
    return out or ['']

def _rule(d,x1,y,x2,width=1): d.line((x1,y,x2,y),fill=RULE,width=width)

def _label(d,x,y,text,width):
    d.text((x,y),str(text).upper(),font=LABEL,fill=MUTED)
    _rule(d,x,y+19,x+width)
    return y+27

def _header(d,page,title,folio=''):
    tagline="It's sorted: your plans, so you don't have to."
    d.text(((A4[0]-d.textlength(tagline,font=ITALIC))/2,16),tagline,font=ITALIC,fill=MUTED)
    mast='The Text-me Times'
    d.text(((A4[0]-d.textlength(mast,font=MAST))/2,35),mast,font=MAST,fill=INK)
    _rule(d,M,125,A4[0]-M,3)
    meta=folio.strip(' _') or datetime.now().strftime('%A, %B %-d, %Y').upper()
    meta=f'VOL. 1  —  {meta}  —  PAGE {page}'
    if d.textlength(meta,font=LABEL)>A4[0]-2*M:
        meta=f'VOL. 1  —  {title[:65]}  —  PAGE {page}'
    d.text(((A4[0]-d.textlength(meta,font=LABEL))/2,137),meta,font=LABEL,fill=MUTED)
    _rule(d,M,160,A4[0]-M)
    return 174

def _footer(d,page):
    y=A4[1]-43; _rule(d,M,y,A4[0]-M)
    text=f'THE TEXT-ME TIMES — {page}'
    d.text(((A4[0]-d.textlength(text,font=LABEL))/2,y+11),text,font=LABEL,fill=MUTED)

def _parse(markdown,images):
    images=images or {}; title='Daily Report'; folio=''; blocks=[]
    for raw in markdown.splitlines():
        s=raw.strip()
        if not s: continue
        if s.startswith('# '): title=s[2:].strip(); continue
        m=IMG_RE.fullmatch(s)
        if m:
            blob=images.get(m.group(2)) or images.get(Path(m.group(2)).name)
            blocks.append(Block('image',m.group(1) or 'Editorial image',blob)); continue
        if s=='---': blocks.append(Block('break','')); continue
        if s.startswith('## '): blocks.append(Block('section',s[3:].strip())); continue
        if s.startswith('### '): blocks.append(Block('headline',s[4:].strip())); continue
        if s.startswith('> '): blocks.append(Block('quote',s[2:].strip())); continue
        if s.startswith('- '): blocks.append(Block('item',s[2:].strip())); continue
        if s.startswith('_') and s.endswith('_'):
            text=s[1:-1].strip()
            if not folio and ('·' in text or re.search(r'\d{1,2}/\d{1,2}',text)): folio=text
            else: blocks.append(Block('caption',text))
            continue
        blocks.append(Block('body',s))
    return title,folio,blocks

def _height(d,b,width):
    if b.kind=='section': return 36
    if b.kind=='headline': return len(_wrap(d,b.text,HED,width))*35+9
    if b.kind=='quote': return len(_wrap(d,b.text,HED,width-18))*35+18
    if b.kind=='caption': return len(_wrap(d,b.text,ITALIC,width))*20+9
    font=SMALL if b.kind=='item' else BODY
    return len(_wrap(d,('•  ' if b.kind=='item' else '')+b.text,font,width))*23+8

def _draw_block(d,b,x,y,width):
    if b.kind=='section': return _label(d,x,y,b.text,width)+5
    if b.kind=='headline':
        for line in _wrap(d,b.text,HED,width): d.text((x,y),line,font=HED,fill=INK); y+=35
        return y+9
    if b.kind=='quote':
        d.line((x,y,x,y+_height(d,b,width)-8),fill=INK,width=3); x+=12; width-=18
        for line in _wrap(d,b.text,HED,width): d.text((x,y),line,font=HED,fill=INK); y+=35
        return y+12
    if b.kind=='caption':
        for line in _wrap(d,b.text,ITALIC,width): d.text((x,y),line,font=ITALIC,fill=MUTED); y+=20
        return y+9
    font=SMALL if b.kind=='item' else BODY; text=('•  ' if b.kind=='item' else '')+b.text
    for line in _wrap(d,text,font,width): d.text((x,y),line,font=font,fill=INK); y+=23
    return y+8

def _new_page(number,title,folio):
    im=Image.new('RGB',A4,PAPER); d=ImageDraw.Draw(im); y=_header(d,number,title,folio); return im,d,y

def _content_pages(title,folio,blocks):
    pages=[]; number=1; im,d,y=_new_page(number,title,folio)
    # The lead story spans two columns. The matrix owns the right rail; no weather widget.
    gap=18; col=(A4[0]-2*M-2*gap)//3; xs=[M,M+col+gap,M+2*(col+gap)]
    lead=[]
    if blocks and blocks[0].kind=='section': lead.append(blocks.pop(0))
    if blocks and blocks[0].kind in ('quote','headline','body'): lead.append(blocks.pop(0))
    y=_label(d,M,y,lead[0].text if lead and lead[0].kind=='section' else 'Your day',col*2+gap)
    lead_text=lead[-1].text if lead else title
    for line in _wrap(d,lead_text,DEK,col*2+gap): d.text((M,y),line,font=DEK,fill=INK); y+=43
    y+=8
    rail_x=xs[2]; rail_y=_label(d,rail_x,174,'The matrix',col)
    for q,name,note in [('Q1','Do it','Deadline or consequence.'),('Q2','Protect it',"Serves the week's goal."),('Q3','Reduce it','Useful, but not yours now.'),('Q4','Remove it','Noise or chosen leisure.')]:
        d.text((rail_x,rail_y),q,font=LABEL,fill=MUTED); d.text((rail_x+45,rail_y),name,font=BODY_BOLD,fill=INK); rail_y+=24
        for line in _wrap(d,note,SMALL,col-45): d.text((rail_x+45,rail_y),line,font=SMALL,fill=MUTED); rail_y+=20
        rail_y+=7
    _rule(d,rail_x,rail_y,rail_x+col); rail_y+=10
    d.text((rail_x,rail_y),'ONE FINAL DECISION',font=LABEL,fill=MUTED); rail_y+=24
    for line in _wrap(d,'The edition ends the sorting with one clear place to begin.',SMALL,col): d.text((rail_x,rail_y),line,font=SMALL,fill=INK); rail_y+=21
    y+=20; top=y; col_i=0; column_bottom=[top,top]
    for b in blocks:
        if b.kind in ('break','image'): continue
        h=_height(d,b,col)
        if y+h>A4[1]-BOTTOM:
            col_i+=1
            if col_i==2: # keep page-one right rail intact
                _footer(d,number); pages.append(im); number+=1; im,d,y=_new_page(number,title,folio); col_i=0; top=y
                column_bottom=[top,top]
            else: y=top
        y=_draw_block(d,b,xs[col_i],y,col); column_bottom[col_i]=max(column_bottom[col_i],y)
        # Start a new newspaper column at a natural section break once the first
        # column has enough copy; sparse reports stay compact instead of drawing
        # empty rules to the foot of the page.
        if b.kind=='section' and col_i==0 and y-top>380:
            col_i=1; y=top
    separator_bottom=max(column_bottom)+6
    if separator_bottom>top+30:
        d.line((xs[1]-gap//2,top,xs[1]-gap//2,separator_bottom),fill=RULE,width=1)
    _footer(d,number); pages.append(im)
    return pages

def _closing_page(number,title,folio,blocks,images):
    im,d,y=_new_page(number,title,folio); y=_label(d,M,y,'The daily cartoon',A4[0]-2*M)
    heading=next((b.text for b in blocks if b.kind=='section'),'Cartoon of the day')
    for line in _wrap(d,heading,DEK,A4[0]-2*M): d.text((M,y),line,font=DEK,fill=INK); y+=43
    y+=8; image=next((b for b in blocks if b.kind=='image' and b.image),None)
    if image:
        try: pic=Image.open(BytesIO(image.image)).convert('L').convert('RGB')
        except (OSError,ValueError): pic=None
        if pic:
            maxw=A4[0]-2*M; maxh=940; scale=min(maxw/pic.width,maxh/pic.height,1.8)
            pic=pic.resize((int(pic.width*scale),int(pic.height*scale)),Image.LANCZOS)
            im.paste(pic,((A4[0]-pic.width)//2,y)); y+=pic.height+10
    rest=[b for b in blocks if b.kind not in ('image','break','section')]
    _rule(d,M,y,A4[0]-M); y+=12
    gap=20; col=(A4[0]-2*M-gap)//2; xs=[M,M+col+gap]; ci=0
    for b in rest:
        h=_height(d,b,col)
        if y+h>A4[1]-BOTTOM: ci=1; y=max(1180,_header_y)
        y=_draw_block(d,b,xs[ci],y,col)
    _footer(d,number); return im

def pages_from_markdown(markdown,images=None):
    title,folio,blocks=_parse(markdown,images or {})
    close_at=next((i for i,b in enumerate(blocks) if b.kind=='section' and any(k in b.text.casefold() for k in ('charge','cartoon'))),None)
    if close_at is None:
        main,closing=blocks,[]
    else:
        main=blocks[:close_at]
        # discard the explicit page break immediately before the cartoon
        if main and main[-1].kind=='break': main=main[:-1]
        closing=blocks[close_at:]
    pages=_content_pages(title,folio,list(main))
    if closing:
        # Never let later readings or hobbies push the cartoon off the last page.
        global _header_y; _header_y=174
        pages.append(_closing_page(len(pages)+1,title,folio,closing,images or {}))
    return pages

def _jpeg(im):
    b=BytesIO(); im.save(b,'JPEG',quality=88,subsampling=0); return b.getvalue()

def _pdf_from_jpegs(jpegs,size):
    w,h=595,842; out=bytearray(b'%PDF-1.4\n'); offsets=[0]
    def obj(n,body):
        offsets.append(len(out)); out.extend(f'{n} 0 obj\n'.encode()); out.extend(body); out.extend(b'\nendobj\n')
    kids=' '.join(f'{3+i*3} 0 R' for i in range(len(jpegs)))
    obj(1,b'<< /Type /Catalog /Pages 2 0 R >>'); obj(2,f'<< /Type /Pages /Kids [{kids}] /Count {len(jpegs)} >>'.encode())
    n=3
    for jpeg in jpegs:
        content=f'q {w} 0 0 {h} 0 0 cm /Im1 Do Q'.encode()
        obj(n,f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w} {h}] /Contents {n+1} 0 R /Resources << /XObject << /Im1 {n+2} 0 R >> >> >>'.encode())
        obj(n+1,f'<< /Length {len(content)} >>\nstream\n'.encode()+content+b'\nendstream')
        obj(n+2,f'<< /Type /XObject /Subtype /Image /Width {size[0]} /Height {size[1]} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length {len(jpeg)} >>\nstream\n'.encode()+jpeg+b'\nendstream'); n+=3
    xref=len(out); out.extend(f'xref\n0 {n}\n0000000000 65535 f \n'.encode())
    for off in offsets[1:]: out.extend(f'{off:010d} 00000 n \n'.encode())
    out.extend(f'trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()); return bytes(out)

def write_pdf(path,markdown,images=None):
    path.parent.mkdir(parents=True,exist_ok=True); pages=pages_from_markdown(markdown,images); path.write_bytes(_pdf_from_jpegs([_jpeg(p) for p in pages],A4))

def main():
    p=argparse.ArgumentParser(); p.add_argument('markdown'); p.add_argument('-o','--out',required=True); a=p.parse_args(); write_pdf(Path(a.out),Path(a.markdown).read_text(encoding='utf-8')); print(a.out); return 0
if __name__=='__main__': raise SystemExit(main())
