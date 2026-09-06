# -*- coding: utf-8 -*-
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1440, 1020
page=(247,248,247); white=(255,255,255); surface=(240,242,241); sage=(240,244,241)
primary=(91,124,115); soft=(141,163,153); deep=(63,93,80); tip=(235,232,218)
border=(224,227,226); ink=(51,56,64); muted=(122,128,135)

def font(size):
    cands=[]
    up=os.environ.get('USERPROFILE','')
    windir=os.environ.get('WINDIR','C\\\\Windows')
    cands += [
        str(Path(windir)/'Fonts'/'malgun.ttf'),
        str(Path(windir)/'Fonts'/'malgunbd.ttf'),
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ]
    for p in cands:
        try: return ImageFont.truetype(p, size)
        except Exception: pass
    return ImageFont.load_default()

def make(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    def draw_ws():
        img=Image.new('RGB',(W,H),page); d=ImageDraw.Draw(img)
        def rr(xy,r,fill,outline=None):
            d.rounded_rectangle(xy,radius=r,fill=fill,outline=outline,width=1 if outline else 0)
        def tx(xy,s,fill=ink,size=14):
            d.text(xy,s,fill=fill,font=font(size))
        rr((40,28,1400,100),20,white,border)
        tx((67,51),'\uac10\uc0ac \uc120\ub840 \ub3c4\uc6b0\ubbf8',ink,20)
        tx((360,55),'\uc5c5\ubb34\ub97c \uc801\uc73c\uba74, \uacb0\uc7ac \uc9c1\uc804 \uc790\ub8cc\uae4c\uc9c0',muted,13)
        rr((979,45,1319,81),18,surface)
        tx((1007,55),'\uac80\uc0c9',primary,12); tx((1089,55),'\uc778\uc0ac\uc774\ud2b8',muted,12); tx((1199,55),'\uac00\uc774\ub4dc',muted,12)
        rr((40,120,1400,240),20,white,border)
        tx((67,139),'\uc9c0\uae08 \ud558\ub824\ub294 \uc77c',deep,12)
        tx((67,163),'\uae30\uc874 \uc6a9\uc5ed\uc758 \uacfc\uc5c5 \ubc94\uc704\ub97c \ubcc0\uacbd\ud558\ub824 \ud55c\ub2e4.',ink,15)
        rr((1159,155,1359,203),14,primary); tx((1195,169),'\uc120\ub840 \uc5f0\uacb0\ud558\uae30',white,14)
        for (x,w,title,sub) in [(40,420,'\ud655\ubcf4\ub41c \uadfc\uac70','\ubcf8\ubb38\uc774 \uc788\ub294 \uac83\ub9cc \uc778\uc6a9'),(480,460,'\ub0b4 \uc5c5\ubb34\uc640\uc758 \uac70\ub9ac','\uac19\uc740 \uc810 / \ub2e4\ub978 \uc810'),(960,440,'\uacb0\uc7ac\uc6a9 \uac80\ud1a0\uba54\ubaa8','\ucd08\uc548 \u00b7 \ubcf5\uc0ac \uac00\ub2a5')]:
            rr((x,268,x+w,968),20,white,border); tx((x+23,291),title,ink,13); tx((x+23,315),sub,muted,12)
        rr((63,355,435,505),14,sage); tx((79,369),'\ubcf8\ubb38 \ud655\ubcf4',deep,11); tx((79,395),'\uc6a9\uc5ed \uacfc\uc5c5\ubc94\uc704 \ubcc0\uacbd \uc9c0\uc801',ink,14)
        rr((63,521,435,641),14,surface); tx((79,535),'\ubaa9\ub85d\ub9cc',muted,11); tx((79,561),'\uba54\ud0c0\ub9cc \uc788\uc5b4 \uc778\uc6a9 \ubcf4\ub958',ink,14)
        rr((63,657,435,797),14,surface); tx((79,671),'\uba74\ucc45\u00b7\ucee8\uc124\ud305',primary,11); tx((79,697),'\ubcf4\ud638\ubc1b\ub294 \uae38',ink,14)
        for i,(chip,body) in enumerate([('\uac19\uc74c','\ubcc0\uacbd\uacc4\uc57d \u00b7 \uc6a9\uc5ed \u00b7 \uc9c0\uc790\uccb4'),('\ub2e4\ub984','\uae08\uc561 \uaddc\ubaa8 \u00b7 \ud589\uc704 \uc2dc\uc810'),('\ud655\uc778','\uc704\uc784\uc804\uacb0 \u00b7 \uc0b0\ucd9c\ub0b4\uc5ed')]):
            y=355+i*104; rr((503,y,915,y+88),12,surface); rr((519,y+16,583,y+40),12,(210,224,218)); tx((529,y+21),chip,primary,11); tx((519,y+48),body,ink,13)
        rr((503,687,915,907),14,tip); tx((523,707),'\ud55c \uc904 \uc815\ub9ac',ink,12); tx((523,739),'\ube44\uc2b7\ud574 \ubcf4\uc774\uc9c0\ub9cc \uacfc\uc5c5 \uc2e0\uc124 \ube44\uc911\uc774 \ud06c\uba74',ink,13)
        d.rectangle((960,268,1400,276),fill=deep)
        for i,lab in enumerate(['\uc5c5\ubb34 \uac1c\uc694','\ucc38\uace0 \uc120\ub840','\uc801\uc6a9\uc0c1 \ucc28\uc774','\uadfc\uac70 \ubc1c\ucdcc','\ubbf8\ud655\uc778 \uc0ac\ud56d','\ub2f4\ub2f9\uc790 \ud310\ub2e8']):
            y=355+i*88; rr((983,y,1375,y+72),12,surface); tx((999,y+12),lab,deep,12); tx((999,y+38),'\u2014',muted,12)
        return img

    def draw_dash():
        img=Image.new('RGB',(W,H),page); d=ImageDraw.Draw(img)
        def rr(xy,r,fill,outline=None):
            d.rounded_rectangle(xy,radius=r,fill=fill,outline=outline,width=1 if outline else 0)
        def tx(xy,s,fill=ink,size=14):
            d.text(xy,s,fill=fill,font=font(size))
        rr((40,28,1400,100),20,white,border)
        tx((67,51),'\uac10\uc0ac \uc120\ub840 \ub3c4\uc6b0\ubbf8',ink,20); tx((360,55),'\uc778\uc0ac\uc774\ud2b8',primary,14)
        rr((40,120,1400,280),20,white,border); d.rectangle((40,120,48,280),fill=deep)
        tx((67,139),'\uc774\ubc88 \uc8fc \uc2dc\uc120',deep,12); tx((67,170),'\uacc4\uc57d \uc5c5\ubb34\uc5d0\uc11c \ubcf8\ubb38 \ud655\ubcf4 \uc0ac\ub840\uac00 \ub298\uace0 \uc788\uc2b5\ub2c8\ub2e4.',ink,17)
        rr((1120,160,1340,240),14,sage); tx((1140,175),'\ubcf8\ubb38 \ud655\ubcf4\uc728',primary,12); tx((1140,198),'12%',deep,28)
        rr((40,308,740,728),20,white,border); tx((63,331),'\uc5c5\ubb34\uc720\ud615 \ubd84\ud3ec',ink,13)
        bars=[200,160,120,100,70,50]; labels=['\uacc4\uc57d','\uc608\uc0b0','\uc778\uc0ac','\ubcf4\uc870\uae08','\uc815\ubcf4\ud654','\uae30\ud0c0']; colors=[primary,soft,deep,primary,soft,(110,140,128)]
        for i,(h,lab,col) in enumerate(zip(bars,labels,colors)):
            x=80+i*100; y=620-h; rr((x,y,x+64,620),8,col); tx((x,635),lab,muted,11)
        rr((760,308,1400,728),20,white,border); tx((783,331),'\uadfc\uac70 \ud488\uc9c8 \uad6c\uc131',ink,13)
        rr((800,390,980,630),14,surface); tx((820,420),'\ubaa9\ub85d\ub9cc',ink,14); tx((820,460),'78%',ink,28)
        rr((1000,390,1180,630),14,primary); tx((1020,420),'\ubcf8\ubb38 \ud655\ubcf4',sage,14); tx((1020,460),'18%',sage,28)
        rr((1200,390,1380,630),14,deep); tx((1220,420),'\uadfc\uac70 \ub300\uc870',sage,14); tx((1220,460),'4%',sage,28)
        rr((40,756,1400,976),20,white,border); tx((63,779),'\ucd5c\uadfc \ubcf8\ubb38 \ud655\ubcf4',ink,13)
        for i,name in enumerate(['\ubcc0\uacbd\uacc4\uc57d \uacfc\uc5c5\ubc94\uc704','\ubcf4\uc870\uae08 \uc815\uc0b0 \uc99d\ube59','\uc704\uc784\uc804\uacb0 \ub204\ub77d']):
            y=820+i*48; rr((63,y,1377,y+40),10,surface); tx((83,y+10),name,ink,13); tx((980,y+12),'\ubcf8\ubb38 \ud655\ubcf4',deep,12); tx((1280,y+12),'\uc5f4\uae30',primary,12)
        return img

    p1=out_dir/'green-workspace.png'; p2=out_dir/'green-dashboard.png'
    draw_ws().save(p1); draw_dash().save(p2)
    print(p1); print(p2)

if __name__ == '__main__':
    # box default
    out = Path('/workspace/audit-helper-proposals/mockups')
    if os.environ.get('USERPROFILE'):
        out = Path(os.environ['USERPROFILE'])/'Desktop'/'audit-helper'/'docs'/'proposals'/'2026-09-06-situation-memo'/'mockups'
    make(out)
