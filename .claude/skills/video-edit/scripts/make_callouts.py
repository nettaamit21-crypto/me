"""Keyword callouts over the video (no cutaway): a "selected text box" (dark box, cream frame with corner handles)
or a frosted "glass pill" with an icon. Each callout is rendered to a transparent .mov with the motion-broll engine,
and the script prints the "broll" entries to paste into finish.json.

usage: python3 make_callouts.py callouts.json <outdir> [--W 1080 --H 1920 --fps 25/1]

callouts.json:
[
  {"text": "אוטומטי", "kind": "box", "at": 3.20, "dur": 1.8, "y": 0.17},
  {"text": "בטוח ומקצועי", "kind": "glass", "icon": "shield", "at": 5.10, "dur": 2.0, "y": 0.25}
]
at/dur are on the timeline the callouts go on (the rough cut). y = vertical centre (0..1). Put "at" on the word.
Icons: shield, check, zap, clock, lock, sparkle, star, heart, arrow, file, folder, search, plus, x, terminal, chip.
Rules: a callout is one key word or a 2-3 word phrase that was just said; at most one every few seconds; keep it
clear of the face and of the captions (top third works for a centred speaker).
"""
import argparse, json, pathlib, subprocess, os, sys, html

ENGINE = pathlib.Path(__file__).resolve().parents[2] / 'motion-broll' / 'engine'
EXTRA_ICONS = {
    'shield': ['M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z'],
    'zap': ['M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z'],
    'lock': ['M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2Z', 'M7 11V7a5 5 0 0 1 10 0v4'],
    'star': ['M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z'],
    'heart': ['M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z'],
}

STYLE = """<style>
.cb{position:absolute;left:0;top:0;transform:translate(-50%,-50%)}
.box{position:relative;background:rgba(62,64,70,.9);padding:26px 60px 30px;color:#fff;font-size:88px;font-weight:800;white-space:nowrap;line-height:1.15;
  text-shadow:0 2px 6px rgba(0,0,0,.25)}
.frm{position:absolute;left:-8px;top:-8px;right:-8px;bottom:-8px;border:3px solid #EFE6A2;pointer-events:none}
.hd{position:absolute;width:18px;height:18px;background:#F6F0C4;box-shadow:0 0 0 1.5px #D9CF86;transform:translate(-50%,-50%)}
.gl{display:flex;align-items:center;gap:22px;padding:24px 56px 26px;border-radius:999px;background:rgba(120,120,128,.32);
  box-shadow:inset 0 0 0 2.5px rgba(255,255,255,.6),0 10px 34px rgba(0,0,0,.16);color:#fff;font-size:68px;font-weight:700;white-space:nowrap;
  text-shadow:0 2px 10px rgba(0,0,0,.28)}
</style>"""

def fragment(c, W, H):
    t_in, t_out = 0.0, float(c['dur'])
    text = html.escape(c['text'])
    if c.get('kind', 'box') == 'box':
        body = (f'<div class="cb" id="cb"><div class="box rtl" id="bx">{text}<div class="frm" id="frm">'
                + ''.join(f'<div class="hd" id="h{i}" style="left:{x}%;top:{y}%"></div>' for i, (x, y) in enumerate([(0, 0), (100, 0), (0, 100), (100, 100)]))
                + '</div></div></div>')
        js = f"""
const pop=M.track(0,[[{t_in + 0.02},1,[16,0.82]]]);
const T_OUT={t_out};
M.scene({{W:{W},H:{H},bg:null,T:{t_out + 0.4},intro:null,center:[{W / 2},{H * float(c.get('y', 0.17)):.1f}],
  SH:{{s:{{w:2,h:2,r:1,bg:'#000000',cam:1}}}},start:'s',SEQ:[],
  geom:(t,g)=>{{g.op=0;return g;}},
  extra:(t)=>{{
    const v=M.vis(t,{t_in},T_OUT,{{din:0,lin:0.18,lout:0.22}}), k=Math.max(0,pop(t)), cb=$('cb');
    cb.style.opacity=v.o; cb.style.filter=v.blur>0.05?`blur(${{v.blur}}px)`:'none';
    cb.style.transform=`translate(-50%,-50%) scale(${{(0.9+0.1*k)*(t>T_OUT?1-0.06*M.clamp((t-T_OUT)/0.25):1)}})`;
    const f=M.eio(M.clamp((t-{t_in}-0.12)/0.25)); $('frm').style.opacity=f;
    for(let i=0;i<4;i++){{const h=M.clamp((t-{t_in}-0.18-0.04*i)/0.16); $('h'+i).style.transform=`translate(-50%,-50%) scale(${{M.eio(h)}})`;}}
  }}}});"""
    else:
        icon = c.get('icon')
        ic = f'<span id="ic"></span>' if icon else ''
        body = f'<div class="cb" id="cb"><div class="gl rtl">{ic}<span>{text}</span></div></div>'
        js = f"""
{'M.IC[' + json.dumps(icon) + ']=' + json.dumps(EXTRA_ICONS[icon]) + ';' if icon in EXTRA_ICONS else ''}
{"$('ic').innerHTML=M.icon(" + json.dumps(icon) + ",62,'#fff',3);" if icon else ''}
const T_OUT={t_out};
M.scene({{W:{W},H:{H},bg:null,T:{t_out + 0.4},intro:null,center:[{W / 2},{H * float(c.get('y', 0.25)):.1f}],
  SH:{{s:{{w:2,h:2,r:1,bg:'#000000',cam:1}}}},start:'s',SEQ:[],
  geom:(t,g)=>{{g.op=0;return g;}},
  extra:(t)=>{{
    const v=M.vis(t,{t_in},T_OUT,{{din:0,lin:0.3,lout:0.32}}), cb=$('cb');
    cb.style.opacity=v.o; cb.style.filter=v.blur>0.05?`blur(${{(v.blur*1.6).toFixed(2)}}px)`:'none';
    cb.style.transform=`translate(-50%,calc(-50% + ${{((1-v.a)*16).toFixed(2)}}px))`;
  }}}});"""
    return (f"<title>callout {text}</title>\n{STYLE}\n<div data-slot=\"world\">{body}</div><!--/world-->\n"
            f"<div data-slot=\"shape\"></div><!--/shape-->\n<script>\nconst $=id=>document.getElementById(id);{js}\n</script>\n")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('callouts'); ap.add_argument('outdir')
    ap.add_argument('--W', type=int, default=1080); ap.add_argument('--H', type=int, default=1920); ap.add_argument('--fps', default='25/1')
    a = ap.parse_args()
    out = pathlib.Path(a.outdir); (out / 'src').mkdir(parents=True, exist_ok=True); (out / 'dist').mkdir(exist_ok=True)
    env = {**os.environ, 'NODE_PATH': os.environ.get('NODE_PATH', str(pathlib.Path('motion/node_modules').resolve()))}
    broll = []
    for i, c in enumerate(json.load(open(a.callouts, encoding='utf-8'))):
        name = f"co{i + 1:02d}"
        src = out / 'src' / f'{name}.html'; src.write_text(fragment(c, a.W, a.H), encoding='utf-8')
        subprocess.run([sys.executable, str(ENGINE / 'build.py'), str(out / 'dist'), str(src)], check=True, stdout=subprocess.DEVNULL)
        mov = out / (f"{name}_{int(c['at'] // 60)}m{c['at'] % 60:05.2f}".replace('.', 's') + '.mov')
        subprocess.run(['node', str(ENGINE / 'render.js'), str(out / 'dist' / f'{name}.html'), str(mov), a.fps], check=True, env=env, stdout=subprocess.DEVNULL)
        broll.append({'file': str(mov), 'at': c['at'], 'mode': 'overlay', 'x': 0, 'y': 0, 'fade': 0})
        print(f"{name}: {c.get('kind', 'box')} '{c['text']}' at {c['at']} -> {mov}", file=sys.stderr)
    print(json.dumps(broll, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main()
