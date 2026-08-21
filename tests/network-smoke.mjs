import assert from 'node:assert/strict';
import { startServer } from '../server.mjs';

const { server, port } = await startServer({ port: 0, host: '127.0.0.1' });
const base = `http://127.0.0.1:${port}`;
const request = async (path, { token, method = 'GET', body } = {}) => {
  const response = await fetch(base + path, {
    method,
    headers: {
      ...(body ? { 'content-type': 'application/json' } : {}),
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  return { response, data: await response.json() };
};
const hero = (id, name, visibility = 'party') => ({
  id, name, role: 'hero', visibility,
  hp: 20, maxHp: 20, tempHp: 0, speed: 30,
  stats: { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 },
  conditions: [], deathSaves: { success: 0, fail: 0 },
  currency: { gp: 10, sp: 0, cp: 0 }, inventory: [], equipment: {},
  resources: [], actions: [], sourceText: 'SECRET SOURCE', gmNotes: 'SECRET GM', audit: [],
});

try {
  const room = 'SAGA42';
  const roomPath = `/api/rooms/${room}`;
  const gmJoin = await request(`${roomPath}/session`, {
    method: 'POST', body: { clientId: 'gm-1', name: 'GM', role: 'gm' },
  });
  assert.equal(gmJoin.data.role, 'gm');
  assert.ok(gmJoin.data.ownerKey);
  const gmToken = gmJoin.data.token;

  const initial = {
    schema: 'dragon-saga-campaign', version: 3,
    meta: { title: 'Test', edition: '2024' },
    session: { token: 'must-not-leak', ownerKey: 'must-not-leak' },
    permissions: { mediaEditors: [], partySheetView: false, playerJournalShared: false },
    settings: {},
    characters: [
      hero('h1', 'Owned'), hero('h2', 'Private', 'private'), hero('h3', 'Unpermitted party sheet'),
      { ...hero('e1', 'Visible enemy'), role: 'enemy', hp: 12, maxHp: 12 },
      { ...hero('e2', 'Hidden enemy'), role: 'enemy' },
    ],
    journal: { party: 'party', chronicle: [], personal: { h1: 'mine', h2: 'theirs' } },
    world: {
      maps: [],
      locations: [
        { id: 'l1', name: 'Open', discovered: true, gmNotes: 'secret' },
        { id: 'l2', name: 'Hidden', discovered: false },
      ],
      routes: [],
    },
    cities: [
      {
        id: 'c1', name: 'Market', available: true,
        merchants: [{
          id: 'm1', name: 'Smith', available: true, buyRate: 0.5,
          stock: [
            { id: 'i1', name: 'Sword', price: 5, quantity: 2, available: true },
            { id: 'i4', name: 'Sealed Relic', price: 30, quantity: 1, available: false },
          ],
        }, {
          id: 'm2', name: 'Closed Trader', available: false, buyRate: 0.5,
          stock: [{ id: 'i3', name: 'Hidden Ore', price: 20, quantity: 1, available: true }],
        }],
      },
      { id: 'c2', name: 'Hidden city', available: false, merchants: [] },
    ],
    assets: [], scenes: [],
    content: { items: [{ id: 'secret' }], actions: [], creatures: [{ id: 'secret' }], mods: [] },
    battle: {
      active: true, round: 1, turnIndex: 0, order: ['h1', 'e1'],
      positions: { h1: 'a1', h2: 't1', e1: 'a2' }, movement: { h1: 30, h2: 30, e1: 30 },
      turnStartZones: { h1: 'a1' }, flags: { h1: {} }, targetId: null, result: null, log: [],
    },
  };

  const init = await request(`${roomPath}/state`, {
    method: 'POST', token: gmToken, body: { baseRevision: 0, state: initial },
  });
  assert.equal(init.response.status, 200);
  assert.equal(init.data.revision, 1);
  assert.deepEqual(init.data.state.session, {}, 'session secrets are never campaign state');

  const join = await request(`${roomPath}/session`, {
    method: 'POST', body: { clientId: 'p-1', name: 'Player', role: 'player', characterId: 'h1' },
  });
  assert.equal(join.data.revision, 2);
  assert.equal(join.data.characterId, 'h1');
  const playerToken = join.data.token;
  const visible = join.data.state;
  assert.deepEqual(visible.characters.map(c => c.id).sort(), ['e1', 'h1', 'h2']);
  const visibleAlly = visible.characters.find(c => c.id === 'h2');
  assert.equal(visibleAlly.sourceText, undefined);
  assert.equal(visibleAlly.actions, undefined, 'positioned ally is a battle projection, not an accessible sheet');
  assert.equal(visible.characters.find(c => c.id === 'e1').sourceText, undefined);
  assert.deepEqual(visible.world.locations.map(x => x.id), ['l1']);
  assert.equal(visible.world.locations[0].gmNotes, undefined);
  assert.deepEqual(Object.keys(visible.journal.personal), ['h1']);
  assert.equal(visible.cities.length, 1);
  assert.equal(visible.content.creatures.length, 0);

  // Valid purchase plus normal owned-sheet and active-turn changes.
  const submitted = structuredClone(visible);
  const own = submitted.characters.find(c => c.id === 'h1');
  const enemy = submitted.characters.find(c => c.id === 'e1');
  own.className = 'Player edited class';
  own.currency.gp = 5;
  own.inventory.push({ id: 'owned-sword', name: 'Sword', quantity: 1, value: 5 });
  enemy.hp = 7;
  submitted.cities[0].merchants[0].stock[0].quantity = 1;
  submitted.permissions.mediaEditors = ['p-1'];
  submitted.world.locations[0].name = 'HACK';
  submitted.assets.push({ id: 'bad', name: 'unauthorized' });
  const write = await request(`${roomPath}/state`, {
    method: 'POST', token: playerToken, body: { baseRevision: 2, state: submitted },
  });
  assert.equal(write.response.status, 200);
  assert.equal(write.data.revision, 3);

  let gmRead = await request(`${roomPath}/state`, { token: gmToken });
  let authoritative = gmRead.data.state;
  assert.equal(authoritative.characters.find(c => c.id === 'h1').className, 'Player edited class');
  assert.equal(authoritative.characters.find(c => c.id === 'e1').hp, 7, 'active player may resolve a battlefield target');
  assert.equal(authoritative.cities[0].merchants[0].stock[0].quantity, 1);
  assert.equal(authoritative.world.locations[0].name, 'Open', 'world editing remains GM-only');
  assert.deepEqual(authoritative.permissions.mediaEditors, [], 'players cannot grant permissions');
  assert.equal(authoritative.assets.length, 0, 'unauthorized media edits are ignored');

  // Hidden stock and closed merchants cannot be transacted against, even if a client forges them back into its payload.
  let availabilityView = await request(`${roomPath}/state`, { token: playerToken });
  const sealedStock = structuredClone(availabilityView.data.state);
  sealedStock.cities[0].merchants[0].stock.push({ id: 'i4', name: 'Sealed Relic', price: 30, quantity: 0, available: true });
  const sealedAttempt = await request(`${roomPath}/state`, {
    method: 'POST', token: playerToken, body: { baseRevision: 3, state: sealedStock },
  });
  assert.equal(sealedAttempt.response.status, 403, 'unavailable stock must reject the whole transaction');

  availabilityView = await request(`${roomPath}/state`, { token: playerToken });
  const closedMerchant = structuredClone(availabilityView.data.state);
  closedMerchant.cities[0].merchants.push({
    id: 'm2', name: 'Closed Trader', available: true, buyRate: 0.5,
    stock: [{ id: 'i3', name: 'Hidden Ore', price: 20, quantity: 0, available: true }],
  });
  const closedAttempt = await request(`${roomPath}/state`, {
    method: 'POST', token: playerToken, body: { baseRevision: 3, state: closedMerchant },
  });
  assert.equal(closedAttempt.response.status, 403, 'an unavailable merchant must reject the whole transaction');

  // Explicit media permission.
  authoritative.permissions.mediaEditors = ['p-1'];
  const grant = await request(`${roomPath}/state`, {
    method: 'POST', token: gmToken, body: { baseRevision: 3, state: authoritative },
  });
  assert.equal(grant.data.revision, 4);
  let fresh = await request(`${roomPath}/state`, { token: playerToken });
  const withAsset = structuredClone(fresh.data.state);
  withAsset.assets.push({ id: 'ok', name: 'permitted.png', kind: 'image', data: 'data:image/png;base64,AA==' });
  const mediaWrite = await request(`${roomPath}/state`, {
    method: 'POST', token: playerToken, body: { baseRevision: 4, state: withAsset },
  });
  assert.equal(mediaWrite.response.status, 200);
  assert.equal(mediaWrite.data.revision, 5);
  gmRead = await request(`${roomPath}/state`, { token: gmToken });
  assert.equal(gmRead.data.state.assets[0].id, 'ok');

  // Forged gold/inventory without an authoritative stock delta is rejected atomically.
  fresh = await request(`${roomPath}/state`, { token: playerToken });
  const minted = structuredClone(fresh.data.state);
  const mintedOwn = minted.characters.find(c => c.id === 'h1');
  mintedOwn.currency.gp += 100;
  mintedOwn.inventory.push({ id: 'forged', name: 'Forged relic', quantity: 1, value: 999 });
  const mintAttempt = await request(`${roomPath}/state`, {
    method: 'POST', token: playerToken, body: { baseRevision: 5, state: minted },
  });
  assert.equal(mintAttempt.response.status, 403);
  gmRead = await request(`${roomPath}/state`, { token: gmToken });
  assert.equal(gmRead.data.revision, 5);
  assert.equal(gmRead.data.state.characters.find(c => c.id === 'h1').currency.gp, 5);
  assert.equal(gmRead.data.state.characters.find(c => c.id === 'h1').inventory.length, 1);

  // A stock decrement with missing payment is also rejected.
  const underpaid = structuredClone(fresh.data.state);
  underpaid.cities[0].merchants[0].stock[0].quantity = 0;
  underpaid.characters.find(c => c.id === 'h1').inventory[0].quantity = 2;
  const underpaidAttempt = await request(`${roomPath}/state`, {
    method: 'POST', token: playerToken, body: { baseRevision: 5, state: underpaid },
  });
  assert.equal(underpaidAttempt.response.status, 403);

  // Valid selling uses the authoritative item value and merchant buyback rate.
  const selling = structuredClone(fresh.data.state);
  const sellingOwn = selling.characters.find(c => c.id === 'h1');
  const swordId = sellingOwn.inventory[0].id;
  sellingOwn.currency.gp = 7.5;
  sellingOwn.inventory = [];
  sellingOwn.equipment.mainHand = swordId; // Must be cleaned because the item is sold.
  selling.cities[0].merchants[0].stock[0].quantity = 2;
  const sale = await request(`${roomPath}/state`, {
    method: 'POST', token: playerToken, body: { baseRevision: 5, state: selling },
  });
  assert.equal(sale.response.status, 200);
  assert.equal(sale.data.revision, 6);
  gmRead = await request(`${roomPath}/state`, { token: gmToken });
  authoritative = gmRead.data.state;
  const afterSale = authoritative.characters.find(c => c.id === 'h1');
  assert.equal(afterSale.currency.gp, 7.5);
  assert.equal(afterSale.inventory.length, 0);
  assert.equal(afterSale.equipment.mainHand, null);
  assert.equal(authoritative.cities[0].merchants[0].stock[0].quantity, 2);

  // Mixed valid/forged commerce rolls back every field and does not consume a revision.
  fresh = await request(`${roomPath}/state`, { token: playerToken });
  const mixed = structuredClone(fresh.data.state);
  const mixedOwn = mixed.characters.find(c => c.id === 'h1');
  mixedOwn.className = 'MUST ROLL BACK';
  mixedOwn.currency.gp = 2.5;
  mixedOwn.inventory.push(
    { id: 'new-sword', name: 'Sword', quantity: 1, value: 5 },
    { id: 'smuggled', name: 'Smuggled crown', quantity: 1, value: 500 },
  );
  mixed.cities[0].merchants[0].stock[0].quantity = 1;
  const mixedAttempt = await request(`${roomPath}/state`, {
    method: 'POST', token: playerToken, body: { baseRevision: 6, state: mixed },
  });
  assert.equal(mixedAttempt.response.status, 403);
  gmRead = await request(`${roomPath}/state`, { token: gmToken });
  assert.equal(gmRead.data.revision, 6);
  assert.equal(gmRead.data.state.characters.find(c => c.id === 'h1').className, 'Player edited class');
  assert.equal(gmRead.data.state.cities[0].merchants[0].stock[0].quantity, 2);

  // End the hero turn, then prove off-turn battle writes cannot affect shared combat.
  fresh = await request(`${roomPath}/state`, { token: playerToken });
  const endTurn = structuredClone(fresh.data.state);
  endTurn.battle.turnIndex = 1;
  endTurn.battle.round = 1;
  const advance = await request(`${roomPath}/state`, {
    method: 'POST', token: playerToken, body: { baseRevision: 6, state: endTurn },
  });
  assert.equal(advance.response.status, 200);
  assert.equal(advance.data.revision, 7);

  fresh = await request(`${roomPath}/state`, { token: playerToken });
  const offTurn = structuredClone(fresh.data.state);
  offTurn.characters.find(c => c.id === 'e1').hp = 1;
  offTurn.battle.positions.h1 = 't1';
  offTurn.battle.positions.e1 = 't2';
  offTurn.battle.movement.h1 = 0;
  offTurn.battle.result = { text: 'FORGED RESULT' };
  offTurn.battle.log.push({ text: 'FORGED LOG' });
  const offTurnWrite = await request(`${roomPath}/state`, {
    method: 'POST', token: playerToken, body: { baseRevision: 7, state: offTurn },
  });
  assert.equal(offTurnWrite.response.status, 200);
  gmRead = await request(`${roomPath}/state`, { token: gmToken });
  authoritative = gmRead.data.state;
  assert.equal(authoritative.characters.find(c => c.id === 'e1').hp, 7);
  assert.deepEqual(authoritative.battle.positions, { h1: 'a1', h2: 't1', e1: 'a2' });
  assert.equal(authoritative.battle.movement.h1, 30);
  assert.equal(authoritative.battle.result, null);
  assert.deepEqual(authoritative.battle.log, []);

  const duplicate = await request(`${roomPath}/session`, {
    method: 'POST', body: { clientId: 'p-2', name: 'Other', role: 'player', characterId: 'h1' },
  });
  assert.equal(duplicate.data.characterId, null);
  assert.ok(duplicate.data.warning);
  const stale = await request(`${roomPath}/state`, {
    method: 'POST', token: playerToken, body: { baseRevision: 8, state: offTurn },
  });
  assert.equal(stale.response.status, 409);

  // The GM can override hero ownership; the former owner immediately loses the private sheet.
  const assignment = await request(`${roomPath}/assignment`, {
    method: 'POST', token: gmToken, body: { clientId: 'p-2', characterId: 'h1' },
  });
  assert.equal(assignment.response.status, 200);
  assert.equal(assignment.data.members.find(member => member.clientId === 'p-2').characterId, 'h1');
  assert.equal(assignment.data.members.find(member => member.clientId === 'p-1').characterId, null);
  const formerOwner = await request(`${roomPath}/state`, { token: playerToken });
  const formerOwnerBattleHero = formerOwner.data.state.characters.find(character => character.id === 'h1');
  assert.ok(formerOwnerBattleHero, 'positioned allies remain visible on the shared battle scene');
  assert.equal(formerOwnerBattleHero.sourceText, undefined);
  assert.equal(formerOwnerBattleHero.className, undefined, 'an unowned battle participant is not an exposed sheet');
  assert.equal(formerOwnerBattleHero.actions, undefined);
  const reassignedOwner = await request(`${roomPath}/state`, { token: duplicate.data.token });
  assert.ok(reassignedOwner.data.state.characters.some(character => character.id === 'h1'));

  console.log('network authority integration: PASS (visibility, trade authority, turn filtering, media, GM ownership override)');
} finally {
  await new Promise(resolve => server.close(resolve));
}
