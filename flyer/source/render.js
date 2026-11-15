const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const dir = process.argv[2];
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 560, height: 794 }, deviceScaleFactor: 3.125 });
  await page.goto('file://' + path.join(dir, 'flyer.html'));
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
  await page.locator('.page').screenshot({ path: path.join(dir, 'flyer.png') });
  await page.pdf({ path: path.join(dir, 'flyer.pdf'), width: '148mm', height: '210mm', printBackground: true });
  await browser.close();
  console.log('done');
})();
