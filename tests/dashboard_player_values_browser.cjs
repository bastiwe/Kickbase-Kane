const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.route('**/api/**', r => r.fulfill({json: {series: [], managers: [], transfers: []}}));
  await page.goto(process.env.DASHBOARD_TEST_URL);

  assert.equal(await page.locator('#metric-roster-count').innerText(), '8/16 Spieler');
  assert.equal(await page.locator('#roster-movers [data-player-id="open-bid"]').count(), 0);
  assert.equal(await page.locator('#market-table [data-player-id="open-bid"]').count(), 1);
  const layoutRoster = await page.evaluate(() => {
    const source = {report: JSON.parse(document.getElementById('data').textContent), api: {}};
    window.KaneLayout.enrich(source);
    return {count: source.dashboard['Kadergröße'], value: source.dashboard['Kaderwert'],
            rows: window.KaneLayout.sectionItems(source, 'roster').length};
  });
  assert.deepEqual(layoutRoster, {count: 8, value: 86419746, rows: 8});
  const tones = ['certain', 'expected', 'uncertain', 'unlikely', 'excluded', 'unknown', 'unknown', 'certain'];
  for (let index = 0; index < tones.length; index++) {
    const row = page.locator(`#roster-movers [data-player-id="${index}"]`);
    assert.equal(await row.locator(`.lineup-symbol.${tones[index]}`).count(), 1);
    const text = (await row.locator('.player-market-value').innerText()).replace(/\s/g, '');
    assert.equal(text, index === 7 ? 'MW–' : 'MW12.345.678€');
    const li = await row.locator('.lineup-li').innerText();
    assert(index === 5 || index === 6 ? li.includes('LI –') : li.includes('%'));
  }
  assert.equal(await page.locator('#timing-risks .player-market-value').count(), 3);
  assert((await page.locator('#timing-risks .player-market-value').first().innerText()).includes('12.345.678'));
  fs.mkdirSync('test-output', {recursive: true});
  for (const width of [320, 390, 768, 1024, 1440]) {
    await page.setViewportSize({width, height: 1000});
    const geometry = await page.evaluate(() => {
      const visible = [...document.querySelectorAll('#roster-movers .lineup-li,#roster-movers .player-market-value,#timing-risks .player-market-value')];
      return {
        pageFits: document.documentElement.scrollWidth <= innerWidth,
        valuesFit: visible.every(el => {
          const bounds = el.getBoundingClientRect(), parent = el.closest('.list-row').getBoundingClientRect();
          return el.scrollWidth <= el.clientWidth + 1 && bounds.right <= parent.right && bounds.left >= parent.left;
        }),
      };
    });
    assert(geometry.pageFits && geometry.valuesFit, `Values must fit at ${width}: ${JSON.stringify(geometry)}`);
    if (width === 390 || width === 1440) {
      await page.locator('.roster-player').first().screenshot({path: `test-output/dashboard-roster-values-${width}.png`});
      await page.locator('.risk-player').first().screenshot({path: `test-output/dashboard-risk-values-${width}.png`});
    }
  }
  await page.locator('.roster-player summary').first().click();
  assert(await page.locator('.roster-player').first().getAttribute('open') !== null);
  assert.deepEqual(errors, []);
  await browser.close();
  console.log('Dashboard player values: LI boundaries, missing values and 5 viewport widths passed.');
})().catch(error => {console.error(error); process.exit(1);});
