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
  vm.runInContext(script + `globalThis.api={formationState, selectFormation, best, currentBudget,
    deficit: value=>{allowDeficit=value}, lock: id=>locked.add(id), force: id=>forced.add(id),
    buy: (id,cost)=>purchases.set(id,cost), selected: ()=>sel};})();`, context);
  return context.api;
}

test('formation selects the highest scoring affordable alternative before turning yellow', () => {
  const p = planner();
  p.deficit(false);
  const state = p.formationState('4-4-2');
  assert.equal(state.kind, 'form-green');
  assert.equal(state.budget, 8000000);
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
  assert.equal(p.formationState('4-4-2').kind, 'form-green');
  p.deficit(false);
  assert.equal(p.formationState('4-4-2').choice.ids.includes('star'), false);
  p.deficit(true);
  p.force('star');
  assert.equal(p.formationState('4-4-2').kind, 'form-green');
  const below = planner(-6000001);
  below.force('star');
  assert.equal(below.formationState('4-4-2').kind, 'form-yellow');
});

test('budget search finds solutions requiring multiple replacements', () => {
  const p = planner(-32000000, [
    {id: 'star2', name: 'Second star', position: 2, mv: 15000000, season: 180, l3: 180},
  ]);
  p.deficit(false);
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
  p.deficit(false);
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

test('simulated purchases are paid even when benched and never counted as sale proceeds', () => {
  const p = planner(20000000);
  p.deficit(false);
  p.buy('star', 22000000);
  const state = p.formationState('4-4-2');
  assert.equal(state.kind, 'form-yellow');
  p.selectFormation('4-4-2');
  assert.equal(p.currentBudget(), state.budget);
  assert.equal(p.currentBudget(), -1000000);
  p.best();
  assert.equal(p.currentBudget(), -1000000);
});
