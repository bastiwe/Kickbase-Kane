const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const browser = await chromium.launch({channel: process.env.BROWSER_CHANNEL || 'chrome', headless: true});
  const fixtures = [
    {opponent: 'Borussia Dortmund', venue: 'Heim', rank: 2, date: '31.10.2026, 18:30'},
    {opponent: 'Mainz 05', venue: 'Auswärts', rank: 7, date: '07.11.2026, 15:30'},
    {opponent: '1. FC Köln', venue: 'Heim', rank: 12, date: '21.11.2026, 15:30'},
  ];
  const portrait = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120"><path fill="#d62b46" d="M10 120V90Q50 65 90 90V120Z"/><ellipse cx="50" cy="52" rx="23" ry="29" fill="#d9af89"/></svg>');
  const positions = [1, ...Array(5).fill(2), ...Array(6).fill(3), ...Array(3).fill(4)];
  const players = positions.map((position, i) => ({
    id: String(1000 + i), name: ['Joshua Kimmich', 'Maximilian Mittelstädt', 'Michael Olise'][i % 3],
    teamId: String(i % 3), team: ['Bayern München', 'VfB Stuttgart', 'Bayern München'][i % 3],
    image: portrait, position, owned: true, mv: 59860000, season: 222 + i, l3: 180,
    totalPoints: 1331, li: 80, status: 'Fit', profitLoss: -1800000, change: 21000,
    fixtures: i === 0 ? fixtures : [],
  }));
  const performance = Array.from({length: 18}, (_, i) => ({
    date: `${String(i + 1).padStart(2, '0')}.10.2026`, points: [303, 254, 92, 216, 195, 271, 0, -20, 111][i % 9],
    minutes: i % 3 ? 96 : null, goals: i % 3 ? 0 : 1, assists: 0,
    opponent: ['Borussia Dortmund', 'Mainz 05', '1. FC Köln'][i % 3], venue: 'Heim', rank: 7,
  }));
  const changes = Array.from({length: 40}, (_, i) => ({
    date: new Date(Date.UTC(2026, 8, 18 + i)).toISOString().slice(0, 10),
    marketValue: 59000000 + i * 21000, change: 21000, percent: .035,
  })).reverse();
  const html = fs.readFileSync('features/mobile_lineup_planner.html', 'utf8')
    .replace('<head>', '<head><base href="http://planner.test/api/hassio_ingress/test/">')
    .replace('__PAYLOAD__', JSON.stringify({players, budget: 5000000, marketPlayers: []}))
    .replace('__SETTINGS__', '{}');
  fs.mkdirSync('test-output', {recursive: true});
  try {
    for (const width of [320, 390, 768, 1280]) {
      const page = await browser.newPage({viewport: {width, height: 950}});
      const errors = [], requests = [], detailCalls = new Map();
      let failId = null;
      page.on('pageerror', error => errors.push(error.message));
      await page.route('http://planner.test/**', async route => {
        const url = new URL(route.request().url());
        requests.push(url.pathname);
        const file = url.pathname.split('/').pop();
        if (['planner_details.js', 'planner_details.css'].includes(file)) return route.fulfill({
          contentType: file.endsWith('.js') ? 'text/javascript' : 'text/css', body: fs.readFileSync('features/' + file, 'utf8'),
        });
        if (url.pathname.includes('/player-details/')) {
          detailCalls.set(file, (detailCalls.get(file) || 0) + 1);
          if (file === failId) return route.fulfill({status: 502, json: {error: 'Test failure'}});
          return route.fulfill({json: {fixtures, performance, history: performance.slice(-8).reverse(),
            seasonLabel: '2026/2027', totalPoints: 1331, season: 222, l3: 180, minutes: 516,
            goals: 0, assists: 3, cards: '0 Gelb / 0 Rot'}});
        }
        if (url.pathname.includes('/player-market-history/')) {
          assert.equal(url.searchParams.get('limit'), '365');
          if (file === failId) return route.fulfill({status: 502, json: {error: 'Test failure'}});
          return route.fulfill({json: {changes}});
        }
        return route.fulfill({json: {formation: '4-4-2', players: []}});
      });
      await page.setContent(html);
      await page.locator('#best').click();
      const selection = () => page.locator('.slot .card').evaluateAll(cards => cards.map(card => card.dataset.player));
      const before = await selection();
      const photo = page.locator('.slot [data-player-details]').first();
      const id = await photo.getAttribute('data-player-details');
      await photo.click();
      const dialog = page.locator('#player-details-dialog');
      await dialog.locator('.pd-data-status').filter({hasText: 'Verfügbare Kickbase-Daten'}).waitFor();
      assert.equal(await dialog.getAttribute('open'), '');
      assert.equal(await dialog.locator('.pd-performance rect').count(), 8);
      assert.equal(await dialog.locator('.pd-fixtures article').count(), 3);
      assert.equal(await dialog.locator('.pd-market-chart circle').count(), 30);
      await dialog.locator('[data-market-days="7"]').click();
      assert.equal(await dialog.locator('.pd-market-chart circle').count(), 7);
      await dialog.locator('[data-performance-window="0"]').click();
      assert.equal(await dialog.locator('.pd-performance rect').count(), 18);
      await dialog.locator('[data-game-summary]').first().click();
      assert.match(await dialog.locator('#pd-game-summary').textContent(), /303 Punkte/);
      assert.deepEqual(await selection(), before);
      const layout = await dialog.evaluate(element => ({
        overflow: element.scrollWidth > element.clientWidth,
        columns: getComputedStyle(element.querySelector('.pd-layout')).gridTemplateColumns.split(' ').length,
      }));
      assert.equal(layout.overflow, false, `detail overflow at ${width}`);
      assert.equal(layout.columns, width < 700 ? 1 : width < 1100 ? 2 : 3);
      if ([390, 1280].includes(width)) {
        await dialog.evaluate(element => element.scrollTo(0, 0));
        await dialog.screenshot({path: `test-output/planner-details-${width}.png`});
      }
      await dialog.locator('[data-close-details]').click();
      await photo.click();
      await dialog.locator('.pd-data-status').filter({hasText: 'Verfügbare Kickbase-Daten'}).waitFor();
      assert.equal(detailCalls.get(id), 1, 'reopening reuses cached details');
      await page.keyboard.press('Escape');
      assert.equal(await dialog.getAttribute('open'), null);
      // A failed request must retain usable report values and leave the lineup untouched.
      const failPhoto = page.locator('.slot [data-player-details]').nth(1);
      failId = await failPhoto.getAttribute('data-player-details');
      await failPhoto.click();
      await dialog.locator('.pd-data-status').filter({hasText: 'Live-Spielerdetails derzeit nicht abrufbar'}).waitFor();
      assert.equal(await dialog.locator('.pd-metric').count(), 10);
      assert.deepEqual(await selection(), before);
      await dialog.locator('[data-close-details]').click();
      failId = null;
      // Opening an image inside the picker must not choose that candidate.
      const firstSlot = page.locator('.slot').first();
      await firstSlot.locator('.lineup-name').click();
      await firstSlot.click();
      const picker = page.locator('#candidate-dialog');
      await picker.locator('.candidate-fixture').first().waitFor();
      await page.waitForFunction(() => [...document.querySelectorAll('.candidate-fixtures')].every(element => element.querySelectorAll('.candidate-fixture').length === 3));
      for (const row of await picker.locator('.candidate-option').all()) {
        assert.equal(await row.locator('.candidate-fixture').count(), 3);
        assert.match(await row.locator('.candidate-fixtures').textContent(), /Pl\. 2/);
        assert.match(await row.locator('.candidate-fixtures').textContent(), /Pl\. 7/);
        assert.match(await row.locator('.candidate-fixtures').textContent(), /Pl\. 12/);
      }
      assert.equal(await picker.evaluate(element => element.scrollWidth > element.clientWidth), false, `picker overflow at ${width}`);
      if ([390, 1280].includes(width)) await picker.screenshot({path: `test-output/planner-candidates-${width}.png`});
      const candidatePhoto = picker.locator('[data-player-details]').first();
      await candidatePhoto.click();
      await dialog.locator('.pd-data-status').filter({hasText: 'Verfügbare Kickbase-Daten'}).waitFor();
      assert.equal(await page.locator('.slot .card').count(), 10);
      await dialog.locator('[data-close-details]').click();
      assert.equal(await picker.getAttribute('open'), '');
      await picker.locator('.candidate-copy').first().click();
      assert.equal(await page.locator('.slot .card').count(), 11);
      assert.equal(await picker.getAttribute('open'), null);
      assert.ok(requests.every(path => path.startsWith('/api/hassio_ingress/test/')), 'all requests preserve HA ingress path');
      assert.deepEqual(errors, []);
      console.log(`details, ranges, fallback, picker, cache and ingress passed at ${width}px`);
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
