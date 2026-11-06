const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.route('**/api/current-lineup', r => r.fulfill({json: {players: []}}));
  await page.goto(process.env.PLANNER_TEST_URL + '/planner');
  await page.locator('[data-form="4-4-2"]').click();
  await page.locator('.slot .card').first().waitFor();
  fs.mkdirSync('test-output', {recursive: true});
  for (const width of [320, 360, 390, 430, 768, 899, 900, 1400]) {
    await page.setViewportSize({width, height: 900});
    for (const formation of ['4-4-2', '5-3-2', '3-6-1']) {
      await page.locator(`[data-form="${formation}"]`).click();
      const layout = await page.evaluate(() => {
        const rect = el => el.getBoundingClientRect();
        const pitch = rect(document.querySelector('#slots'));
        const lines = [...document.querySelectorAll('.formation-line')];
        return {
          overflow: document.documentElement.scrollWidth > innerWidth,
          overlayHeight: rect(document.querySelector('#overlay')).height,
          limitInOverlay: !!document.querySelector('#overlay #deficit-form'),
          limitAboveForms: rect(document.querySelector('#deficit-form')).bottom <= rect(document.querySelector('#forms')).top,
          rows: lines.every(line => {
            const slots = [...line.children].map(rect);
            return slots.every((r, i) => Math.abs(r.top - slots[0].top) < 1 && r.left >= pitch.left && r.right <= pitch.right && (!i || r.left >= slots[i - 1].right));
          }),
          attackAboveKeeper: rect(document.querySelector('.formation-4')).top < rect(document.querySelector('.formation-1')).top,
        };
      });
      assert(!layout.overflow, `${width} ${formation}: page overflow`);
      assert(layout.rows && layout.attackAboveKeeper, `${width} ${formation}: formation geometry`);
      assert(!layout.limitInOverlay && layout.limitAboveForms, 'Limit must precede formations outside sticky budget');
      assert(layout.overlayHeight < 125, `${width}: compact budget`);
    }
    if (width === 390 || width === 1400) {
      await page.locator('[data-form="4-4-2"]').click();
      await page.locator('.lineup-box').screenshot({path: `test-output/planner-pitch-${width}.png`, style: ".top,.overlay,.toast{visibility:hidden!important}"});
    }
  }
  await page.setViewportSize({width: 390, height: 844});
  await page.locator('#deficit').fill('0');
  await page.locator('#deficit-form button').click();
  assert((await page.locator('#deficit-active').innerText()).includes('0'));
  await page.locator('.slot .lineup-name').first().click();
  await page.locator('.slot.empty').first().click();
  await page.locator('#candidate-dialog').waitFor({state: 'visible'});
  await page.locator('[data-candidate]').first().click();
  assert.equal(await page.locator('.slot.empty').count(), 0);
  assert.deepEqual(errors, []);
  await browser.close();
  console.log('Planner layout: 8 viewport widths, 3 formations, budget and player replacement passed.');
})().catch(e => { console.error(e); process.exit(1); });
