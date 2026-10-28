const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const browser = await chromium.launch({channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true});
  try {
    const crest = process.env.PLANNER_REAL_ARTWORK
      ? 'https://kickbase.b-cdn.net/content/file/ff70df040a9f4179a7b45219225a2273.svg'
      : 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="48" fill="#2364b5"/><circle cx="50" cy="50" r="35" fill="none" stroke="white" stroke-width="10"/></svg>');
    const portrait = process.env.PLANNER_REAL_ARTWORK
      ? 'https://kickbase.b-cdn.net/content/file/b41a70e2188a4c72aa165cfc7606c3e9.png'
      : 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120"><path fill="#e23a48" d="M5 120V95Q50 65 95 95V120Z"/><ellipse cx="50" cy="65" rx="23" ry="29" fill="#d9af89"/></svg>');
    const portraits = process.env.PLANNER_REAL_ARTWORK ? [portrait,
      'https://kickbase.b-cdn.net/content/file/8558eff47626439593b2acd71e400ab3.png',
      'https://kickbase.b-cdn.net/content/file/98ea8901b970421b88f6a41a3137142f.png'] : [portrait];
    const positions = [1, ...Array(5).fill(2), ...Array(6).fill(3), ...Array(3).fill(4)];
    const players = positions.map((position, i) => ({
      id: String(i), name: ['Alexander Lange', 'Maximilian Mittelstädt', 'Michael Olise'][i % 3],
      position, owned: true, mv: 12000000, season: 150 + i, l3: 110 + i,
      li: [80, 79, 65, 64, 25, 24, 1, 0, null][i % 9], change: i % 2 ? -123456 : 123456,
      profitLoss: i % 2 ? 12345678 : -12345678,
      status: i === 2 ? 'Angeschlagen' : 'Fit', recentForm: [0, 271, 195],
      fixtures: [{opponent: 'Mönchengladbach', venue: 'Auswärts', rank: 12}], image: portraits[i % portraits.length], teamImage: crest,
    }));
    const template = fs.readFileSync('features/mobile_lineup_planner.html', 'utf8')
      .replace('<head>', '<head><base href="http://planner.test/">')
      .replace('__PAYLOAD__', JSON.stringify({players, budget: 5000000, marketPlayers: []}))
      .replace('__SETTINGS__', '{}');
    fs.mkdirSync('test-output', {recursive: true});
    const results = [];
    for (const width of [320, 390, 430, 768, 900, 1024, 1280]) {
      const page = await browser.newPage({viewport: {width, height: 900}, hasTouch: width < 900});
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('http://planner.test/**', route => route.fulfill({
        contentType: 'application/json', body: JSON.stringify({formation: '4-4-2', players: []}),
      }));
      await page.setContent(template);
      await page.locator('#best').click();
      if (width >= 900) await page.locator('[data-form="3-6-1"]').click();
      assert.equal(await page.locator('.slot .card').count(), 11);
      const selectedIds = await page.locator('.slot .card').evaluateAll(cards => cards.map(card => card.dataset.player));
      const averagePoints = selectedIds.reduce((sum, id) => sum + players.find(player => player.id === id).season, 0);
      const activeFormation = await page.locator('#forms .active').getAttribute('data-form');
      assert.equal(await page.locator('#forms .active').textContent(),
        `${activeFormation} (${averagePoints.toLocaleString('de-DE', {maximumFractionDigits: 1})} Ø-Pkt.)`);
      if (width < 900) {
        for (const y of [800, 1600]) {
          await page.evaluate(y => window.scrollTo(0, y), y);
          const sticky = await page.evaluate(() => ({
            position: getComputedStyle(document.querySelector('#overlay')).position,
            top: document.querySelector('#overlay').getBoundingClientRect().top,
            headerBottom: document.querySelector('.top').getBoundingClientRect().bottom,
          }));
          assert.equal(sticky.position, 'sticky');
          assert.ok(Math.abs(sticky.top - sticky.headerBottom - 14) < 1, `budget must stick below header at ${width}px, scroll ${y}`);
        }
        await page.evaluate(() => window.scrollTo(0, 0));
      }
      const metrics = await page.evaluate(() => ({
        overflow: document.documentElement.scrollWidth > innerWidth,
        slotsDisplay: getComputedStyle(document.querySelector('.slots')).display,
        cards: [...document.querySelectorAll('.slot .card,.bank .card')].map(card => ({
          width: card.getBoundingClientRect().width,
          detailsVisible: getComputedStyle(card.querySelector('.desktop-lineup-card')).display !== 'none',
          oldTextHidden: getComputedStyle(card.querySelector('.card-copy')).display === 'none',
          crestOpacity: getComputedStyle(card.querySelector('.lineup-crest')).opacity,
          crestIsBackground: getComputedStyle(card.querySelector('.lineup-crest')).zIndex === '-1',
          photoZoom: card.querySelector('.lineup-photo img').getBoundingClientRect().height /
                     card.querySelector('.lineup-photo').getBoundingClientRect().height,
          photoPosition: getComputedStyle(card.querySelector('.lineup-photo')).position,
          photoOrigin: getComputedStyle(card.querySelector('.lineup-photo img')).transformOrigin,
          photoTop: card.querySelector('.lineup-photo img').getBoundingClientRect().top -
                    card.querySelector('.lineup-photo').getBoundingClientRect().top,
          financialsVisible: card.querySelector('.lineup-financials').getBoundingClientRect().height > 0,
          financialsFit: [...card.querySelectorAll('.lineup-financials b')].every(value => value.scrollWidth <= value.clientWidth),
          detailsInOrder: card.querySelector('.lineup-status').getBoundingClientRect().bottom <=
            card.querySelector('.lineup-financials').getBoundingClientRect().top &&
            card.querySelector('.lineup-financials').getBoundingClientRect().bottom <=
            card.querySelector('.start-toggle').getBoundingClientRect().top,
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
      assert.ok(metrics.cards.every(card => card.financialsVisible && card.financialsFit && card.detailsInOrder), `financial row layout at ${width}: ${JSON.stringify(metrics.cards.filter(card => !card.financialsFit || !card.detailsInOrder))}`);
      for (const player of players) {
        const expected = player.li == null ? 'Unbekannt: – % LI' :
          `${player.li >= 80 ? 'Sicher' : player.li >= 65 ? 'Erwartet' : player.li >= 25 ? 'Unsicher' : player.li > 0 ? 'Unwahrscheinlich' : 'Ausgeschlossen'}: ${player.li} % LI`;
        assert.equal(await page.locator(`[data-player="${player.id}"] .lineup-prob`).getAttribute('title'), expected);
      }
      assert.ok(metrics.cards.every(card => card.crestOpacity === '0.05' && card.crestIsBackground));
      assert.ok(metrics.cards.every(card => card.photoZoom > 1.5));
      assert.ok(metrics.cards.every(card => card.photoPosition === 'relative' && card.photoTop < 0));
      assert.ok(metrics.cards.every(card => card.photoOrigin.endsWith(' 0px')));
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
        const rows = await page.locator('.formation-line').evaluateAll(lines => lines.map(line =>
          [...line.querySelectorAll('.slot')].map(el => ({left: el.getBoundingClientRect().left,
            right: el.getBoundingClientRect().right}))));
        for (const row of rows) for (let i = 1; i < row.length; i++) {
          assert.ok(Math.abs(row[i].left - row[i - 1].right - 12) < 1, `row gap at ${width}`);
        }
        if (width === 1280) await page.locator('.slots').screenshot({path: 'test-output/planner-compact-pitch.png',
          style: '.top,.overlay,.toast{visibility:hidden !important}'});
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
        await heldStarter.screenshot({path: `test-output/planner-held-starter-${width}.png`,
          style: '.top,.overlay,.toast{visibility:hidden !important}'});
      }
      await swipeStarter(130);
      assert.doesNotMatch(await heldStarter.getAttribute('class'), /locked/);
      assert.equal(await page.locator('.slot .card').count(), 11);
      if (width === 390 || width === 1280) {
        await page.locator('.slot .card').first().screenshot({path: `test-output/planner-card-${width}.png`,
          style: '.top,.overlay,.toast{visibility:hidden !important}'});
        await page.locator('.bank .card').first().screenshot({path: `test-output/planner-bank-${width}.png`,
          style: '.top,.overlay,.toast{visibility:hidden !important}'});
        if (width === 1280) for (let i = 0; i < 3; i++) {
          await page.locator('.slot .card').nth(i).screenshot({path: `test-output/planner-face-${i}.png`,
            style: '.top,.overlay,.toast{visibility:hidden !important}'});
        }
      }
      assert.deepEqual(errors, []);
      results.push({width, overflow: metrics.overflow, cards: metrics.cards.length});
      await page.close();
    }
    const budgetPage = await browser.newPage({viewport: {width: 390, height: 900}, hasTouch: true});
    await budgetPage.route('http://planner.test/**', route => route.fulfill({
      contentType: 'application/json', body: JSON.stringify({formation: '4-4-2', players: []}),
    }));
    await budgetPage.setContent(template.replace('"budget":5000000', '"budget":-50000001'));
    const formation = budgetPage.locator('[data-form="4-4-2"]');
    const limit = budgetPage.locator('#deficit');
    const active = budgetPage.locator('#deficit-active');
    const apply = budgetPage.locator('#deficit-form button');
    assert.match(await formation.getAttribute('class'), /form-green/);
    await limit.fill('2000000');
    await formation.click(); // Re-rendering must not apply an unconfirmed draft.
    assert.match(await formation.getAttribute('class'), /form-green/);
    assert.match(await active.textContent(), /5\.000\.000/);
    await apply.click();
    assert.match(await formation.getAttribute('class'), /form-yellow/);
    assert.match(await active.textContent(), /2\.000\.000/);
    await limit.fill('3000000');
    await limit.press('Enter');
    assert.match(await formation.getAttribute('class'), /form-green/);
    assert.match(await active.textContent(), /3\.000\.000/);
    await limit.fill('0');
    await apply.click();
    assert.match(await formation.getAttribute('class'), /form-yellow/);
    assert.match(await active.textContent(), /bis 0/);
    for (const value of ['-1', '', '1.5']) {
      await limit.fill(value);
      await apply.click();
      assert.match(await active.textContent(), /bis 0/);
    }
    await budgetPage.close();
    const flagPage = await browser.newPage({viewport: {width: 1280, height: 900}});
    await flagPage.route('http://planner.test/**', route => route.fulfill({
      contentType: 'application/json', body: JSON.stringify({formation: '4-4-2', players: []}),
    }));
    const flagPlayers = [1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4].map((position, i) => ({
      id: String(i), name: `Player ${i}`, position, mv: 1000000, season: 100, l3: 100,
    }));
    flagPlayers.push({id: 'star', name: 'Star', position: 2, mv: 20000000, season: 200, l3: 200});
    const flagTemplate = () => template.replace(JSON.stringify({players, budget: 5000000, marketPlayers: []}),
      JSON.stringify({players: flagPlayers, budget: -12000000, marketPlayers: []}));
    await flagPage.setContent(flagTemplate());
    const activeFlagForm = flagPage.locator('#forms .active');
    await flagPage.locator('[data-form="4-4-2"]').click();
    assert.match(await activeFlagForm.getAttribute('class'), /form-green/);
    await flagPage.locator('[data-lock="star"]').click();
    assert.match(await activeFlagForm.getAttribute('class'), /form-yellow/);
    assert.match(await flagPage.locator('#budget').textContent(), /-12\.000\.000/);
    await flagPage.locator('[data-lock="star"]').click();
    await flagPage.locator('[data-sell="star"]').click();
    assert.match(await activeFlagForm.getAttribute('class'), /form-green/);
    await flagPage.locator('.bank [data-player="star"] .lineup-name').click();
    await flagPage.locator('[data-slot="1"] .lineup-name').click();
    assert.match(await activeFlagForm.getAttribute('class'), /form-yellow/);
    assert.match(await activeFlagForm.getAttribute('title'), /-11\.000\.000/);
    assert.match(await activeFlagForm.textContent(), /1\.200 Ø-Pkt/);
    await flagPage.locator('[data-start="star"]').click();
    assert.match(await activeFlagForm.getAttribute('class'), /form-yellow/);
    await flagPage.evaluate(() => {
      const dataTransfer = new DataTransfer();
      document.querySelector('[data-player="star"]').dispatchEvent(new DragEvent('dragstart', {bubbles: true, dataTransfer}));
      document.querySelector('#bank').dispatchEvent(new DragEvent('drop', {bubbles: true, dataTransfer}));
    });
    assert.equal(await flagPage.locator('.slot [data-player="star"]').count(), 1);
    assert.equal(await flagPage.locator('.slot .card').count(), 11);
    // Multiple pins must change the formation and then show the actual forced deficit.
    flagPlayers.push({id: 'mid5', name: 'Fifth midfielder', position: 3, mv: 20000000, season: 50, l3: 50});
    await flagPage.setContent(flagTemplate());
    await flagPage.locator('[data-form="4-4-2"]').click();
    for (const id of ['5', '6', '7', '8', 'mid5']) await flagPage.locator(`[data-start="${id}"]`).click();
    assert.notEqual(await activeFlagForm.getAttribute('data-form'), '4-4-2');
    assert.match(await activeFlagForm.getAttribute('class'), /form-green/);
    await flagPage.locator('[data-start="star"]').click();
    assert.match(await activeFlagForm.getAttribute('class'), /form-yellow/);
    assert.match(await activeFlagForm.getAttribute('title'), /-10\.000\.000/);
    assert.match(await flagPage.locator('[data-form="4-4-2"]').getAttribute('class'), /form-red/);
    for (const id of ['5', '6', '7', '8', 'mid5', 'star']) {
      assert.equal(await flagPage.locator(`.slot [data-player="${id}"]`).count(), 1);
    }
    await flagPage.close();
    console.log(JSON.stringify({layouts: results, customBudget: 'passed', liveFlagsAndSwaps: 'passed'}));
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
