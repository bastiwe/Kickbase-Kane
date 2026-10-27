const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  try {
    const positions = [1, ...Array(5).fill(2), ...Array(6).fill(3), ...Array(3).fill(4)];
    const players = positions.map((position, i) => ({
      id: String(i), name: ['Alexander Lange', 'Maximilian Mittelstädt', 'Michael Olise'][i % 3],
      position, owned: true, mv: 12000000, season: 150 + i, l3: 110 + i,
      li: 90, status: i === 2 ? 'Angeschlagen' : 'Fit', recentForm: [0, 271, 195],
      fixtures: [{opponent: 'Mönchengladbach', venue: 'Auswärts', rank: 12}], image: '',
    }));
    const template = fs.readFileSync('features/mobile_lineup_planner.html', 'utf8')
      .replace('<head>', '<head><base href="http://planner.test/">')
      .replace('__PAYLOAD__', JSON.stringify({players, budget: 5000000, marketPlayers: []}))
      .replace('__SETTINGS__', '{}');
    fs.mkdirSync('test-output', {recursive: true});
    const results = [];
    for (const width of [320, 390, 430, 768, 1280]) {
      const page = await browser.newPage({viewport: {width, height: 900}, hasTouch: width < 900});
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('http://planner.test/**', route => route.fulfill({
        contentType: 'application/json', body: JSON.stringify({formation: '4-4-2', players: []}),
      }));
      await page.setContent(template);
      await page.locator('#best').click();
      assert.equal(await page.locator('.slot .card').count(), 11);
      const metrics = await page.evaluate(() => ({
        overflow: document.documentElement.scrollWidth > innerWidth,
        slotsDisplay: getComputedStyle(document.querySelector('.slots')).display,
        cards: [...document.querySelectorAll('.slot .card,.bank .card')].map(card => ({
          width: card.getBoundingClientRect().width,
          detailsVisible: getComputedStyle(card.querySelector('.desktop-lineup-card')).display !== 'none',
          oldTextHidden: getComputedStyle(card.querySelector('.card-copy')).display === 'none',
        })),
        bankActions: getComputedStyle(document.querySelector('.bank .plan-actions')).display,
      }));
      if (metrics.overflow) console.error(await page.evaluate(() => ({root: document.documentElement.scrollWidth,
        body: document.body.scrollWidth, viewport: innerWidth, scrollX,
        overflowing: [...document.querySelectorAll('body *')].filter(el => el.clientWidth && el.scrollWidth > el.clientWidth + 1)
          .map(el => ({tag: el.tagName, class: el.className, client: el.clientWidth, scroll: el.scrollWidth,
                       overflow: getComputedStyle(el).overflow, transform: getComputedStyle(el).transform})).slice(0, 30),
        offenders: [...document.querySelectorAll('body *')]
        .filter(el => getComputedStyle(el).display !== 'none' && el.getBoundingClientRect().right + scrollX > innerWidth)
        .map(el => ({tag: el.tagName, class: el.className, width: el.getBoundingClientRect().width,
                     right: el.getBoundingClientRect().right + scrollX})).slice(0, 30)})));
      assert.equal(metrics.overflow, false, `page overflow at ${width}`);
      assert.ok(metrics.cards.every(card => card.detailsVisible && card.oldTextHidden));
      if (width < 900) {
        assert.equal(metrics.slotsDisplay, 'grid');
        assert.equal(metrics.bankActions, 'none');
        assert.ok(metrics.cards.every(card => card.width > width * .8));
        // The shared cards retain the existing left-swipe sale/keep gestures.
        const card = page.locator('.bank .card').first();
        const id = await card.getAttribute('data-player');
        const swipeLeft = () => page.locator(`[data-player="${id}"]`).evaluate(el => {
          const start = new Touch({identifier: 1, target: el, clientX: 180, clientY: 80});
          const end = new Touch({identifier: 1, target: el, clientX: 50, clientY: 80});
          el.dispatchEvent(new TouchEvent('touchstart', {bubbles: true, touches: [start]}));
          el.dispatchEvent(new TouchEvent('touchmove', {bubbles: true, touches: [end]}));
          el.dispatchEvent(new TouchEvent('touchend', {bubbles: true, changedTouches: [end]}));
        });
        await swipeLeft();
        await swipeLeft();
        assert.match(await page.locator(`[data-player="${id}"]`).getAttribute('class'), /locked/);
      } else {
        assert.equal(metrics.bankActions, 'grid');
        assert.ok(metrics.cards.every(card => card.width <= 178));
      }
      // Holding a starter must be visible too, and removing hold clears the edge.
      const starterId = await page.locator('.slot .card').first().getAttribute('data-player');
      const swipeStarter = dx => page.locator(`.slot [data-player="${starterId}"]`).evaluate((el, distance) => {
        const start = new Touch({identifier: 2, target: el, clientX: 180, clientY: 80});
        const end = new Touch({identifier: 2, target: el, clientX: 180 + distance, clientY: 80});
        el.dispatchEvent(new TouchEvent('touchstart', {bubbles: true, touches: [start]}));
        el.dispatchEvent(new TouchEvent('touchmove', {bubbles: true, touches: [end]}));
        el.dispatchEvent(new TouchEvent('touchend', {bubbles: true, changedTouches: [end]}));
      }, dx);
      await swipeStarter(-130);
      const heldStarter = page.locator(`.slot [data-player="${starterId}"]`);
      assert.match(await heldStarter.getAttribute('class'), /locked/);
      const edge = await heldStarter.evaluate(el => ({
        color: getComputedStyle(el).borderLeftColor, width: getComputedStyle(el).borderLeftWidth,
      }));
      assert.equal(edge.color, 'rgb(38, 208, 126)');
      assert.equal(edge.width, '4px');
      if (width === 390 || width === 1280) {
        await heldStarter.screenshot({path: `test-output/planner-held-starter-${width}.png`});
      }
      await swipeStarter(130);
      assert.doesNotMatch(await heldStarter.getAttribute('class'), /locked/);
      assert.equal(await page.locator('.slot .card').count(), 11);
      if (width === 390 || width === 1280) {
        await page.locator('.slot .card').first().screenshot({path: `test-output/planner-card-${width}.png`});
        await page.locator('.bank .card').first().screenshot({path: `test-output/planner-bank-${width}.png`});
      }
      assert.deepEqual(errors, []);
      results.push({width, overflow: metrics.overflow, cards: metrics.cards.length});
      await page.close();
    }
    console.log(JSON.stringify(results));
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
