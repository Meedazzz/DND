const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const nodeCrypto = require('node:crypto');
const crypto = { randomUUID: () => nodeCrypto.randomUUID(), getRandomValues: array => { array.fill(9); return array; } };

class ClassList {
  constructor() { this.values = new Set(); }
  add(...items) { items.forEach(item => this.values.add(item)); }
  remove(...items) { items.forEach(item => this.values.delete(item)); }
  toggle(item, on) { if (on === undefined) on = !this.values.has(item); on ? this.add(item) : this.remove(item); return on; }
  contains(item) { return this.values.has(item); }
}
class Style {
  constructor() { this.props = {}; }
  setProperty(name, value) { this.props[name] = String(value); }
}
class Element {
  constructor(id = '') {
    this.id = id; this.dataset = {}; this.classList = new ClassList(); this.style = new Style();
    this.listeners = {}; this.children = []; this.value = ''; this.textContent = ''; this.hidden = false; this._html = '';
  }
  set innerHTML(value) { this._html = String(value); }
  get innerHTML() { return this._html; }
  addEventListener(type, listener) { this.listeners[type] = listener; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  closest() { return this; }
  matches() { return false; }
  hasAttribute() { return false; }
  append(item) { this.children.push(item); }
  remove() {}
  click() {}
}

const ids = ['app', 'roleBadge', 'roleHint', 'navRound', 'characterNavLabel', 'navCharacters', 'syncStatus', 'saveExportBtn', 'updateBtn', 'settingsBtn', 'campaignTitle', 'autosaveLabel', 'quickDiceBtn', 'roomBtn', 'profileBtn', 'mainContent', 'toastHost', 'modalHost', 'campaignImportInput'];
const elements = Object.fromEntries(ids.map(id => [id, new Element(id)]));
const views = ['dashboard', 'battle', 'characters', 'journal', 'world', 'cities', 'scene', 'library', 'photo', 'workshop', 'rules'].map(view => Object.assign(new Element(), { dataset: { view } }));
const editions = ['2014', '2024'].map(edition => Object.assign(new Element(), { dataset: { edition } }));
const listeners = {};
const textNodes = [];
const document = {
  body: {}, textNodes,
  querySelector: selector => selector === '#syncStatus span'
    ? (elements.syncStatus.span || (elements.syncStatus.span = new Element()))
    : selector.startsWith('#') ? elements[selector.slice(1)] || null : null,
  querySelectorAll: selector => selector === '.nav-item' ? views : selector === '[data-edition]' ? editions : [],
  addEventListener: (type, listener) => { listeners[type] = listener; },
  createElement: () => new Element(),
  createTreeWalker: () => {
    let index = 0;
    return { nextNode: () => textNodes[index++] || null };
  },
};
const storage = new Map();
Object.assign(global, {
  document,
  window: { dragonSagaDesktop: null, addEventListener() {} },
  localStorage: { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, String(value)) },
  requestAnimationFrame: fn => fn(), confirm: () => true,
  EventSource: class {}, Audio: class {}, CustomEvent: class {}, FileReader: class {},
  Blob: global.Blob, URL: global.URL, NodeFilter: { SHOW_TEXT: 4 },
  setTimeout: () => 0, clearTimeout: () => {},
});
Object.defineProperty(global, 'crypto', { value: crypto, configurable: true });

vm.runInThisContext(fs.readFileSync(require.resolve('../public/engine.js'), 'utf8'), { filename: 'engine.js' });
window.DragonEngine = global.DragonEngine;
vm.runInThisContext(fs.readFileSync(require.resolve('../public/photo-editor.js'), 'utf8'), { filename: 'photo-editor.js' });
let appSource = fs.readFileSync(require.resolve('../public/app.js'), 'utf8');
appSource = appSource.replace(
  'render();\n})();',
  `render();
   globalThis.__DragonSagaTacticalTest = {
     baseState, normalize, getState: () => state,
     setState: value => { state = normalize(value); currentView = 'battle'; renderQueued = false; },
     moveActor, beginTurn, resolveAction, tacticalBreather, disengageActor,
     investigateBoss, rearCover, legalMelee, renderBattle, actorCard, renderSheet,
     sceneObject, applyScales, applyLocalization
   };
})();`,
);
vm.runInThisContext(appSource, { filename: 'app.js' });
const T = global.__DragonSagaTacticalTest;
assert.ok(T, 'tactical test bridge should be injected only by this harness');

const action = (id, overrides = {}) => ({
  id, name: id, type: 'attack', kind: 'melee', cost: 'action', targetSide: 'enemy',
  attackBonus: 100, damage: '1', damageType: 'slashing', saveAbility: null, saveDC: null,
  halfOnSave: false, currentUses: null, maxUses: null, notes: '', ...overrides,
});
const character = (id, name, role = 'hero', overrides = {}) => ({
  ...DragonEngine.blankCharacter(role), id, name, role, hp: 20, maxHp: 20, ac: 10,
  actions: [], ...overrides,
});
function battleState(characters, positions, order = characters.map(c => c.id), turnIndex = 0) {
  const state = T.baseState();
  state.session.role = 'gm';
  state.characters = characters;
  state.battle.active = true;
  state.battle.order = order;
  state.battle.turnIndex = turnIndex;
  state.battle.positions = { ...positions };
  state.battle.movement = Object.fromEntries(characters.map(c => [c.id, c.speed]));
  state.battle.turnStartZones = Object.fromEntries(characters.map(c => [c.id, positions[c.id]]));
  state.battle.flags = Object.fromEntries(characters.map(c => [c.id, { actionUsed: false, bonusUsed: false, disengaged: false }]));
  return state;
}

// A legal adjacent move costs 10 feet and leaving a vanguard triggers every available adjacent reaction.
{
  const runner = character('h', 'Runner');
  const enemy1 = character('e1', 'Guard one', 'enemy', { actions: [action('oa1')] });
  const enemy2 = character('e2', 'Guard two', 'enemy', { actions: [action('oa2')] });
  T.setState(battleState([runner, enemy1, enemy2], { h: 'a1', e1: 'a2', e2: 'a2' }));
  T.moveActor('h', -1);
  const state = T.getState();
  assert.equal(state.battle.positions.h, 't1');
  assert.equal(state.battle.movement.h, 20);
  assert.equal(state.characters.find(c => c.id === 'h').hp, 18);
  assert.equal(state.characters.find(c => c.id === 'e1').reactionAvailable, false);
  assert.equal(state.characters.find(c => c.id === 'e2').reactionAvailable, false);
}

// An impossible move must not provoke reactions before movement validation.
{
  const runner = character('h', 'Spent runner');
  const enemy = character('e', 'Guard', 'enemy', { actions: [action('oa')] });
  const state = battleState([runner, enemy], { h: 'a1', e: 'a2' });
  state.battle.movement.h = 0;
  T.setState(state);
  T.moveActor('h', -1);
  assert.equal(T.getState().battle.positions.h, 'a1');
  assert.equal(T.getState().characters.find(c => c.id === 'e').reactionAvailable, true);
  assert.equal(T.getState().characters.find(c => c.id === 'h').hp, 20);
}

// Disengage consumes the action and prevents opportunity attacks.
{
  const runner = character('h', 'Careful runner');
  const enemy = character('e', 'Guard', 'enemy', { actions: [action('oa')] });
  T.setState(battleState([runner, enemy], { h: 'a1', e: 'a2' }));
  T.disengageActor(T.getState().characters.find(c => c.id === 'h'));
  T.moveActor('h', -1);
  const state = T.getState();
  assert.equal(state.battle.flags.h.actionUsed, true);
  assert.equal(state.battle.positions.h, 't1');
  assert.equal(state.characters.find(c => c.id === 'e').reactionAvailable, true);
}

// Speed-40 flank spends all movement, crosses rear-to-rear, and does not provoke.
{
  const scout = character('h', 'Scout', 'hero', { speed: 40 });
  const enemy = character('e', 'Guard', 'enemy', { actions: [action('oa')] });
  T.setState(battleState([scout, enemy], { h: 't1', e: 'a2' }));
  T.moveActor('h', 0, 'flank');
  const state = T.getState();
  assert.equal(state.battle.positions.h, 't2');
  assert.equal(state.battle.movement.h, 0);
  assert.equal(state.battle.flags.h.flanked, true);
  assert.equal(state.characters.find(c => c.id === 'e').reactionAvailable, true);
}

// Rear-to-vanguard movement enables one charged melee attack and one incoming exposed attack.
{
  const charger = character('h', 'Charger', 'hero', { actions: [action('charge')] });
  const enemy = character('e', 'Target', 'enemy', { actions: [action('counter')] });
  T.setState(battleState([charger, enemy], { h: 't1', e: 'a2' }));
  T.moveActor('h', 1);
  let state = T.getState();
  assert.equal(state.battle.flags.h.chargeReady, true);
  T.resolveAction(state.characters.find(c => c.id === 'h'), state.characters.find(c => c.id === 'h').actions[0], state.characters.find(c => c.id === 'e'));
  state = T.getState();
  assert.equal(state.battle.flags.h.chargeReady, false);
  assert.equal(state.battle.flags.h.charged, true);
  assert.equal(state.characters.find(c => c.id === 'h').exposedCharge, true);
  assert.match(state.battle.result.text, /ПОПАДАНИЕ/);
  T.resolveAction(state.characters.find(c => c.id === 'e'), state.characters.find(c => c.id === 'e').actions[0], state.characters.find(c => c.id === 'h'));
  assert.equal(T.getState().characters.find(c => c.id === 'h').exposedCharge, false);
  assert.match(T.getState().battle.result.text, /уязвимость после натиска/);
}

// Melee cannot reach across the full line; action and resource economies are enforced.
{
  const hero = character('h', 'Hero', 'hero', {
    actions: [
      action('strike', { currentUses: 2, maxUses: 2 }),
      action('quick', { type: 'damage', kind: 'ranged', cost: 'bonus' }),
    ],
  });
  const enemy = character('e', 'Far enemy', 'enemy');
  T.setState(battleState([hero, enemy], { h: 't1', e: 't2' }));
  let state = T.getState();
  T.resolveAction(state.characters[0], state.characters[0].actions[0], state.characters[1]);
  assert.equal(T.getState().characters[1].hp, 20);
  assert.equal(T.getState().battle.flags.h.actionUsed, false);
  assert.equal(T.getState().characters[0].actions[0].currentUses, 2);
  T.getState().battle.positions.h = 'a1';
  T.getState().battle.positions.e = 'a2';
  state = T.getState();
  T.resolveAction(state.characters[0], state.characters[0].actions[0], state.characters[1]);
  assert.equal(T.getState().characters[1].hp, 19);
  assert.equal(T.getState().characters[0].actions[0].currentUses, 1);
  T.resolveAction(state.characters[0], state.characters[0].actions[0], state.characters[1]);
  assert.equal(T.getState().characters[1].hp, 19, 'second action in the same turn is blocked');
  T.resolveAction(state.characters[0], state.characters[0].actions[1], state.characters[1]);
  assert.equal(T.getState().characters[1].hp, 18, 'bonus action remains independently available');
  T.resolveAction(state.characters[0], state.characters[0].actions[1], state.characters[1]);
  assert.equal(T.getState().characters[1].hp, 18, 'second bonus action is blocked');
}

// Tactical Breather spends one Hit Die and one bonus action only in a safe friendly rear.
{
  const hero = character('h', 'Wounded', 'hero', { hp: 1, stats: { str: 10, dex: 10, con: 14, int: 10, wis: 10, cha: 10 }, hitDice: { die: 8, current: 1, max: 1 } });
  T.setState(battleState([hero], { h: 't1' }));
  T.tacticalBreather(T.getState().characters[0]);
  const state = T.getState();
  assert.ok(state.characters[0].hp > 1);
  assert.equal(state.characters[0].hitDice.current, 0);
  assert.equal(state.battle.flags.h.bonusUsed, true);
  const hp = state.characters[0].hp;
  T.tacticalBreather(state.characters[0]);
  assert.equal(T.getState().characters[0].hp, hp);
}

// Rear Cover adds +2 AC and disadvantage to a direct ranged attack.
{
  const rear = character('h1', 'Rear hero', 'hero');
  const vanguard = character('h2', 'Shield hero', 'hero');
  const archer = character('e', 'Archer', 'enemy', { actions: [action('shot', { kind: 'ranged' })] });
  T.setState(battleState([archer, rear, vanguard], { e: 'a2', h1: 't1', h2: 'a1' }, ['e', 'h1', 'h2']));
  let state = T.getState();
  assert.equal(T.rearCover(state.characters.find(c => c.id === 'h1')), true);
  T.resolveAction(state.characters.find(c => c.id === 'e'), state.characters.find(c => c.id === 'e').actions[0], state.characters.find(c => c.id === 'h1'));
  assert.match(T.getState().battle.result.text, /КД 12/);
  assert.match(T.getState().battle.result.text, /укрытие тыла/);
}

// Boss investigation uses nature and distance for DC without consuming an action.
{
  const analyst = character('h', 'Analyst', 'hero');
  const boss = character('b', 'Boss', 'enemy', { boss: true, telegraph: { name: 'Rune storm', nature: 'magical', counter: 'Break the rune', stage: 'prepared' } });
  T.setState(battleState([analyst, boss], { h: 't1', b: 't2' }));
  T.investigateBoss(T.getState().characters[0], T.getState().characters[1], 'analysis');
  const state = T.getState();
  assert.match(state.battle.log.at(-1).text, /Сл 17/);
  assert.equal(state.battle.flags.h.actionUsed, false);
  assert.equal(state.battle.flags.h.bonusUsed, false);
}

// Two full-body models remain separate actor nodes, with movement, conditions, current-turn, and tooltips rendered.
{
  const first = character('h1', 'First', 'hero', { conditions: ['отравлен'], modelScale: 120 });
  const second = character('h2', 'Second', 'hero', { modelScale: 80 });
  const state = battleState([first, second], { h1: 'a1', h2: 'a1' });
  state.battle.movement.h1 = 15;
  T.setState(state);
  const firstCard = T.actorCard(T.getState().characters[0]);
  const secondCard = T.actorCard(T.getState().characters[1]);
  assert.match(firstCard, /class="actor hero current/);
  assert.match(firstCard, /15 фт/);
  assert.match(firstCard, /title="отравлен"/);
  assert.match(firstCard, /--actor-scale:1\.2/);
  assert.match(secondCard, /data-target="h2"/);
  const field = T.renderBattle();
  assert.match(field, /Т1[\s\S]*А1[\s\S]*А2[\s\S]*Т2/);
  assert.equal((field.match(/class="actor hero/g) || []).length, 2);
}

// Relative scene object sizing and owned-sheet inventory/resource output stay intact.
{
  const hero = character('h', 'Equipped', 'hero', {
    resources: [{ id: 'r', name: 'Focus', current: 1, max: 2, recovery: 'short' }],
    inventory: [{ id: 'sword', name: 'Sword', quantity: 1, value: 5, equippedSlot: 'mainHand' }],
    equipment: { armor: null, mainHand: 'sword', offHand: null, accessory: null },
  });
  const state = battleState([hero], { h: 't1' });
  state.assets = [{ id: 'asset', name: 'Model', kind: 'image', data: 'data:image/png;base64,AA==' }];
  T.setState(state);
  const objectHtml = T.sceneObject({ id: 'o', assetId: 'asset', x: 25, y: 75, scale: 33 });
  assert.match(objectHtml, /left:25%;top:75%;width:33%/);
  const sheet = T.renderSheet(T.getState().characters[0]);
  assert.match(sheet, /Focus[\s\S]*<span>1\/2<\/span>/);
  assert.match(sheet, /Основная рука: Sword/);
}

// Theme values, idle timing clamps, and exact-string localization are declarative.
{
  const state = T.baseState();
  state.settings.theme = { accent: '#123abc', gold: '#fed321' };
  state.settings.animation = { idleDuration: 99 };
  state.settings.localization = { 'Exact text': 'Точный текст' };
  T.setState(state);
  T.applyScales();
  assert.equal(elements.app.style.props['--accent'], '#123abc');
  assert.equal(elements.app.style.props['--gold'], '#fed321');
  assert.equal(elements.app.style.props['--idle-duration'], '10s');
  textNodes.push({ nodeValue: ' Exact text ' }, { nodeValue: 'Not translated' });
  T.applyLocalization();
  assert.equal(textNodes[0].nodeValue, ' Точный текст ');
  assert.equal(textNodes[1].nodeValue, 'Not translated');
}

const css = fs.readFileSync(require.resolve('../public/styles.css'), 'utf8');
assert.match(css, /\.zone-actors\{[^}]*display:flex/);
assert.match(css, /\.actor\{[^}]*margin:0 -11%/);
assert.match(css, /animation:idle var\(--idle-duration/);
console.log('tactical renderer integration: PASS (movement, reactions, flank, charge, cover, breather, boss, models, themes)');
