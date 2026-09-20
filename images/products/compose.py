import sys, numpy as np
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
    wm=wood_mask(a); rows=wm.sum(1); w=a.shape[1]
    ys=np.where(rows>w*0.12)[0]; wood_top,wood_bot=ys.min(),ys.max()
    body_h=wood_bot-wood_top
    zone_top=int(wood_top-0.20*body_h)
    r,g,b,al=a[...,0],a[...,1],a[...,2],a[...,3]
    zone=np.zeros(al.shape,bool); zone[:max(zone_top,0)]=True
    warm=(r>b+10)
    kill=(zone&(al>0)) if nograss else (zone&(~warm)&(al>0))
    a[...,3][kill]=0
    # soften faint alpha in zone (ghost remnants)
    faint=zone&(al<90)
    a[...,3][faint]=0
    # alpha bottom (base)
    al=a[...,3]; ys=np.where((al>128).sum(1)>w*0.12)[0]; base_y=ys.max()
    cols=np.where(al[base_y-5:base_y+1].max(0)>128)[0]
    return a, dict(wood_top=wood_top,wood_bot=wood_bot,body_h=body_h,base_y=base_y,base_x0=int(cols.min()),base_x1=int(cols.max()))

def wood_lum(a):
    wm=wood_mask(a); rgb=a[...,:3][wm]; return (0.299*rgb[:,0]+0.587*rgb[:,1]+0.114*rgb[:,2]).mean()

def render(a,m,gain):
    scale=BODY_H/m['body_h']
    im=Image.fromarray(np.clip(a,0,255).astype(np.uint8),'RGBA')
    nw,nh=int(round(im.width*scale)),int(round(im.height*scale))
    im=im.resize((nw,nh),Image.LANCZOS)
    # gain on rgb only
    arr=np.array(im).astype(np.float32); arr[...,:3]=np.clip(arr[...,:3]*gain,0,255); im=Image.fromarray(arr.astype(np.uint8),'RGBA')
    bx=(m['base_x0']+m['base_x1'])/2*scale; bw=(m['base_x1']-m['base_x0'])*scale; by=m['base_y']*scale
    ox=int(round(CW/2-bx)); oy=int(round(BASE_Y-by))
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
    singles=[]
    for k,(a,m,l) in enumerate(data):
        gain=float(np.clip(med/l,0.94,1.06))
        img,geo=render(a,m,gain); print(srcs[k],'gain',round(gain,3),'geo',geo)
        img.save(f'{out}/single_{k+1}.jpg',quality=94,subsampling=0); singles.append(img)
    gap=36
    col=Image.new('RGB',(CW*3+gap*2,CH),GAP)
    for k,s in enumerate(singles): col.paste(s,(k*(CW+gap),0))
    col.save(f'{out}/collage.jpg',quality=92,subsampling=0)
    col.resize((2400,int(col.height*2400/col.width)),Image.LANCZOS).save(f'{out}/collage_2400.jpg',quality=90)
