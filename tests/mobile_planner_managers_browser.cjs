const assert = require('node:assert/strict');
const fs = require('node:fs');
const {test} = require('node:test');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

test('manager simulations use separate rosters, budgets, and drafts', async () => {
  const browser = await chromium.launch({channel: process.env.BROWSER_CHANNEL || 'chrome', headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 390, height: 900}});
    const positions = [1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4];
    const squad = prefix => positions.map((position, i) => ({
      id: prefix + i, name: prefix + ' Spieler ' + i, position, mv: 1_000_000, season: 100, owned: true,
    }));
    const own = squad('own');
    const other = squad('other');
    const reserve = {...other[1], id: 'reserve', name: 'Reserve'};
    const offer = {...reserve, id: 'offer', name: 'Marktspieler', owned: false, mv: 2_000_000};
    const lineup = players => ({formation: '4-4-2', players: players.map(player => player.id)});
    const html = fs.readFileSync('features/mobile_lineup_planner.html', 'utf8')
      .replace('<head>', '<head><base href="http://planner.test/">')
      .replace('__PAYLOAD__', JSON.stringify({user: 'owner', players: own, budget: 5_000_000,
        marketPlayers: [{...reserve, owned: false}, offer]}))
      .replace('__SETTINGS__', '{}');
    const saves = [];
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://planner.test/**', async route => {
      const url = new URL(route.request().url());
      if (url.pathname === '/api/apply-lineup') {
        saves.push(route.request().postDataJSON().state);
        return route.fulfill({json: {applied: true}});
      }
      if (url.pathname === '/api/current-lineup') return route.fulfill({json: lineup(own)});
      if (url.pathname === '/api/planner-managers') {
        if (url.searchParams.get('manager') === 'other') {
          return route.fulfill({json: {players: [...other, reserve], lineup: lineup(other), budget: -9_000_000}});
        }
        if (url.searchParams.get('manager') === 'unknown') {
          return route.fulfill({json: {players: other, lineup: lineup(other), budget: null}});
        }
        return route.fulfill({json: {managers: [{id: 'other', name: 'Mitmanager'}, {id: 'unknown', name: 'Offen'}]}});
      }
      if (/\.(css|js)$/.test(url.pathname)) {
        return route.fulfill({path: 'features' + url.pathname});
      }
      return route.fulfill({status: 404});
    });
    await page.setContent(html);
    const marketOptions = page.locator('#market-player option');
    const ownMarket = await marketOptions.allTextContents();
    const reserveOption = page.locator('#market-player option[value="reserve"]');
    assert.equal(await reserveOption.isEnabled(), true);
    await page.locator('#manager').selectOption('other');
    await page.locator('#manager-status').filter({hasText: 'Geschätzter Kontostand'}).waitFor();
    assert.match(await page.locator('#budget').textContent(), /-8\.000\.000/);
    assert.equal(await page.locator('#apply').isVisible(), false);
    assert.deepEqual(await marketOptions.allTextContents(), ownMarket);
    assert.equal(await reserveOption.isDisabled(), true);
    await page.locator('#market-player').evaluate(select => { select.value = 'reserve'; });
    await page.locator('#simulate').click();
    assert.equal(await page.locator('#simulated').textContent(), '');
    await page.locator('#apply').evaluate(button => button.click());
    await page.locator('#market-player').selectOption(offer.id);
    await page.locator('#simulate').click();
    assert.match(await page.locator('#budget').textContent(), /-10\.000\.000/);
    assert.deepEqual(await marketOptions.allTextContents(), ownMarket);
    assert.equal(await page.locator('#market-player option[value="offer"]').isDisabled(), true);
    await page.locator('#manager').selectOption('unknown');
    await page.locator('#manager-status').filter({hasText: 'Keine Kontostandsschätzung'}).waitFor();
    assert.equal(await page.locator('#budget').textContent(), '–');
    assert.equal(await page.locator('#deficit-form').isVisible(), false);
    await page.locator('#best').click();
    assert.equal(await page.locator('.slot .card').count(), 11);
    await page.locator('#manager').selectOption('');
    assert.deepEqual(await marketOptions.allTextContents(), ownMarket);
    assert.equal(await reserveOption.isEnabled(), true);
    assert.match(await page.locator('#budget').textContent(), /5\.000\.000/);
    assert.equal(await page.locator('#simulated').textContent(), '');
    assert.deepEqual(saves, []);
    await page.locator('#apply').click();
    await page.locator('#toast').filter({hasText: 'wurde in Kickbase gespeichert'}).waitFor();
    assert.deepEqual(saves, [{formation: '4-4-2', selection: lineup(own).players, manager: 'owner'}]);
    await page.locator('#manager').selectOption('other');
    assert.match(await page.locator('#budget').textContent(), /-10\.000\.000/);
    assert.match(await page.locator('#simulated').textContent(), /Marktspieler/);
    assert.deepEqual(errors, []);
  } finally {
    await browser.close();
  }
});
