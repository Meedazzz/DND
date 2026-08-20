import http from 'node:http';
import { randomUUID } from 'node:crypto';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC = path.join(__dirname, 'public');
const PORT = Number(process.env.PORT || 4173);
const rooms = new Map();
const MAX_BODY = 12 * 1024 * 1024;

const mime = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.webp': 'image/webp', '.gif': 'image/gif', '.mp3': 'audio/mpeg', '.ogg': 'audio/ogg',
  '.wav': 'audio/wav', '.m4a': 'audio/mp4', '.woff': 'font/woff', '.woff2': 'font/woff2'
};

function json(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(body));
}

function roomFor(code) {
  if (!rooms.has(code)) rooms.set(code, {
    state: null, revision: 0, clients: new Set(), sessions: new Map(),
    ownerKey: null, touched: Date.now()
  });
  return rooms.get(code);
}

function clone(value) {
  return value === undefined ? undefined : structuredClone(value);
}

function authToken(req, url) {
  const bearer = String(req.headers.authorization || '').match(/^Bearer\s+(.+)$/i)?.[1];
  return bearer || url.searchParams.get('token') || '';
}

function sessionFor(room, req, url) {
  const token = authToken(req, url);
  const session = room.sessions.get(token) || null;
  if (session) session.touched = Date.now();
  return session;
}

function membersFor(room) {
  const members = [];
  for (const session of room.sessions.values()) {
    members.push({
      clientId: session.clientId,
      name: session.name,
      role: session.role,
      characterId: session.characterId || null
    });
  }
  return members;
}

function networkOverlay(room) {
  const members = membersFor(room);
  const owners = {};
  for (const member of members) {
    if (member.role === 'player' && member.characterId) owners[member.characterId] = member.clientId;
  }
  return {
    members,
    owners,
    gmClientId: members.find(member => member.role === 'gm')?.clientId || null
  };
}

function stateForSession(room, session) {
  if (!room.state) return null;
  const visible = clone(room.state);
  visible.network = { ...(visible.network || {}), ...networkOverlay(room) };
  if (!session || session.role !== 'gm') {
    const ownId = session?.characterId || null;
    visible.characters = (visible.characters || [])
      .filter(character => character.id === ownId || character.visibility !== 'gm')
      .map(character => {
        if (character.id === ownId) return character;
        delete character.rawText;
        delete character.gmNotes;
        return character;
      });
    if (visible.compendium) {
      visible.compendium.creatures = [];
      visible.compendium.events = [];
      visible.compendium.locations = [];
      visible.compendium.buildings = [];
    }
    if (visible.expedition?.route) {
      visible.expedition.route = visible.expedition.route.map(node => node.status === 'locked'
        ? { id: node.id, status: 'locked', type: 'unknown', name: 'Неизведанный путь' }
        : node);
    }
  }
  return visible;
}

function broadcast(room, sender = null) {
  for (const client of room.clients) {
    try {
      const session = room.sessions.get(client.token) || null;
      const payload = { state: stateForSession(room, session), revision: room.revision, sender };
      client.response.write(`data: ${JSON.stringify(payload)}\n\n`);
    } catch {
      room.clients.delete(client);
    }
  }
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let size = 0; const chunks = [];
    req.on('data', chunk => {
      size += chunk.length;
      if (size > MAX_BODY) { reject(new Error('Payload too large')); req.destroy(); return; }
      chunks.push(chunk);
    });
    req.on('end', () => {
      try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8') || '{}')); }
      catch { reject(new Error('Invalid JSON')); }
    });
    req.on('error', reject);
  });
}

function claimedByAnother(room, characterId, token) {
  if (!characterId) return false;
  for (const [otherToken, session] of room.sessions) {
    if (otherToken !== token && session.role === 'player' && session.characterId === characterId) return true;
  }
  return false;
}

function registerSession(room, body) {
  const existingToken = String(body.sessionToken || '');
  const existing = room.sessions.get(existingToken);
  let token = existing ? existingToken : randomUUID();
  let ownerKey = null;
  let role = 'player';

  if (body.role === 'gm') {
    if (!room.ownerKey) {
      room.ownerKey = randomUUID() + randomUUID();
      ownerKey = room.ownerKey;
      role = 'gm';
    } else if (String(body.ownerKey || '') === room.ownerKey || existing?.role === 'gm') {
      role = 'gm';
    }
  }

  const requestedCharacter = String(body.characterId || '') || null;
  let characterId = role === 'player' ? requestedCharacter : null;
  let warning = '';
  if (role === 'player' && characterId) {
    const hero = room.state?.characters?.find(character => character.id === characterId && character.role === 'hero');
    if ((room.state && !hero) || claimedByAnother(room, characterId, token)) {
      characterId = null;
      warning = 'Герой уже занят или отсутствует в кампании';
    }
  }

  const session = {
    token,
    clientId: String(body.clientId || existing?.clientId || randomUUID()).slice(0, 100),
    name: String(body.name || existing?.name || 'Игрок').trim().slice(0, 80) || 'Игрок',
    role,
    characterId,
    touched: Date.now()
  };
  room.sessions.set(token, session);
  room.touched = Date.now();
  return { session, ownerKey, warning };
}

const TARGET_FIELDS = [
  'hp', 'tempHp', 'conditions', 'statusEffects', 'concentration', 'deathSaves',
  'stress', 'resolve', 'rank'
];

function activeCharacterId(state) {
  if (!state?.combat?.started) return null;
  const ordered = [...(state.characters || [])].sort((a, b) => (b.initiativeRoll ?? -999) - (a.initiativeRoll ?? -999));
  return ordered[state.combat.turnIndex]?.id || null;
}

function validFormation(next, current, ownId) {
  if (!Array.isArray(next) || !Array.isArray(current)) return null;
  const currentIds = current.map(slot => slot.characterId).sort().join('|');
  const nextIds = next.map(slot => slot.characterId).sort().join('|');
  if (currentIds !== nextIds || !next.some(slot => slot.characterId === ownId)) return null;
  if (next.some(slot => !['hero', 'enemy'].includes(slot.side) || !Number.isInteger(slot.rank) || slot.rank < 1 || slot.rank > 5)) return null;
  return clone(next);
}

function sanitizePlayerInventory(currentItems,submittedItems) {
  const submitted=new Map((Array.isArray(submittedItems)?submittedItems:[]).map(item=>[item?.id,item]));
  const result=[];
  for(const item of Array.isArray(currentItems)?currentItems:[]){
    const next=submitted.get(item.id);if(!next)continue;
    const quantity=Math.max(0,Math.min(Number(item.quantity||1),Number(next.quantity||0)));
    if(quantity>0)result.push({...clone(item),quantity});
  }
  return result;
}

function applyPlayerState(room, session, incoming) {
  const current = room.state;
  const next = clone(current);
  const ownId = session.characterId;
  if (!ownId) throw Object.assign(new Error('No hero assigned'), { status: 403 });

  const currentOwn = current.characters?.find(character => character.id === ownId && character.role === 'hero');
  const incomingOwn = incoming.characters?.find(character => character.id === ownId);
  if (!currentOwn || !incomingOwn) throw Object.assign(new Error('Assigned hero is missing'), { status: 403 });

  const ownIndex = next.characters.findIndex(character => character.id === ownId);
  next.characters[ownIndex] = {
    ...clone(incomingOwn),
    id: currentOwn.id,
    role: currentOwn.role,
    relationships: clone(currentOwn.relationships || {}),
    inventory: sanitizePlayerInventory(currentOwn.inventory, incomingOwn.inventory),
    visibility: currentOwn.visibility
  };

  const ownsActiveTurn = activeCharacterId(current) === ownId;
  if (ownsActiveTurn) {
    for (const character of next.characters) {
      if (character.id === ownId) continue;
      const submitted = incoming.characters?.find(candidate => candidate.id === character.id);
      if (!submitted) continue;
      for (const field of TARGET_FIELDS) if (field in submitted) character[field] = clone(submitted[field]);
    }
    if (incoming.expedition && current.expedition) {
      next.expedition.light = Math.max(0, Math.min(100, Number(incoming.expedition.light ?? current.expedition.light)));
    }
  }

  if (incoming.combat?.targetId && next.characters.some(character => character.id === incoming.combat.targetId)) {
    next.combat.targetId = incoming.combat.targetId;
  }

  const oldLog = Array.isArray(current.rollLog) ? current.rollLog : [];
  const submittedLog = Array.isArray(incoming.rollLog) ? incoming.rollLog : [];
  const oldIds = new Set(oldLog.map(entry => entry.id));
  const additions = submittedLog.filter(entry => entry?.id && !oldIds.has(entry.id)).slice(0, 20);
  next.rollLog = [...clone(additions), ...clone(oldLog)].slice(0, 100);

  if (incoming.scene && current.scene) {
    const ownCurrentToken = current.scene.tokens?.find(token => token.characterId === ownId);
    const ownSubmittedToken = incoming.scene.tokens?.find(token => token.characterId === ownId);
    if (ownCurrentToken && ownSubmittedToken) {
      const tokenIndex = next.scene.tokens.findIndex(token => token.characterId === ownId);
      next.scene.tokens[tokenIndex] = {
        ...next.scene.tokens[tokenIndex],
        x: Math.max(0, Math.min(100, Number(ownSubmittedToken.x))),
        y: Math.max(0, Math.min(100, Number(ownSubmittedToken.y)))
      };
    }
    const formation = validFormation(incoming.scene.formation, current.scene.formation, ownId);
    if (formation) next.scene.formation = formation;
  }

  next.network = clone(current.network || {});
  return next;
}

async function serveStatic(req, res) {
  const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
  const requested = pathname === '/' ? '/index.html' : pathname;
  const file = path.normalize(path.join(PUBLIC, requested));
  if (!file.startsWith(PUBLIC)) return json(res, 403, { error: 'Forbidden' });
  try {
    const info = await stat(file);
    if (!info.isFile()) throw new Error('not file');
    const data = await readFile(file);
    res.writeHead(200, {
      'Content-Type': mime[path.extname(file)] || 'application/octet-stream',
      'Cache-Control': path.extname(file) === '.html' ? 'no-store' : 'public, max-age=300',
      'X-Content-Type-Options': 'nosniff'
    });
    res.end(data);
  } catch {
    if (!path.extname(requested)) {
      try {
        const data = await readFile(path.join(PUBLIC, 'index.html'));
        res.writeHead(200, { 'Content-Type': mime['.html'], 'Cache-Control': 'no-store' });
        return res.end(data);
      } catch {}
    }
    json(res, 404, { error: 'Not found' });
  }
}

export function createHttpServer() {
  return http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://localhost');
    const roomMatch = url.pathname.match(/^\/api\/rooms\/([A-ZА-Я0-9_-]{1,12})\/(state|events|session)$/i);

    if (roomMatch) {
      const code = roomMatch[1].toUpperCase();
      const action = roomMatch[2].toLowerCase();
      const room = roomFor(code);

      if (action === 'session' && req.method === 'DELETE') {
        const token = authToken(req, url);
        if (!room.sessions.has(token)) return json(res, 401, { error: 'Room session required' });
        const departed = room.sessions.get(token);
        room.sessions.delete(token);
        if (room.state) { room.revision += 1; broadcast(room, departed.clientId); }
        return json(res, 200, { ok: true, revision: room.revision });
      }

      if (action === 'session' && req.method === 'POST') {
        try {
          const body = await readBody(req);
          const { session, ownerKey, warning } = registerSession(room, body);
          if (room.state) { room.revision += 1; broadcast(room, session.clientId); }
          return json(res, 200, {
            ok: true,
            token: session.token,
            ownerKey,
            role: session.role,
            characterId: session.characterId,
            warning,
            state: stateForSession(room, session),
            revision: room.revision
          });
        } catch (error) {
          return json(res, error.message === 'Payload too large' ? 413 : 400, { error: error.message });
        }
      }

      if (action === 'state' && req.method === 'GET') {
        const session = sessionFor(room, req, url);
        if (!session) return json(res, 401, { error: 'Room session required' });
        if (!room.state) return json(res, 404, { error: 'Empty room' });
        return json(res, 200, { state: stateForSession(room, session), revision: room.revision });
      }

      if (action === 'state' && req.method === 'POST') {
        try {
          const session = sessionFor(room, req, url);
          if (!session) return json(res, 401, { error: 'Room session required' });
          const body = await readBody(req);
          if (!body.state || typeof body.state !== 'object') return json(res, 400, { error: 'Missing state' });
          if (Number(body.baseRevision) !== room.revision) {
            return json(res, 409, { error: 'Revision conflict', state: stateForSession(room, session), revision: room.revision });
          }
          if (!room.state) {
            if (session.role !== 'gm') return json(res, 403, { error: 'Only the room master can initialize a campaign' });
            room.state = body.state;
          } else {
            room.state = session.role === 'gm' ? body.state : applyPlayerState(room, session, body.state);
          }
          room.revision += 1;
          room.touched = Date.now();
          broadcast(room, session.clientId);
          return json(res, 200, {
            ok: true,
            revision: room.revision,
            state: stateForSession(room, session)
          });
        } catch (error) {
          return json(res, error.status || (error.message === 'Payload too large' ? 413 : 400), { error: error.message });
        }
      }

      if (action === 'events' && req.method === 'GET') {
        const session = sessionFor(room, req, url);
        if (!session) return json(res, 401, { error: 'Room session required' });
        res.writeHead(200, {
          'Content-Type': 'text/event-stream; charset=utf-8',
          'Cache-Control': 'no-cache, no-transform',
          'Connection': 'keep-alive',
          'X-Accel-Buffering': 'no'
        });
        res.write(': GrimDice authenticated room connected\n\n');
        const client = { response: res, token: session.token };
        room.clients.add(client);
        if (room.state) {
          const payload = { state: stateForSession(room, session), revision: room.revision, sender: null };
          res.write(`data: ${JSON.stringify(payload)}\n\n`);
        }
        const ping = setInterval(() => { try { res.write(': ping\n\n'); } catch {} }, 20000);
        req.on('close', () => { clearInterval(ping); room.clients.delete(client); });
        return;
      }
    }

    if (url.pathname === '/api/health') return json(res, 200, { ok: true, rooms: rooms.size, protocol: 2 });
    serveStatic(req, res);
  });
}

setInterval(() => {
  const cutoff = Date.now() - 12 * 60 * 60 * 1000;
  for (const [code, room] of rooms) if (room.touched < cutoff && room.clients.size === 0) rooms.delete(code);
}, 30 * 60 * 1000).unref();

export function startServer({ port = PORT, host = '0.0.0.0' } = {}) {
  const server = createHttpServer();
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, host, () => {
      const actualPort = server.address().port;
      console.log(`GrimDice is ready on http://${host}:${actualPort}`);
      resolve({ server, port: actualPort, host });
    });
  });
}

const isDirectRun = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isDirectRun) startServer().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
