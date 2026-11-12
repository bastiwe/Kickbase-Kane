const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.route('**/api/**', r => r.fulfill({json: {series: [], managers: [], transfers: []}}));
  await page.route('**/api/manager-budgets', r => r.fulfill({json: {managers: [
    {name: 'Voller Kader', cash: 5123456, squadValue: 199999999, buyingPower: 71123456, squadSize: 16, squadLimit: 16,
      clubLimits: [{name: 'Bayern München', count: 3, limit: 3}, {name: 'Stuttgart', count: 4, limit: 3}]},
    {name: 'Freie Plätze', squadSize: 14, squadLimit: 16, clubLimits: []},
  ]}}));
  await page.route('**/api/big-market-players', r => r.fulfill({json: {players: [
    {id: 'live-elite', name: 'Live Transferangebot', team: 'Stuttgart', position: 4, mv: 42500000},
  ]}}));
  await page.goto(process.env.DASHBOARD_TEST_URL);
  const managerCards = page.locator('.manager-budget-card');
  await managerCards.last().waitFor();
  assert.match(await managerCards.first().innerText(), /Kadergröße\s+16\/16/);
  assert.match(await managerCards.last().innerText(), /Kadergröße\s+14\/16/);
  assert.deepEqual(await managerCards.first().locator('.manager-club-limits li').allTextContents(),
    ['3/3 Bayern München', '4/3 Stuttgart']);
  assert.equal(await managerCards.last().locator('.manager-club-limits').count(), 0);
  await page.locator('#big-market-players .big-boy-card').waitFor();
  assert.match(await page.locator('#big-market-players').innerText(), /Live Transferangebot[\s\S]*42\.500\.000/);
  assert.equal(await page.locator('#market-table [data-player-id="live-elite"]').count(), 0);

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
        bigBoysPosition: (() => {
          const big = document.querySelector('.big-boys-panel').getBoundingClientRect();
          const squad = document.querySelector('.metric-squad').getBoundingClientRect();
          const budget = document.querySelector('.metric-budget').getBoundingClientRect();
          if (innerWidth <= 820) return big.bottom <= squad.top;
          return big.right <= squad.left && big.top === squad.top &&
            (innerWidth <= 900 || Math.abs(squad.width * 2 - budget.width) < 1);
        })(),
        valuesFit: visible.every(el => {
          const bounds = el.getBoundingClientRect(), parent = el.closest('.list-row').getBoundingClientRect();
          return el.scrollWidth <= el.clientWidth + 1 && bounds.right <= parent.right && bounds.left >= parent.left;
        }),
      };
    });
    assert(geometry.pageFits && geometry.valuesFit && geometry.bigBoysPosition, `Dashboard layout at ${width}: ${JSON.stringify(geometry)}`);
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
