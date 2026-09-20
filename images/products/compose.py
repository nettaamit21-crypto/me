import sys, os, json, numpy as np
from PIL import Image, ImageFilter, ImageDraw
BG=(248,246,242)          # near-white warm
GAP=(236,231,222)
CW,CH=1080,1350           # 4:5 canvas
BASE_Y=int(CH*0.83)       # base line
BODY_H=int(CH*0.33)       # wood body height on canvas

def load(path):
    im=Image.open(path).convert('RGBA'); a=np.array(im).astype(np.float32); return a

def wood_mask(a):
    r,g,b,al=a[...,0],a[...,1],a[...,2],a[...,3]
    return (al>200)&(r>g)&(g>b)&((r-b)>40)

def clean(a,nograss=False):
    """remove grey/blue ghost pixels above the glass tube; return array + metrics"""
    w=a.shape[1]; rows=(a[...,3]>200).sum(1)
    ys=np.where(rows>w*0.12)[0]; wood_top,wood_bot=int(ys.min()),int(ys.max())   # body = wide alpha rows (tube/grass are narrow)
    body_h=wood_bot-wood_top
    zone_top=int(wood_top-0.20*body_h)
    r,g,b,al=a[...,0],a[...,1],a[...,2],a[...,3]
    if nograss:   # everything above the glass tube goes (tube = first row wider than 3% of the image)
        y=wood_top; miss=0                                        # walk up from the wood: glass rows are neutral, grass rows warm
        while y>0 and miss<4:
            m=al[y]>128; n=int(m.sum())
            warm_row=float((r[y]-b[y])[m].mean()) if n else 0.0
            tube_row = (n>=30 and warm_row<12)                      # wide and neutral = glass; thin or warm = stems/grass
            miss = 0 if (tube_row or n<3) else miss+1
            y-=1
        zone_top=y+miss-2
        if wood_top-zone_top>0.5*body_h: zone_top=int(wood_top-0.20*body_h)
    zone=np.zeros(al.shape,bool); zone[:max(zone_top,0)]=True
    warm=(r>b+int(os.environ.get('WARM','20')))&~((r>g+50)&(r>b+50))   # keep golden grass, drop grey/blue ghosts and red tool remnants
    kill=(zone&(al>0)) if nograss else (zone&(~warm)&(al>0))
    a[...,3][kill]=0
    # soften faint alpha in zone (ghost remnants)
    faint=zone&(al<int(os.environ.get('FAINT','90')))
    a[...,3][faint]=0
    # alpha bottom (base)
    al=a[...,3]; ys=np.where((al>128).sum(1)>w*0.12)[0]; base_y=ys.max()
    cols=np.where(al[base_y-5:base_y+1].max(0)>128)[0]
    return a, dict(wood_top=wood_top,wood_bot=wood_bot,body_h=body_h,base_y=base_y,base_x0=int(cols.min()),base_x1=int(cols.max()))

def wood_lum(a):
    wm=(a[...,3]>200)&(a[...,0]>a[...,2]); rows=(a[...,3]>200).sum(1); ys=np.where(rows>a.shape[1]*0.12)[0]
    wm[:ys.min()]=False; rgb=a[...,:3][wm]; return (0.299*rgb[:,0]+0.587*rgb[:,1]+0.114*rgb[:,2]).mean()

def render(a,m,gain,body_h=None,erase=()):
    scale=(body_h or BODY_H)/m['body_h']
    im=Image.fromarray(np.clip(a,0,255).astype(np.uint8),'RGBA')
    nw,nh=int(round(im.width*scale)),int(round(im.height*scale))
    im=im.resize((nw,nh),Image.LANCZOS)
    # gain on rgb only
    arr=np.array(im).astype(np.float32); arr[...,:3]=np.clip(arr[...,:3]*gain,0,255); im=Image.fromarray(arr.astype(np.uint8),'RGBA')
    bx=(m['base_x0']+m['base_x1'])/2*scale; bw=(m['base_x1']-m['base_x0'])*scale; by=m['base_y']*scale
    ox=int(round(CW/2-bx)); oy=int(round(BASE_Y-by))
    if erase:
        arr=np.array(im).astype(np.float32)
        for x0,y0,x1,y1,mode in erase:
            X0,Y0,X1,Y1=max(0,x0-ox),max(0,y0-oy),min(im.width,x1-ox),min(im.height,y1-oy)
            sub=arr[Y0:Y1,X0:X1]
            if mode=='all': sub[...,3]=0
            elif mode=='brass':
                lum=0.299*sub[...,0]+0.587*sub[...,1]+0.114*sub[...,2]
                sub[...,3][(lum>150)|(sub[...,1]>=sub[...,0])|((sub[...,0]-sub[...,2])<45)]=0
            elif mode=='grey':
                sub[...,3][(sub[...,0]-sub[...,2])<45]=0
            else:
                lum=0.299*sub[...,0]+0.587*sub[...,1]+0.114*sub[...,2]
                pale=(lum>118)&((sub[...,0]-sub[...,2])<85)
                sub[...,3][pale]=0
        im=Image.fromarray(arr.astype(np.uint8),'RGBA')
    canvas=Image.new('RGBA',(CW,CH),BG+(255,))
    # shadow: soft ellipse under base
    sh=Image.new('L',(CW,CH),0); d=ImageDraw.Draw(sh)
    cx,cy=CW/2,BASE_Y
    d.ellipse((cx-bw*0.66,cy-bw*0.05,cx+bw*0.66,cy+bw*0.11),fill=150)
    sh=sh.filter(ImageFilter.GaussianBlur(float(bw*0.06)))
    core=Image.new('L',(CW,CH),0); d=ImageDraw.Draw(core)
    d.ellipse((cx-bw*0.50,cy-bw*0.015,cx+bw*0.50,cy+bw*0.05),fill=210)
    core=core.filter(ImageFilter.GaussianBlur(float(bw*0.02)))
    s=np.maximum(np.array(sh),np.array(core)).astype(np.float32)/255.0
    c=np.array(canvas).astype(np.float32)
    shade=np.array([70,60,50],np.float32)
    c[...,:3]=c[...,:3]*(1-s[...,None]*0.7)+shade*(s[...,None]*0.7)
    canvas=Image.fromarray(c.astype(np.uint8),'RGBA')
    canvas.alpha_composite(im,(ox,oy)) if (ox>=0 and oy>=0) else canvas.alpha_composite(im.crop((max(0,-ox),max(0,-oy),im.width,im.height)),(max(0,ox),max(0,oy)))
    return canvas.convert('RGB'), (ox,oy,nw,nh)

if __name__=='__main__':
    out=sys.argv[1]; srcs=sys.argv[2:]
    data=[]
    for p in srcs:
        ng=p.endswith('!'); p=p.rstrip('!'); a=load(p); a,m=clean(a,ng); data.append((a,m,wood_lum(a)))
    med=np.median([d[2] for d in data])
    body_h=BODY_H
    for a,m,l in data:
        al=a[...,3]; top=int(np.where((al>40).sum(1)>6)[0].min())
        avail=BASE_Y-int(CH*0.05); need=(m['base_y']-top)/m['body_h']
        body_h=min(body_h,int(avail/need))
    print('body_h',body_h)
    singles=[]
    for k,(a,m,l) in enumerate(data):
        gain=float(np.clip(med/l,0.94,1.06))
        img,geo=render(a,m,gain,body_h,json.loads(os.environ.get('ERASE','{}')).get(str(k),())); print(srcs[k],'gain',round(gain,3),'geo',geo)
        img.save(f'{out}/single_{k+1}.jpg',quality=94,subsampling=0); singles.append(img)
    gap=36
    col=Image.new('RGB',(CW*3+gap*2,CH),GAP)
    for k,s in enumerate(singles): col.paste(s,(k*(CW+gap),0))
    col.save(f'{out}/collage.jpg',quality=92,subsampling=0)
    col.resize((2400,int(col.height*2400/col.width)),Image.LANCZOS).save(f'{out}/collage_2400.jpg',quality=90)
