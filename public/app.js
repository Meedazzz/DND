(() => {
  'use strict';

  const STORAGE_KEY = 'grimdice-campaign-v1';
  const ABILITIES = ['str', 'dex', 'con', 'int', 'wis', 'cha'];
  const MAX_RANKS = 5;
  const CONTENT_CATEGORIES = { abilities:'Способности', creatures:'Существа', items:'Предметы', effects:'Эффекты', locations:'Локации', events:'События', buildings:'Здания' };
  const MEDIA_CATEGORIES = {
    sprites:{label:'Спрайты и токены',accept:'image/*,.webm,.mp4',glyph:'♟',preview:'image'},
    portraits:{label:'Портреты',accept:'image/*',glyph:'◈',preview:'image'},
    backgrounds:{label:'Боевые фоны',accept:'image/*,.webm,.mp4',glyph:'▧',preview:'image'},
    maps:{label:'Карты маршрутов',accept:'image/*,.svg',glyph:'⌘',preview:'image'},
    effects:{label:'Визуальные эффекты',accept:'image/*,.webm,.mp4,.json',glyph:'✦',preview:'image'},
    sounds:{label:'Звуки',accept:'audio/*',glyph:'◖',preview:'audio'},
    music:{label:'Музыка',accept:'audio/*',glyph:'♪',preview:'audio'},
    fonts:{label:'Шрифты',accept:'.woff,.woff2,.ttf,.otf,font/*',glyph:'Aa',preview:'file'},
    animations:{label:'Определения анимаций',accept:'.json,application/json',glyph:'↝',preview:'file'},
    themes:{label:'Темы',accept:'.json,application/json',glyph:'◐',preview:'file'},
    localization:{label:'Локализация',accept:'.json,application/json,.csv,text/csv',glyph:'ЯA',preview:'file'}
  };
  const EXPEDITION_NODE_LABELS = { start:'Привал', battle:'Схватка', hazard:'Опасность', curio:'Находка', camp:'Лагерь', elite:'Элита', boss:'Владыка' };
  const ABILITY_RU = { str: 'СИЛ', dex: 'ЛОВ', con: 'ТЕЛ', int: 'ИНТ', wis: 'МДР', cha: 'ХАР' };
  const CONDITION_OPTIONS = ['Ослеплён', 'Очарован', 'Оглушён', 'Испуган', 'Невидим', 'Парализован', 'Отравлен', 'Сбит с ног', 'Опутан', 'Без сознания', 'Истощение 1', 'Застигнут врасплох', 'Концентрация'];
  const SAMPLE_TEXT = `Имя: Сестра Мирен\nКласс: Жрец 5\nРаса: Человек\nКД: 18\nХиты: 38/38\nСкорость: 30 футов\nБонус мастерства: +3\nСИЛ 14, ЛОВ 10, ТЕЛ 16, ИНТ 11, МДР 18, ХАР 13\nСпасброски: МДР +7, ХАР +4\nСл заклинаний: 15\nАтака заклинанием: +7\nСопротивления: некротический\nРесурсы: Божественный канал 1/1 (короткий отдых); Целительное касание 2/2 (долгий отдых)\n\nДействия:\nБулава. Атака +5, урон 1d6+2 дробящий.\nСвященное пламя. Спасбросок ЛОВ Сл 15, урон 2d8 излучение.\nЛечение ран. Лечение 1d8+4, дистанция касание.\nДуховное оружие. Атака заклинанием +7, урон 1d8+4 силовой, 10 раундов.\nНаправленная мощь (1/1, короткий отдых). Урон 2d10 излучение.`;

  const runtime = {
    view: 'combat',
    rollMode: 'normal',
    editCharacterId: null,
    editTab: 'main',
    clientId: cryptoId(),
    eventSource: null,
    roomCode: null,
    roomToken: null,
    roomOwnerKey: null,
    roomRevision: 0,
    applyingRemote: false,
    mutationVersion: 0,
    syncing: false,
    syncQueued: false,
    syncTimer: null,
    assetUrls: new Map(),
    audio: null,
    playingTrack: null,
    workshopCategory: 'abilities',
    localProfile: loadLocalProfile(),
    db: null,
    stageEffect: null,
    appliedThemeId: null,
    appliedFontId: null,
    desktop: !!window.grimdiceDesktop
  };

  function loadLocalProfile() {
    try { return { clientId: cryptoId(), name: 'Игрок', role: 'gm', characterId: null, ...JSON.parse(localStorage.getItem('grimdice-profile-v2') || '{}') }; }
    catch { return { clientId: cryptoId(), name: 'Игрок', role: 'gm', characterId: null }; }
  }

  function saveLocalProfile() { try { localStorage.setItem('grimdice-profile-v2', JSON.stringify(runtime.localProfile)); } catch {} }

  function loadRoomCredential(code) {
    try { return JSON.parse(localStorage.getItem(`grimdice-room-${code}`) || '{}'); }
    catch { return {}; }
  }

  function saveRoomCredential(code, credential) {
    try { localStorage.setItem(`grimdice-room-${code}`, JSON.stringify(credential)); } catch {}
  }

  function cryptoId() {
    if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
    return 'id-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
  }

  function abilityMod(score) { return Math.floor(((Number(score) || 10) - 10) / 2); }
  function signed(n) { n = Number(n) || 0; return n >= 0 ? `+${n}` : `${n}`; }
  function esc(v = '') { return String(v).replace(/[&<>'"]/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[c])); }
  function clamp(n, min, max) { return Math.min(max, Math.max(min, Number(n) || 0)); }
  function initials(name = '?') { return name.trim().split(/\s+/).slice(0, 2).map(x => x[0] || '').join('').toUpperCase(); }
  function nowTime() { return new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }); }
  function normalizeType(v='') { return v.toLowerCase().trim().replace(/ого$|ому$|ым$|ый$|ая$|ое$/,''); }

  function createBlankCharacter() {
    return {
      id: cryptoId(), name: 'Безымянный', className: '', race: '', level: 1, role: 'hero', edition: '2024',
      ac: 10, hp: 1, maxHp: 1, tempHp: 0, speed: 30, initiative: 0, proficiency: 2,
      stats: { str: 10, dex: 10, con: 10, int: 10, wis: 10, cha: 10 }, saves: {}, skills: {},
      spellDC: null, spellAttack: null, passivePerception: null,
      resistances: [], vulnerabilities: [], immunities: [], conditions: [], deathSaves: { success: 0, fail: 0 },
      actions: [], resources: [], tokenAsset: null, sourceText: '', audit: [], notes: '',
      stress: 0, maxStress: 200, resolve: 'steady', quirks: [], diseases: [], relationships: {}, statusEffects: [], inventory: [],
      initiativeRoll: null
    };
  }

  function parseCharacterText(sourceText, edition = '2024') {
    const text = String(sourceText || '').replace(/\r/g, '').trim();
    const c = createBlankCharacter();
    c.edition = edition;
    c.sourceText = text;
    const lines = text.split('\n').map(s => s.trim()).filter(Boolean);
    const found = new Set();
    const warnings = [];

    const capture = (regex) => {
      const m = text.match(regex);
      return m ? m[1]?.trim() : null;
    };
    const field = (key, value) => { if (value !== null && value !== undefined && value !== '') found.add(key); };

    const explicitName = capture(/^(?:имя|name)\s*[:—-]\s*(.+)$/im);
    const firstLine = lines[0] || '';
    if (explicitName) c.name = explicitName;
    else if (firstLine && !/(?:кд|ac|хиты|hp|класс|class|уров|level|сил|str)\s*[:\d]/i.test(firstLine)) c.name = firstLine.replace(/^#+\s*/, '');
    field('Имя', c.name !== 'Безымянный' ? c.name : null);

    let classLine = capture(/^(?:класс|class)\s*[:—-]\s*(.+)$/im);
    const levelExplicit = capture(/^(?:уровень|level)\s*[:—-]?\s*(\d+)/im);
    if (classLine) {
      const lm = classLine.match(/(.+?)(?:\s+(\d+)(?:-?го)?\s*(?:уровня|level)?\s*)$/i);
      if (lm) { c.className = lm[1].trim(); c.level = Number(lm[2]); }
      else c.className = classLine;
      field('Класс', c.className);
    }
    if (levelExplicit) c.level = Number(levelExplicit);
    field('Уровень', levelExplicit || (classLine && /\d/.test(classLine)) ? c.level : null);

    const race = capture(/^(?:раса|race|вид|species)\s*[:—-]\s*(.+)$/im);
    if (race) c.race = race;
    field('Раса', race);

    const ac = capture(/^(?:кд|ac|armor\s+class)\s*[:—-]?\s*(\d+)/im);
    if (ac) c.ac = Number(ac);
    field('КД', ac);

    const hpMatch = text.match(/^(?:хиты|оз|hp|hit\s+points)\s*[:—-]?\s*(\d+)(?:\s*(?:\/|из)\s*(\d+))?/im);
    if (hpMatch) { c.hp = Number(hpMatch[1]); c.maxHp = Number(hpMatch[2] || hpMatch[1]); }
    field('Хиты', hpMatch?.[1]);

    const speed = capture(/^(?:скорость|speed)\s*[:—-]?\s*(\d+)/im);
    if (speed) c.speed = Number(speed);
    field('Скорость', speed);

    const prof = capture(/^(?:бонус\s+мастерства|proficiency(?:\s+bonus)?)\s*[:—-]?\s*\+?(\d+)/im);
    if (prof) c.proficiency = Number(prof);
    else c.proficiency = Math.ceil(c.level / 4) + 1;
    field('Бонус мастерства', prof);

    const initiative = capture(/^(?:инициатива|initiative)\s*[:—-]?\s*\+?(-?\d+)/im);
    if (initiative !== null) c.initiative = Number(initiative);
    field('Инициатива', initiative);

    const abilityPatterns = {
      str: /(?:\bСИЛ\b|\bSTR\b|сила)\s*[:—-]?\s*(\d+)/ig,
      dex: /(?:\bЛОВ\b|\bDEX\b|ловкость)\s*[:—-]?\s*(\d+)/ig,
      con: /(?:\bТЕЛ\b|\bCON\b|телосложение)\s*[:—-]?\s*(\d+)/ig,
      int: /(?:\bИНТ\b|\bINT\b|интеллект)\s*[:—-]?\s*(\d+)/ig,
      wis: /(?:\bМДР\b|\bWIS\b|мудрость)\s*[:—-]?\s*(\d+)/ig,
      cha: /(?:\bХАР\b|\bCHA\b|харизма)\s*[:—-]?\s*(\d+)/ig
    };
    for (const [key, rx] of Object.entries(abilityPatterns)) {
      const m = [...text.matchAll(rx)].find(x => Number(x[1]) <= 30);
      if (m) { c.stats[key] = Number(m[1]); found.add(ABILITY_RU[key]); }
    }
    if (initiative === null) c.initiative = abilityMod(c.stats.dex);

    const spellDC = capture(/(?:сл\s*(?:заклинаний|спасброска)?|spell\s+save\s+dc)\s*[:—-]?\s*(\d+)/im);
    if (spellDC) c.spellDC = Number(spellDC);
    field('Сл заклинаний', spellDC);
    const spellAttack = capture(/(?:атака\s+заклинани(?:ем|й)|spell\s+attack(?:\s+bonus)?)\s*[:—-]?\s*\+?(-?\d+)/im);
    if (spellAttack) c.spellAttack = Number(spellAttack);
    field('Атака заклинанием', spellAttack);

    const savesLine = capture(/^(?:спасброски|saving\s+throws|saves)\s*[:—-]\s*(.+)$/im);
    if (savesLine) {
      for (const key of ABILITIES) {
        const aliases = {str:'СИЛ|STR',dex:'ЛОВ|DEX',con:'ТЕЛ|CON',int:'ИНТ|INT',wis:'МДР|WIS',cha:'ХАР|CHA'}[key];
        const m = savesLine.match(new RegExp(`(?:${aliases})\\s*([+-]\\d+)`, 'i'));
        if (m) c.saves[key] = Number(m[1]);
      }
      found.add('Спасброски');
    }

    const parseList = (rx, key) => {
      const raw = capture(rx);
      if (!raw) return [];
      found.add(key);
      return raw.split(/[,;]/).map(x => x.trim().toLowerCase()).filter(Boolean);
    };
    c.resistances = parseList(/^(?:сопротивления|resistances?|damage\s+resistances?)\s*[:—-]\s*(.+)$/im, 'Сопротивления');
    c.vulnerabilities = parseList(/^(?:уязвимости|vulnerabilities?|damage\s+vulnerabilities?)\s*[:—-]\s*(.+)$/im, 'Уязвимости');
    c.immunities = parseList(/^(?:иммунитеты|immunities?|damage\s+immunities?)\s*[:—-]\s*(.+)$/im, 'Иммунитеты');

    const resourcesLine = capture(/^(?:ресурсы|resources?|использования)\s*[:—-]\s*(.+)$/im);
    if (resourcesLine) {
      for (const part of resourcesLine.split(/;|,(?=\s*[^,]+\d+\s*\/\s*\d+)/)) {
        const m = part.trim().match(/^(.+?)\s+(\d+)\s*\/\s*(\d+)(?:\s*\(([^)]+)\))?/i);
        if (!m) continue;
        c.resources.push({ id: cryptoId(), name: m[1].trim(), current: Number(m[2]), max: Number(m[3]), recovery: recoveryFromText(m[4] || '') });
      }
      if (c.resources.length) found.add('Ресурсы');
    }

    const actionLines = lines.filter(line => {
      if (/^(?:имя|name|класс|class|раса|race|вид|species|кд|ac|armor class|хиты|hp|hit points|скорость|speed|бонус мастерства|proficiency|уровень|level|сопротивления|resistances|уязвимости|vulnerabilities|иммунитеты|immunities|ресурсы|resources|спасброски|saving throws|сила|ловкость|телосложение|интеллект|мудрость|харизма)\s*[:—-]/i.test(line)) return false;
      if (/^(?:действия|actions|заклинания|spells|бонусные действия|реакции)\s*:??$/i.test(line)) return false;
      return /\d+d\d+|\d+к\d+|к попаданию|to hit|спасбросок|saving throw|лечение|healing/i.test(line);
    });

    for (const line of actionLines) {
      const action = parseActionLine(line, c);
      if (action) c.actions.push(action);
    }
    if (c.actions.length) found.add('Действия');

    if (!ac) warnings.push('КД не найдена — оставлено 10.');
    if (!hpMatch) warnings.push('Хиты не найдены — оставлено 1/1.');
    if (!ABILITIES.some(k => found.has(ABILITY_RU[k]))) warnings.push('Характеристики не найдены — оставлены значения 10.');
    if (!c.actions.length) warnings.push('Боевые действия не распознаны. Их можно добавить вручную.');
    if (!explicitName && c.name !== 'Безымянный') warnings.push('Имя взято из первой строки — проверьте.');

    c.audit = [
      ...[...found].map(label => ({ label, status: 'ok', note: 'найдено в исходнике' })),
      ...warnings.map(note => ({ label: 'Проверка', status: 'warn', note }))
    ];
    return { character: c, warnings, found: [...found] };
  }

  function recoveryFromText(text = '') {
    if (/корот|short/i.test(text)) return 'short';
    if (/рассвет|dawn/i.test(text)) return 'dawn';
    if (/раунд|round/i.test(text)) return 'round';
    return 'long';
  }

  function abilityFromText(text = '') {
    const map = [
      ['str', /\b(?:СИЛ|STR)\b|сил[аыу]?/i], ['dex', /\b(?:ЛОВ|DEX)\b|ловкост/i],
      ['con', /\b(?:ТЕЛ|CON)\b|телослож/i], ['int', /\b(?:ИНТ|INT)\b|интеллект/i],
      ['wis', /\b(?:МДР|WIS)\b|мудрост/i], ['cha', /\b(?:ХАР|CHA)\b|харизм/i]
    ];
    return map.find(([,rx]) => rx.test(text))?.[0] || null;
  }

  function parseRankSpec(spec = '') {
    const ranks = new Set();
    for (const part of String(spec).split(/[,;\s]+/).filter(Boolean)) {
      const range = part.match(/([1-5])\s*[–—-]\s*([1-5])/);
      if (range) { const a=Number(range[1]), b=Number(range[2]); for(let i=Math.min(a,b);i<=Math.max(a,b);i++)ranks.add(i); }
      else if (/^[1-5]$/.test(part)) ranks.add(Number(part));
    }
    return [...ranks].sort();
  }

  function parseActionLine(line, character) {
    const clean = line.replace(/^[-•*]\s*/, '').trim();
    if (!clean) return null;
    const split = clean.match(/^(.+?)(?:\.|:|—)\s+(.+)$/);
    let name = split ? split[1].trim() : clean.split(/\s{2,}/)[0];
    let body = split ? split[2].trim() : clean;
    if (name.length > 70) name = name.slice(0, 70);

    let attackBonus = null;
    const atk = body.match(/(?:атака(?:\s+заклинанием)?|бросок\s+атаки|attack(?:\s+roll)?)[^\d+−-]*([+−-]\s*\d+)/i)
      || body.match(/([+−-]\s*\d+)\s*(?:к\s+попаданию|to\s+hit)/i);
    if (atk) attackBonus = Number(atk[1].replace(/\s/g,'').replace('−','-'));
    if (attackBonus === null && /атака заклинанием/i.test(body) && character.spellAttack !== null) attackBonus = character.spellAttack;

    const diceMatches = [...body.matchAll(/\b(\d+\s*[dк]\s*\d+(?:\s*[+−-]\s*\d+)?)\b/ig)];
    let damage = diceMatches[0] ? diceMatches[0][1].replace(/\s/g,'').replace(/к/i,'d').replace('−','-') : '';
    const healing = /лечение|восстанавлив|healing|regains?/i.test(body);
    const savePart = body.match(/(?:спасбросок|saving\s+throw|save)\s*([^,;.]+)/i);
    const saveAbility = savePart ? abilityFromText(savePart[1]) : null;
    const dcMatch = body.match(/(?:Сл|DC)\s*(\d+)/i);
    const saveDC = dcMatch ? Number(dcMatch[1]) : (saveAbility ? character.spellDC : null);
    const halfOnSave = /половин|half/i.test(body);
    const concentration = /концентрац|concentration/i.test(body);

    const typeWords = ['рубящ', 'колющ', 'дробящ', 'огонь', 'холод', 'кислот', 'электр', 'гром', 'яд', 'психичес', 'силов', 'излучен', 'некрот', 'slashing', 'piercing', 'bludgeoning', 'fire', 'cold', 'acid', 'lightning', 'thunder', 'poison', 'psychic', 'force', 'radiant', 'necrotic'];
    const damageType = typeWords.find(w => new RegExp(w, 'i').test(body)) || '';
    const usesMatch = clean.match(/\((\d+)\s*\/\s*(\d+)(?:,\s*([^)]+))?\)/);
    const maxUses = usesMatch ? Number(usesMatch[2]) : null;
    const currentUses = usesMatch ? Number(usesMatch[1]) : null;
    const recovery = recoveryFromText(usesMatch?.[3] || body);
    const rechargeMatch = body.match(/(?:перезарядка|recharge)\s*(\d)\s*[–—-]\s*(\d)/i);
    const range = body.match(/(?:дистанция|range)\s*[:—-]?\s*([^,;.]+)/i)?.[1]?.trim() || '';
    const fromRanks = body.match(/(?:из\s+позиций|позиции|from\s+ranks?)\s*[:—-]?\s*([1-5][1-5,;\s–—-]*)/i);
    const targetRanks = body.match(/(?:цели|target\s+ranks?)\s*[:—-]?\s*([1-5][1-5,;\s–—-]*)/i);

    let type = 'utility';
    if (healing) type = 'heal';
    else if (saveAbility) type = 'save';
    else if (attackBonus !== null) type = /заклин|spell/i.test(clean) ? 'spell' : 'attack';
    else if (damage) type = 'damage';

    return {
      id: cryptoId(), name, type, attackBonus, damage, damageType, saveAbility, saveDC,
      halfOnSave, concentration, range, currentUses, maxUses, recovery,
      validFrom: fromRanks ? parseRankSpec(fromRanks[1]) : [],
      validTargets: targetRanks ? parseRankSpec(targetRanks[1]) : [],
      targetSide: healing ? 'ally' : (type === 'utility' ? 'any' : 'enemy'),
      recharge: rechargeMatch ? `${rechargeMatch[1]}-${rechargeMatch[2]}` : null,
      notes: body
    };
  }

  function defaultExpedition() {
    const route = [
      { id:cryptoId(), type:'start', name:'Последний фонарь', status:'current' },
      { id:cryptoId(), type:'hazard', name:'Разбитый тракт', status:'locked' },
      { id:cryptoId(), type:'battle', name:'Мост висельников', status:'locked' },
      { id:cryptoId(), type:'curio', name:'Забытая часовня', status:'locked' },
      { id:cryptoId(), type:'camp', name:'Тихая крипта', status:'locked' },
      { id:cryptoId(), type:'elite', name:'Врата из кости', status:'locked' },
      { id:cryptoId(), type:'boss', name:'Сердце колокольни', status:'locked' }
    ];
    route[1].branchTo = route[3].id;
    route[1].branchLabel = 'Тропа паломников';
    return {
      active: false, name: 'Дорога под багровой звездой', region: 'Пепельные окраины', light: 82, danger: 1,
      nodeIndex: 0, campPoints: 12, currency: 240,
      supplies: { food: 12, torches: 8, medicine: 3, tools: 2, keys: 2 },
      inventory: [], log: [], route
    };
  }

  function defaultHub() {
    return {
      name: 'Бастион Углей', background: '/builtin/ember-bastion.jpg', gold: 1450, relics: 18,
      inventory: [], assignments: {},
      buildings: [
        { id:cryptoId(), name:'Братство клинка', icon:'⚔', level:1, maxLevel:5, cost:300, description:'Обучение приёмам и настройка боевых комплектов.' },
        { id:cryptoId(), name:'Скрипторий', icon:'✧', level:1, maxLevel:5, cost:350, description:'Заклинания, ритуалы и исследования новых эффектов.' },
        { id:cryptoId(), name:'Лазарет', icon:'✚', level:1, maxLevel:5, cost:260, description:'Лечение травм, болезней и тяжёлого стресса.' },
        { id:cryptoId(), name:'Приют странников', icon:'♟', level:1, maxLevel:5, cost:280, description:'Найм, резерв и распределение владельцев героев.' },
        { id:cryptoId(), name:'Реликварий', icon:'◇', level:1, maxLevel:5, cost:420, description:'Хранение трофеев, предметов и пакетов контента.' },
        { id:cryptoId(), name:'Костровой двор', icon:'♨', level:1, maxLevel:5, cost:220, description:'Отдых, разговоры и восстановление отношений.' }
      ]
    };
  }

  function defaultCompendium() {
    return {
      abilities: [], creatures: [], items: [], effects: [], locations: [], events: [],
      buildings: [], mods: [], schemaVersion: 1
    };
  }

  function defaultMedia(){return Object.fromEntries(Object.keys(MEDIA_CATEGORIES).map(key=>[key,[]]));}

  function demoState() {
    const hero1 = parseCharacterText(`Имя: Эйра Воронья Клятва\nКласс: Паладин 5\nРаса: Человек\nКД: 18\nХиты: 44/44\nСкорость: 30\nБонус мастерства: +3\nСИЛ 18, ЛОВ 10, ТЕЛ 16, ИНТ 9, МДР 12, ХАР 16\nСпасброски: МДР +4, ХАР +6\nРесурсы: Божественная кара 3/3 (долгий отдых); Возложение рук 25/25 (долгий отдых)\nДлинный меч. Атака +7, урон 1d8+4 рубящий.\nБожественная кара (3/3, долгий отдых). Урон 2d8 излучение.\nЛечащее касание. Лечение 1d10+5.`, '2024').character;
    const hero2 = parseCharacterText(`Имя: Финч Тихий\nКласс: Плут 5\nРаса: Легконогий полурослик\nКД: 15\nХиты: 33/33\nСкорость: 25\nСИЛ 8, ЛОВ 18, ТЕЛ 14, ИНТ 13, МДР 12, ХАР 11\nСпасброски: ЛОВ +7, ИНТ +4\nКороткий меч. Атака +7, урон 1d6+4 колющий.\nСкрытая атака. Урон 3d6 колющий.\nКороткий лук. Атака +7, урон 1d6+4 колющий, дистанция 80 футов.`, '2024').character;
    const hero3 = parseCharacterText(`Имя: Орина Пепельная\nКласс: Волшебник 5\nРаса: Высший эльф\nКД: 13\nХиты: 27/27\nСкорость: 30\nСИЛ 8, ЛОВ 14, ТЕЛ 13, ИНТ 18, МДР 12, ХАР 10\nСл заклинаний: 15\nАтака заклинанием: +7\nРесурсы: Ячейка 3 круга 2/2 (долгий отдых); Ячейка 2 круга 3/3 (долгий отдых)\nОгненный снаряд. Атака заклинанием +7, урон 2d10 огонь.\nОгненный шар. Спасбросок ЛОВ Сл 15, урон 8d6 огонь, половина при успехе.\nВолшебная стрела. Урон 3d4+3 силовой.`, '2024').character;
    const hero4 = parseCharacterText(`Имя: Торвен Железная Песня\nКласс: Бард 5\nРаса: Дварф\nКД: 16\nХиты: 39/39\nСкорость: 25\nСИЛ 14, ЛОВ 14, ТЕЛ 16, ИНТ 10, МДР 12, ХАР 18\nСл заклинаний: 15\nАтака заклинанием: +7\nРесурсы: Вдохновение 4/4 (короткий отдых)\nБоевой напев. Атака +6, урон 1d8+3 гром, из позиций 2-4, цели 1-4.\nПесня стойкости. Лечение 1d8+4, из позиций 2-5.`, '2024').character;
    const hero5 = parseCharacterText(`Имя: Каэль Следопыт\nКласс: Следопыт 5\nРаса: Лесной эльф\nКД: 16\nХиты: 42/42\nСкорость: 35\nСИЛ 10, ЛОВ 18, ТЕЛ 14, ИНТ 11, МДР 16, ХАР 9\nСпасброски: ЛОВ +7, МДР +6\nРесурсы: Метка охотника 3/3 (долгий отдых)\nДлинный лук. Атака +7, урон 1d8+4 колющий, из позиций 3-5, цели 1-5.\nПарные клинки. Атака +7, урон 2d6+4 рубящий, из позиций 1-2, цели 1-2.`, '2024').character;
    const enemy = parseCharacterText(`Имя: Проклятый смотритель\nКласс: Нежить\nКД: 14\nХиты: 52/52\nСкорость: 30\nСИЛ 16, ЛОВ 12, ТЕЛ 16, ИНТ 7, МДР 10, ХАР 8\nСопротивления: некротический\nУязвимости: излучение\nРжавый тесак. Атака +5, урон 1d10+3 рубящий.\nМогильный холод (2/2, долгий отдых). Спасбросок ТЕЛ Сл 13, урон 3d6 холод, половина при успехе.`, '2024').character;
    enemy.role = 'enemy';
    return {
      version: 1,
      campaign: { title: 'Пепел на тракте', edition: '2024', updatedAt: Date.now() },
      characters: [hero1, hero2, hero3, hero4, hero5, enemy],
      combat: { round: 1, turnIndex: 0, started: false, targetId: enemy.id, cover: 0 },
      rollLog: [],
      scene: { backgroundAsset: null, builtinBackground: '/builtin/ash-cathedral.jpg', mode: 'formation', name: 'Собор Пепла', formation: [], tokens: [] },
      expedition: defaultExpedition(),
      hub: defaultHub(),
      compendium: defaultCompendium(),
      network: { gmClientId: null, owners: {}, members: [] },
      media: defaultMedia()
    };
  }

  function migrateState(raw) {
    const base = demoState();
    const s = raw && typeof raw === 'object' ? raw : base;
    s.campaign ||= base.campaign;
    s.characters ||= [];
    s.combat ||= base.combat;
    s.rollLog ||= [];
    s.scene ||= base.scene;
    s.scene.tokens ||= [];
    s.scene.formation ||= [];
    s.scene.mode ||= 'formation';
    s.scene.name ||= 'Безымянное поле';
    s.scene.builtinBackground ??= '/builtin/ash-cathedral.jpg';
    s.expedition = { ...defaultExpedition(), ...(s.expedition || {}) };
    s.expedition.supplies = { ...defaultExpedition().supplies, ...(s.expedition.supplies || {}) };
    s.expedition.route ||= defaultExpedition().route; s.expedition.inventory ||= []; s.expedition.log ||= [];
    for(const node of s.expedition.route){node.status||='locked';node.branchTo??=null;node.branchLabel||='Альтернативный путь';node.selectedNextId??=null;node.rewardClaimed=!!node.rewardClaimed;}
    s.hub = { ...defaultHub(), ...(s.hub || {}) }; s.hub.buildings ||= defaultHub().buildings; s.hub.inventory ||= []; s.hub.assignments ||= {};
    s.compendium = { ...defaultCompendium(), ...(s.compendium || {}) };
    for (const key of Object.keys(CONTENT_CATEGORIES)) s.compendium[key] ||= [];
    s.compendium.mods ||= [];
    s.network = { gmClientId:null, owners:{}, members:[], ...(s.network || {}) }; s.network.owners ||= {}; s.network.members ||= [];
    s.media ||= defaultMedia();
    if(!s.media.sprites?.length&&s.media.images?.length)s.media.sprites=s.media.images;
    if(!s.media.music?.length&&s.media.audio?.length)s.media.music=s.media.audio;
    for(const key of Object.keys(MEDIA_CATEGORIES))s.media[key]||=[];
    s.media.images=s.media.sprites;
    s.media.audio=s.media.music;
    for (const c of s.characters) {
      Object.assign(c, { ...createBlankCharacter(), ...c });
      c.stats = { str:10,dex:10,con:10,int:10,wis:10,cha:10,...c.stats };
      c.actions ||= []; c.resources ||= []; c.conditions ||= []; c.audit ||= [];
      c.deathSaves = { success: 0, fail: 0, ...(c.deathSaves || {}) };
      c.stress = clamp(c.stress || 0, 0, c.maxStress || 200); c.maxStress ||= 200; c.resolve ||= 'steady';
      c.quirks ||= []; c.diseases ||= []; c.relationships ||= {}; c.statusEffects ||= []; c.inventory ||= [];
    }
    return s;
  }

  function loadState() {
    try { return migrateState(JSON.parse(localStorage.getItem(STORAGE_KEY))); }
    catch { return demoState(); }
  }

  let state = loadState();

  function saveState() {
    try {
      document.getElementById('autosaveLabel')?.classList.add('saving');
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      setTimeout(() => document.getElementById('autosaveLabel')?.classList.remove('saving'), 220);
    } catch (err) { toast('Локальное хранилище заполнено. Экспортируйте кампанию.', 'Ошибка'); }
  }

  function commit(render = true, sync = true) {
    state.campaign.updatedAt = Date.now();
    if (!runtime.applyingRemote) runtime.mutationVersion++;
    saveState();
    if (sync && !runtime.applyingRemote) scheduleSync();
    updateChrome();
    if (render) renderView();
  }

  function updateChrome() {
    document.getElementById('campaignTitle').innerHTML = `${esc(state.campaign.title)} <span>✎</span>`;
    document.querySelectorAll('[data-edition]').forEach(b => b.classList.toggle('active', b.dataset.edition === state.campaign.edition));
    document.getElementById('navRound').textContent = `РАУНД ${state.combat.round}`;
    document.getElementById('navCharacters').textContent = `${state.characters.length} ЛИСТОВ`;
    document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('active', b.dataset.view === runtime.view));
    const sync = document.getElementById('syncStatus');
    const roomBtn = document.getElementById('roomBtn');
    sync.classList.toggle('live', !!runtime.roomCode);
    roomBtn.classList.toggle('live', !!runtime.roomCode);
    sync.querySelector('span').textContent = runtime.roomCode ? `Стол ${runtime.roomCode}` : 'Локальная игра';
    roomBtn.querySelector('span').textContent = runtime.roomCode ? runtime.roomCode : 'Подключить стол';
  }

  function renderView() {
    const main = document.getElementById('mainContent');
    if (!main) return;
    if (runtime.view === 'combat') main.innerHTML = renderCombat();
    else if (runtime.view === 'expedition') main.innerHTML = renderExpedition();
    else if (runtime.view === 'hub') main.innerHTML = renderHub();
    else if (runtime.view === 'characters') main.innerHTML = renderCharacters();
    else if (runtime.view === 'scene') main.innerHTML = renderScene();
    else if (runtime.view === 'library') main.innerHTML = renderLibrary();
    else if (runtime.view === 'workshop') main.innerHTML = renderWorkshop();
    else if (runtime.view === 'rules') main.innerHTML = renderRules();
    resolveAssetElements();
  }

  function orderedCombatants() {
    if (!state.combat.started) return [...state.characters];
    return [...state.characters].sort((a,b) => (b.initiativeRoll ?? -999) - (a.initiativeRoll ?? -999));
  }

  function activeCharacter() {
    const ordered = orderedCombatants();
    return ordered[state.combat.turnIndex] || null;
  }

  function renderCombat() {
    const ordered = orderedCombatants();
    const active = activeCharacter();
    const targets = state.characters.map(c => `<option value="${c.id}" ${state.combat.targetId===c.id?'selected':''}>${c.role==='enemy'?'☠ ':''}${esc(c.name)} · КД ${c.ac}</option>`).join('');
    return `<section class="view">
      <div class="view-heading">
        <div><span class="section-kicker">МАСТЕРСКАЯ СТОЛА</span><h1>${state.combat.started ? 'Схватка продолжается' : 'Боевой стол готов'}</h1><p>${state.combat.started ? `Сейчас действует ${esc(active?.name || '—')}. Все броски, попадания, сопротивления и трата ресурсов пишутся в журнал.` : 'Выберите цель и нажмите «Разыграть» — движок сам проверит попадание, спасбросок, крит и урон.'}</p></div>
        <div class="heading-actions">
          <button class="outline-btn" data-action="short-rest">◔ Короткий отдых</button>
          <button class="outline-btn" data-action="long-rest">☾ Долгий отдых</button>
          <button class="red-btn" data-action="import-text">＋ Импорт из текста</button>
        </div>
      </div>

      <div class="battle-toolbar">
        <div class="round-block"><div class="round-seal"><b>${state.combat.round}</b></div><div class="round-copy"><small>РАУНД</small><strong>${state.combat.started ? 'Идёт бой' : 'Ожидание'}</strong></div></div>
        <div class="target-control"><label for="targetSelect">ЦЕЛЬ</label><select id="targetSelect" class="select"><option value="">— без цели —</option>${targets}</select><select id="coverSelect" class="select" title="Укрытие цели"><option value="0" ${state.combat.cover===0?'selected':''}>Без укрытия</option><option value="2" ${state.combat.cover===2?'selected':''}>½ укрытие · +2 КД</option><option value="5" ${state.combat.cover===5?'selected':''}>¾ укрытие · +5 КД</option></select></div>
        <div class="roll-mode"><label>d20</label>${['normal','adv','dis'].map((m,i)=>`<button class="segment ${runtime.rollMode===m?'active':''}" data-roll-mode="${m}">${['Обычно','Преим.','Помеха'][i]}</button>`).join('')}</div>
        <div class="turn-buttons">${state.combat.started ? `<button class="dark-btn" data-action="reset-combat">■ Стоп</button><button class="red-btn" data-action="next-turn">Следующий ход →</button>` : `<button class="red-btn" data-action="start-combat">⚔ Бросить инициативу</button>`}</div>
      </div>

      <div class="initiative-track">${ordered.map((c,i)=>renderInitiative(c,i,active?.id)).join('')}</div>
      <div class="battle-layout">
        <div class="combatants-grid">${ordered.length ? ordered.map(c => renderCombatant(c, active?.id)).join('') : `<div class="empty-card"><div><b>Здесь пока тихо</b>Импортируйте текстовый лист персонажа.</div></div>`}</div>
        <aside class="right-rail">${renderDicePanel()}${renderLogPanel()}</aside>
      </div>
    </section>`;
  }

  function renderInitiative(c, i, activeId) {
    const init = c.initiativeRoll ?? '—';
    return `<button class="init-card ${c.id===activeId && state.combat.started?'active':''} ${c.hp<=0?'dead':''}" data-select-turn="${i}">
      <div class="init-avatar" ${c.tokenAsset?`data-asset-bg="${c.tokenAsset}"`:''}>${c.tokenAsset?'':esc(initials(c.name))}</div>
      <div class="init-copy"><b>${esc(c.name)}</b><small>${c.role==='enemy'?'ПРОТИВНИК':esc(c.className || 'ПЕРСОНАЖ')}</small></div><span class="init-roll">${init}</span>
    </button>`;
  }

  function renderCombatant(c, activeId) {
    const hpPct = clamp(c.hp / Math.max(1,c.maxHp)*100, 0, 100);
    const subtitle = [c.race, c.className, c.level ? `${c.level} ур.` : ''].filter(Boolean).join(' · ');
    const actionRows = c.actions.slice(0,6).map(a => renderActionRow(c,a)).join('');
    return `<article class="combatant-card ${c.role==='enemy'?'enemy':''} ${c.id===activeId&&state.combat.started?'active':''}">
      <div class="card-head">
        <div class="sheet-avatar" ${c.tokenAsset?`data-asset-bg="${c.tokenAsset}"`:''}>${c.tokenAsset?'':esc(initials(c.name))}</div>
        <div class="card-title"><h3>${esc(c.name)}</h3><p>${esc(subtitle || (c.role==='enemy'?'ПРОТИВНИК':'ПЕРСОНАЖ'))}</p></div>
        <div class="ac-shield"><b>${c.ac}</b><small>КД</small></div>
      </div>
      <div class="hp-block"><div class="hp-line"><div class="hp-copy"><small>ХП</small>${c.hp}${c.tempHp?` <span title="Временные хиты">+${c.tempHp}</span>`:''} / ${c.maxHp}</div><div class="hp-bar"><i class="${hpPct>60?'healthy':''}" style="width:${hpPct}%"></i></div><div class="hp-controls"><button data-hp="${c.id}" data-delta="-">−</button><input data-hp-input="${c.id}" value="1" inputmode="numeric"><button data-hp="${c.id}" data-delta="+">+</button></div></div></div>
      <div class="card-meta"><span>ИНИЦ <b>${signed(c.initiative)}</b></span><span>СКОР <b>${c.speed}</b></span>${c.spellDC?`<span>СЛ <b>${c.spellDC}</b></span>`:''}<span>МАСТ <b>${signed(c.proficiency)}</b></span><span>СТРЕСС <b>${c.stress}</b></span><span>ДУХ <b>${esc(resolveLabel(c.resolve))}</b></span></div>
      ${c.conditions.length?`<div class="conditions">${c.conditions.map((x,i)=>`<span class="condition">${esc(x)}<button data-remove-condition="${c.id}" data-index="${i}">×</button></span>`).join('')}</div>`:''}
      <div class="actions-list">${actionRows || `<div class="action-row"><div class="action-main"><div class="action-name"><b>Нет действий</b></div><div class="action-detail">Откройте лист и добавьте механику</div></div></div>`}</div>
      <div class="card-footer"><button data-sheet="${c.id}">□ Полный лист</button><button data-condition="${c.id}">＋ Состояние</button><button data-rest="${c.id}">↻ Отдых</button><button data-more-actions="${c.id}">••• ${Math.max(0,c.actions.length-6) || ''}</button></div>
    </article>`;
  }

  function renderActionRow(c,a) {
    const detail = actionDetail(a);
    let pips = '';
    if (a.maxUses !== null && a.maxUses !== undefined) pips = `<span class="use-pips" title="Использования ${a.currentUses}/${a.maxUses}">${Array.from({length:Math.min(a.maxUses,8)},(_,i)=>`<i class="${i<a.currentUses?'full':''}"></i>`).join('')}</span>`;
    const disabled = a.maxUses !== null && a.currentUses <= 0;
    return `<div class="action-row"><div class="action-main"><div class="action-name"><b>${esc(a.name)}</b>${a.type==='spell'?'<i>ЧАРЫ</i>':''}${a.concentration?'<i>КОНЦ.</i>':''}${pips}</div><div class="action-detail">${esc(detail)}</div></div><button class="play-action" data-play-action="${c.id}" data-action-id="${a.id}" ${disabled?'disabled':''}>↯ Разыграть</button></div>`;
  }

  function actionDetail(a) {
    const p = [];
    if (a.attackBonus !== null && a.attackBonus !== undefined) p.push(`попадание ${signed(a.attackBonus)}`);
    if (a.saveAbility) p.push(`${ABILITY_RU[a.saveAbility]} Сл ${a.saveDC || '?'}`);
    if (a.damage) p.push(`${a.type==='heal'?'лечение':'урон'} ${a.damage}${a.damageType?' '+a.damageType:''}`);
    if (a.maxUses !== null && a.maxUses !== undefined) p.push(`${a.currentUses}/${a.maxUses}`);
    return p.join(' · ') || a.notes || 'особое действие';
  }

  function renderDicePanel() {
    return `<section class="dice-panel"><div class="panel-title"><h3>Кости на столе</h3><button data-action="clear-roll-mode">СБРОСИТЬ РЕЖИМ</button></div><div class="dice-row">${[4,6,8,10,12,20].map(d=>`<button class="die-btn" data-die="${d}">d${d}</button>`).join('')}</div><form class="custom-roll" id="customRollForm"><input id="customRollInput" placeholder="2d6+3" aria-label="Формула броска"><button>Бросить</button></form></section>`;
  }

  function renderLogPanel() {
    const logs = state.rollLog.slice(0,30).map(l => `<div class="log-entry ${l.outcome||''}"><div class="log-head"><b>${esc(l.actor || 'Стол')} · ${esc(l.name)}</b><time>${esc(l.time)}</time></div><div class="log-expression">${esc(l.expression || '')}</div><div class="log-result"><strong>${l.total ?? '—'}</strong><span>${esc(l.summary || l.detail || '')}</span></div></div>`).join('');
    return `<section class="log-panel"><div class="panel-title"><h3>Журнал бросков</h3><button data-action="clear-log">ОЧИСТИТЬ</button></div><div class="roll-log">${logs || `<div class="log-empty"><span class="big-rune">◇</span>Первый бросок нарушит тишину</div>`}</div></section>`;
  }

  function isGameMaster() { return !runtime.roomCode || runtime.localProfile.role === 'gm'; }

  function canControlCharacter(characterId) {
    if (isGameMaster()) return true;
    return runtime.localProfile.characterId === characterId || state.network.owners?.[characterId] === runtime.clientId;
  }

  function partyHeroes() { return state.characters.filter(c => c.role === 'hero').slice(0, MAX_RANKS); }

  function relationshipPairs(heroes=partyHeroes()) {
    const pairs=[];
    for(let i=0;i<heroes.length;i++)for(let j=i+1;j<heroes.length;j++)pairs.push([heroes[i],heroes[j],Number(heroes[i].relationships?.[heroes[j].id]||0)]);
    return pairs;
  }

  function relationshipTier(value) {
    return value>=50?'devoted':value>=20?'trusted':value<=-50?'hostile':value<=-20?'strained':'neutral';
  }

  function relationshipLabel(value) {
    return ({devoted:'преданы',trusted:'доверяют',neutral:'нейтральны',strained:'напряжены',hostile:'враждуют'})[relationshipTier(value)];
  }

  function setRelationship(a,b,value){
    if(!a||!b||a.id===b.id)return;
    a.relationships||={};b.relationships||={};
    const next=clamp(Number(value)||0,-100,100);a.relationships[b.id]=next;b.relationships[a.id]=next;
  }

  function changeRelationship(a,b,delta,reason=''){
    const before=Number(a?.relationships?.[b?.id]||0);setRelationship(a,b,before+Number(delta||0));
    if(reason)addRoadLog('Отношения',`${a.name} и ${b.name}: ${delta>0?'+':''}${delta} · ${reason}.`);
  }

  function changeRandomRelationship(delta,reason){
    const pairs=relationshipPairs();if(!pairs.length)return;const [a,b]=pairs[randomDie(pairs.length)-1];changeRelationship(a,b,delta,reason);
  }

  function renderExpedition() {
    const ex = state.expedition;
    const current = ex.route[ex.nodeIndex] || ex.route.at(-1);
    const party = partyHeroes();
    const supplies = [
      ['food','Провизия','♨'],['torches','Факелы','♜'],['medicine','Лекарства','✚'],['tools','Инструменты','⚒'],['keys','Ключи','⚿']
    ];
    return `<section class="expedition-view">
      <div class="expedition-hero">
        <div class="expedition-backdrop"></div>
        <div class="expedition-heading"><span class="section-kicker">ПОХОД ПЯТИ</span><h1>${esc(ex.name)}</h1><p>${esc(ex.region)} · опасность ${ex.danger} · ${ex.active ? 'экспедиция идёт' : 'подготовка маршрута'}</p></div>
        <div class="light-meter"><div class="light-orb">${ex.light>66?'☀':ex.light>32?'◐':'●'}</div><div><small>СВЕТ</small><b>${ex.light}</b><div class="light-track"><i style="width:${clamp(ex.light,0,100)}%"></i></div></div><button data-expedition-light="-10" ${isGameMaster()?'':'disabled'}>−</button><button data-expedition-light="10" ${isGameMaster()?'':'disabled'}>＋</button></div>
      </div>

      <div class="expedition-layout">
        <section class="route-panel panel">
          <div class="panel-title"><div><h3>Карта пути</h3><small>${current ? `Текущая точка: ${esc(current.name)}` : 'Маршрут пуст'}</small></div><div><button data-action="edit-route">РЕДАКТОР МАРШРУТА</button></div></div>
          <div class="route-map">${ex.route.map((n,i)=>`<button class="route-node ${n.type} ${n.status||(i<ex.nodeIndex?'cleared':i===ex.nodeIndex?'current':'locked')}" data-route-node="${i}" ${!isGameMaster()?'disabled':''}><span><i>${nodeGlyph(n.type)}</i></span><b>${esc(n.name)}</b><small>${esc(EXPEDITION_NODE_LABELS[n.type]||n.type)} · ${i+1}</small></button>${i<ex.route.length-1?'<i class="route-link"></i>':''}`).join('')}</div>
          ${current?.branchTo&&ex.active?`<div class="branch-choice"><div><small>РАЗВИЛКА</small><b>Выберите продолжение пути</b></div><button data-route-choice="${esc(ex.route[ex.nodeIndex+1]?.id||'')}" class="${current.selectedNextId===ex.route[ex.nodeIndex+1]?.id?'selected':''}" ${!isGameMaster()?'disabled':''}>Прямой тракт<small>${esc(ex.route[ex.nodeIndex+1]?.name||'конец')}</small></button><span>ИЛИ</span><button data-route-choice="${esc(current.branchTo)}" class="${current.selectedNextId===current.branchTo?'selected':''}" ${!isGameMaster()?'disabled':''}>${esc(current.branchLabel||'Иной путь')}<small>${esc(ex.route.find(n=>n.id===current.branchTo)?.name||'неизведанное')}</small></button></div>`:''}
          <div class="route-actions"><button class="dark-btn" data-action="reset-expedition" ${isGameMaster()?'':'disabled'}>↺ Сбросить</button><div class="route-current"><small>СЛЕДУЮЩЕЕ ИСПЫТАНИЕ</small><b>${esc(current?.name || 'Конец маршрута')}</b></div>${ex.active?`<button class="red-btn" data-action="advance-expedition" ${isGameMaster()?'':'disabled'}>Продолжить путь →</button>`:`<button class="red-btn" data-action="start-expedition" ${isGameMaster()?'':'disabled'}>Зажечь фонарь →</button>`}</div>
        </section>

        <aside class="provision-panel panel"><div class="panel-title"><h3>Припасы</h3><b>${ex.currency} ◇</b></div><div class="provision-list">${supplies.map(([key,label,glyph])=>`<div class="provision-row"><span>${glyph}</span><div><b>${label}</b><small>${supplyHint(key)}</small></div><button data-supply="${key}" data-delta="-1" ${isGameMaster()?'':'disabled'}>−</button><strong>${ex.supplies[key]||0}</strong><button data-supply="${key}" data-delta="1" ${isGameMaster()?'':'disabled'}>＋</button></div>`).join('')}</div><button class="camp-btn" data-action="camp-expedition" ${isGameMaster()?'':'disabled'}>♨ Разбить лагерь <small>${ex.campPoints} очков подготовки</small></button><div class="loot-pocket"><div><small>ДОБЫЧА В ПОХОДЕ</small><b>${ex.inventory.reduce((n,x)=>n+(x.quantity||1),0)} предметов</b></div>${ex.inventory.slice(0,5).map(item=>`<button data-assign-loot="${item.id}" ${isGameMaster()?'':'disabled'}><span>${esc(item.icon||'◇')}</span><b>${esc(item.name)}</b><small>${item.quantity||1} шт. · ${esc(item.rarity||'обычный')}</small></button>`).join('')||'<p>Трофеев пока нет.</p>'}</div></aside>
      </div>

      <section class="expedition-party"><div class="party-heading"><span>ОТРЯД · ${party.length}/${MAX_RANKS}</span><small>Хиты, стресс, решимость и владелец</small></div><div class="marching-party">${party.map((c,i)=>renderMarchHero(c,i+1)).join('')}${Array.from({length:Math.max(0,MAX_RANKS-party.length)},()=>'<div class="march-empty">＋</div>').join('')}</div></section>
      <section class="expedition-journal panel"><div class="panel-title"><h3>Дорожный журнал</h3><button data-action="clear-expedition-log">ОЧИСТИТЬ</button></div><div class="road-log">${ex.log.slice(0,12).map(x=>`<div><time>${esc(x.time)}</time><b>${esc(x.title)}</b><span>${esc(x.text)}</span></div>`).join('')||'<p>Пока слышен только треск факелов.</p>'}</div></section>
    </section>`;
  }

  function nodeGlyph(type) { return ({start:'⌂',battle:'⚔',hazard:'⚠',curio:'◇',camp:'♨',elite:'♛',boss:'☠'})[type] || '◆'; }
  function supplyHint(key) { return ({food:'отдых и голод',torches:'сохраняют свет',medicine:'снимает травмы',tools:'опасности пути',keys:'запертые находки'})[key] || ''; }

  function renderMarchHero(c, rank) {
    const hp = clamp(c.hp / Math.max(1,c.maxHp)*100,0,100), stress = clamp(c.stress / Math.max(1,c.maxStress)*100,0,100);
    const owner = state.network.members?.find(m=>m.clientId===(state.network.owners?.[c.id]));
    return `<article class="march-hero ${c.resolve!=='steady'?'resolve-'+c.resolve:''}" data-sheet="${c.id}"><span class="march-rank">${rank}</span><div class="march-portrait" ${c.tokenAsset?`data-asset-bg="${c.tokenAsset}"`:''}>${c.tokenAsset?'':esc(initials(c.name))}</div><div class="march-copy"><b>${esc(c.name)}</b><small>${esc(c.className||'Герой')} · ${owner?esc(owner.name):'без владельца'}</small><div class="march-bar hp"><i style="width:${hp}%"></i><span>${c.hp}/${c.maxHp}</span></div><div class="march-bar stress"><i style="width:${stress}%"></i><span>стресс ${c.stress}/${c.maxStress}</span></div></div></article>`;
  }

  function renderHub() {
    const h=state.hub, heroes=state.characters.filter(c=>c.role==='hero'), pairs=relationshipPairs(heroes);
    return `<section class="hub-view"><div class="hub-panorama"><img src="${esc(h.background||'/builtin/ember-bastion.jpg')}" alt=""><div class="hub-title"><span class="section-kicker">УБЕЖИЩЕ МАСТЕРА</span><h1>${esc(h.name)}</h1><p>Районы, назначения, отношения и трофеи сохраняются между походами.</p></div><div class="hub-wallet"><span><small>ЗОЛОТО</small><b>${h.gold}</b></span><span><small>РЕЛИКВИИ</small><b>${h.relics}</b></span></div></div>
      <div class="hub-content"><div class="building-grid">${h.buildings.map(b=>`<article class="building-card"><span class="building-glyph">${esc(b.icon||'◆')}</span><div><small>УРОВЕНЬ ${b.level}/${b.maxLevel}</small><h3>${esc(b.name)}</h3><p>${esc(b.description)}</p></div><div class="building-actions"><button class="dark-btn" data-edit-building="${b.id}" ${isGameMaster()?'':'disabled'}>✎</button><button class="outline-btn" data-upgrade-building="${b.id}" ${b.level>=b.maxLevel||!isGameMaster()?'disabled':''}>Улучшить · ${b.cost} ◇</button></div></article>`).join('')}</div>
      <aside class="recovery-roster panel"><div class="panel-title"><h3>Распределение</h3><button data-action="hub-rest-all" ${isGameMaster()?'':'disabled'}>СМЕНА ЗАВЕРШЕНА</button></div>${heroes.map(c=>`<div class="recovery-row assigned"><div class="init-avatar" ${c.tokenAsset?`data-asset-bg="${c.tokenAsset}"`:''}>${c.tokenAsset?'':esc(initials(c.name))}</div><div><b>${esc(c.name)}</b><small>стресс ${c.stress} · ${resolveLabel(c.resolve)}</small><select class="select" data-hub-assignment="${c.id}" ${!isGameMaster()?'disabled':''}><option value="">Свободен</option>${h.buildings.map(b=>`<option value="${b.id}" ${h.assignments[c.id]===b.id?'selected':''}>${esc(b.name)}</option>`).join('')}</select>${(c.inventory||[]).map(item=>`<button class="hero-item" data-use-item="${item.id}" data-character="${c.id}" ${!canControlCharacter(c.id)?'disabled':''}>${esc(item.icon||'◇')} ${esc(item.name)} · ${item.quantity||1}</button>`).join('')}</div><button data-hub-recover="${c.id}" ${!isGameMaster()?'disabled':''}>−25</button></div>`).join('')||'<p class="log-empty">Нет героев</p>'}<div class="vault-list"><small>ХРАНИЛИЩЕ</small>${h.inventory.map(item=>`<span>${esc(item.icon||'◇')} <b>${esc(item.name)}</b> · ${item.quantity||1}</span>`).join('')||'<p>Пусто</p>'}</div></aside></div>
      <section class="relationship-panel panel"><div class="panel-title"><div><h3>Узы отряда</h3><small>От −100 до +100; пороги влияют на стресс и лечение.</small></div></div><div class="relationship-grid">${pairs.map(([a,b,value])=>`<article class="relationship-card ${relationshipTier(value)}"><div><b>${esc(a.name)}</b><span>↔</span><b>${esc(b.name)}</b></div><small>${relationshipLabel(value)}</small><div class="relationship-track"><i style="left:${clamp((value+100)/2,0,100)}%"></i></div><footer><button data-relationship="${a.id}|${b.id}" data-delta="-5" ${!isGameMaster()?'disabled':''}>−</button><strong>${value>0?'+':''}${value}</strong><button data-relationship="${a.id}|${b.id}" data-delta="5" ${!isGameMaster()?'disabled':''}>＋</button></footer></article>`).join('')||'<p>Для отношений нужны хотя бы два героя.</p>'}</div></section>
    </section>`;
  }

  function resolveLabel(v) { return ({steady:'собран',afflicted:'надломлен',virtuous:'воодушевлён'})[v]||v; }

  function renderWorkshop() {
    const cat=runtime.workshopCategory, rows=state.compendium[cat]||[];
    return `<section class="view workshop-view"><div class="view-heading"><div><span class="section-kicker">МАСТЕРСКАЯ МИРА</span><h1>Конструктор контента и модов</h1><p>Создавайте собственные способности, существ, предметы, эффекты, локации и события. Формат декларативный: никакого исполняемого кода из пакета.</p></div><div class="heading-actions"><button class="dark-btn" data-action="import-mod">⇧ Импорт пакета</button><button class="dark-btn" data-action="export-mod">⇩ Экспорт пакета</button><button class="red-btn" data-action="new-content">＋ Новый объект</button></div></div>
      <div class="workshop-layout"><aside class="workshop-tabs">${Object.entries(CONTENT_CATEGORIES).map(([k,v])=>`<button data-workshop-category="${k}" class="${cat===k?'active':''}"><span>${contentGlyph(k)}</span><b>${v}</b><small>${(state.compendium[k]||[]).length} объектов</small></button>`).join('')}<div class="mod-summary"><small>УСТАНОВЛЕННЫЕ ПАКЕТЫ</small><b>${state.compendium.mods.length}</b><span>Пакет v2 включает контент и бинарные ассеты</span></div></aside>
      <main class="content-catalog"><div class="catalog-head"><div><span class="section-kicker">${esc(CONTENT_CATEGORIES[cat]).toUpperCase()}</span><h2>${rows.length?'Пользовательский архив':'Категория пуста'}</h2></div><button class="outline-btn" data-action="new-content">Создать</button></div><div class="content-grid">${rows.map(item=>`<article class="content-card"><span>${esc(item.icon||contentGlyph(cat))}</span><div><small>${esc(item.type||CONTENT_CATEGORIES[cat])}</small><h3>${esc(item.name||'Без названия')}</h3><p>${esc(item.description||item.notes||'Пользовательский объект')}</p><code>${esc(item.id||'')}</code></div><div>${cat==='abilities'?`<button data-attach-content="${item.id}" title="Добавить герою">＋</button>`:''}<button data-edit-content="${item.id}">✎</button><button data-duplicate-content="${item.id}">⧉</button><button class="danger" data-delete-content="${item.id}">×</button></div></article>`).join('')||`<button class="content-empty" data-action="new-content"><strong>＋</strong><b>Создать первый объект</b><span>Откроется JSON-редактор со схемой и проверкой.</span></button>`}</div></main></div>
      <section class="schema-help"><b>Декларативные операции:</b><code>damage</code><code>heal</code><code>stress</code><code>condition</code><code>move</code><code>light</code><code>resource</code><span>Можно связывать объект с действием персонажа через поле <code>effects</code>.</span></section>
    </section>`;
  }

  function contentGlyph(cat) { return ({abilities:'⚔',creatures:'☠',items:'◇',effects:'✧',locations:'⌂',events:'!',buildings:'♜'})[cat]||'◆'; }

  function renderCharacters() {
    return `<section class="view"><div class="view-heading"><div><span class="section-kicker">АРХИВ ЛИСТОВ</span><h1>Персонажи и существа</h1><p>Исходный текст хранится дословно. Парсер извлекает только явно найденные значения и показывает, что требует проверки.</p></div><div class="heading-actions"><button class="dark-btn" data-action="new-blank">＋ Пустой лист</button><button class="red-btn" data-action="import-text">⌁ Вставить текст</button></div></div>
      <div class="character-library">${state.characters.map(renderLibraryCard).join('')}<button class="add-character-card" data-action="import-text"><div><strong>＋</strong><b>Импортировать персонажа</b><span>Русский или английский статблок</span></div></button></div></section>`;
  }

  function renderLibraryCard(c) {
    return `<article class="library-card"><div class="library-top"><div class="sheet-avatar" ${c.tokenAsset?`data-asset-bg="${c.tokenAsset}"`:''}>${c.tokenAsset?'':esc(initials(c.name))}</div><div><h3>${esc(c.name)}</h3><p>${esc([c.race,c.className,c.level?`${c.level} ур.`:''].filter(Boolean).join(' · ')||'Без описания')}</p></div>${c.role==='enemy'?'<span class="enemy-tag">ВРАГ</span>':''}</div>
      <div class="stat-six">${ABILITIES.map(k=>`<div class="mini-stat"><small>${ABILITY_RU[k]}</small><b>${signed(abilityMod(c.stats[k]))}</b></div>`).join('')}</div>
      <div class="library-summary"><span>КД <b>${c.ac}</b></span><span>ХП <b>${c.hp}/${c.maxHp}</b></span><span>Действий <b>${c.actions.length}</b></span><span>Ресурсов <b>${c.resources.length}</b></span></div>
      <div class="library-card-actions"><button data-sheet="${c.id}">Открыть лист</button><button data-duplicate="${c.id}">Дубликат</button><button data-toggle-role="${c.id}">${c.role==='enemy'?'Сделать героем':'Сделать врагом'}</button><button class="danger" data-delete-character="${c.id}">Удалить</button></div></article>`;
  }

  function renderScene() {
    ensureFormation();
    const bg = state.scene.backgroundAsset;
    const active = activeCharacter() || state.characters.find(c => c.role === 'hero');
    const selected = state.characters.find(c => c.id === state.combat.targetId);
    const heroes = formationSide('hero');
    const enemies = formationSide('enemy');
    const effect = runtime.stageEffect;
    const activeRank = state.scene.formation.find(x => x.characterId === active?.id)?.rank || 1;
    const abilities = (active?.actions || []).map(a => {
      const allowed = !a.validFrom?.length || a.validFrom.includes(activeRank);
      const spent = a.maxUses !== null && a.maxUses !== undefined && a.currentUses <= 0;
      return `<button class="stage-ability ${allowed && !spent ? '' : 'locked'}" data-play-action="${active.id}" data-action-id="${a.id}" ${allowed && !spent ? '' : 'disabled'} title="${esc(a.notes || actionDetail(a))}"><span>${abilityGlyph(a)}</span><b>${esc(a.name)}</b><small>${esc(actionDetail(a))}</small></button>`;
    }).join('');
    return `<section class="stage-view">
      <div class="stage-topbar">
        <div><span class="section-kicker">ПОСТАНОВОЧНАЯ СЦЕНА</span><h1>${esc(state.scene.name)}</h1></div>
        <div class="stage-round"><small>РАУНД</small><b>${state.combat.round}</b><span>${state.combat.started ? `ХОД: ${esc(active?.name || '—')}` : 'БОЙ НЕ НАЧАТ'}</span></div><div class="stage-light"><small>СВЕТ</small><b>${state.expedition.light}</b><i><span style="width:${state.expedition.light}%"></span></i></div>
        <div class="heading-actions"><button class="dark-btn" data-action="scene-bg">▧ Фон сцены</button><button class="dark-btn" data-action="rename-scene">✎ Название</button><button class="dark-btn" data-action="stage-fullscreen">⛶ Экран</button>${state.combat.started ? '<button class="red-btn" data-action="next-turn">Следующий ход →</button>' : '<button class="red-btn" data-action="start-combat">⚔ Начать бой</button>'}</div>
      </div>
      <div class="darkest-stage ${effect ? `effect-${effect.type}` : ''}" id="darkestStage">
        ${bg ? `<img class="darkest-backdrop" data-asset-src="${bg}" alt="Фон сцены">` : state.scene.builtinBackground ? `<img class="darkest-backdrop" src="${esc(state.scene.builtinBackground)}" alt="Фон сцены">` : '<div class="darkest-backdrop generated"></div>'}
        ${state.scene.effectAsset?`<div class="custom-effect-layer" data-asset-bg="${state.scene.effectAsset}"></div>`:''}
        <div class="stage-vignette"></div><div class="stage-floor"></div><div class="stage-torch left"></div><div class="stage-torch right"></div>
        <div class="formation heroes">${emptyRanks(heroes)}${heroes.map(x => renderStageActor(x.character, x.rank, active?.id, selected?.id, effect)).join('')}</div>
        <div class="stage-versus"><i></i><b>VS</b><i></i></div>
        <div class="formation enemies">${enemies.map(x => renderStageActor(x.character, x.rank, active?.id, selected?.id, effect)).join('')}${emptyRanks(enemies)}</div>
        <div class="stage-announcer"><small>${state.combat.targetId ? 'ВЫБРАНА ЦЕЛЬ' : 'ВЫБЕРИТЕ ЦЕЛЬ'}</small><b>${esc(selected?.name || '—')}</b></div>
      </div>
      <div class="stage-console">
        <div class="active-fighter"><div class="active-portrait" ${active?.tokenAsset ? `data-asset-bg="${active.tokenAsset}"` : ''}>${active?.tokenAsset ? '' : esc(initials(active?.name || '?'))}</div><div><small>ДЕЙСТВУЕТ · ПОЗИЦИЯ ${activeRank}</small><b>${esc(active?.name || 'Нет участников')}</b><span>${active ? `${active.hp}/${active.maxHp} ХП · КД ${active.ac}` : ''}</span></div></div>
        <div class="ability-ribbon">${abilities || '<div class="stage-no-actions">В листе активного персонажа нет боевых действий</div>'}</div>
        <div class="stage-dice"><button class="die-btn" data-die="20">d20</button><button class="die-btn" data-die="6">d6</button><button class="icon-btn" data-action="stage-log">≡ Журнал</button></div>
      </div>
      <div class="formation-help"><span>Нажмите на бойца, чтобы выбрать цель.</span><span>Стрелки под фигурой меняют позицию 1–4.</span><span class="target-dot"></span><span>Красная рамка — текущая цель.</span></div>
    </section>`;
  }

  function abilityGlyph(a) {
    if (a.type === 'heal') return '✦';
    if (a.type === 'spell' || a.type === 'save') return '✧';
    if (a.type === 'utility') return '◆';
    return '⚔';
  }

  function ensureFormation(reset = false) {
    if (reset) state.scene.formation = [];
    const formation = state.scene.formation;
    for (const role of ['hero', 'enemy']) {
      const members = state.characters.filter(c => c.role === role);
      members.forEach((c, i) => {
        let slot = formation.find(x => x.characterId === c.id);
        if (!slot) formation.push({ characterId: c.id, side: role, rank: Math.min(MAX_RANKS, i + 1) });
        else slot.side = role;
      });
    }
    state.scene.formation = formation.filter(x => state.characters.some(c => c.id === x.characterId));
    normalizeFormation('hero'); normalizeFormation('enemy');
  }

  function normalizeFormation(side) {
    const slots = state.scene.formation.filter(x => x.side === side).sort((a,b) => a.rank - b.rank);
    slots.forEach((x,i) => x.rank = Math.min(MAX_RANKS, i + 1));
  }

  function formationSide(side) {
    return state.scene.formation.filter(x => x.side === side).map(x => ({ ...x, character: state.characters.find(c => c.id === x.characterId) })).filter(x => x.character).sort((a,b) => side === 'hero' ? b.rank - a.rank : a.rank - b.rank);
  }

  function moveFormationRank(characterId, direction) {
    ensureFormation();
    const slot = state.scene.formation.find(x => x.characterId === characterId);
    if (!slot) return;
    const delta = direction === 'forward' ? -1 : 1;
    const nextRank = clamp(slot.rank + delta, 1, MAX_RANKS);
    const other = state.scene.formation.find(x => x.side === slot.side && x.rank === nextRank);
    if (other) other.rank = slot.rank;
    slot.rank = nextRank;
    commit();
  }

  function emptyRanks(sideMembers) {
    return Array.from({length: Math.max(0, MAX_RANKS-sideMembers.length)}, (_,i) => `<div class="empty-rank"><span>${sideMembers.length+i+1}</span></div>`).join('');
  }

  function renderStageActor(c, rank, activeId, targetId, effect) {
    const hpPct = clamp(c.hp / Math.max(1,c.maxHp) * 100, 0, 100);
    const stateClass = c.hp <= 0 ? 'fallen' : c.id === activeId ? 'active' : '';
    const effectClass = effect?.targetId === c.id ? `impact-${effect.type}` : '';
    return `<article class="stage-actor ${c.role} ${stateClass} ${c.id===targetId?'targeted':''} ${effectClass}" data-stage-target="${c.id}">
      <div class="rank-number">${rank}</div>
      <div class="actor-silhouette" ${c.tokenAsset ? `data-asset-bg="${c.tokenAsset}"` : ''}>${c.tokenAsset ? '' : `<span>${esc(initials(c.name))}</span><i>${c.role==='enemy'?'☠':'♟'}</i>`}</div>
      <div class="actor-plate"><b>${esc(c.name)}</b><small>${esc(c.className || (c.role==='enemy'?'ПРОТИВНИК':'ГЕРОЙ'))}</small><div class="actor-hp"><i style="width:${hpPct}%"></i></div><div class="actor-stress"><i style="width:${clamp(c.stress/Math.max(1,c.maxStress)*100,0,100)}%"></i></div><span>${c.hp}/${c.maxHp}</span></div>
      <div class="rank-controls"><button data-move-rank="${c.id}" data-direction="back" title="Назад">‹</button><em>ПОЗ ${rank}</em><button data-move-rank="${c.id}" data-direction="forward" title="Вперёд">›</button></div>
      ${c.conditions.length ? `<div class="stage-conditions">${c.conditions.slice(0,3).map(x=>`<i title="${esc(x)}">${esc(x[0])}</i>`).join('')}</div>` : ''}
    </article>`;
  }

  function renderLibrary() {
    const panels=Object.entries(MEDIA_CATEGORIES).map(([kind,def])=>{
      const rows=(state.media[kind]||[]).map(asset=>{
        if(def.preview==='audio')return `<div class="track"><button class="track-play" data-play-track="${asset.id}">${runtime.playingTrack===asset.id?'Ⅱ':'▶'}</button><div><b>${esc(asset.name)}</b><small>${formatBytes(asset.size)} · ${esc(asset.type||'audio')}</small></div><input class="volume" data-volume="${asset.id}" type="range" min="0" max="1" step=".05" value=".7"><button class="asset-remove" data-remove-asset="${asset.id}" data-kind="${kind}">×</button></div>`;
        const visual=def.preview==='image'&&String(asset.type||'').startsWith('image/')?`<img data-asset-src="${asset.id}" alt="">`:`<span>${def.glyph}</span>`;
        const applyLabel=['sprites','portraits'].includes(kind)?'ГЕРОЮ':['backgrounds','maps','effects'].includes(kind)?'СЦЕНА':['fonts','animations','themes','localization'].includes(kind)?'ВКЛ':'';
        return `<div class="asset-item"><div class="asset-thumb">${visual}</div><div><b>${esc(asset.name)}</b><small>${formatBytes(asset.size)} · ${esc(asset.type||'файл')}</small></div><div class="asset-tools">${applyLabel?`<button data-apply-asset="${asset.id}" data-kind="${kind}">${applyLabel}</button>`:''}<button data-remove-asset="${asset.id}" data-kind="${kind}">×</button></div></div>`;
      }).join('');
      return `<section class="panel media-category"><div class="panel-title"><h3>${def.glyph} ${def.label}</h3>${def.preview==='audio'?'<button data-action="stop-audio">СТОП</button>':''}</div><button class="drop-zone" data-upload-media="${kind}"><strong>Добавить: ${def.label.toLowerCase()}</strong>${esc(def.accept)} · локальное бинарное хранилище</button><div class="asset-list">${rows||'<div class="log-empty">Файлов пока нет</div>'}</div></section>`;
    }).join('');
    const count=Object.keys(MEDIA_CATEGORIES).reduce((n,k)=>n+(state.media[k]?.length||0),0);
    return `<section class="view"><div class="view-heading"><div><span class="section-kicker">АРХИВ МАСТЕРА · ${count} ФАЙЛОВ</span><h1>Медиатека и визуальные моды</h1><p>Спрайты, портреты, фоны, карты, эффекты, звук, музыка, шрифты, декларативные анимации, темы и локализация. Бинарные данные хранятся в IndexedDB и могут включаться в пакет мода.</p></div><div class="heading-actions"><button class="dark-btn" data-upload-media="sprites">♟ Спрайты</button><button class="red-btn" data-upload-media="music">♪ Музыка</button></div></div><div class="media-grid categorized">${panels}</div></section>`;
  }

  function renderRules() {
    const e = state.campaign.edition;
    return `<section class="view"><div class="view-heading"><div><span class="section-kicker">ПРОФИЛЬ 5E · ${e}</span><h1>Что считает движок</h1><p>Автоматизация опирается только на цифры и свойства листа. Неуказанная механика не выдумывается — исходник всегда доступен для сверки.</p></div><div class="heading-actions"><button class="outline-btn" data-action="show-parser-format">Формат импорта</button><button class="red-btn" data-action="import-text">Проверить статблок</button></div></div>
      <div class="rules-grid">
        ${ruleCard('Атаки и критические попадания','d20 + бонус против КД цели; натуральные 1/20; преимущество и помеха; удвоение костей урона при крите. Укрытие добавляет +2 или +5 КД.',['попадание','крит','укрытие'])}
        ${ruleCard('Заклинания и спасброски','Атака заклинанием или спасбросок цели против Сл. Поддерживается половина урона при успехе и концентрация как отслеживаемое состояние.',['атака чарами','Сл','½ урона'])}
        ${ruleCard('Урон, лечение и защиты','Временные хиты поглощают урон первыми. Иммунитет обнуляет, сопротивление делит, уязвимость удваивает урон указанного типа.',['временные ХП','сопротивление','уязвимость'])}
        ${ruleCard('Концентрация и смерть','При получении урона концентрация автоматически проверяется против Сл 10 или половины урона. При 0 ХП персонаж делает спасброски от смерти в начале хода.',['ТЕЛ','3 успеха / 3 провала','натуральные 1/20'])}
        ${ruleCard('Ресурсы и отдых','Счётчики N/N тратятся действием. Короткий и долгий отдых восстанавливают ресурсы по пометке. Перезарядка 5–6 проверяется в начале хода.',['N/N','короткий отдых','перезарядка'])}
        ${ruleCard('Инициатива и раунды', e==='2024'?'В профиле 2024 состояние «Застигнут врасплох» даёт помеху инициативе.':'В профиле 2014 застигнутый врасплох участник отмечается в трекере; решение о действиях первого хода остаётся у мастера.',['инициатива',e==='2024'?'помеха 2024':'сюрприз 2014'])}
        ${ruleCard('Честный импорт без ИИ','Регулярный детерминированный парсер. Он показывает найденные поля, предупреждает о пропусках и хранит исходный текст дословно.',['без генерации','аудит','исходник'])}
      </div>
      <div class="edition-diff"><div class="head">Механика</div><div class="head">2014</div><div class="head">2024</div><div>Сюрприз</div><div>Статус до первого хода ведёт мастер</div><div>Помеха инициативе автоматизирована</div><div>Истощение</div><div>Уровни отмечаются состояниями</div><div>Уровни отмечаются; штрафы применяет мастер</div><div>Отдых</div><div>Ресурсы по тегу short/long</div><div>Ресурсы по тегу short/long</div><div>Контент</div><div>Пользовательский / открытый</div><div>Пользовательский / открытый</div></div>
      <p style="color:var(--faint);font-size:10px;line-height:1.6;margin-top:14px">GrimDice — помощник, а не замена книгам правил. В приложение не встроены закрытые тексты заклинаний, классов и монстров; их можно добавить из собственных материалов. Спорные формулировки и редкие исключения остаются за мастером.</p>
    </section>`;
  }

  function ruleCard(title,text,tags) { return `<article class="rule-card"><h3>${title}</h3><p>${text}</p><div class="rule-tags">${tags.map(x=>`<span class="auto">✓ ${x}</span>`).join('')}</div></article>`; }

  function randomDie(sides) {
    const range = 0x100000000;
    const limit = range - (range % sides);
    const arr = new Uint32Array(1); let n;
    do { crypto.getRandomValues(arr); n = arr[0]; } while (n >= limit);
    return (n % sides) + 1;
  }

  function rollExpression(expression, options = {}) {
    const expr = String(expression || '').toLowerCase().replace(/к/g,'d').replace(/−/g,'-').replace(/\s+/g,'');
    if (!expr || !/^[+\-]?\d+(?:d\d+)?(?:[+\-]\d+(?:d\d+)?)*$/.test(expr)) throw new Error('Формат: 2d6+3');
    const terms = expr.match(/[+\-]?\d+(?:d\d+)?/g) || [];
    let total = 0; const details = [];
    for (const term of terms) {
      const sign = term.startsWith('-') ? -1 : 1;
      const core = term.replace(/^[+\-]/,'');
      if (core.includes('d')) {
        let [count,sides] = core.split('d').map(Number);
        if (count > 100 || sides > 1000 || count < 1 || sides < 2) throw new Error('Слишком большая кость');
        if (options.crit) count *= 2;
        const rolls = Array.from({length:count},()=>randomDie(sides));
        total += sign * rolls.reduce((a,b)=>a+b,0);
        details.push(`${sign<0?'−':''}[${rolls.join(', ')}]`);
      } else { total += sign * Number(core); details.push(`${sign<0?'−':'+'}${core}`); }
    }
    return { total, detail: details.join(' '), expression: expr };
  }

  function d20(mod=0, mode='normal') {
    const rolls = mode==='normal' ? [randomDie(20)] : [randomDie(20),randomDie(20)];
    const natural = mode==='adv' ? Math.max(...rolls) : mode==='dis' ? Math.min(...rolls) : rolls[0];
    return { natural, total:natural+Number(mod||0), rolls, detail:`d20 [${rolls.join(', ')}] ${signed(mod)}${mode==='adv'?' · преимущество':mode==='dis'?' · помеха':''}` };
  }

  function addLog(entry) {
    state.rollLog.unshift({ id:cryptoId(), time:nowTime(), ...entry });
    state.rollLog = state.rollLog.slice(0,100);
  }

  function playAction(characterId, actionId) {
    const c = state.characters.find(x=>x.id===characterId);
    const a = c?.actions.find(x=>x.id===actionId);
    if (!c || !a) return;
    if (!canControlCharacter(c.id)) { toast('Этот герой закреплён за другим игроком','Управление'); return; }
    if (a.maxUses !== null && a.maxUses !== undefined && a.currentUses <= 0) { toast('Использования закончились', a.name); return; }
    const target = state.characters.find(x=>x.id===state.combat.targetId);
    const sourceSlot = state.scene.formation?.find(x=>x.characterId===c.id);
    const targetSlot = target ? state.scene.formation?.find(x=>x.characterId===target.id) : null;
    if (a.validFrom?.length && sourceSlot && !a.validFrom.includes(sourceSlot.rank)) { toast(`Доступно только из позиций: ${a.validFrom.join(', ')}`, a.name); return; }
    if (target && a.targetSide === 'enemy' && target.role === c.role) { toast('Для этой способности нужна вражеская цель', a.name); return; }
    if (target && a.targetSide === 'ally' && target.role !== c.role) { toast('Для этой способности нужен союзник', a.name); return; }
    if (target && a.validTargets?.length && targetSlot && !a.validTargets.includes(targetSlot.rank)) { toast(`Цель должна быть в позиции: ${a.validTargets.join(', ')}`, a.name); return; }
    let consumed = false;
    const consume = () => { if (!consumed && a.maxUses !== null && a.maxUses !== undefined) { a.currentUses--; consumed=true; } };

    if (a.attackBonus !== null && a.attackBonus !== undefined) {
      const attack = d20(a.attackBonus, runtime.rollMode);
      const targetAC = target ? target.ac + Number(state.combat.cover||0) : null;
      const crit = attack.natural===20;
      const miss = attack.natural===1 || (targetAC!==null && !crit && attack.total<targetAC);
      const hit = targetAC===null ? !miss : !miss;
      let summary = targetAC===null ? `бросок атаки${crit?' · КРИТ':''}` : `${hit?'попадание':'промах'} по КД ${targetAC}${crit?' · КРИТ':''}`;
      addLog({ actor:c.name,name:a.name,expression:attack.detail,total:attack.total,detail:attack.detail,summary,outcome:crit?'crit':hit?'hit':'miss' });
      if (hit && a.damage) {
        const damage = rollExpression(a.damage,{crit});
        const applied = target ? applyDamage(target,damage.total,a.damageType) : { amount:damage.total, note:'цель не выбрана' };
        addLog({ actor:c.name,name:`${a.name} · урон`,expression:`${crit?'крит · ':''}${a.damage} → ${damage.detail}`,total:applied.amount,summary:target?`${target.name}: ${applied.note}`:'урон не применён',outcome:crit?'crit':'hit' });
      }
      consume();
    } else if (a.saveAbility) {
      const dc = Number(a.saveDC || c.spellDC || 10);
      if (target) {
        const bonus = target.saves[a.saveAbility] ?? abilityMod(target.stats[a.saveAbility]);
        const save = d20(bonus,'normal');
        const success = save.total>=dc;
        addLog({ actor:target.name,name:`Спасбросок от «${a.name}»`,expression:save.detail,total:save.total,summary:`${ABILITY_RU[a.saveAbility]} против Сл ${dc} · ${success?'успех':'провал'}`,outcome:success?'hit':'miss' });
        if (a.damage) {
          const dmg=rollExpression(a.damage);
          const raw=success?(a.halfOnSave?Math.floor(dmg.total/2):0):dmg.total;
          const applied=applyDamage(target,raw,a.damageType);
          addLog({actor:c.name,name:`${a.name} · урон`,expression:`${a.damage} → ${dmg.detail}${success&&a.halfOnSave?' · половина':''}`,total:applied.amount,summary:`${target.name}: ${applied.note}`,outcome:success?'':'hit'});
        }
      } else {
        addLog({actor:c.name,name:a.name,expression:`Спасбросок ${ABILITY_RU[a.saveAbility]} против Сл ${dc}`,total:'—',summary:'выберите цель'});
      }
      consume();
    } else if (a.type==='heal') {
      const healed = rollExpression(a.damage || '0');
      const recipient = target || c, bond=recipient.id===c.id?0:Number(c.relationships?.[recipient.id]||0);
      const bondBonus=bond>=20?Math.floor(bond/20):bond<=-50?-2:0;
      const before=recipient.hp; recipient.hp=clamp(recipient.hp+Math.max(0,healed.total+bondBonus),0,recipient.maxHp);
      if(recipient.hp>0){recipient.conditions=recipient.conditions.filter(x=>x!=='Без сознания');recipient.deathSaves={success:0,fail:0};}
      addLog({actor:c.name,name:a.name,expression:`${a.damage} → ${healed.detail}${bondBonus?` · узы ${bondBonus>0?'+':''}${bondBonus}`:''}`,total:recipient.hp-before,summary:`${recipient.name}: восстановлено хитов`,outcome:'hit'});
      consume();
    } else if (a.damage) {
      const dmg=rollExpression(a.damage);
      const applied=target?applyDamage(target,dmg.total,a.damageType):{amount:dmg.total,note:'цель не выбрана'};
      addLog({actor:c.name,name:a.name,expression:`${a.damage} → ${dmg.detail}`,total:applied.amount,summary:target?`${target.name}: ${applied.note}`:'урон не применён',outcome:'hit'});
      consume();
    } else {
      addLog({actor:c.name,name:a.name,expression:a.notes||'особое действие',total:'✓',summary:'отмечено в журнале'}); consume();
    }
    if (a.effects?.length) executeDeclarativeEffects(a,c,target);
    if (a.concentration && !c.conditions.includes('Концентрация')) c.conditions.push('Концентрация');
    runtime.stageEffect = { targetId: (a.type === 'heal' ? (target || c) : target)?.id || c.id, type: a.type === 'heal' ? 'heal' : 'hit' };
    setTimeout(() => { runtime.stageEffect = null; }, 900);
    commit();
  }

  function matchesDamageType(list, damageType) {
    const t=normalizeType(damageType);
    return t && list.some(x=>normalizeType(x).includes(t)||t.includes(normalizeType(x)));
  }

  function applyDamage(target, amount, type='') {
    let final=Math.max(0,Number(amount)||0); let factor=1; let reason='';
    if (matchesDamageType(target.immunities,type)) { factor=0; reason='иммунитет'; }
    else if (matchesDamageType(target.resistances,type)) { factor=.5; reason='сопротивление'; }
    else if (matchesDamageType(target.vulnerabilities,type)) { factor=2; reason='уязвимость'; }
    final = factor===.5 ? Math.floor(final/2) : final*factor;
    let remaining=final;
    if (target.tempHp>0) { const absorb=Math.min(target.tempHp,remaining); target.tempHp-=absorb; remaining-=absorb; }
    const wasAtZero=target.hp<=0;
    target.hp=clamp(target.hp-remaining,0,target.maxHp);
    if(final>0&&target.conditions.includes('Концентрация')){
      const dc=Math.max(10,Math.floor(final/2));
      const bonus=target.saves.con??abilityMod(target.stats.con);
      const check=d20(bonus,'normal');
      const success=check.total>=dc;
      addLog({actor:target.name,name:'Концентрация',expression:check.detail,total:check.total,summary:`ТЕЛ против Сл ${dc} · ${success?'удержана':'потеряна'}`,outcome:success?'hit':'miss'});
      if(!success)target.conditions=target.conditions.filter(x=>x!=='Концентрация');
    }
    if(target.hp===0){
      if(!target.conditions.includes('Без сознания'))target.conditions.push('Без сознания');
      target.deathSaves ||= {success:0,fail:0};
      if(wasAtZero&&remaining>0){target.deathSaves.fail=clamp(target.deathSaves.fail+1,0,3);if(target.deathSaves.fail>=3&&!target.conditions.includes('Мёртв'))target.conditions.push('Мёртв');}
    }
    return { amount:final, note:`${final} урона${type?' · '+type:''}${reason?' · '+reason:''}` };
  }

  function startCombat() {
    if(!isGameMaster())return toast('Бой начинает мастер','Права стола');
    for (const c of state.characters) {
      const surprised = c.conditions.some(x=>/застигнут/i.test(x));
      const mode = state.campaign.edition==='2024' && surprised ? 'dis' : 'normal';
      const r=d20(c.initiative,mode); c.initiativeRoll=r.total;
      addLog({actor:c.name,name:'Инициатива',expression:r.detail,total:r.total,summary:mode==='dis'?'застигнут · помеха':''});
    }
    state.combat.started=true; state.combat.round=1; state.combat.turnIndex=0; commit();
  }

  function rollDeathSave(character) {
    character.deathSaves ||= {success:0,fail:0};
    const natural=randomDie(20);
    let summary='';
    if(natural===20){character.hp=1;character.deathSaves={success:0,fail:0};character.conditions=character.conditions.filter(x=>x!=='Без сознания');summary='натуральная 20 · 1 ХП';}
    else if(natural===1){character.deathSaves.fail=clamp(character.deathSaves.fail+2,0,3);summary='натуральная 1 · два провала';}
    else if(natural>=10){character.deathSaves.success=clamp(character.deathSaves.success+1,0,3);summary=`успех ${character.deathSaves.success}/3`;}
    else{character.deathSaves.fail=clamp(character.deathSaves.fail+1,0,3);summary=`провал ${character.deathSaves.fail}/3`;}
    if(character.deathSaves.success>=3){character.deathSaves={success:0,fail:0};character.conditions=character.conditions.filter(x=>x!=='Без сознания');character.conditions.push('Стабилен');summary='три успеха · стабилен';}
    if(character.deathSaves.fail>=3&&!character.conditions.includes('Мёртв')){character.conditions.push('Мёртв');summary='три провала · смерть';}
    addLog({actor:character.name,name:'Спасбросок от смерти',expression:`d20 [${natural}]`,total:natural,summary,outcome:natural>=10?'hit':'miss'});
  }

  function nextTurn() {
    if(!isGameMaster())return toast('Очередью управляет мастер','Права стола');
    const ordered=orderedCombatants(); if (!ordered.length) return;
    state.combat.turnIndex++;
    if (state.combat.turnIndex>=ordered.length) { state.combat.turnIndex=0; state.combat.round++; }
    const actor=ordered[state.combat.turnIndex];
    if (actor) {
      tickStatusEffects(actor);
      if(actor.role==='hero'){
        const bonds=partyHeroes().filter(h=>h.id!==actor.id).map(h=>Number(actor.relationships?.[h.id]||0));
        const bondStress=bonds.filter(v=>v<=-50).length*2-bonds.filter(v=>v>=50).length*2;
        if(bondStress){applyStress(actor,bondStress,'узы отряда');addLog({actor:actor.name,name:'Узы отряда',expression:bonds.map(v=>relationshipLabel(v)).join(', '),total:bondStress,summary:bondStress>0?'вражда усиливает стресс':'преданность снимает стресс',outcome:bondStress>0?'miss':'hit'});}
      }
      if(actor.role==='hero'&&actor.hp<=0&&!actor.conditions.includes('Мёртв')&&!actor.conditions.includes('Стабилен'))rollDeathSave(actor);
      for (const a of actor.actions.filter(x=>x.recharge && x.currentUses<x.maxUses)) {
        const threshold=Number(a.recharge.split('-')[0]); const r=randomDie(6);
        if (r>=threshold) a.currentUses=a.maxUses;
        addLog({actor:actor.name,name:`Перезарядка · ${a.name}`,expression:`d6 [${r}]`,total:r,summary:r>=threshold?'восстановлено':'не восстановлено',outcome:r>=threshold?'hit':'miss'});
      }
    }
    commit();
  }

  function takeRest(type, characterId=null) {
    if(!isGameMaster()&&!characterId)return toast('Общий отдых объявляет мастер','Права стола');
    if(characterId&&!canControlCharacter(characterId))return toast('Нет управления этим героем','Права стола');
    const chars=characterId?state.characters.filter(c=>c.id===characterId):state.characters;
    for (const c of chars) {
      for (const r of c.resources) if (type==='long'||r.recovery==='short') r.current=r.max;
      for (const a of c.actions) if (a.maxUses!==null&&a.maxUses!==undefined&&(type==='long'||a.recovery==='short')) a.currentUses=a.maxUses;
      if (type==='long'&&!c.conditions.includes('Мёртв')) { c.hp=c.maxHp; c.tempHp=0; c.stress=Math.max(0,c.stress-35); if(c.stress<100)c.resolve='steady'; c.deathSaves={success:0,fail:0}; c.conditions=c.conditions.filter(x=>!['Без сознания','Стабилен'].includes(x)); }
    }
    addLog({actor:'Мастер',name:type==='long'?'Долгий отдых':'Короткий отдых',expression:`Участников: ${chars.length}`,total:'✓',summary:'ресурсы восстановлены'});
    commit(); toast('Счётчики восстановлены', type==='long'?'Долгий отдых':'Короткий отдых');
  }

  function addRoadLog(title, text) {
    state.expedition.log.unshift({ id:cryptoId(), time:nowTime(), title, text });
    state.expedition.log = state.expedition.log.slice(0, 60);
  }

  function mergeInventoryItem(inventory,item){
    const existing=inventory.find(x=>x.templateId&&item.templateId&&x.templateId===item.templateId||x.name===item.name&&JSON.stringify(x.effects||[])===JSON.stringify(item.effects||[]));
    if(existing)existing.quantity=(existing.quantity||1)+(item.quantity||1);else inventory.push({...structuredClone(item),id:cryptoId(),quantity:item.quantity||1});
  }

  function generateLoot(node){
    const authored=state.compendium.items||[];
    let item=authored.length?structuredClone(authored[randomDie(authored.length)-1]):null;
    if(!item){
      const pool=[
        {name:'Соль пепельника',icon:'✚',rarity:'обычный',description:'Одноразовое лечение 1d8+2.',effects:[{op:'heal',target:'self',value:'1d8+2'}]},
        {name:'Осколок чёрного зеркала',icon:'◇',rarity:'редкий',description:'Снимает 8 стресса.',effects:[{op:'stress',target:'self',value:-8}]},
        {name:'Флакон живого угля',icon:'✦',rarity:'необычный',description:'Дарует регенерацию на 3 хода.',effects:[{op:'regen',target:'self',value:2,duration:3}]},
        {name:'Шипованный талисман',icon:'⚔',rarity:'необычный',description:'Наносит выбранной цели 1d6 силового урона.',effects:[{op:'damage',target:'target',value:'1d6',damageType:'силовой'}]}
      ];
      item=structuredClone(pool[randomDie(pool.length)-1]);
    }
    item.templateId ||= item.id||null;item.id=cryptoId();item.quantity=1;item.source=node.name;
    mergeInventoryItem(state.expedition.inventory,item);node.rewardClaimed=true;
    addRoadLog('Получена добыча',`${item.name} · ${item.rarity||'обычный предмет'} · ${node.name}.`);
    if(node.type==='elite'||node.type==='boss')state.hub.relics+=node.type==='boss'?3:1;
  }

  function showAssignLoot(itemId){
    const item=state.expedition.inventory.find(x=>x.id===itemId),heroes=partyHeroes();if(!item)return;
    showModal(`<div class="modal"><div class="modal-head"><div><h2>Распределить добычу</h2><p>${esc(item.name)} · предмет перейдёт в личный инвентарь героя.</p></div><button class="modal-close" data-close-modal>×</button></div><div class="modal-body"><div class="form-field"><label>Получатель</label><select id="lootCharacter" class="select">${heroes.map(c=>`<option value="${c.id}">${esc(c.name)}</option>`).join('')}<option value="hub">Хранилище Бастиона</option></select></div><p>${esc(item.description||'Эффекты задаются декларативно и исполняются без кода.')}</p></div><div class="modal-actions"><span></span><div class="modal-actions-right"><button class="dark-btn" data-close-modal>Отмена</button><button class="red-btn" data-confirm-loot="${item.id}">Передать</button></div></div></div>`);
  }

  function transferLoot(itemId,characterId){
    const index=state.expedition.inventory.findIndex(x=>x.id===itemId);if(index<0)return;const item=state.expedition.inventory[index];
    const destination=characterId==='hub'?state.hub.inventory:state.characters.find(c=>c.id===characterId)?.inventory;if(!destination)return;
    mergeInventoryItem(destination,{...item,quantity:1});item.quantity=(item.quantity||1)-1;if(item.quantity<=0)state.expedition.inventory.splice(index,1);
    closeModal();commit();toast('Предмет передан',item.name);
  }

  function useInventoryItem(characterId,itemId){
    const character=state.characters.find(c=>c.id===characterId);if(!character||!canControlCharacter(characterId))return toast('Нет управления этим героем','Инвентарь');
    const index=(character.inventory||[]).findIndex(x=>x.id===itemId);if(index<0)return;const item=character.inventory[index];
    const target=state.characters.find(c=>c.id===state.combat.targetId)||character;
    executeDeclarativeEffects({name:item.name,effects:item.effects||[]},character,target);
    item.quantity=(item.quantity||1)-1;if(item.quantity<=0)character.inventory.splice(index,1);
    addLog({actor:character.name,name:`Предмет · ${item.name}`,expression:item.description||'декларативный эффект',total:'✓',summary:`цель: ${target.name}`});commit();toast('Предмет использован',item.name);
  }

  function applyHubAssignments(){
    const heroes=state.characters.filter(c=>c.role==='hero');
    for(const hero of heroes){
      const building=state.hub.buildings.find(b=>b.id===state.hub.assignments[hero.id]);if(!building)continue;
      if(/лазарет/i.test(building.name)){hero.stress=Math.max(0,hero.stress-(10+building.level*5));if(hero.diseases.length&&building.level>=2)hero.diseases.shift();}
      else if(/братство|клин/i.test(building.name))hero.tempHp=Math.max(hero.tempHp||0,building.level*2);
      else if(/скриптор/i.test(building.name)){for(const r of hero.resources)r.current=r.max;}
    }
    const courtyard=state.hub.buildings.find(b=>/костров|двор/i.test(b.name));
    if(courtyard){const assigned=heroes.filter(h=>state.hub.assignments[h.id]===courtyard.id);for(let i=0;i<assigned.length;i++)for(let j=i+1;j<assigned.length;j++)changeRelationship(assigned[i],assigned[j],2+courtyard.level,'совместная смена у костра');}
  }

  function startExpedition() {
    if (!isGameMaster()) return toast('Только мастер начинает экспедицию','Права стола');
    const ex=state.expedition; ex.active=true; ex.nodeIndex=0; ex.light=clamp(ex.light,1,100);
    ex.route.forEach((n,i)=>{n.status=i===0?'current':'locked';n.selectedNextId=null;n.rewardClaimed=false;});
    ex.inventory=[];addRoadLog('Экспедиция началась', `${partyHeroes().length} героев покидают ${state.hub.name}.`);
    commit();
  }

  function resolveExpeditionNode(node) {
    const ex=state.expedition, heroes=partyHeroes();
    const lightLoss=Math.min(ex.light, 4+randomDie(6)); ex.light-=lightLoss;
    if(node.type==='hazard'){
      const stress=3+randomDie(6); heroes.forEach(c=>applyStress(c,stress,'опасность пути'));changeRandomRelationship(-2,'взаимные обвинения после опасности');
      addRoadLog(node.name, `Опасный переход: каждый герой получает ${stress} стресса. Свет −${lightLoss}.`);
    } else if(node.type==='battle'||node.type==='elite'||node.type==='boss'){
      const stress=node.type==='boss'?10:node.type==='elite'?6:3; heroes.forEach(c=>applyStress(c,stress,node.name));
      state.scene.name=node.name; state.combat.started=false; state.combat.round=1; state.combat.turnIndex=0;
      addRoadLog(node.name, `Обнаружен противник. Стресс отряда +${stress}, свет −${lightLoss}.`);
      runtime.view='scene';
    } else if(node.type==='curio'){
      const roll=randomDie(20);
      if(roll>=11){const loot=40+randomDie(6)*10; ex.currency+=loot; state.hub.gold+=loot;changeRandomRelationship(2,'удача разделена на всех');addRoadLog(node.name, `Находка принесла ${loot} золота. Свет −${lightLoss}.`);}
      else {heroes.forEach(c=>applyStress(c,5,'тревожная находка'));changeRandomRelationship(-2,'спор из-за дурного знака');addRoadLog(node.name, `Находка оказалась дурным знаком. Стресс +5, свет −${lightLoss}.`);}
    } else if(node.type==='camp'){
      ex.campPoints=Math.max(ex.campPoints,12); addRoadLog(node.name, `Безопасное место для лагеря. Свет −${lightLoss}.`);
    } else addRoadLog(node.name, `Путь продолжается. Свет −${lightLoss}.`);
    if(ex.light<=0){heroes.forEach(c=>applyStress(c,8,'полная тьма'));addRoadLog('Тьма наступает','Без света каждый герой получает 8 стресса.');}
  }

  function advanceExpedition() {
    if(!isGameMaster())return toast('Маршрутом управляет мастер','Права стола');
    const ex=state.expedition;if(!ex.active)return startExpedition();
    const current=ex.route[ex.nodeIndex];
    if(current?.branchTo&&!current.selectedNextId)return toast('Сначала выберите один из путей','Развилка маршрута');
    if(current&&!current.rewardClaimed&&['battle','elite','boss','curio'].includes(current.type))generateLoot(current);
    if(current&&['battle','elite','boss'].includes(current.type))changeRandomRelationship(1,'общая победа');
    if(current)current.status='cleared';
    const previousIndex=ex.nodeIndex,chosen=current?.selectedNextId, nextIndex=chosen?ex.route.findIndex(n=>n.id===chosen):ex.nodeIndex+1;
    if(nextIndex>previousIndex+1)for(let i=previousIndex+1;i<nextIndex;i++)if(ex.route[i].status==='locked')ex.route[i].status='skipped';
    if(nextIndex<0||nextIndex>=ex.route.length){
      ex.active=false;for(const item of ex.inventory)mergeInventoryItem(state.hub.inventory,item);ex.inventory=[];
      addRoadLog('Путь завершён','Отряд возвращается в бастион; нераспределённая добыча перенесена в хранилище.');commit();return;
    }
    ex.nodeIndex=nextIndex; const node=ex.route[ex.nodeIndex];node.status='current';resolveExpeditionNode(node);commit();
  }

  function applyStress(target, amount, reason='') {
    const before=target.stress||0; target.stress=clamp(before+Number(amount||0),0,target.maxStress||200);
    if(target.resolve==='steady'&&target.stress>=100){
      const test=randomDie(100); target.resolve=test<=20?'virtuous':'afflicted';
      addLog({actor:target.name,name:'Проверка решимости',expression:`d100 [${test}]`,total:test,summary:target.resolve==='virtuous'?'проявлена стойкость':'психологический надлом',outcome:target.resolve==='virtuous'?'hit':'miss'});
    }
    if(target.stress>=200){target.stress=100; const loss=Math.max(1,Math.floor(target.maxHp*.25));applyDamage(target,loss,'психический');addLog({actor:target.name,name:'Кризис',expression:reason||'предельный стресс',total:loss,summary:'потеря хитов от кризиса',outcome:'miss'});}
    return target.stress-before;
  }

  function executeDeclarativeEffects(action, actor, target) {
    for(const effect of action.effects||[]){
      let targets=effect.target==='self'?[actor]:effect.target==='all-allies'?state.characters.filter(c=>c.role===actor.role):effect.target==='all-enemies'?state.characters.filter(c=>c.role!==actor.role):[target||actor];
      for(const recipient of targets.filter(Boolean)){
        let value=effect.value;
        if(typeof value==='string'&&/d|к/i.test(value)){try{value=rollExpression(value).total;}catch{value=0;}}
        value=Number(value)||0;
        if(effect.op==='stress')applyStress(recipient,value,action.name);
        else if(effect.op==='light')state.expedition.light=clamp(state.expedition.light+value,0,100);
        else if(effect.op==='heal')recipient.hp=clamp(recipient.hp+value,0,recipient.maxHp);
        else if(effect.op==='damage')applyDamage(recipient,value,effect.damageType||'');
        else if(effect.op==='condition'&&effect.name&&!recipient.conditions.includes(effect.name))recipient.conditions.push(effect.name);
        else if(['bleed','blight','horror','regen'].includes(effect.op))recipient.statusEffects.push({id:cryptoId(),name:effect.name||effect.op,type:effect.op,value,duration:Number(effect.duration)||3});
        else if(effect.op==='move'){const slot=state.scene.formation.find(x=>x.characterId===recipient.id);if(slot)moveFormationRankSilent(recipient.id,value<0?'forward':'back',Math.abs(value)||1);}
      }
    }
  }

  function moveFormationRankSilent(characterId,direction,steps=1){for(let i=0;i<steps;i++){const slot=state.scene.formation.find(x=>x.characterId===characterId);if(!slot)return;const next=clamp(slot.rank+(direction==='forward'?-1:1),1,MAX_RANKS);const other=state.scene.formation.find(x=>x.side===slot.side&&x.rank===next);if(other)other.rank=slot.rank;slot.rank=next;}}

  function tickStatusEffects(actor){
    for(const fx of [...(actor.statusEffects||[])]){
      if(fx.type==='bleed'||fx.type==='blight'){const applied=applyDamage(actor,fx.value,fx.type==='bleed'?'кровотечение':'яд');addLog({actor:actor.name,name:fx.name,expression:`${fx.value} · остаётся ${fx.duration-1}`,total:applied.amount,summary:'периодический урон',outcome:'miss'});}
      else if(fx.type==='horror')applyStress(actor,fx.value,fx.name);
      else if(fx.type==='regen')actor.hp=clamp(actor.hp+fx.value,0,actor.maxHp);
      fx.duration--;
    }
    actor.statusEffects=actor.statusEffects.filter(x=>x.duration>0);
  }

  function showCampModal(){
    const ex=state.expedition, heroes=partyHeroes();
    showModal(`<div class="modal wide"><div class="modal-head"><div><h2>Лагерь экспедиции</h2><p>Распределите ${ex.campPoints} очков подготовки. Разговоры создают постоянные узы.</p></div><button class="modal-close" data-close-modal>×</button></div><div class="modal-body"><div class="camp-grid">${heroes.map(c=>`<article class="camp-hero"><div class="init-avatar" ${c.tokenAsset?`data-asset-bg="${c.tokenAsset}"`:''}>${c.tokenAsset?'':esc(initials(c.name))}</div><div><b>${esc(c.name)}</b><small>${c.hp}/${c.maxHp} ХП · стресс ${c.stress}</small></div><button data-camp-heal="${c.id}" ${ex.campPoints<3?'disabled':''}>Лечение · 3</button><button data-camp-stress="${c.id}" ${ex.campPoints<2?'disabled':''}>Успокоить · 2</button></article>`).join('')}</div><div class="camp-bonds"><small>РАЗГОВОРЫ У ОГНЯ · 2 ОЧКА</small>${relationshipPairs(heroes).map(([a,b,value])=>`<button data-camp-bond="${a.id}|${b.id}" ${ex.campPoints<2?'disabled':''}><b>${esc(a.name)} ↔ ${esc(b.name)}</b><span>${relationshipLabel(value)} · ${value>0?'+':''}${value}</span></button>`).join('')}</div></div><div class="modal-actions"><b>Осталось: ${ex.campPoints}</b><div class="modal-actions-right"><button class="dark-btn" data-close-modal>Продолжить позже</button><button class="red-btn" data-action="finish-camp">Свернуть лагерь</button></div></div></div>`);resolveAssetElements();
  }

  function editRouteModal(){
    const rows=state.expedition.route.map((n,i)=>`<div class="route-editor-row"><input class="text-input" data-route-name="${i}" value="${esc(n.name)}"><select class="select" data-route-type="${i}">${Object.entries(EXPEDITION_NODE_LABELS).map(([k,v])=>`<option value="${k}" ${n.type===k?'selected':''}>${v}</option>`).join('')}</select><select class="select" data-route-branch="${i}"><option value="">Без развилки</option>${state.expedition.route.map((target,j)=>j>i+1?`<option value="${target.id}" ${n.branchTo===target.id?'selected':''}>Ветка → ${esc(target.name)}</option>`:'').join('')}</select><input class="text-input" data-route-branch-label="${i}" value="${esc(n.branchLabel||'Альтернативный путь')}" placeholder="Название ветки"><button class="danger-btn" data-remove-route-node="${i}">×</button></div>`).join('');
    showModal(`<div class="modal"><div class="modal-head"><div><h2>Редактор маршрута</h2><p>До и после начала похода мастер может изменить любую точку.</p></div><button class="modal-close" data-close-modal>×</button></div><div class="modal-body"><div id="routeEditor">${rows}</div><button class="outline-btn" data-action="add-route-node">＋ Точка пути</button></div><div class="modal-actions"><span></span><div class="modal-actions-right"><button class="dark-btn" data-close-modal>Отмена</button><button class="red-btn" data-action="save-route">Сохранить маршрут</button></div></div></div>`);
  }

  function contentTemplate(category){
    const base={id:cryptoId(),name:'Новый объект',type:category,icon:contentGlyph(category),description:''};
    if(category==='abilities')return {...base,type:'attack',validFrom:[1,2,3,4,5],validTargets:[1,2,3,4,5],attackBonus:0,damage:'1d6',damageType:'',effects:[]};
    if(category==='creatures')return {...base,ac:12,hp:20,rank:1,ai:{priority:'nearest',actions:[]}};
    if(category==='items')return {...base,rarity:'common',price:100,effects:[]};
    if(category==='effects')return {...base,op:'condition',target:'target',value:0,duration:1};
    if(category==='locations')return {...base,nodeType:'battle',backgroundAsset:null,danger:1};
    if(category==='events')return {...base,choices:[{label:'Продолжить',effects:[]}]};
    return {...base,level:1,maxLevel:5,cost:250};
  }

  function showBuildingEditor(building){
    showModal(`<div class="modal"><div class="modal-head"><div><h2>Редактор района</h2><p>Изменения применяются только к текущей кампании.</p></div><button class="modal-close" data-close-modal>×</button></div><div class="modal-body"><div class="form-grid"><div class="form-field"><label>Название</label><input id="buildingName" class="text-input" value="${esc(building.name)}"></div><div class="form-field"><label>Символ</label><input id="buildingIcon" class="text-input" value="${esc(building.icon||'◆')}"></div><div class="form-field"><label>Уровень</label><input id="buildingLevel" class="number-input" type="number" value="${building.level}"></div><div class="form-field"><label>Максимальный уровень</label><input id="buildingMax" class="number-input" type="number" value="${building.maxLevel}"></div><div class="form-field"><label>Цена улучшения</label><input id="buildingCost" class="number-input" type="number" value="${building.cost}"></div><div class="form-field full"><label>Описание</label><textarea id="buildingDescription" class="textarea">${esc(building.description)}</textarea></div></div></div><div class="modal-actions"><span></span><div class="modal-actions-right"><button class="dark-btn" data-close-modal>Отмена</button><button class="red-btn" data-save-building="${building.id}">Сохранить</button></div></div></div>`);
  }

  function showAttachContent(item){
    const heroes=state.characters.filter(c=>c.role==='hero');
    showModal(`<div class="modal"><div class="modal-head"><div><h2>Добавить способность</h2><p>${esc(item.name)} будет скопирована в лист и останется редактируемой.</p></div><button class="modal-close" data-close-modal>×</button></div><div class="modal-body"><div class="form-field"><label>Персонаж</label><select id="attachCharacter" class="select">${heroes.map(c=>`<option value="${c.id}">${esc(c.name)}</option>`).join('')}</select></div></div><div class="modal-actions"><span></span><div class="modal-actions-right"><button class="dark-btn" data-close-modal>Отмена</button><button class="red-btn" data-confirm-attach="${item.id}">Добавить в лист</button></div></div></div>`);
  }

  function showContentEditor(item=null){
    const category=runtime.workshopCategory, value=item||contentTemplate(category);
    showModal(`<div class="modal wide"><div class="modal-head"><div><h2>${item?'Редактировать':'Новый объект'} · ${esc(CONTENT_CATEGORIES[category])}</h2><p>JSON проверяется перед сохранением. Скрипты и HTML не выполняются.</p></div><button class="modal-close" data-close-modal>×</button></div><div class="modal-body"><textarea id="contentJson" class="import-editor" spellcheck="false">${esc(JSON.stringify(value,null,2))}</textarea><div class="schema-help"><b>Обязательные поля:</b><code>id</code><code>name</code><span>Способность может содержать массив <code>effects</code> с операциями damage, heal, stress, light, condition, bleed, blight, horror, regen или move.</span></div></div><div class="modal-actions"><span id="contentValidation">Локальная схема GrimDice Forge</span><div class="modal-actions-right"><button class="dark-btn" data-close-modal>Отмена</button><button class="red-btn" data-action="save-content">Проверить и сохранить</button></div></div></div>`);
  }

  function blobToDataURL(blob){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(reader.error);reader.readAsDataURL(blob);});}

  async function exportMod(){
    const assets=[];
    for(const [kind] of Object.entries(MEDIA_CATEGORIES))for(const meta of state.media[kind]||[]){const blob=await getAssetBlob(meta.id).catch(()=>null);if(blob)assets.push({...meta,kind,data:await blobToDataURL(blob)});}
    const pack={format:'grimdice-mod',version:2,name:`${state.campaign.title} · пользовательский пакет`,exportedAt:new Date().toISOString(),content:Object.fromEntries(Object.keys(CONTENT_CATEGORIES).map(k=>[k,state.compendium[k]])),assets};
    const data=JSON.stringify(pack), name='grimdice-full.mod.json';
    if(window.grimdiceDesktop){const r=await window.grimdiceDesktop.saveCampaign(data,name);if(!r.canceled)toast(`Пакет сохранён · бинарных файлов: ${assets.length}`,'Конструктор');return;}
    const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([data],{type:'application/json'}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);toast(`Контент и бинарные файлы: ${assets.length}`,'Пакет готов');
  }

  async function importMod(){
    const files=await pickFiles('.json,.mod.json,application/json',false);if(!files[0])return;
    try{
      const pack=JSON.parse(await files[0].text());if(pack.format!=='grimdice-mod'||!pack.content||![1,2].includes(Number(pack.version)))throw new Error('Неизвестный или несовместимый пакет GrimDice');
      for(const k of Object.keys(CONTENT_CATEGORIES))for(const item of pack.content[k]||[]){if(item&&typeof item==='object'&&!state.compendium[k].some(x=>x.id===item.id))state.compendium[k].push(item);}
      let importedAssets=0;
      const known=new Set(Object.keys(MEDIA_CATEGORIES).flatMap(k=>(state.media[k]||[]).map(a=>a.id)));
      for(const asset of pack.assets||[]){if(!asset?.id||!MEDIA_CATEGORIES[asset.kind]||typeof asset.data!=='string'||known.has(asset.id))continue;const blob=await (await fetch(asset.data)).blob();await putAsset(blob,asset.id);state.media[asset.kind].push({id:asset.id,name:String(asset.name||'asset'),size:blob.size,type:String(asset.type||blob.type||'application/octet-stream')});known.add(asset.id);importedAssets++;}
      state.compendium.mods.push({id:cryptoId(),name:pack.name||files[0].name,version:Number(pack.version),assets:importedAssets,importedAt:Date.now()});commit();toast(`Контент установлен · файлов: ${importedAssets}`,'Пакет установлен');
    }catch(err){toast(err.message,'Ошибка пакета');}
  }

  function showImportModal() {
    showModal(`<div class="modal wide"><div class="modal-head"><div><h2>Импорт из чистого текста</h2><p>Детерминированно: без ИИ, догадок и переписывания исходника</p></div><button class="modal-close" data-close-modal>×</button></div><div class="modal-body"><div class="import-grid"><div><textarea id="importText" class="import-editor" spellcheck="false" placeholder="Вставьте сюда персонажа или статблок…"></textarea></div><aside class="import-help"><h3>Что распознаётся</h3><p>Имя, класс, уровень, КД, хиты, скорость, 6 характеристик, спасброски, Сл, бонус атаки чарами, защиты, действия, урон и счётчики N/N.</p><ul><li>Одна механика — одна строка.</li><li>Пишите кости как 2d6+3 или 2к6+3.</li><li>Не найденное поле не додумывается.</li></ul><div class="code-sample">${esc(SAMPLE_TEXT.slice(0,640))}</div></aside></div></div><div class="modal-actions"><button class="dark-btn" data-action="paste-sample">Вставить пример</button><div class="modal-actions-right"><button class="dark-btn" data-close-modal>Отмена</button><button class="red-btn" data-action="parse-import">Разобрать без ИИ →</button></div></div></div>`);
    setTimeout(()=>document.getElementById('importText')?.focus(),40);
  }

  function showImportPreview(result) {
    const c=result.character;
    showModal(`<div class="modal wide"><div class="modal-head"><div><h2>Проверка импорта · ${esc(c.name)}</h2><p>Найдено полей: ${result.found.length} · предупреждений: ${result.warnings.length}</p></div><button class="modal-close" data-close-modal>×</button></div><div class="modal-body"><div class="sheet-layout"><aside class="sheet-sidebar"><div class="sheet-identity"><span class="section-kicker">ПРЕДПРОСМОТР</span><h2>${esc(c.name)}</h2><p>${esc([c.race,c.className,c.level?`${c.level} ур.`:''].filter(Boolean).join(' · '))}</p><div class="big-vitals"><div><small>КД</small><b>${c.ac}</b></div><div><small>ХП</small><b>${c.hp}/${c.maxHp}</b></div><div><small>ДЕЙСТВИЯ</small><b>${c.actions.length}</b></div></div></div></aside><div class="sheet-content"><h3 style="font-family:Georgia;margin-top:0">Аудит полей</h3><div class="audit-list">${c.audit.map(x=>`<div class="audit-item ${x.status}"><span>${esc(x.label)}</span><b>${x.status==='ok'?'✓ ':'⚠ '}${esc(x.note)}</b></div>`).join('')}</div><h3 style="font-family:Georgia">Распознанные действия</h3>${c.actions.map(a=>`<div class="action-row"><div><b>${esc(a.name)}</b><div class="action-detail">${esc(actionDetail(a))}</div></div></div>`).join('')||'<p style="color:var(--muted)">Нет действий</p>'}</div></div></div><div class="modal-actions"><button class="dark-btn" data-action="back-to-import">← Назад к тексту</button><div class="modal-actions-right"><button class="dark-btn" data-close-modal>Отмена</button><button class="red-btn" id="confirmImportBtn">Добавить на стол</button></div></div></div>`);
    document.getElementById('confirmImportBtn').onclick=()=>{ state.characters.push(c); closeModal(); commit(); toast('Исходный текст сохранён в листе', c.name); };
  }

  function showCharacterSheet(id, tab='main') {
    const c=state.characters.find(x=>x.id===id); if (!c) return;
    runtime.editCharacterId=id; runtime.editTab=tab;
    const content = tab==='main' ? renderSheetMain(c) : tab==='actions' ? renderSheetActions(c) : renderSheetSource(c);
    showModal(`<div class="modal wide"><div class="modal-head"><div><h2>${esc(c.name)}</h2><p>Лист персонажа · профиль ${c.edition}</p></div><button class="modal-close" data-close-modal>×</button></div><div class="modal-body"><div class="sheet-layout"><aside class="sheet-sidebar"><div class="portrait-zone" ${c.tokenAsset?`data-asset-bg="${c.tokenAsset}"`:''}><div style="font:48px Georgia;color:#5e4c45">${c.tokenAsset?'':esc(initials(c.name))}</div><button class="dark-btn" data-action="upload-portrait" data-character="${c.id}">▧ Портрет</button></div><div class="sheet-identity"><h2>${esc(c.name)}</h2><p>${esc([c.race,c.className,c.level?`${c.level} ур.`:''].filter(Boolean).join(' · '))}</p><div class="big-vitals"><div><small>КД</small><b>${c.ac}</b></div><div><small>ХП</small><b>${c.hp}/${c.maxHp}</b></div><div><small>СКОР</small><b>${c.speed}</b></div></div></div></aside><div class="sheet-content"><div class="tabs"><button data-sheet-tab="main" class="${tab==='main'?'active':''}">Основа</button><button data-sheet-tab="actions" class="${tab==='actions'?'active':''}">Действия (${c.actions.length})</button><button data-sheet-tab="source" class="${tab==='source'?'active':''}">Исходник и аудит</button></div>${content}</div></div></div><div class="modal-actions"><span style="color:var(--faint);font-size:9px">Изменения применяются только после сохранения</span><div class="modal-actions-right"><button class="dark-btn" data-close-modal>Закрыть</button>${tab!=='source'?'<button class="red-btn" data-action="save-sheet">Сохранить лист</button>':''}</div></div></div>`);
    resolveAssetElements();
  }

  function renderSheetMain(c) {
    return `<form id="sheetForm"><div class="form-grid"><div class="form-field"><label>Имя</label><input class="text-input" name="name" value="${esc(c.name)}"></div><div class="form-field"><label>Роль</label><select class="select" name="role"><option value="hero" ${c.role==='hero'?'selected':''}>Герой</option><option value="enemy" ${c.role==='enemy'?'selected':''}>Противник</option></select></div><div class="form-field"><label>Класс / вид существа</label><input class="text-input" name="className" value="${esc(c.className)}"></div><div class="form-field"><label>Раса / вид</label><input class="text-input" name="race" value="${esc(c.race)}"></div><div class="form-field"><label>Уровень</label><input class="number-input" type="number" name="level" value="${c.level}"></div><div class="form-field"><label>Бонус мастерства</label><input class="number-input" type="number" name="proficiency" value="${c.proficiency}"></div><div class="form-field"><label>КД</label><input class="number-input" type="number" name="ac" value="${c.ac}"></div><div class="form-field"><label>Скорость</label><input class="number-input" type="number" name="speed" value="${c.speed}"></div><div class="form-field"><label>Текущие хиты</label><input class="number-input" type="number" name="hp" value="${c.hp}"></div><div class="form-field"><label>Максимум хитов</label><input class="number-input" type="number" name="maxHp" value="${c.maxHp}"></div><div class="form-field"><label>Стресс</label><input class="number-input" type="number" name="stress" min="0" max="${c.maxStress}" value="${c.stress}"></div><div class="form-field"><label>Решимость</label><select class="select" name="resolve"><option value="steady" ${c.resolve==='steady'?'selected':''}>Собран</option><option value="afflicted" ${c.resolve==='afflicted'?'selected':''}>Надломлен</option><option value="virtuous" ${c.resolve==='virtuous'?'selected':''}>Воодушевлён</option></select></div><div class="form-field"><label>Черты / причуды</label><input class="text-input" name="quirks" value="${esc(c.quirks.join(', '))}"></div><div class="form-field"><label>Болезни / травмы</label><input class="text-input" name="diseases" value="${esc(c.diseases.join(', '))}"></div>${ABILITIES.map(k=>`<div class="form-field"><label>${ABILITY_RU[k]} · модификатор ${signed(abilityMod(c.stats[k]))}</label><input class="number-input" type="number" name="stat_${k}" value="${c.stats[k]}"></div>`).join('')}<div class="form-field"><label>Сл заклинаний</label><input class="number-input" type="number" name="spellDC" value="${c.spellDC??''}"></div><div class="form-field"><label>Атака заклинанием</label><input class="number-input" type="number" name="spellAttack" value="${c.spellAttack??''}"></div><div class="form-field"><label>Сопротивления (через запятую)</label><input class="text-input" name="resistances" value="${esc(c.resistances.join(', '))}"></div><div class="form-field"><label>Уязвимости</label><input class="text-input" name="vulnerabilities" value="${esc(c.vulnerabilities.join(', '))}"></div><div class="form-field full"><label>Иммунитеты</label><input class="text-input" name="immunities" value="${esc(c.immunities.join(', '))}"></div></div></form>`;
  }

  function renderSheetActions(c) {
    return `<form id="actionsForm"><div id="actionEditor">${c.actions.map((a,i)=>`<div class="action-editor-row" data-action-row="${a.id}"><input class="text-input" name="a_name_${i}" value="${esc(a.name)}" placeholder="Название"><select class="select" name="a_type_${i}"><option value="attack" ${a.type==='attack'?'selected':''}>Атака</option><option value="spell" ${a.type==='spell'?'selected':''}>Чары</option><option value="save" ${a.type==='save'?'selected':''}>Спасбросок</option><option value="damage" ${a.type==='damage'?'selected':''}>Урон</option><option value="heal" ${a.type==='heal'?'selected':''}>Лечение</option><option value="utility" ${a.type==='utility'?'selected':''}>Особое</option></select><input class="number-input" name="a_attack_${i}" value="${a.attackBonus??''}" placeholder="Атака +"><input class="text-input" name="a_damage_${i}" value="${esc(a.damage)}" placeholder="1d8+3"><button type="button" class="danger-btn" data-remove-action-editor="${a.id}">×</button><input class="text-input" name="a_dtype_${i}" value="${esc(a.damageType)}" placeholder="Тип урона"><select class="select" name="a_save_${i}"><option value="">Нет спасброска</option>${ABILITIES.map(k=>`<option value="${k}" ${a.saveAbility===k?'selected':''}>${ABILITY_RU[k]}</option>`).join('')}</select><input class="number-input" name="a_dc_${i}" value="${a.saveDC??''}" placeholder="Сл"><input class="text-input" name="a_uses_${i}" value="${a.maxUses!==null&&a.maxUses!==undefined?`${a.currentUses}/${a.maxUses}`:''}" placeholder="2/2"><input class="text-input" name="a_from_${i}" value="${esc((a.validFrom||[]).join(','))}" placeholder="Из позиций: 1,2"><input class="text-input" name="a_targets_${i}" value="${esc((a.validTargets||[]).join(','))}" placeholder="Цели: 1-3"><input type="hidden" name="a_id_${i}" value="${a.id}"></div>`).join('')}</div><button type="button" class="outline-btn" data-action="add-action-editor">＋ Добавить действие</button></form>`;
  }

  function renderSheetSource(c) {
    return `<h3 style="font-family:Georgia">Аудит импорта</h3><div class="audit-list">${c.audit.map(x=>`<div class="audit-item ${x.status}"><span>${esc(x.label)}</span><b>${x.status==='ok'?'✓':'⚠'} ${esc(x.note)}</b></div>`).join('')||'<div class="audit-item"><span>Лист создан вручную</span><b>—</b></div>'}</div><h3 style="font-family:Georgia">Оригинал без изменений</h3><div class="source-box">${esc(c.sourceText||'Исходный текст отсутствует.')}</div>`;
  }

  function saveSheet() {
    if(runtime.editCharacterId&&!canControlCharacter(runtime.editCharacterId))return toast('Редактировать этот лист может его игрок или мастер','Права стола');
    const c=state.characters.find(x=>x.id===runtime.editCharacterId); if(!c)return;
    if (runtime.editTab==='main') {
      const f=new FormData(document.getElementById('sheetForm'));
      c.name=f.get('name')||'Безымянный'; c.role=f.get('role'); c.className=f.get('className'); c.race=f.get('race');
      for(const k of ['level','proficiency','ac','speed','hp','maxHp','stress']) c[k]=Number(f.get(k))||0;
      c.stress=clamp(c.stress,0,c.maxStress); c.resolve=f.get('resolve')||'steady';
      for(const k of ['quirks','diseases']) c[k]=String(f.get(k)||'').split(',').map(x=>x.trim()).filter(Boolean);
      for(const k of ABILITIES) c.stats[k]=Number(f.get(`stat_${k}`))||10;
      c.spellDC=f.get('spellDC')===''?null:Number(f.get('spellDC')); c.spellAttack=f.get('spellAttack')===''?null:Number(f.get('spellAttack'));
      for(const k of ['resistances','vulnerabilities','immunities']) c[k]=String(f.get(k)||'').split(',').map(x=>x.trim().toLowerCase()).filter(Boolean);
    } else if(runtime.editTab==='actions') {
      const rows=[...document.querySelectorAll('[data-action-row]')];
      c.actions=rows.map((row,i)=>{
        const old=c.actions.find(a=>a.id===row.dataset.actionRow)||{};
        const val=n=>row.querySelector(`[name="${n}_${i}"]`)?.value ?? '';
        const uses=val('a_uses').match(/(\d+)\s*\/\s*(\d+)/);
        return {...old,id:val('a_id')||cryptoId(),name:val('a_name')||'Действие',type:val('a_type'),attackBonus:val('a_attack')===''?null:Number(val('a_attack')),damage:val('a_damage'),damageType:val('a_dtype'),saveAbility:val('a_save')||null,saveDC:val('a_dc')===''?null:Number(val('a_dc')),currentUses:uses?Number(uses[1]):null,maxUses:uses?Number(uses[2]):null,validFrom:parseRankSpec(val('a_from')),validTargets:parseRankSpec(val('a_targets')),targetSide:old.targetSide||((val('a_type')==='heal')?'ally':'enemy'),halfOnSave:old.halfOnSave||false,recovery:old.recovery||'long',notes:old.notes||''};
      });
    }
    commit(); closeModal(); toast('Лист обновлён',c.name);
  }

  function showConditionModal(id) {
    const c=state.characters.find(x=>x.id===id); if(!c)return;
    showModal(`<div class="modal"><div class="modal-head"><div><h2>Состояние · ${esc(c.name)}</h2><p>Отметка появится на карточке и жетоне</p></div><button class="modal-close" data-close-modal>×</button></div><div class="modal-body"><div class="rule-tags" style="gap:8px">${CONDITION_OPTIONS.map(x=>`<button class="outline-btn" data-add-condition="${esc(x)}" data-character="${c.id}">${esc(x)}</button>`).join('')}</div><div class="form-field" style="margin-top:14px"><label>Своя пометка</label><input id="customCondition" class="text-input" placeholder="Например: Благословение, 3 раунда"></div></div><div class="modal-actions"><span></span><div class="modal-actions-right"><button class="dark-btn" data-close-modal>Отмена</button><button class="red-btn" data-action="add-custom-condition" data-character="${c.id}">Добавить</button></div></div></div>`);
  }

  function showRoomModal() {
    const code=runtime.roomCode||Math.random().toString(36).slice(2,8).toUpperCase();
    const link=`${location.origin}${location.pathname}?room=${code}`;
    const heroes=state.characters.filter(c=>c.role==='hero');
    showModal(`<div class="modal"><div class="modal-head"><div><h2>${runtime.roomCode?'Общий стол подключён':'Подключить общий стол'}</h2><p>Мастер ведёт мир, каждый игрок управляет закреплённым героем</p></div><button class="modal-close" data-close-modal>×</button></div><div class="modal-body"><div class="form-grid"><div class="form-field full"><label>Код комнаты</label><div class="room-code"><input id="roomCodeInput" class="text-input" maxlength="12" value="${code}"><button class="dark-btn" data-action="copy-room-code">Копировать</button></div></div><div class="form-field"><label>Ваше имя</label><input id="roomPlayerName" class="text-input" value="${esc(runtime.localProfile.name||'Игрок')}"></div><div class="form-field"><label>Роль</label><select id="roomPlayerRole" class="select"><option value="gm" ${runtime.localProfile.role==='gm'?'selected':''}>Мастер</option><option value="player" ${runtime.localProfile.role==='player'?'selected':''}>Игрок</option></select></div><div class="form-field full"><label>Персонаж игрока</label><select id="roomCharacter" class="select"><option value="">— мастер / наблюдатель —</option>${heroes.map(c=>`<option value="${c.id}" ${runtime.localProfile.characterId===c.id?'selected':''}>${esc(c.name)}</option>`).join('')}</select></div></div><p style="color:var(--muted);line-height:1.6">Игрок может разыгрывать способности и менять хиты только своего героя. Мастер сохраняет контроль над очередью, противниками, маршрутом, редакторами и может перехватить любого персонажа.</p><div id="networkInfo" class="room-link">${runtime.desktop?'Определяю адреса этого компьютера…':esc(link)}</div>${state.network.members?.length?`<div class="member-list">${state.network.members.map(m=>`<span><i class="${m.role}"></i>${esc(m.name)} · ${m.role==='gm'?'мастер':esc(state.characters.find(c=>c.id===m.characterId)?.name||'наблюдатель')}</span>`).join('')}</div>`:''}</div><div class="modal-actions">${runtime.roomCode?'<button class="danger-btn" data-action="disconnect-room">Отключиться</button>':'<span></span>'}<div class="modal-actions-right"><button class="dark-btn" data-close-modal>Отмена</button><button class="red-btn" data-action="connect-room">${runtime.roomCode?'Применить профиль':'Войти в комнату'}</button></div></div></div>`);
    if(window.grimdiceDesktop)window.grimdiceDesktop.networkInfo().then(info=>{const box=document.getElementById('networkInfo');if(box)box.innerHTML=info.addresses.length?info.addresses.map(x=>`${esc(x.name)}: <b>http://${esc(x.address)}:${info.port}</b>`).join('<br>'):'Сетевой адрес не найден. Подключитесь к LAN или Hamachi.';});
  }

  function registerLocalMember(){
    runtime.localProfile.clientId=runtime.clientId; saveLocalProfile();
    state.network.members=state.network.members.filter(m=>m.clientId!==runtime.clientId);
    const member={clientId:runtime.clientId,name:runtime.localProfile.name||'Игрок',role:runtime.localProfile.role,characterId:runtime.localProfile.characterId||null};
    state.network.members.push(member);
    if(member.role==='gm'&&!state.network.gmClientId)state.network.gmClientId=runtime.clientId;
    if(member.characterId){for(const [cid,owner] of Object.entries(state.network.owners))if(owner===runtime.clientId)delete state.network.owners[cid];state.network.owners[member.characterId]=runtime.clientId;}
  }

  function showSettings() {
    showModal(`<div class="modal"><div class="modal-head"><div><h2>Настройки кампании</h2><p>Локальные данные и перенос между устройствами</p></div><button class="modal-close" data-close-modal>×</button></div><div class="modal-body"><div class="form-grid"><div class="form-field full"><label>Название кампании</label><input id="settingsTitle" class="text-input" value="${esc(state.campaign.title)}"></div><div class="form-field"><label>Редакция</label><select id="settingsEdition" class="select"><option value="2014" ${state.campaign.edition==='2014'?'selected':''}>5e · 2014</option><option value="2024" ${state.campaign.edition==='2024'?'selected':''}>5e · 2024</option></select></div></div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:18px"><button class="dark-btn" data-action="export-campaign">Экспорт JSON</button><button class="dark-btn" data-action="import-campaign">Импорт JSON</button><button class="danger-btn" data-action="reset-demo">Сбросить на демо</button></div></div><div class="modal-actions"><span></span><div class="modal-actions-right"><button class="dark-btn" data-close-modal>Отмена</button><button class="red-btn" data-action="save-settings">Сохранить</button></div></div></div>`);
  }

  function showModal(html) { document.getElementById('modalHost').innerHTML=`<div class="modal-backdrop">${html}</div>`; resolveAssetElements(); }
  function closeModal() { document.getElementById('modalHost').innerHTML=''; }
  function toast(message,title='GrimDice') { const el=document.createElement('div'); el.className='toast'; el.innerHTML=`<b>${esc(title)}</b><br>${esc(message)}`; document.getElementById('toastHost').append(el); setTimeout(()=>el.remove(),3500); }

  function ensureSceneTokens(reset=false) {
    if(reset) state.scene.tokens=[];
    state.characters.forEach((c,i)=>{ if(!state.scene.tokens.some(t=>t.characterId===c.id)) state.scene.tokens.push({id:cryptoId(),characterId:c.id,x:18+(i%4)*19,y:35+Math.floor(i/4)*24}); });
    state.scene.tokens=state.scene.tokens.filter(t=>state.characters.some(c=>c.id===t.characterId));
  }

  function initTokenDrag(token) {
    token.addEventListener('pointerdown',e=>{
      const sceneToken=state.scene.tokens.find(x=>x.id===token.dataset.token);
      if(e.button!==0||!sceneToken||!canControlCharacter(sceneToken.characterId))return;
      token.setPointerCapture(e.pointerId); const stage=document.getElementById('sceneStage');
      const move=ev=>{ const r=stage.getBoundingClientRect(); const x=clamp((ev.clientX-r.left)/r.width*100,2,98); const y=clamp((ev.clientY-r.top)/r.height*100,3,97); token.style.left=x+'%'; token.style.top=y+'%'; const t=state.scene.tokens.find(x=>x.id===token.dataset.token); if(t){t.x=x;t.y=y;} };
      const up=()=>{ token.removeEventListener('pointermove',move); commit(false); };
      token.addEventListener('pointermove',move); token.addEventListener('pointerup',up,{once:true});
    });
  }

  async function openAssetDB() {
    if(runtime.db)return runtime.db;
    runtime.db=await new Promise((resolve,reject)=>{ const req=indexedDB.open('grimdice-assets',1); req.onupgradeneeded=()=>{ if(!req.result.objectStoreNames.contains('files'))req.result.createObjectStore('files'); }; req.onsuccess=()=>resolve(req.result); req.onerror=()=>reject(req.error); });
    return runtime.db;
  }
  async function putAsset(file,id=cryptoId()) { const db=await openAssetDB(); await new Promise((res,rej)=>{const tx=db.transaction('files','readwrite');tx.objectStore('files').put(file,id);tx.oncomplete=res;tx.onerror=()=>rej(tx.error);}); return id; }
  async function getAssetBlob(id){const db=await openAssetDB();return new Promise((res,rej)=>{const r=db.transaction('files').objectStore('files').get(id);r.onsuccess=()=>res(r.result||null);r.onerror=()=>rej(r.error);});}
  async function getAssetUrl(id) {
    if(runtime.assetUrls.has(id))return runtime.assetUrls.get(id);
    const blob=await getAssetBlob(id);
    if(!blob)return null; const url=URL.createObjectURL(blob); runtime.assetUrls.set(id,url); return url;
  }
  async function deleteAsset(id) { try{const db=await openAssetDB();await new Promise((res,rej)=>{const tx=db.transaction('files','readwrite');tx.objectStore('files').delete(id);tx.oncomplete=res;tx.onerror=()=>rej(tx.error);});}catch{} const url=runtime.assetUrls.get(id);if(url)URL.revokeObjectURL(url);runtime.assetUrls.delete(id); }
  async function resolveAssetElements() {
    document.querySelectorAll('[data-asset-src]').forEach(async el=>{const u=await getAssetUrl(el.dataset.assetSrc).catch(()=>null);if(u)el.src=u;});
    document.querySelectorAll('[data-asset-bg]').forEach(async el=>{const u=await getAssetUrl(el.dataset.assetBg).catch(()=>null);if(u){el.style.backgroundImage=`url("${u}")`;el.style.backgroundSize='cover';el.style.backgroundPosition='center';}});
    document.querySelectorAll('[data-token]').forEach(initTokenDrag);
    applyActiveVisualMods();
  }
  function applyLocalization(root=document.body){
    const strings=state.media.activeLocalization?.strings;if(!strings||typeof strings!=='object'||!document.createTreeWalker)return;
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let node;
    while((node=walker.nextNode())){const raw=node.nodeValue,trim=raw.trim();if(trim&&typeof strings[trim]==='string')node.nodeValue=raw.replace(trim,strings[trim]);}
    if(typeof strings['GrimDice — мастерская боя 5e']==='string')document.title=strings['GrimDice — мастерская боя 5e'];
  }
  async function applyActiveVisualMods(){
    if(state.media.activeThemeId&&runtime.appliedThemeId!==state.media.activeThemeId){
      try{const manifest=JSON.parse(await (await getAssetBlob(state.media.activeThemeId)).text());for(const [key,value] of Object.entries(manifest.variables||{}))if(/^--[a-z0-9-]{2,40}$/i.test(key)&&typeof value==='string'&&!/url\s*\(|expression\s*\(/i.test(value))document.documentElement.style.setProperty(key,value);runtime.appliedThemeId=state.media.activeThemeId;}catch{}
    }
    if(state.media.activeFontId&&runtime.appliedFontId!==state.media.activeFontId&&globalThis.FontFace){
      try{const url=await getAssetUrl(state.media.activeFontId),face=new FontFace('GrimDice Mod Font',`url(${url})`);await face.load();document.fonts.add(face);document.documentElement.style.setProperty('--ui-font','"GrimDice Mod Font", system-ui, sans-serif');runtime.appliedFontId=state.media.activeFontId;}catch{}
    }
    const allowed=new Set(['.stage-actor','.actor-silhouette','.stage-backdrop','.stage-environment','.impact-hit','.impact-heal']);
    for(const animation of state.media.activeAnimations?.animations||[]){if(!allowed.has(animation.selector)||!Array.isArray(animation.keyframes))continue;document.querySelectorAll(animation.selector).forEach(el=>el.animate?.(animation.keyframes,{duration:clamp(animation.options?.duration||900,100,30000),iterations:animation.options?.iterations==='Infinity'?Infinity:clamp(animation.options?.iterations||1,1,20),easing:String(animation.options?.easing||'ease').slice(0,40)}));}
    applyLocalization(document.getElementById('app')||document.body);
  }
  function formatBytes(n=0){return n>1048576?`${(n/1048576).toFixed(1)} МБ`:n>1024?`${Math.round(n/1024)} КБ`:`${n} Б`;}

  function pickFiles(accept,multiple=true) { return new Promise(resolve=>{const input=document.createElement('input');input.type='file';input.accept=accept;input.multiple=multiple;input.onchange=()=>resolve([...input.files]);input.click();}); }
  async function applyMediaAsset(kind,id){
    if(!isGameMaster())return toast('Визуальными модами управляет мастер','Права стола');
    if(['sprites','portraits'].includes(kind)){
      const heroes=state.characters.filter(c=>c.role==='hero');
      return showModal(`<div class="modal"><div class="modal-head"><div><h2>Назначить визуал герою</h2><p>Файл станет портретом и боевым токеном.</p></div><button class="modal-close" data-close-modal>×</button></div><div class="modal-body"><select id="assetCharacter" class="select">${heroes.map(c=>`<option value="${c.id}">${esc(c.name)}</option>`).join('')}</select></div><div class="modal-actions"><span></span><button class="red-btn" data-confirm-asset-character="${id}">Назначить</button></div></div>`);
    }
    if(kind==='backgrounds'||kind==='maps'){state.scene.backgroundAsset=id;commit();toast('Фон назначен текущей сцене','Медиатека');return;}
    if(kind==='effects'){state.scene.effectAsset=state.scene.effectAsset===id?null:id;commit();toast(state.scene.effectAsset?'Слой эффекта включён':'Слой эффекта выключен','Медиатека');return;}
    try{
      if(kind==='fonts'){state.media.activeFontId=id;runtime.appliedFontId=null;await applyActiveVisualMods();}
      else {const blob=await getAssetBlob(id);if(!blob)throw new Error('Бинарный файл не найден');const manifest=JSON.parse(await blob.text());
        if(kind==='themes'){if(!manifest.variables||typeof manifest.variables!=='object')throw new Error('Тема должна содержать объект variables');state.media.activeThemeId=id;runtime.appliedThemeId=null;}
        else if(kind==='animations'){if(!Array.isArray(manifest.animations))throw new Error('Манифест должен содержать массив animations');state.media.activeAnimations=manifest;state.media.activeAnimationsId=id;}
        else if(kind==='localization'){if(!manifest.strings||typeof manifest.strings!=='object')throw new Error('Локализация должна содержать объект strings');state.media.activeLocalization=manifest;state.media.activeLocalizationId=id;}
      }
      commit();await applyActiveVisualMods();toast('Декларативный визуальный мод активирован',MEDIA_CATEGORIES[kind].label);
    }catch(error){toast(error.message,'Файл не прошёл проверку');}
  }

  async function uploadMedia(kind) {
    const def=MEDIA_CATEGORIES[kind];if(!def)return;
    const files=await pickFiles(def.accept);
    for(const file of files){const id=await putAsset(file);state.media[kind].push({id,name:file.name,size:file.size,type:file.type||'application/octet-stream'});}
    commit(); toast(`Добавлено файлов: ${files.length}`,def.label);
  }
  async function uploadPortrait(id) { const files=await pickFiles('image/*',false);if(!files[0])return;const asset=await putAsset(files[0]);const c=state.characters.find(x=>x.id===id);if(c)c.tokenAsset=asset;state.media.portraits.push({id:asset,name:files[0].name,size:files[0].size,type:files[0].type});commit();showCharacterSheet(id,runtime.editTab); }
  async function uploadSceneBackground() { const files=await pickFiles('image/*',false);if(!files[0])return;const asset=await putAsset(files[0]);state.scene.backgroundAsset=asset;state.media.backgrounds.push({id:asset,name:files[0].name,size:files[0].size,type:files[0].type});commit(); }
  async function toggleTrack(id) {
    if(runtime.playingTrack===id){runtime.audio?.pause();runtime.playingTrack=null;renderView();return;}
    const url=await getAssetUrl(id);if(!url)return toast('Файл не найден на этом устройстве','Медиатека');
    runtime.audio?.pause();runtime.audio=new Audio(url);runtime.audio.loop=true;runtime.audio.volume=.7;runtime.audio.play();runtime.playingTrack=id;runtime.audio.onended=()=>{runtime.playingTrack=null;renderView();};renderView();
  }

  async function exportCampaign() {
    const fileName=`grimdice-${state.campaign.title.replace(/[^\p{L}\p{N}]+/gu,'-').toLowerCase()}.grimdice.json`;
    const data=JSON.stringify(state,null,2);
    if (window.grimdiceDesktop) {
      const result=await window.grimdiceDesktop.saveCampaign(data,fileName);
      if(!result.canceled)toast(`Сохранено: ${result.path}`,'Кампания');
      return;
    }
    const blob=new Blob([data],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=fileName;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);toast('Персонажи и бой выгружены. Ассеты остаются локально.','Экспорт');
  }
  async function importCampaignFile(){
    if(window.grimdiceDesktop){const result=await window.grimdiceDesktop.openCampaign();if(result.canceled)return;try{state=migrateState(JSON.parse(result.data));closeModal();commit();toast(`Открыто: ${result.path}`,'Кампания');}catch{toast('Файл кампании повреждён','Ошибка');}return;}
    document.getElementById('campaignImportInput').click();
  }

  async function connectRoom(code) {
    code=String(code||'').trim().toUpperCase().replace(/[^A-ZА-Я0-9_-]/gi,'').slice(0,12);if(!code)return toast('Введите код комнаты','Общий стол');
    disconnectRoom(false,false); runtime.roomCode=code;
    try {
      const credential=loadRoomCredential(code);
      const response=await fetch(`/api/rooms/${encodeURIComponent(code)}/session`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({clientId:runtime.clientId,name:runtime.localProfile.name,role:runtime.localProfile.role,characterId:runtime.localProfile.characterId,sessionToken:credential.token||null,ownerKey:credential.ownerKey||null})
      });
      const joined=await response.json();
      if(!response.ok||!joined.token)throw new Error(joined.error||'Сессия отклонена');
      const requestedRole=runtime.localProfile.role;
      runtime.roomToken=joined.token;runtime.roomOwnerKey=joined.ownerKey||credential.ownerKey||null;runtime.roomRevision=joined.revision||0;
      runtime.localProfile.role=joined.role||'player';runtime.localProfile.characterId=joined.characterId||null;saveLocalProfile();
      saveRoomCredential(code,{token:runtime.roomToken,ownerKey:runtime.roomOwnerKey});
      if(joined.state){runtime.applyingRemote=true;state=migrateState(joined.state);saveState();runtime.applyingRemote=false;}
      else registerLocalMember();
      runtime.eventSource=new EventSource(`/api/rooms/${encodeURIComponent(code)}/events?token=${encodeURIComponent(runtime.roomToken)}`);
      runtime.eventSource.onmessage=ev=>{try{const data=JSON.parse(ev.data);if(data.sender===runtime.clientId||!data.state||data.revision<=runtime.roomRevision)return;runtime.roomRevision=data.revision;runtime.applyingRemote=true;state=migrateState(data.state);saveState();runtime.applyingRemote=false;updateChrome();renderView();toast('Стол обновлён другим участником',`Комната ${code}`);}catch{}};
      runtime.eventSource.onerror=()=>{document.getElementById('syncStatus')?.classList.remove('live');};
      if(!joined.state&&runtime.localProfile.role==='gm')scheduleSync(0);
      const url=new URL(location.href);url.searchParams.set('room',code);history.replaceState(null,'',url);
      closeModal();updateChrome();renderView();
      if(requestedRole==='gm'&&runtime.localProfile.role!=='gm')toast('Роль мастера уже занята: подключено как игрок','Защищённая комната');
      else if(joined.warning)toast(joined.warning,'Назначение героя');
      else toast('Защищённая синхронизация включена',`Стол ${code}`);
    }catch(err){runtime.roomCode=null;runtime.roomToken=null;updateChrome();toast(err.message||'Сервер комнаты недоступен','Ошибка подключения');}
  }
  function disconnectRoom(updateUrl=true,notifyServer=true){const oldCode=runtime.roomCode,oldToken=runtime.roomToken;runtime.eventSource?.close();runtime.eventSource=null;if(notifyServer&&oldCode&&oldToken)fetch(`/api/rooms/${encodeURIComponent(oldCode)}/session?token=${encodeURIComponent(oldToken)}`,{method:'DELETE',keepalive:true}).catch(()=>{});clearTimeout(runtime.syncTimer);runtime.syncTimer=null;runtime.syncQueued=false;runtime.syncing=false;runtime.roomCode=null;runtime.roomToken=null;runtime.roomOwnerKey=null;runtime.roomRevision=0;if(updateUrl){const u=new URL(location.href);u.searchParams.delete('room');history.replaceState(null,'',u);}updateChrome();}
  function scheduleSync(delay=220){if(!runtime.roomCode||!runtime.roomToken)return;if(runtime.syncing){runtime.syncQueued=true;return;}clearTimeout(runtime.syncTimer);runtime.syncTimer=setTimeout(pushRoomState,delay);}
  async function pushRoomState(){
    if(!runtime.roomCode||!runtime.roomToken)return;
    if(runtime.syncing){runtime.syncQueued=true;return;}
    runtime.syncing=true;runtime.syncTimer=null;
    const sentVersion=runtime.mutationVersion;
    try{
      const r=await fetch(`/api/rooms/${encodeURIComponent(runtime.roomCode)}/state`,{method:'POST',headers:{'Content-Type':'application/json','Authorization':`Bearer ${runtime.roomToken}`},body:JSON.stringify({clientId:runtime.clientId,baseRevision:runtime.roomRevision,state})});
      const d=await r.json().catch(()=>({}));
      if(r.ok){
        runtime.roomRevision=d.revision||runtime.roomRevision;
        if(d.state&&runtime.mutationVersion===sentVersion){runtime.applyingRemote=true;state=migrateState(d.state);saveState();runtime.applyingRemote=false;updateChrome();renderView();}
        else if(runtime.mutationVersion!==sentVersion)runtime.syncQueued=true;
        document.getElementById('syncStatus')?.classList.add('live');
      }else if(r.status===409&&d.state){
        runtime.roomRevision=d.revision||runtime.roomRevision;runtime.applyingRemote=true;state=migrateState(d.state);saveState();runtime.applyingRemote=false;runtime.syncQueued=false;updateChrome();renderView();toast('Получена более новая версия; локальный конфликт отменён','Синхронизация');
      }else if(r.status===401){toast('Сессия комнаты истекла. Подключитесь снова.','Синхронизация');disconnectRoom();}
      else toast(d.error||'Сервер отклонил изменение','Синхронизация');
    }catch{document.getElementById('syncStatus')?.classList.remove('live');}
    finally{runtime.syncing=false;if(runtime.syncQueued){runtime.syncQueued=false;scheduleSync(0);}}
  }

  function handleClick(e) {
    const btn=e.target.closest('button,[data-sheet],[data-hp],[data-play-action],[data-stage-target]'); if(!btn)return;
    if(btn.dataset.view){runtime.view=btn.dataset.view;updateChrome();renderView();return;}
    if(btn.dataset.edition){state.campaign.edition=btn.dataset.edition;commit();return;}
    if(btn.dataset.rollMode){runtime.rollMode=btn.dataset.rollMode;renderView();return;}
    if(btn.dataset.die){const r=rollExpression(`1d${btn.dataset.die}`);addLog({actor:'Стол',name:`Бросок d${btn.dataset.die}`,expression:r.detail,total:r.total,summary:'свободный бросок'});commit();return;}
    if(btn.dataset.playAction){playAction(btn.dataset.playAction,btn.dataset.actionId);return;}
    if(btn.dataset.stageTarget){state.combat.targetId=btn.dataset.stageTarget;commit();return;}
    if(btn.dataset.expeditionLight){if(isGameMaster()){state.expedition.light=clamp(state.expedition.light+Number(btn.dataset.expeditionLight),0,100);commit();}return;}
    if(btn.dataset.routeNode!==undefined){if(isGameMaster()){state.expedition.nodeIndex=clamp(Number(btn.dataset.routeNode),0,state.expedition.route.length-1);state.expedition.route.forEach((n,i)=>n.status=i<state.expedition.nodeIndex?'cleared':i===state.expedition.nodeIndex?'current':'locked');commit();}return;}
    if(btn.dataset.routeChoice){if(isGameMaster()){const current=state.expedition.route[state.expedition.nodeIndex];if(current){current.selectedNextId=btn.dataset.routeChoice;addRoadLog('Выбран путь',state.expedition.route.find(n=>n.id===current.selectedNextId)?.name||'неизведанное направление');commit();}}return;}
    if(btn.dataset.assignLoot){if(isGameMaster())showAssignLoot(btn.dataset.assignLoot);return;}
    if(btn.dataset.confirmLoot){if(isGameMaster())transferLoot(btn.dataset.confirmLoot,document.getElementById('lootCharacter')?.value);return;}
    if(btn.dataset.useItem){useInventoryItem(btn.dataset.character,btn.dataset.useItem);return;}
    if(btn.dataset.relationship){if(isGameMaster()){const [aId,bId]=btn.dataset.relationship.split('|'),a=state.characters.find(c=>c.id===aId),b=state.characters.find(c=>c.id===bId);changeRelationship(a,b,Number(btn.dataset.delta));commit();}return;}
    if(btn.dataset.supply){if(isGameMaster()){state.expedition.supplies[btn.dataset.supply]=Math.max(0,(state.expedition.supplies[btn.dataset.supply]||0)+Number(btn.dataset.delta));commit();}return;}
    if(btn.dataset.campHeal){const c=state.characters.find(x=>x.id===btn.dataset.campHeal);if(isGameMaster()&&c&&state.expedition.campPoints>=3){state.expedition.campPoints-=3;c.hp=clamp(c.hp+Math.max(1,Math.floor(c.maxHp*.25)),0,c.maxHp);showCampModal();commit(false);}return;}
    if(btn.dataset.campStress){const c=state.characters.find(x=>x.id===btn.dataset.campStress);if(isGameMaster()&&c&&state.expedition.campPoints>=2){state.expedition.campPoints-=2;c.stress=Math.max(0,c.stress-20);if(c.stress<100)c.resolve='steady';showCampModal();commit(false);}return;}
    if(btn.dataset.campBond){if(isGameMaster()&&state.expedition.campPoints>=2){const [aId,bId]=btn.dataset.campBond.split('|'),a=state.characters.find(c=>c.id===aId),b=state.characters.find(c=>c.id===bId);state.expedition.campPoints-=2;changeRelationship(a,b,8,'разговор у лагерного огня');showCampModal();commit(false);}return;}
    if(btn.dataset.hubRecover){const c=state.characters.find(x=>x.id===btn.dataset.hubRecover);if(isGameMaster()&&c){c.stress=Math.max(0,c.stress-25);if(c.stress<100)c.resolve='steady';commit();}return;}
    if(btn.dataset.upgradeBuilding){const b=state.hub.buildings.find(x=>x.id===btn.dataset.upgradeBuilding);if(b&&isGameMaster()&&b.level<b.maxLevel&&state.hub.gold>=b.cost){state.hub.gold-=b.cost;b.level++;b.cost=Math.ceil(b.cost*1.55/10)*10;commit();}else if(b&&state.hub.gold<b.cost)toast('Недостаточно золота','Бастион');return;}
    if(btn.dataset.editBuilding){const b=state.hub.buildings.find(x=>x.id===btn.dataset.editBuilding);if(b&&isGameMaster())showBuildingEditor(b);return;}
    if(btn.dataset.saveBuilding){const b=state.hub.buildings.find(x=>x.id===btn.dataset.saveBuilding);if(b){b.name=document.getElementById('buildingName').value||b.name;b.icon=document.getElementById('buildingIcon').value||'◆';b.level=Math.max(0,Number(document.getElementById('buildingLevel').value)||0);b.maxLevel=Math.max(1,Number(document.getElementById('buildingMax').value)||1);b.cost=Math.max(0,Number(document.getElementById('buildingCost').value)||0);b.description=document.getElementById('buildingDescription').value;closeModal();commit();}return;}
    if(btn.dataset.workshopCategory){runtime.workshopCategory=btn.dataset.workshopCategory;renderView();return;}
    if(btn.dataset.editContent){const x=(state.compendium[runtime.workshopCategory]||[]).find(x=>x.id===btn.dataset.editContent);if(x)showContentEditor(x);return;}
    if(btn.dataset.attachContent){const x=(state.compendium.abilities||[]).find(x=>x.id===btn.dataset.attachContent);if(x)showAttachContent(x);return;}
    if(btn.dataset.confirmAttach){const x=(state.compendium.abilities||[]).find(x=>x.id===btn.dataset.confirmAttach),c=state.characters.find(x=>x.id===document.getElementById('attachCharacter')?.value);if(x&&c){const a={id:cryptoId(),name:x.name||'Способность',type:x.type||'utility',attackBonus:x.attackBonus??null,damage:x.damage||'',damageType:x.damageType||'',saveAbility:x.saveAbility||null,saveDC:x.saveDC??null,currentUses:x.currentUses??x.maxUses??null,maxUses:x.maxUses??null,validFrom:x.validFrom||[],validTargets:x.validTargets||[],targetSide:x.targetSide||'enemy',recovery:x.recovery||'long',halfOnSave:!!x.halfOnSave,concentration:!!x.concentration,effects:structuredClone(x.effects||[]),notes:x.description||x.notes||''};c.actions.push(a);closeModal();commit();toast('Способность добавлена в лист',c.name);}return;}
    if(btn.dataset.duplicateContent){const rows=state.compendium[runtime.workshopCategory]||[],x=rows.find(x=>x.id===btn.dataset.duplicateContent);if(x){const copy=structuredClone(x);copy.id=cryptoId();copy.name=(copy.name||'Объект')+' · копия';rows.push(copy);commit();}return;}
    if(btn.dataset.deleteContent){const rows=state.compendium[runtime.workshopCategory]||[];if(confirm('Удалить объект из конструктора?')){state.compendium[runtime.workshopCategory]=rows.filter(x=>x.id!==btn.dataset.deleteContent);commit();}return;}
    if(btn.dataset.removeRouteNode!==undefined){if(isGameMaster()){const removed=state.expedition.route.splice(Number(btn.dataset.removeRouteNode),1)[0];for(const node of state.expedition.route)if(node.branchTo===removed?.id){node.branchTo=null;node.selectedNextId=null;}state.expedition.nodeIndex=clamp(state.expedition.nodeIndex,0,Math.max(0,state.expedition.route.length-1));editRouteModal();}return;}
    if(btn.dataset.moveRank){if(!canControlCharacter(btn.dataset.moveRank))return toast('Нет управления этим героем','Права стола');moveFormationRank(btn.dataset.moveRank,btn.dataset.direction);return;}
    if(btn.dataset.sheet){showCharacterSheet(btn.dataset.sheet);return;}
    if(btn.dataset.hp){if(!canControlCharacter(btn.dataset.hp))return toast('Нет управления этим героем','Права стола');const c=state.characters.find(x=>x.id===btn.dataset.hp);const input=document.querySelector(`[data-hp-input="${btn.dataset.hp}"]`);const amount=Math.max(1,Number(input?.value)||1);if(btn.dataset.delta==='+'){c.hp=clamp(c.hp+amount,0,c.maxHp);if(c.hp>0){c.conditions=c.conditions.filter(x=>x!=='Без сознания');c.deathSaves={success:0,fail:0};}}else applyDamage(c,amount,'');commit();return;}
    if(btn.dataset.selectTurn!==undefined&&state.combat.started){if(isGameMaster()){state.combat.turnIndex=Number(btn.dataset.selectTurn);commit();}else toast('Очередью управляет мастер','Права стола');return;}
    if(btn.dataset.condition){showConditionModal(btn.dataset.condition);return;}
    if(btn.dataset.removeCondition){const c=state.characters.find(x=>x.id===btn.dataset.removeCondition);c?.conditions.splice(Number(btn.dataset.index),1);commit();return;}
    if(btn.dataset.rest){takeRest('long',btn.dataset.rest);return;}
    if(btn.dataset.addCondition){const c=state.characters.find(x=>x.id===btn.dataset.character);if(c&&!c.conditions.includes(btn.dataset.addCondition))c.conditions.push(btn.dataset.addCondition);closeModal();commit();return;}
    if(btn.dataset.duplicate){const c=state.characters.find(x=>x.id===btn.dataset.duplicate);if(c){const copy=structuredClone(c);copy.id=cryptoId();copy.name+=' · копия';copy.actions.forEach(a=>a.id=cryptoId());copy.resources.forEach(r=>r.id=cryptoId());state.characters.push(copy);commit();}return;}
    if(btn.dataset.toggleRole){const c=state.characters.find(x=>x.id===btn.dataset.toggleRole);if(c)c.role=c.role==='enemy'?'hero':'enemy';commit();return;}
    if(btn.dataset.deleteCharacter){const c=state.characters.find(x=>x.id===btn.dataset.deleteCharacter);if(c&&confirm(`Удалить «${c.name}»?`)){state.characters=state.characters.filter(x=>x.id!==c.id);commit();}return;}
    if(btn.dataset.sheetTab){showCharacterSheet(runtime.editCharacterId,btn.dataset.sheetTab);return;}
    if(btn.dataset.removeActionEditor){const c=state.characters.find(x=>x.id===runtime.editCharacterId);if(c)c.actions=c.actions.filter(a=>a.id!==btn.dataset.removeActionEditor);showCharacterSheet(c.id,'actions');return;}
    if(btn.dataset.playTrack){toggleTrack(btn.dataset.playTrack);return;}
    if(btn.dataset.uploadMedia){if(isGameMaster())uploadMedia(btn.dataset.uploadMedia);else toast('Медиатекой управляет мастер','Права стола');return;}
    if(btn.dataset.applyAsset){applyMediaAsset(btn.dataset.kind,btn.dataset.applyAsset);return;}
    if(btn.dataset.confirmAssetCharacter){const c=state.characters.find(x=>x.id===document.getElementById('assetCharacter')?.value);if(isGameMaster()&&c){c.tokenAsset=btn.dataset.confirmAssetCharacter;closeModal();commit();toast('Портрет и токен назначены',c.name);}return;}
    if(btn.dataset.removeAsset){if(isGameMaster()){state.media[btn.dataset.kind]=state.media[btn.dataset.kind].filter(a=>a.id!==btn.dataset.removeAsset);deleteAsset(btn.dataset.removeAsset);commit();}return;}
    if(btn.hasAttribute('data-close-modal')){closeModal();return;}

    const a=btn.dataset.action;
    if(!a)return;
    if(a==='import-text')showImportModal();
    else if(a==='paste-sample'){document.getElementById('importText').value=SAMPLE_TEXT;}
    else if(a==='parse-import'){const text=document.getElementById('importText').value;if(!text.trim())return toast('Вставьте текст персонажа','Импорт');showImportPreview(parseCharacterText(text,state.campaign.edition));}
    else if(a==='back-to-import')showImportModal();
    else if(a==='new-blank'){const c=createBlankCharacter();c.edition=state.campaign.edition;state.characters.push(c);commit();showCharacterSheet(c.id);}
    else if(a==='start-expedition')startExpedition();
    else if(a==='advance-expedition')advanceExpedition();
    else if(a==='reset-expedition'){if(isGameMaster()&&confirm('Сбросить прогресс текущего маршрута?')){state.expedition.active=false;state.expedition.nodeIndex=0;state.expedition.inventory=[];state.expedition.route.forEach((n,i)=>{n.status=i===0?'current':'locked';n.selectedNextId=null;n.rewardClaimed=false;});commit();}}
    else if(a==='camp-expedition'){if(isGameMaster())showCampModal();else toast('Лагерь распределяет мастер','Права стола');}
    else if(a==='finish-camp'){if(isGameMaster()){state.expedition.supplies.food=Math.max(0,state.expedition.supplies.food-4);state.expedition.light=clamp(state.expedition.light+20,0,100);addRoadLog('Лагерь свёрнут','Отряд восстановил силы и возвращается на маршрут.');closeModal();commit();}}
    else if(a==='edit-route'){if(isGameMaster())editRouteModal();}
    else if(a==='add-route-node'){if(isGameMaster()){state.expedition.route.push({id:cryptoId(),type:'battle',name:'Новая точка',status:'locked',branchTo:null,branchLabel:'Альтернативный путь',selectedNextId:null,rewardClaimed:false});editRouteModal();}}
    else if(a==='save-route'){if(isGameMaster()){document.querySelectorAll('[data-route-name]').forEach(input=>{const i=Number(input.dataset.routeName),n=state.expedition.route[i];if(n){n.name=input.value||`Точка ${i+1}`;n.type=document.querySelector(`[data-route-type="${i}"]`)?.value||'battle';n.branchTo=document.querySelector(`[data-route-branch="${i}"]`)?.value||null;n.branchLabel=document.querySelector(`[data-route-branch-label="${i}"]`)?.value||'Альтернативный путь';}});closeModal();commit();}}
    else if(a==='clear-expedition-log'){if(isGameMaster()){state.expedition.log=[];commit();}}
    else if(a==='hub-rest-all'){if(isGameMaster()){state.characters.filter(c=>c.role==='hero').forEach(c=>{c.hp=c.maxHp;c.stress=Math.max(0,c.stress-35);if(c.stress<100)c.resolve='steady';});applyHubAssignments();commit();toast('Назначения районов применены','Бастион');}}
    else if(a==='new-content'){if(isGameMaster())showContentEditor();else toast('Конструктор доступен мастеру','Права стола');}
    else if(a==='save-content'){try{const item=JSON.parse(document.getElementById('contentJson').value);if(!item||typeof item!=='object'||Array.isArray(item)||!String(item.name||'').trim())throw new Error('Нужно непустое поле name');item.id=String(item.id||cryptoId());const rows=state.compendium[runtime.workshopCategory];const index=rows.findIndex(x=>x.id===item.id);if(index>=0)rows[index]=item;else rows.push(item);closeModal();commit();toast('Объект прошёл проверку и сохранён','Конструктор');}catch(err){const box=document.getElementById('contentValidation');if(box){box.textContent=err.message;box.style.color='var(--red-bright)';}}}
    else if(a==='export-mod')exportMod();
    else if(a==='import-mod')importMod();
    else if(a==='start-combat')startCombat();
    else if(a==='next-turn')nextTurn();
    else if(a==='reset-combat'){state.combat.started=false;state.combat.turnIndex=0;state.characters.forEach(c=>c.initiativeRoll=null);commit();}
    else if(a==='short-rest')takeRest('short');
    else if(a==='long-rest')takeRest('long');
    else if(a==='clear-log'){state.rollLog=[];commit();}
    else if(a==='clear-roll-mode'){runtime.rollMode='normal';renderView();}
    else if(a==='save-sheet')saveSheet();
    else if(a==='add-action-editor'){const c=state.characters.find(x=>x.id===runtime.editCharacterId);c.actions.push({id:cryptoId(),name:'Новое действие',type:'attack',attackBonus:0,damage:'1d6',damageType:'',saveAbility:null,saveDC:null,currentUses:null,maxUses:null,validFrom:[],validTargets:[],targetSide:'enemy',recovery:'long',notes:''});showCharacterSheet(c.id,'actions');}
    else if(a==='upload-portrait')uploadPortrait(btn.dataset.character);
    else if(a==='add-custom-condition'){const value=document.getElementById('customCondition').value.trim();const c=state.characters.find(x=>x.id===btn.dataset.character);if(value&&c)c.conditions.push(value);closeModal();commit();}
    else if(a==='scene-bg')uploadSceneBackground();
    else if(a==='rename-scene'){const name=prompt('Название сцены',state.scene.name);if(name?.trim()){state.scene.name=name.trim();commit();}}
    else if(a==='stage-fullscreen'){const el=document.getElementById('darkestStage');if(!document.fullscreenElement)el?.requestFullscreen?.();else document.exitFullscreen?.();}
    else if(a==='stage-log'){runtime.view='combat';updateChrome();renderView();}
    else if(a==='scene-add-token'){ensureFormation(true);commit();}
    else if(a==='toggle-grid'){state.scene.grid=!state.scene.grid;commit();}
    else if(a==='reset-tokens'){ensureFormation(true);commit();}
    else if(a==='clear-scene'){state.scene.backgroundAsset=null;state.scene.formation=[];commit();}
    else if(a==='upload-images')uploadMedia('sprites');
    else if(a==='upload-audio')uploadMedia('music');
    else if(a==='stop-audio'){runtime.audio?.pause();runtime.playingTrack=null;renderView();}
    else if(a==='show-parser-format')showImportModal();
    else if(a==='copy-room-code'){navigator.clipboard?.writeText(document.getElementById('roomCodeInput').value);toast('Код скопирован','Общий стол');}
    else if(a==='connect-room'){runtime.localProfile.name=document.getElementById('roomPlayerName')?.value.trim()||'Игрок';runtime.localProfile.role=document.getElementById('roomPlayerRole')?.value||'player';runtime.localProfile.characterId=document.getElementById('roomCharacter')?.value||null;saveLocalProfile();connectRoom(document.getElementById('roomCodeInput').value);}
    else if(a==='disconnect-room'){disconnectRoom();closeModal();renderView();}
    else if(a==='export-campaign')exportCampaign();
    else if(a==='import-campaign')importCampaignFile();
    else if(a==='reset-demo'){if(confirm('Сбросить текущую кампанию и вернуть демонстрационные данные?')){state=demoState();closeModal();commit();}}
    else if(a==='save-settings'){state.campaign.title=document.getElementById('settingsTitle').value||'Безымянная кампания';state.campaign.edition=document.getElementById('settingsEdition').value;closeModal();commit();}
  }

  function handleChange(e){if(e.target.id==='targetSelect'){state.combat.targetId=e.target.value;commit(false);}else if(e.target.id==='coverSelect'){state.combat.cover=Number(e.target.value);commit(false);}else if(e.target.id==='gridSize'){state.scene.gridSize=clamp(e.target.value,24,120);commit();}else if(e.target.dataset.hubAssignment&&isGameMaster()){state.hub.assignments[e.target.dataset.hubAssignment]=e.target.value||null;commit();}else if(e.target.dataset.volume&&runtime.playingTrack===e.target.dataset.volume&&runtime.audio){runtime.audio.volume=Number(e.target.value);}}
  function handleSubmit(e){if(e.target.id==='customRollForm'){e.preventDefault();try{const v=document.getElementById('customRollInput').value;const r=rollExpression(v);addLog({actor:'Стол',name:'Свободный бросок',expression:`${v} → ${r.detail}`,total:r.total,summary:'пользовательская формула'});commit();}catch(err){toast(err.message,'Неверная формула');}}}

  function bindGlobal() {
    document.addEventListener('click',handleClick);
    document.addEventListener('change',handleChange);
    document.addEventListener('submit',handleSubmit);
    document.getElementById('campaignTitle').addEventListener('click',()=>{const v=prompt('Название кампании',state.campaign.title);if(v?.trim()){state.campaign.title=v.trim();commit();}});
    document.getElementById('roomBtn').addEventListener('click',showRoomModal);
    document.getElementById('settingsBtn').addEventListener('click',showSettings);
    document.getElementById('gmMenuBtn').addEventListener('click',showSettings);
    document.getElementById('saveExportBtn').addEventListener('click',exportCampaign);
    document.getElementById('quickDiceBtn').addEventListener('click',()=>{runtime.view='combat';updateChrome();renderView();setTimeout(()=>document.getElementById('customRollInput')?.focus(),20);});
    document.getElementById('campaignImportInput').addEventListener('change',async e=>{const file=e.target.files[0];if(!file)return;try{state=migrateState(JSON.parse(await file.text()));closeModal();commit();toast('Кампания загружена','Импорт');}catch{toast('Не удалось прочитать JSON','Ошибка');}e.target.value='';});
    document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();exportCampaign();}});
    window.grimdiceDesktop?.onCommand(command=>{
      if(command==='open')importCampaignFile();
      else if(command==='save-as')exportCampaign();
      else if(command==='new'&&confirm('Создать новую кампанию? Несохранённые изменения останутся только в локальной копии.')){const fresh=demoState();fresh.campaign.title='Новая кампания';fresh.characters=[];fresh.rollLog=[];fresh.scene.formation=[];state=fresh;commit();}
      else if(command.startsWith('view-')){runtime.view=command.slice(5);updateChrome();renderView();}
    });
  }

  bindGlobal(); updateChrome(); renderView();
  const roomFromUrl=new URLSearchParams(location.search).get('room');if(roomFromUrl)connectRoom(roomFromUrl);
})();
