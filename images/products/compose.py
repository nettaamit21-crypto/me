"""Product-photo composer: cutout (RGBA) -> textured warm backdrop + natural directional shadow.
usage: compose2.py OUT_DIR src1.png src2.png src3.png   (suffix '^' = may run off the top edge)
env: ERASE='{"<idx>":[[x0,y0,x1,y1,"all"|"grey"|"pale"|"brass"],...]}' canvas-space cleanups; SEED=int"""
import sys, os, json, numpy as np
from PIL import Image, ImageFilter, ImageDraw
CW,CH=1080,1350
BASE_Y=int(CH*0.83); BODY_H=int(CH*0.33)
GAP=(226,218,204)
SEED=int(os.environ.get('SEED','7'))

# ---------- backdrop ----------
def backdrop(seed):
    rng=np.random.default_rng(seed)
    y=np.linspace(0,1,CH)[:,None]; x=np.linspace(0,1,CW)[None,:]
    top=np.array([246,242,235],np.float32); bot=np.array([236,229,217],np.float32)   # warm bone -> pale clay
    img=np.broadcast_to(top*(1-y)[...,None]+bot*y[...,None],(CH,CW,3)).copy()
    img+= (x-0.5)[...,None]*np.array([3,2,0],np.float32)                              # faint left/right light falloff
    # soft mottling (plaster / paper), two octaves
    for size,amp in ((18,1.6),(90,2.2)):
        n=rng.standard_normal((CH//size+2,CW//size+2))
        n=Image.fromarray(np.clip(n*40+128,0,255).astype(np.uint8),'L').resize((CW,CH),Image.BICUBIC)
        n=(np.array(n.filter(ImageFilter.GaussianBlur(size*0.35)),np.float32)-128)/40
        img+= (n*amp)[...,None]*np.array([1.0,0.9,0.75],np.float32)
    return np.clip(img,0,255)

def grain(img,rng,sigma=1.8):
    n=rng.standard_normal(img.shape[:2]).astype(np.float32)*sigma
    return np.clip(img+n[...,None]*np.array([1.0,0.95,0.9],np.float32),0,255)

# ---------- cutout analysis ----------
def load(path): return np.array(Image.open(path).convert('RGBA')).astype(np.float32)

def analyse(a):
    al=a[...,3]; w=a.shape[1]; rows=(al>200).sum(1)
    ys=np.where(rows>w*0.12)[0]; cuts=np.where(np.diff(ys)>1)[0]; body=max(np.split(ys,cuts+1),key=len)
    wood_top,wood_bot=int(body.min()),int(body.max())
    base_y=wood_bot
    cols=np.where(al[base_y-5:base_y+1].max(0)>128)[0]
    top_rows=np.where((al>40).sum(1)>6)[0]
    return dict(wood_top=wood_top,base_y=base_y,body_h=wood_bot-wood_top,base_x0=int(cols.min()),base_x1=int(cols.max()),top=int(top_rows.min()))

def clean(a,m):
    """drop red tool remnants above the body; feather alpha slightly"""
    r,g,b,al=a[...,0],a[...,1],a[...,2],a[...,3]
    zone=np.zeros(al.shape,bool); zone[:m['wood_top']]=True
    al[zone&(r>g+50)&(r>b+50)]=0
    cool=zone&(al>0)&((r-b)<15)                      # stems that picked up the wall's cool cast: nudge warm
    a[...,0][cool]=np.clip(r[cool]*1.06,0,255); a[...,2][cool]=b[cool]*0.92
    al_img=Image.fromarray(al.astype(np.uint8),'L').filter(ImageFilter.GaussianBlur(0.7))
    a[...,3]=np.array(al_img,np.float32)
    return a

def wood_lum(a,m):
    wm=(a[...,3]>200)&(a[...,0]>a[...,2]); wm[:m['wood_top']]=False
    rgb=a[...,:3][wm]; return float((0.299*rgb[:,0]+0.587*rgb[:,1]+0.114*rgb[:,2]).mean())

# ---------- shadow ----------
def shadow_layer(alpha_canvas,bx,by,body_top_y):
    """soft directional shadow cast by the object's own silhouette, anchored on its bottom contour.
    light from behind-right -> shadow toward the viewer and to the left."""
    H,W=alpha_canvas.shape
    A=alpha_canvas/255.0
    ys,xs=np.nonzero(A>0.05)
    # bottom contour per column (lowest opaque pixel), smoothed
    bottom=np.full(W,-1.0)
    y0=int(body_top_y)                                # contour from the body only, never from the stems
    for x in np.unique(xs):
        col=np.where(A[y0:,x]>0.5)[0]
        if len(col)>8: bottom[x]=col.max()+y0
    known=bottom>=0
    if known.sum()>2:
        xi=np.arange(W); bottom=np.interp(xi,xi[known],bottom[known])
    h=bottom[xs]-ys                                   # height of the pixel above the table
    h=np.clip(h,0,None)
    tx=xs-0.62*h; ty=bottom[xs]+0.26*h                # shear left, compress toward the viewer
    ti=np.clip(np.round(ty).astype(int),0,H-1); tj=np.clip(np.round(tx).astype(int),0,W-1)
    w=A[ys,xs]*np.clip(1.0-h/((by-body_top_y)*2.2),0.12,1.0)   # farther = lighter
    sh=np.zeros((H,W),np.float32); np.add.at(sh,(ti,tj),w); sh=np.clip(sh,0,1)
    # fill splat holes and soften: near part crisper, far part softer
    im=Image.fromarray((sh*255).astype(np.uint8),'L')
    near=np.array(im.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(9)),np.float32)/255
    far=np.array(im.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(32)),np.float32)/255
    dist=np.zeros((H,W),np.float32); dist[ti,tj]=h; dist=np.array(Image.fromarray(np.clip(dist/4,0,255).astype(np.uint8),'L').filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(12)),np.float32)*4
    t=np.clip(dist/((by-body_top_y)*1.0),0,1)
    sh=near*(1-t)+far*t
    # contact shadow: thin dark seam along the bottom contour
    c=np.zeros((H,W),np.float32)
    for x in np.where(known)[0]:
        yb=int(bottom[x]); c[max(0,yb-2):min(H,yb+5),x]=1.0
    c=np.array(Image.fromarray((c*255).astype(np.uint8),'L').filter(ImageFilter.GaussianBlur(5)),np.float32)/255
    return np.clip(sh*0.42+c*0.6,0,1)

# ---------- render ----------
def render(a,m,gain,body_h,erase,rng):
    scale=body_h/m['body_h']
    im=Image.fromarray(np.clip(a,0,255).astype(np.uint8),'RGBA')
    nw,nh=int(round(im.width*scale)),int(round(im.height*scale))
    im=im.resize((nw,nh),Image.LANCZOS)
    arr=np.array(im).astype(np.float32); arr[...,:3]=np.clip(arr[...,:3]*gain,0,255)
    bx=(m['base_x0']+m['base_x1'])/2*scale; by=m['base_y']*scale
    ox=int(round(CW/2-bx)); oy=int(round(BASE_Y-by))
    if erase:
        for x0,y0,x1,y1,mode in erase:
            X0,Y0,X1,Y1=max(0,x0-ox),max(0,y0-oy),min(nw,x1-ox),min(nh,y1-oy)
            sub=arr[Y0:Y1,X0:X1]; lum=0.299*sub[...,0]+0.587*sub[...,1]+0.114*sub[...,2]
            if mode=='all': sub[...,3]=0
            elif mode=='grey': sub[...,3][(sub[...,0]-sub[...,2])<45]=0
            elif mode=='pale': sub[...,3][(lum>118)&((sub[...,0]-sub[...,2])<85)]=0
            elif mode=='handle': sub[...,3][(lum>140)&((sub[...,0]-sub[...,1])<14)]=0   # pale brass tool handle, not golden grass
            elif mode=='brass': sub[...,3][(lum>150)|(sub[...,1]>=sub[...,0])|((sub[...,0]-sub[...,2])<45)]=0
    # place object on a transparent canvas (may overflow edges)
    obj=np.zeros((CH,CW,4),np.float32)
    x0,y0=max(0,ox),max(0,oy); x1,y1=min(CW,ox+nw),min(CH,oy+nh)
    obj[y0:y1,x0:x1]=arr[y0-oy:y1-oy,x0-ox:x1-ox]
    bg=backdrop(SEED)
    sh=shadow_layer(obj[...,3],CW/2,BASE_Y,BASE_Y-body_h)
    tint=np.array([88,72,58],np.float32)
    bg=bg*(1-sh[...,None]*0.7)+tint*(sh[...,None]*0.7)
    al=(obj[...,3]/255.0)[...,None]
    out=bg*(1-al)+obj[...,:3]*al
    out=Image.fromarray(out.astype(np.uint8),'RGB').filter(ImageFilter.UnsharpMask(radius=1.1,percent=85,threshold=2))
    out=grain(np.array(out).astype(np.float32),rng)
    return Image.fromarray(out.astype(np.uint8),'RGB')

if __name__=='__main__':
    out=sys.argv[1]; srcs=sys.argv[2:]; rng=np.random.default_rng(SEED)
    erase_all=json.loads(os.environ.get('ERASE','{}'))
    data=[]
    for p in srcs:
        overflow=p.endswith('^'); p=p.rstrip('^')
        a=load(p); m=analyse(a); a=clean(a,m); data.append((a,m,wood_lum(a,m),overflow))
    med=float(np.median([d[2] for d in data]))
    body_h=BODY_H
    for a,m,l,ov in data:
        if ov: continue
        avail=BASE_Y-int(CH*0.05); need=(m['base_y']-m['top'])/m['body_h']
        body_h=min(body_h,int(avail/need))
    print('body_h',body_h)
    singles=[]
    for k,(a,m,l,ov) in enumerate(data):
        gain=float(np.clip(med/l,0.94,1.06))
        img=render(a,m,gain,body_h,erase_all.get(str(k),()),np.random.default_rng(SEED+k))
        img.save(f'{out}/single_{k+1}.jpg',quality=94,subsampling=0); singles.append(img); print(srcs[k],'gain',round(gain,3))
    gap=36
    col=Image.new('RGB',(CW*3+gap*2,CH),GAP)
    for k,s in enumerate(singles): col.paste(s,(k*(CW+gap),0))
    col.save(f'{out}/collage.jpg',quality=92,subsampling=0)
    col.resize((2400,int(col.height*2400/col.width)),Image.LANCZOS).save(f'{out}/collage_2400.jpg',quality=90)
