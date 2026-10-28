const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');

const template = fs.readFileSync('features/mobile_lineup_planner.html', 'utf8');
// Execute the planner's real selection and rendering code with a minimal DOM.
const script = template.split(/<script>\r?\n/)[1].split("document.addEventListener('click'")[0];
function planner(budget = -12000000, extraPlayers = []) {
  const positions = [1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4];
  const players = positions.map((position, i) => ({
    id: String(i), name: `Player ${i}`, position, mv: 1000000, season: 100, l3: 100,
  }));
  players.push({id: 'star', name: 'Star', position: 2, mv: 20000000, season: 200, l3: 200});
  players.push(...extraPlayers);
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {style: {setProperty() {}}, classList: {add() {}, remove() {}}, offsetHeight: 100});
    return elements.get(id);
  };
  const context = vm.createContext({
    document: {querySelector: id => id === '#data' ? {textContent: JSON.stringify({players, budget})} : element(id),
      getElementById: element, documentElement: element('root')},
    window: {}, addEventListener() {}, setTimeout() {}, clearTimeout() {},
  });
  vm.runInContext(script + `globalThis.api={formationState, selectFormation, best, currentBudget, lineupProbability, lineupFinancials, toggleStarter, place,
    currentForm: ()=>form,
    deficit: applyBudgetLimit, lock: id=>locked.add(id), force: id=>forced.add(id),
    buy: (id,cost)=>purchases.set(id,cost), selected: ()=>sel};})();`, context);
  return context.api;
}

test('LI symbols and short tooltips use the five requested boundaries', () => {
  const p = planner();
  for (const [rate, tone, label, icon] of [
    [100, 'certain', 'Sicher', '✦'], [80, 'certain', 'Sicher', '✦'],
    [79, 'expected', 'Erwartet', '✓'], [65, 'expected', 'Erwartet', '✓'],
    [64, 'uncertain', 'Unsicher', '?'], [25, 'uncertain', 'Unsicher', '?'],
    [24, 'unlikely', 'Unwahrscheinlich', '!'], [1, 'unlikely', 'Unwahrscheinlich', '!'],
    [0, 'excluded', 'Ausgeschlossen', '×'],
  ]) {
    const status = p.lineupProbability(rate);
    assert.equal(status.tone, tone);
    assert.equal(status.icon, icon);
    assert.equal(status.title, `${label}: ${rate} % LI`);
  }
  for (const rate of [null, undefined, '', 'invalid', -1, 101]) {
    assert.equal(p.lineupProbability(rate).tone, 'unknown');
  }
});

test('financial row formats signed forecasts and profit/loss with missing values preserved', () => {
  const p = planner();
  const html = p.lineupFinancials({change: 123456, profitLoss: -12345678});
  assert.match(html, /Erw\. 1T/);
  assert.match(html, /G\/V/);
  assert.match(html, /class="green">\+123\.456/);
  assert.match(html, /class="red">-12\.345\.678/);
  const missing = p.lineupFinancials({change: null, profitLoss: null});
  assert.equal((missing.match(/<b class="">–<\/b>/g) || []).length, 2);
});

test('formation selects the highest scoring affordable alternative before turning yellow', () => {
  const p = planner();
  p.deficit(0);
  const state = p.formationState('4-4-2');
  assert.equal(state.kind, 'form-green');
  assert.equal(state.budget, 8000000);
  assert.equal(state.averagePoints, 1100);
  assert.equal(state.choice.ids.includes('star'), false);
  p.selectFormation('4-4-2');
  assert.equal(p.selected().filter(Boolean).length, 11);
  assert.equal(p.currentBudget(), state.budget);
  p.best();
  assert.equal(p.currentBudget(), state.budget);
});

test('deficit option includes exactly minus five million and rejects values below it', () => {
  const p = planner(-6000000); // Keeping the star leaves exactly -5 million.
  assert.equal(p.formationState('4-4-2').choice.ids.includes('star'), true);
  assert.equal(p.formationState('4-4-2').budget, -5000000);
  assert.equal(p.formationState('4-4-2').averagePoints, 1200);
  assert.equal(p.formationState('4-4-2').kind, 'form-green');
  p.deficit(0);
  assert.equal(p.formationState('4-4-2').choice.ids.includes('star'), false);
  assert.equal(p.formationState('4-4-2').averagePoints, 1100);
  p.deficit(5000000);
  p.force('star');
  assert.equal(p.formationState('4-4-2').kind, 'form-green');
  const below = planner(-6000001);
  below.force('star');
  assert.equal(below.formationState('4-4-2').kind, 'form-yellow');
});

test('custom confirmed deficit controls formation choices and best eleven', () => {
  const p = planner(-12000000);
  assert.equal(p.deficit('11000000'), true);
  assert.equal(p.formationState('4-4-2').choice.ids.includes('star'), true);
  p.best();
  assert.equal(p.currentBudget(), -11000000);
  assert.equal(p.deficit('10999999'), true);
  assert.equal(p.formationState('4-4-2').kind, 'form-yellow');
  assert.equal(p.formationState('4-4-2', false).choice.ids.includes('star'), false);
  p.selectFormation('4-4-2');
  assert.equal(p.currentBudget(), 8000000);
  p.best();
  assert.equal(p.currentBudget(), 8000000);
  const forced = planner(-12000000);
  forced.force('star');
  forced.deficit(11000000);
  assert.equal(forced.formationState('4-4-2').kind, 'form-green');
  forced.deficit(10999999);
  assert.equal(forced.formationState('4-4-2').kind, 'form-yellow');
});

test('invalid deficit amounts preserve the active budget limit', () => {
  const p = planner(-12000000);
  p.force('star');
  p.deficit(11000000);
  for (const value of ['', ' ', 'invalid', -1, 1.5, Infinity, '9007199254740992']) {
    assert.equal(p.deficit(value), false);
    assert.equal(p.formationState('4-4-2').kind, 'form-green');
  }
  assert.equal(p.deficit(0), true);
  assert.equal(p.formationState('4-4-2').kind, 'form-yellow');
});

test('budget search finds solutions requiring multiple replacements', () => {
  const p = planner(-32000000, [
    {id: 'star2', name: 'Second star', position: 2, mv: 15000000, season: 180, l3: 180},
  ]);
  p.deficit(0);
  const state = p.formationState('4-4-2');
  assert.equal(state.kind, 'form-green');
  assert.equal(state.budget, 3000000);
  assert.equal(state.choice.ids.includes('star'), false);
  assert.equal(state.choice.ids.includes('star2'), false);
  p.selectFormation('4-4-2');
  assert.equal(p.currentBudget(), state.budget);
});

test('zero budget is green and yellow means no affordable complete lineup exists', () => {
  const p = planner(-20000000);
  p.deficit(0);
  assert.equal(p.formationState('4-4-2').kind, 'form-green');
  assert.equal(p.formationState('4-4-2').budget, 0);
  const impossible = planner(-25000001);
  assert.equal(impossible.formationState('4-4-2').kind, 'form-yellow');
  impossible.selectFormation('4-4-2');
  assert.equal(impossible.selected().filter(Boolean).length, 11);
  assert.equal(impossible.formationState('4-3-3').kind, 'form-red');
});

test('held players and forced starters cannot be sold to fund an alternative', () => {
  const held = planner();
  held.lock('star');
  assert.equal(held.formationState('4-4-2').kind, 'form-yellow');
  const forced = planner();
  forced.force('star');
  assert.equal(forced.formationState('4-4-2').kind, 'form-yellow');
  assert.equal(forced.formationState('4-4-2').choice.ids.includes('star'), true);
  forced.force('0');
  forced.force('1');
  assert.equal(forced.formationState('4-3-3').kind, 'form-red');
});

test('active formation reacts to swaps even if another affordable lineup is possible', () => {
  const p = planner();
  p.selectFormation('4-4-2');
  assert.equal(p.currentBudget(), 8000000);
  p.place('star', 1);
  assert.equal(p.currentBudget(), -11000000);
  assert.equal(p.formationState('4-4-2').kind, 'form-yellow');
  assert.equal(p.formationState('4-4-2').averagePoints, 1200);
  assert.equal(p.formationState('4-4-2', false).kind, 'form-green');
  p.place('1', 1);
  assert.equal(p.formationState('4-4-2').kind, 'form-green');
  assert.equal(p.formationState('4-4-2').averagePoints, 1100);
});

test('held bench players never finance the budget, including after a swap', () => {
  const p = planner();
  p.selectFormation('4-4-2');
  p.lock('star'); // The stale sale entry must no longer count.
  assert.equal(p.currentBudget(), -12000000);
  assert.equal(p.formationState('4-4-2').kind, 'form-yellow');
  p.place('star', 1);
  assert.equal(p.currentBudget(), -11000000);
  assert.equal(p.selected().includes('star'), true);
  p.place('1', 1);
  assert.equal(p.currentBudget(), -12000000);
  assert.equal(p.selected().includes('star'), false);
});

test('multiple starter pins change formation and immediately expose the resulting deficit', () => {
  const p = planner(-12000000, [
    {id: 'mid5', name: 'Fifth midfielder', position: 3, mv: 20000000, season: 50, l3: 50},
  ]);
  p.selectFormation('4-4-2');
  for (const id of ['5', '6', '7', '8', 'mid5']) p.toggleStarter(id);
  assert.notEqual(p.currentForm(), '4-4-2');
  for (const id of ['5', '6', '7', '8', 'mid5']) assert.equal(p.selected().includes(id), true);
  assert.equal(p.formationState(p.currentForm()).kind, 'form-green');
  p.toggleStarter('star');
  assert.equal(p.selected().includes('star'), true);
  assert.equal(p.currentBudget(), -10000000);
  assert.equal(p.formationState(p.currentForm()).kind, 'form-yellow');
  assert.equal(p.formationState('4-4-2').kind, 'form-red');
  p.toggleStarter('star');
  p.best();
  assert.equal(p.formationState(p.currentForm()).kind, 'form-green');
});

test('simulated purchases are paid even when benched and never counted as sale proceeds', () => {
  const p = planner(20000000);
  p.deficit(0);
  p.buy('star', 22000000);
  const state = p.formationState('4-4-2');
  assert.equal(state.kind, 'form-yellow');
  p.selectFormation('4-4-2');
  assert.equal(p.currentBudget(), state.budget);
  assert.equal(p.currentBudget(), -1000000);
  p.best();
  assert.equal(p.currentBudget(), -1000000);
});
