"""Generate a numbered-tips tracker clip ("10 things", "5 signs", "3 rules") from a small JSON spec.

usage: python3 make_tips_card.py spec.json motion/clips/<series>/01-tips.html
then:  python3 $MB/engine/build.py motion/dist motion/clips/<series>/01-tips.html
       NODE_PATH=./motion/node_modules node $MB/engine/render.js motion/dist/01-tips.html motion/<v>/out/tips_0m00s00.mov 25/1

One shape for the whole video: a dark hook card, then one ivory card per tip (gold number in an ink circle,
the tip title, a progress bar with one segment per tip), then a "Send this" pill with a click and a Follow
button that turns into "Following". The card width follows each title, so every tip change is a small morph.

spec.json (all times on the rough-cut timeline, each one ON the spoken word):
{
  "T": 56.16,                                   # rough-cut length (add the end hold if grade.sh adds one)
  "colors": {"ink": "#0B0B0C", "gold": "#C9A24D", "gold_light": "#E2C27A", "ivory": "#F5F1E8", "muted": "#8E8778"},
  "hook": {"at": 0.45, "big": "10", "line": "things every woman needs to know",
           "sub": {"at": 2.99, "html": "<b>Number 9</b> will make some men angry"}},     # sub is optional
  "tips": [{"at": 5.18, "title": "Never teach him to love you"}, ...],                  # "at" = the spoken number
  "send": {"at": 52.40, "click": 52.75, "title": "Send this", "sub": "to a woman who needs number 10"},
  "follow": {"at": 55.10, "click": 55.45, "label": "Follow for more"}                   # optional
}
Titles: 2-6 words, shortened from the speaker's own line (never new claims). Keep them under ~32 characters.
Stage is 1080x420; overlay it at y ~1100-1120 on a 1080x1920 video (the lap/table area, below the captions).
"""
import json, sys, html as H

def main():
    spec = json.load(open(sys.argv[1], encoding='utf-8')); out = sys.argv[2]
    C = {'ink': '#0B0B0C', 'gold': '#C9A24D', 'gold_light': '#E2C27A', 'ivory': '#F5F1E8', 'muted': '#8E8778', **spec.get('colors', {})}
    tips = spec['tips']; n = len(tips); NUM = [t['at'] for t in tips]
    hook = spec['hook']; send = spec['send']; fol = spec.get('follow'); T = spec['T']
    SEND = send['at']; FOL = fol['at'] if fol else None
    GR = ','.join(str(int(C['gold'].lstrip('#')[i:i + 2], 16)) for i in (0, 2, 4))
    seg_w = max(20, min(44, (520 - 8 * (n - 1)) // n))
    layers = ''.join(f'<div class="L" id="L{i}"><div class="nc" id="n{i}"><span class="sf">{i + 1}</span></div>'
                     f'<div class="tt">{H.escape(t["title"])}</div></div>\n  ' for i, t in enumerate(tips))
    W = [max(700, 210 + len(t['title']) * 21) for t in tips]
    SH = ','.join(f"t{i}:{{w:{W[i]},h:160,r:40,bg:IV,cam:1}}" for i in range(n))
    seq = [f"[{NUM[i]},'t{i}']" for i in range(n)] + [f"[{SEND},'s']"] + ([f"[{FOL},'f']"] if fol else [])
    lay = ',\n    '.join(f"{{el:'L{i}',tin:{NUM[i]},tout:{NUM[i + 1] if i < n - 1 else SEND},anchor:'l'}}" for i in range(n))
    sub = hook.get('sub')
    clicks = [send['click']] + ([fol['click']] if fol else [])
    keys = [[0, 320, 330], [send['click'] - 0.45, 320, 330], [send['click'] - 0.15, -294, 14], [send['click'] + 0.1, -294, 14]]
    if fol: keys += [[fol['click'] - 0.55, 196, 14], [fol['click'] + 0.1, 196, 14]]
    keys += [[T - 0.05, 300, 330]]
    sub_html = f'<div class="h2" id="h2">{sub["html"]}</div>' if sub else ''
    sub_js = f"update:(t)=>{{const v=M.vis(t,{sub['at']},null,{{din:0,lin:0.3}}); M.apply($('h2'),v);}}" if sub else ''
    fol_html = ('<div class="L" id="Lf"><div class="nm">' + H.escape(fol.get('label', 'Follow for more')) +
                '</div><div class="bt" id="bt"><span id="icK"></span><span id="bl">Follow</span></div></div>') if fol else ''
    fc = fol['click'] + 0.03 if fol else 0
    fol_js = (f",\n    {{el:'Lf',tin:{FOL},tout:null,update:(t)=>{{const k=M.clamp(fol(t)), b=$('bt').style; b.background=k>0.5?GD:IV; b.color=BK;"
              f" M.setText($('bl'),t<{fc}?'Follow':'Following'); $('icK').innerHTML=t<{fc}?'':M.icon('check',26,BK,3.4); $('icK').style.display=t<{fc}?'none':'';}}}}") if fol else ''
    page = f'''<title>{H.escape(hook.get('big', ''))} {H.escape(hook['line'])}</title>
<style>
html.alpha #shape{{box-shadow:0 0 0 2px {C['gold']}e6,0 16px 46px rgba(0,0,0,.35)}}
.sf{{font-family:'Liberation Serif',Georgia,serif;font-style:italic}}
.nc{{position:absolute;left:24px;top:-56px;width:112px;height:112px;border-radius:56px;background:{C['ink']};display:flex;align-items:center;justify-content:center;color:{C['gold_light']};font-size:64px;line-height:1}}
.nc span{{transform:translateY(-3px)}}
.tt{{position:absolute;left:162px;top:-46px;font-size:40px;font-weight:700;color:{C['ink']};white-space:nowrap;letter-spacing:-.01em}}
.pb{{position:absolute;left:162px;top:20px;display:flex;gap:8px}}
.sg{{width:{seg_w}px;height:8px;border-radius:4px;background:#E4DCCB;overflow:hidden}}
.sg i{{display:block;height:100%;width:0;background:{C['gold']}}}
.hn{{position:absolute;left:-422px;top:-74px;font-size:150px;line-height:1;color:{C['gold_light']}}}
.h1{{position:absolute;left:-245px;top:-48px;font-size:38px;font-weight:700;color:{C['ivory']};white-space:nowrap}}
.h2{{position:absolute;left:-245px;top:10px;font-size:30px;font-weight:500;color:{C['muted']};white-space:nowrap}}
.h2 b{{color:{C['gold_light']};font-weight:600}}
.nm{{position:absolute;left:-290px;top:-26px;color:{C['ivory']};font-size:38px;font-weight:600;white-space:nowrap}}
.bt{{position:absolute;left:84px;top:-33px;width:226px;height:66px;border-radius:33px;display:flex;align-items:center;justify-content:center;gap:10px;font-size:30px;font-weight:600}}
.sic{{position:absolute;left:-330px;top:-36px;width:72px;height:72px;border-radius:36px;display:flex;align-items:center;justify-content:center}}
.sa{{position:absolute;left:-236px;top:-40px;font-size:40px;font-weight:600;color:{C['ivory']};white-space:nowrap}}
.sbb{{position:absolute;left:-236px;top:6px;font-size:26px;font-weight:500;color:{C['muted']};white-space:nowrap}}
</style>
<div data-slot="shape">
  <div class="L" id="Lh"><div class="hn sf">{H.escape(hook.get('big', ''))}</div><div class="h1">{H.escape(hook['line'])}</div>
    {sub_html}</div>
  {layers}<div class="L" id="Lp"><div class="pb">{''.join(f'<div class="sg"><i id="g{i}"></i></div>' for i in range(n))}</div></div>
  <div class="L" id="Ls"><div class="sic" id="sic"></div><div class="sa">{H.escape(send.get('title', 'Send this'))}</div><div class="sbb">{H.escape(send.get('sub', ''))}</div></div>
  {fol_html}
</div><!--/shape-->
<script>
const $=id=>document.getElementById(id);
M.IC.send=['M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z','m21.854 2.147-10.94 10.939'];
const NUM={json.dumps(NUM)};
const snd=M.track(0,[[{send['click']},1,[20,0.78]]]){f", fol=M.track(0,[[{fol['click']},1,[20,0.78]]])" if fol else ''};
const IV='{C['ivory']}', BK='{C['ink']}', GD='{C['gold']}';
M.scene({{
  W:1080,H:420,bg:null,T:{T},intro:{hook['at']},center:[540,190],
  SH:{{h:{{w:920,h:190,r:44,bg:BK,cam:1}},{SH},s:{{w:740,h:124,r:62,bg:BK,cam:1}},f:{{w:660,h:124,r:62,bg:BK,cam:1}}}},
  start:'h', SEQ:[{','.join(seq)}],
  // all states hang from one top edge so the card grows downward and never jumps
  geom:(t,g)=>{{g.cy=-85+g.h/2; g.fy=0; return g;}},
  layers:[
    {{el:'Lh',tin:{hook['at']},tout:{NUM[0]}{',' + sub_js if sub else ''}}},
    {lay},
    {{el:'Lp',tin:{NUM[0]},tout:{SEND},anchor:'l'}},
    {{el:'Ls',tin:{SEND},tout:{FOL if fol else 'null'},update:(t)=>{{const k=M.clamp(snd(t)), s=$('sic').style; s.background=`rgba({GR},${{k.toFixed(3)}})`;
      s.boxShadow=`inset 0 0 0 2px rgba({GR},${{(1-k).toFixed(3)}})`; $('sic').innerHTML=M.icon('send',36,k>0.5?BK:GD,2.6);}}}}{fol_js}
  ],
  extra:(t)=>{{
    for(let i=0;i<NUM.length;i++){{
      $('g'+i).style.width=(100*M.eio(M.clamp((t-NUM[i]-0.1)/0.45))).toFixed(1)+'%';
      const k=M.S(t-NUM[i],16,0.7); $('n'+i).style.transform=`scale(${{(0.6+0.4*Math.max(0,k)).toFixed(3)}})`;}}
  }},
  cursor:{{size:42,clicks:{json.dumps(clicks)},keys:{json.dumps([[round(x, 2) for x in k] for k in keys])}}},
}});
</script>
'''
    import os; os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, 'w', encoding='utf-8').write(page)
    print(f'{n} tips, widths {W} -> {out}')

if __name__ == '__main__':
    main()
