from __future__ import annotations

import argparse, math, os, re, shutil, subprocess, textwrap, wave
from pathlib import Path
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W,H,FPS = 1920,1080,30
TOTAL = 136.0
NAVY = (5,17,31)
CYAN = (69,214,255)
WHITE = (238,246,255)
MUTED = (165,184,205)
ORANGE = (255,170,73)
FONT_REG_CAND = [
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
    '/usr/share/fonts/truetype/arphic-gbsn00lp/gbsn00lp.ttf',
]
FONT_BOLD_CAND = [
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
]

def font_path(cands):
    for p in cands:
        if Path(p).exists(): return p
    raise FileNotFoundError('No CJK font found')
FONT_REG = font_path(FONT_REG_CAND)
FONT_BOLD = font_path(FONT_BOLD_CAND)

def run(cmd: List[str]):
    print('+', ' '.join(cmd))
    subprocess.run(cmd, check=True)

def fit_image(path: Path) -> Image.Image:
    im = Image.open(path).convert('RGB')
    if im.size != (W,H):
        im = im.resize((W,H), Image.Resampling.LANCZOS)
    return im

def add_overlay(src: Path, dst: Path, kicker: str='', title: str='', subtitle: str='', accent=CYAN, darken=0.0):
    im = fit_image(src).convert('RGBA')
    if darken:
        shade = Image.new('RGBA',(W,H),(0,0,0,int(255*darken)))
        im = Image.alpha_composite(im, shade)
    ov = Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(ov)
    # subtle top-left glass panel
    if kicker or title or subtitle:
        box=(78,66,1130,285)
        d.rounded_rectangle(box, radius=22, fill=(4,15,28,190), outline=(74,123,160,70), width=2)
        if kicker:
            f=ImageFont.truetype(FONT_BOLD,26); d.text((110,92), kicker, font=f, fill=accent+(255,))
        if title:
            f=ImageFont.truetype(FONT_BOLD,54); d.text((108,132), title, font=f, fill=WHITE+(255,))
        if subtitle:
            f=ImageFont.truetype(FONT_REG,28); d.text((110,210), subtitle, font=f, fill=MUTED+(255,))
    out=Image.alpha_composite(im,ov).convert('RGB'); out.save(dst, quality=96)

def hook_image(src: Path, dst: Path):
    im=fit_image(src).convert('RGBA')
    # emphasize map area with dark global veil and cyan line accents
    veil=Image.new('RGBA',(W,H),(0,6,16,78)); im=Image.alpha_composite(im,veil)
    ov=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(ov)
    f1=ImageFont.truetype(FONT_BOLD,62); f2=ImageFont.truetype(FONT_REG,30)
    d.rounded_rectangle((90,735,1830,970),26,fill=(3,14,28,205),outline=(67,161,204,70),width=2)
    d.text((130,780),'é£é™©ï¼Œä»æ¥ä¸åªæ˜¯ä¸€ä¸ªæ•°å­—ã€‚',font=f1,fill=WHITE+(255,))
    d.text((132,870),'åœ°å½¢  Â·  å†°å·  Â·  é™æ°´  Â·  é¥æ„Ÿ  Â·  å†å²ç¾å®³',font=f2,fill=CYAN+(255,))
    Image.alpha_composite(im,ov).convert('RGB').save(dst,quality=96)

def meaning_image(src: Path, dst: Path):
    im=fit_image(src).convert('RGBA')
    ov=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(ov)
    d.rounded_rectangle((250,825,1670,975),28,fill=(3,14,28,220),outline=(70,176,217,90),width=2)
    f=ImageFont.truetype(FONT_BOLD,35); small=ImageFont.truetype(FONT_REG,24)
    text='è¯æ®   â†’   ä¸“ä¸š Agent   â†’   é£é™©æ¨¡å‹   â†’   ç»¼åˆ   â†’   Critic'
    bbox=d.textbbox((0,0),text,font=f); d.text(((W-(bbox[2]-bbox[0]))/2,862),text,font=f,fill=WHITE+(255,))
    t2='Evidence-based Â· Reproducible Â· Reviewable Â· Bounded'
    bbox2=d.textbbox((0,0),t2,font=small); d.text(((W-(bbox2[2]-bbox2[0]))/2,925),t2,font=small,fill=CYAN+(255,))
    Image.alpha_composite(im,ov).convert('RGB').save(dst,quality=96)

def make_end(dst: Path):
    im=Image.new('RGB',(W,H),NAVY); d=ImageDraw.Draw(im)
    # minimal line mountain mark
    pts=[(790,410),(930,285),(1020,385),(1090,320),(1225,455)]
    d.line(pts,fill=CYAN,width=6,joint='curve')
    d.ellipse((925,280,942,297),fill=WHITE)
    f1=ImageFont.truetype(FONT_BOLD,72); f2=ImageFont.truetype(FONT_BOLD,42); f3=ImageFont.truetype(FONT_REG,27); f4=ImageFont.truetype(FONT_REG,24)
    for text,y,f,fill in [
        ('MountainGuardian',510,f1,WHITE),('å±±æ²³å®ˆæœ›è€…',610,f2,WHITE),('Evidence. Intelligence. Review.',710,f3,CYAN),('mountainguardian.cn',790,f4,MUTED)]:
        bb=d.textbbox((0,0),text,font=f); d.text(((W-(bb[2]-bb[0]))/2,y),text,font=f,fill=fill)
    im.save(dst,quality=96)

def transparent_overlay(dst: Path, title: str, foot: str):
    ov=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(ov)
    f1=ImageFont.truetype(FONT_BOLD,29); f2=ImageFont.truetype(FONT_REG,24)
    d.rounded_rectangle((75,58,800,126),18,fill=(3,14,28,185),outline=(74,176,220,75),width=2)
    d.text((105,77),title,font=f1,fill=WHITE+(255,))
    d.rounded_rectangle((75,940,1015,1015),16,fill=(3,14,28,180))
    d.text((105,960),foot,font=f2,fill=MUTED+(255,))
    ov.save(dst)

def make_still_clip(img: Path, out: Path, duration: float, direction='in', zoom=1.055):
    frames=max(1,int(round(duration*FPS)))
    if direction=='in': z=f"min(zoom+{(›ÛÛKLJKÙœ˜[Y\Î‹ŸKŞ›ÛÛ_JH‚ˆ[ÙNˆYˆšYŠ\JÛ‹
KŞ›ÛÛ_KX^
›ÛÛK^Ê›ÛÛKLJKÙœ˜[Y\Î‹ŸKKŒ
JH‚ˆ™YˆœØØ[O^ÕßNÒK›ÛÛ\[^IŞŞŸIÎIÚ]ËÌ‹J]ËŞ›ÛÛKÌŠIÎOIÚZÌ‹JZŞ›ÛÛKÌŠIÎ™^Ùœ˜[Y\ßNœÏ^Õß^ÒN™œÜÏ^Ñ”ßK›Ü›X]^]]Œ‚ˆ[ŠÉÙ™›\YÉË	Ë^IË	Ë[ÙÛ]™[	Ë	Ù\œ›Ü‰Ë	Ë[ÛÜ	Ë	ÌIË	ËZIËİŠ[YÊK	Ë]	Ë‰ŞÙ\˜][Û‹ŒÙŸIË	Ë]™‰Ë™‹	Ë\‰ËİŠ”ÊK	ËX[‰Ë	ËXÎ‰Ë	ÛX	Ë	Ë\™\Ù]	Ë	İ™\Y˜\İ	Ë	ËXÜ™‰Ë	ÌNIË	Ë\^Ù›]	Ë	Ş]]Œ	ËİŠİ]
WJB‚™YˆXZÙWÜš\Ú×ØÛ\
˜]Ëİ™\›^Kİ]İ\LÌKŒ\˜][ÛLÍËŒ
N‚ˆš[Yˆ–Ì—\ØØ[O^ÕßNÒKœÏ^Ñ”ßVİ—NÖİ—VÌN—[İ™\›^OLŒ™›Ü›X]X]]Ë›Ü›X]^]]Œˆ‚ˆ[ŠÉÙ™›\YÉË	Ë^IË	Ë[ÙÛ]™[	Ë	Ù\œ›Ü‰Ë	Ë\ÜÉËİŠİ\
K	Ë]	ËİŠ\˜][ÛŠK	ËZIËİŠ˜]ÊK	Ë[ÛÜ	Ë	ÌIË	ËZIËİŠİ™\›^JK	ËYš[\—ØÛÛ\^	Ëš[	Ë]	ËİŠ\˜][ÛŠK	ËX[‰Ë	ËXÎ‰Ë	ÛX	Ë	Ë\™\Ù]	Ë	İ™\Y˜\İ	Ë	ËXÜ™‰Ë	ÌNIË	Ë\^Ù›]	ËİŠİ]
WJB‚™YˆÙ[™\˜]WØ[XšY[
]ˆ\˜][ÛUÕSÜM
N‚ˆZ[
\˜][ÛŠœÜŠNÈ[œ˜\˜[™ÙJ‹\O[œ™›Ø]
KÜÜ‚ˆ[LMJÌŒŒ
›œœÚ[ŠŠ›œœJÌMËŒ
JÌŒLŠ›œœÚ[ŠŠ›œœJÌÌKŒ
ÌÊBˆYJŒ
›œœÚ[ŠŠ›œœJMJ
JÌŒN
›œœÚ[ŠŠ›œœJŒLL

ÌŒÊJÌŒL
›œœÚ[ŠŠ›œœJŒŒŒ

ÌJJJ™[‚ˆšYÚJŒ
›œœÚ[ŠŠ›œœJMJ
ÌŒÊJÌŒN
›œœÚ[ŠŠ›œœJŒLLJ
ÌJJÌŒL
›œœÚ[ŠŠ›œœJŒŒŒJ
ÌKŒJJJ™[‚ˆ›ÜˆÈ[ˆÌML‹KLMKLÌWN‚ˆLZ[
ÊœÜŠNÈZ[
ÍJœÜŠNÈ\[Z[ŠÍŒ‹ZL
BˆYˆ\LˆÛÛ[YBˆY[œ˜\˜[™ÙJ\
NÈO[œ™^
ZYÊŒN
œÜŠJBˆ[ÙOLŒÍJ›œœÚ[ŠŠ›œœJŠLŒ
ÌJšYÌÍŒ
JšYÜÜŠJ™BˆYÚLšL
İ\JÏ\[ÙNÈšYÚÚLšL
İ\JÏ\[ÙJŒL‚ˆ˜YOZ[
ÊœÜŠNÈYÎ™˜YWJ[œ›[œÜXÙJK˜YJNÈšYÚÎ™˜YWJ[œ›[œÜXÙJK˜YJBˆYËY˜YN—J[œ›[œÜXÙJK˜YJNÈšYÚËY˜YN—J[œ›[œÜXÙJK˜YJBˆÛOJœ˜Û\
œœİXÚÊÓECB1