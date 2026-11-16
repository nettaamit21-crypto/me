const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const dir = process.argv[2], scale = Number(process.argv[3] || 1), out = process.argv[4] || 'wood_out.png';
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1132, height: 1600 }, deviceScaleFactor: scale });
  await page.goto('file://' + path.join(dir, 'wood.html'));
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(200);
  await page.locator('.page').screenshot({ path: path.join(dir, out) });
  await browser.close();
})();
