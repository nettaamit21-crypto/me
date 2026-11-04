// Render static graphic sprites (text blocks, cards, tags, UI panels) from HTML to transparent PNGs, with Heebo
// (Hebrew/Latin, OFL) loaded from the hebrew-captions fonts. Animate them afterwards in Python (position, scale,
// opacity, blur), which is much faster than rendering every frame in a browser.
// usage: NODE_PATH=./motion/node_modules node sprites.js sprites.json <outdir>
// sprites.json: {"css": "shared CSS", "sprites": [{"name": "hook", "html": "<div class=big>…</div>"}, …]}
// Each sprite is laid out inline-block at its natural size (add padding in CSS for shadows/glow) and cropped to it.
const {chromium} = require('playwright'); const fs = require('fs'); const path = require('path');
(async () => {
  const [spec, out] = process.argv.slice(2); const S = JSON.parse(fs.readFileSync(spec, 'utf8'));
  fs.mkdirSync(out, {recursive: true});
  const F = path.resolve(__dirname, '../../hebrew-captions/fonts');
  const face = (w, f) => `@font-face{font-family:'Heebo';font-weight:${w};src:url('file://${F}/${f}')}`;
  const head = `<meta charset="utf-8"><style>${face(500, 'Heebo-Medium.ttf')}${face(700, 'Heebo-Bold.ttf')}${face(900, 'Heebo-Black.ttf')}
    html,body{margin:0;background:transparent}body{font-family:'Heebo',sans-serif;-webkit-font-smoothing:antialiased}
    #s{display:inline-block}${S.css || ''}</style>`;
  const b = await chromium.launch(); const p = await b.newPage({viewport: {width: 2400, height: 1600}, deviceScaleFactor: 1});
  for (const s of S.sprites) {
    await p.setContent(`<!doctype html><html><head>${head}</head><body><div id="s">${s.html}</div></body></html>`);
    await p.evaluate(() => document.fonts.ready);
    const el = await p.$('#s'); await el.screenshot({path: path.join(out, s.name + '.png'), omitBackground: true});
  }
  await b.close(); console.log(S.sprites.length, 'sprites ->', out);
})();
