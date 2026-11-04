# Card patterns

Every pattern is a **state** of the one continuous shape (`SH` entry + a layer with `tin/tout`). Chain them in the order the speaker talks. Times are rough-cut word times. The working sources are in `../templates/`; copy one into `motion/clips/<series>/`, then change the text, times and colours.

Shared skeleton (all templates use it):

```js
M.scene({
  W:1080, H:460, bg:null, T:<rough length>, intro:<first word>, center:[540,200],
  SH:{ h:{w:860,h:170,r:44,bg:BK,cam:1}, c:{w:780,h:214,r:44,bg:IV,cam:1}, s:{w:680,h:124,r:62,bg:BK,cam:1} },
  start:'h', SEQ:[[t1,'c'],[t2,'s']],
  geom:(t,g)=>{g.cy=TOP+g.h/2; g.fy=0; return g;},   // one top edge: states grow downward, never jump
  layers:[{el:'Lh',tin:intro,tout:t1,anchor:'t'}, …],
  extra:(t)=>{ /* per-item pop-ins: M.vis(t, wordTime, null, {din:0, lin:0.22}) */ },
  cursor:{size:42, clicks:[…], keys:[[0,300,360], …]},   // rest the cursor off-stage (y beyond the stage height)
});
```
CSS that every card shares: `html.alpha #shape{box-shadow:0 0 0 2px rgba(201,162,77,.9),0 16px 46px rgba(0,0,0,.35)}` (gold hairline + drop shadow), `.sf{font-family:'Liberation Serif',Georgia,serif;font-style:italic}`.

Item pop-in used everywhere (blur in, rise 10 px, a 6% scale breath, chips get a gold flash):
```js
const v=M.vis(t,ti,null,{din:0,lin:0.22}); e.style.opacity=v.o; e.style.filter=v.blur>0.05?`blur(${v.blur}px)`:'none';
const k=M.clamp((t-ti)/0.35); e.style.transform=`translateY(${((1-v.a)*10).toFixed(1)}px) scale(${(1+0.06*Math.sin(Math.PI*k)).toFixed(3)})`;
```

| Pattern | Use it when the speaker… | Look | Lands on | Template |
|---|---|---|---|---|
| **Hook card** | opens with a promise/teaser | ink card, serif italic line in ivory, second line in gold (or a big gold serif number + sans title) | intro on the first word, line 2 on its first word | all |
| **Not-about chip** | dismisses something ("nothing to do with how she looks") | ivory pill, "Almost nothing to do with" + chip, strike-through | chip on the noun, strike on the next beat | story-calendar |
| **List with chips** | lists things under one heading ("never ask him for his effort / time / a date") | ivory card, ink ✕/number circle + title, gold-outline chips in a row | each chip on its noun | story-list-quote-compare, signs-tracker-chips |
| **Numbered tips** | counts tips/signs/rules ("1. … 2. …") | ivory card: ink circle with gold serif number, tip title, progress bar (one segment per tip); width follows the title | each state on the spoken number | `scripts/make_tips_card.py` |
| **Signs tracker** | a few numbered signs, each with sub-points | numbered title row + chips per sign; a small pill rests between signs | number on the number, chips on their words | signs-tracker-chips |
| **Quote** | says the key line ("a man who needs a reminder to love you…") | ink card, two serif italic lines, one gold key word per line, a gold ” mark | line 1 on its first word, line 2 on its first word | story-list-quote-compare, story-calendar |
| **Compare / truth vs act** | contrasts two things ("what he does without being asked is who he is; everything else is performance") | ivory card, two rows split by a gold rule: left label, right chip (gold fill = truth, outlined + struck = the fake) | left on its word, right on its word, rule draws before row 2 | story-list-quote-compare, story-calendar |
| **Checklist** | gives do/don't actions | ivory card, rows with an ink ✓ (gold check) or a grey ✕ (struck text) | each row on its verb | story-calendar |
| **Calendar story** | describes a life/routine and a man entering it | ivory "Her life" card: header chips (Standards, 🔒 Her time & energy), day blocks with a gold edge; a dashed "Him" block arrives offset, shakes on "doesn't clear the calendar", settles on "makes room", fills gold on "worth room" | each block on its phrase | story-calendar |
| **Eye pill** | "sit back and watch" moments | small ivory pill with an ink eye icon + serif text | on the phrase | story-list-quote-compare |
| **A vs B choice** | a dilemma between two options/men | ink hook with A/B rows; ivory card with two columns and live heartbeat traces (A fast and irregular, B slow and steady); reframe rows (struck word → gold word); ink poll card "Love him more / Be loved more" | each row/chip on its words | `templates/ab-choice.html` |
| **2 AM message** | describes him texting/typing back ("he'll be the one awake at 2 AM typing: I made a mistake") | ink card: muted "2:00 AM", avatar + "Him", typing dots bubble on "typing", then an ivory message bubble with his words | dots on "typing", message on its first word | `templates/late-message.html` |
| **Follow** | "follow me…" | ink pill "Follow for more" + ivory button → gold "✓ Following" on a cursor click | click on "follow" | all |
| **Send** | "send this to…" | ink pill, gold-outline send icon fills gold on a cursor click, "Send this" + muted subline | click on "send" | all |
| **Zodiac coin** | names zodiac signs | 3D gold coin flipping to each sign's glyph, on the chest | each flip on the sign's word | zodiac-coin-3d |

## Windows: the card only on the meaningful lines (30-40% of the runtime)
```js
const WIN=[[0.2,5.0],[20.2,28.5],[41.05,48.2],[60.25,67.96]];        // hook, the load list, the contrast, quote + CTA
const onScreen=t=>{for(const [a,b] of WIN){if(t>=a-0.01&&t<=b+0.35)
  return Math.min(M.eio(M.clamp((t-a)/0.3)),1-M.eio(M.clamp((t-b)/0.3)));} return 0;};
// in M.scene:
geom:(t,g)=>{g.cy=TOP+g.h/2; g.fy=0; const k=onScreen(t); g.op*=k; g.sc*=0.9+0.1*k; return g;},
SEQ:[[19.4,'l'],[40.3,'g'],[59.5,'q'],[64.38,'s']],                   // switch states while hidden, ~0.7 s before each window
```
Layers of states you dropped: hide them with CSS (`#La,#Lw{display:none}`), since a layer not listed in `layers` stays visible. Working example: `motion/clips/series-alone/01-doing-it-alone.html`.

## Icons
`M.IC` has arrow, check, x, plus, folder, terminal, file, pencil, coin, clock, chip, sparkle, castle, search. The templates add (Lucide, ISC): `send`, `eye`, `heart`, `lock`. Copy their path arrays when needed.

## Sizes that work on 1080x1920
- Title text 38-42 px bold; chips 28-30 px in 56-60 px pills; quote lines 44-46 px serif italic; tip numbers 64 px serif in a 112 px circle; hook number 150 px.
- Card widths 700-920 px (keep ≥ 80 px from the frame edges); heights: pill 104-124, card 160-240, tall card (4 rows) 364-388.
- A one-line title needs about `21 px × characters + 210 px` of card width at 40 px.

## Placement
Stage top at y ≈ 1060-1120. The captions (`--below-face`) sit around y 0.45-0.55 (≈ 860-1060), so the card's top edge sits just under them. Check one still at the tallest caption (two lines) over the tallest card state.
