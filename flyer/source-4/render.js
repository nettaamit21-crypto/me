const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const dir = process.argv[2], scale = Number(process.argv[3] || 2);
  const browser = await chromium.launch();
  for (const name of process.argv.slice(4)) {
    const page = await browser.newPage({ viewport: { width: 1132, height: 1600 }, deviceScaleFactor: scale });
    await page.goto('file://' + path.join(dir, name + '.html'));
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(200);
    await page.locator('.page').screenshot({ path: path.join(dir, name + '_out.png') });
    await page.close();
  }
  await browser.close();
})();
