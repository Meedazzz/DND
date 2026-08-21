(() => {
  'use strict';
  const ABILITIES = ['str','dex','con','int','wis','cha'];
  const ABILITY_RU = {str:'СИЛ',dex:'ЛОВ',con:'ТЕЛ',int:'ИНТ',wis:'МДР',cha:'ХАР'};
  const id = () => globalThis.crypto?.randomUUID?.() || `id-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  const clamp = (n,min,max) => Math.min(max,Math.max(min,Number(n)||0));
  const abilityMod = score => Math.floor(((Number(score)||10)-10)/2);
  const signed = n => (Number(n)||0)>=0?`+${Number(n)||0}`:`${Number(n)||0}`;

  function blankCharacter(role='hero') {
    return {
      id:id(),name:'Безымянный',role,visibility:'party',ownerId:null,className:'',race:'',level:1,edition:'2024',
      ac:10,hp:1,maxHp:1,tempHp:0,speed:30,initiative:0,proficiency:2,initiativeRoll:null,
      stats:{str:10,dex:10,con:10,int:10,wis:10,cha:10},saves:{},skills:{},spellDC:null,spellAttack:null,passivePerception:null,
      resistances:[],vulnerabilities:[],immunities:[],conditions:[],deathSaves:{success:0,fail:0},
      actions:[],resources:[],inventory:[],equipment:{armor:null,mainHand:null,offHand:null,accessory:null},currency:{gp:0,sp:0,cp:0},
      hitDice:{die:8,current:1,max:1},tokenAsset:null,portraitAsset:null,modelScale:100,sourceText:'',audit:[],notes:'',gmNotes:'',
      boss:false,reactionAvailable:true,bonusActionUsed:false,actionUsed:false
    };
  }

  function recoveryFromText(text='') {
    if(/корот|short/i.test(text))return 'short';
    if(/рассвет|dawn/i.test(text))return 'dawn';
    if(/раунд|round/i.test(text))return 'round';
    return 'long';
  }
  function abilityFromText(text='') {
    const map=[['str',/\b(?:СИЛ|STR)\b|сил[аыу]?/i],['dex',/\b(?:ЛОВ|DEX)\b|ловкост/i],['con',/\b(?:ТЕЛ|CON)\b|телослож/i],['int',/\b(?:ИНТ|INT)\b|интеллект/i],['wis',/\b(?:МДР|WIS)\b|мудрост/i],['cha',/\b(?:ХАР|CHA)\b|харизм/i]];
    return map.find(([,rx])=>rx.test(text))?.[0]||null;
  }
  function parseActionLine(line,character) {
    const clean=String(line||'').replace(/^[-•*]\s*/,'').trim();if(!clean)return null;
    const split=clean.match(/^(.+?)(?:\.|:|—)\s+(.+)$/);let name=split?split[1].trim():clean.split(/\s{2,}/)[0];const body=split?split[2].trim():clean;
    name=name.slice(0,100);
    let attackBonus=null;
    const atk=body.match(/(?:атака(?:\s+заклинанием)?|бросок\s+атаки|attack(?:\s+roll)?)[^\d+−-]*([+−-]\s*\d+)/i)||body.match(/([+−-]\s*\d+)\s*(?:к\s+попаданию|to\s+hit)/i);
    if(atk)attackBonus=Number(atk[1].replace(/\s/g,'').replace('−','-'));
    if(attackBonus===null&&/атака заклинанием/i.test(body)&&character.spellAttack!==null)attackBonus=character.spellAttack;
    const dice=[...body.matchAll(/\b(\d+\s*[dк]\s*\d+(?:\s*[+−-]\s*\d+)?)\b/ig)];
    const damage=dice[0]?dice[0][1].replace(/\s/g,'').replace(/к/i,'d').replace('−','-'):'';
    const healing=/лечение|восстанавлив|healing|regains?/i.test(body);
    const savePart=body.match(/(?:спасбросок|saving\s+throw|save)\s*([^,;.]+)/i);
    const saveAbility=savePart?abilityFromText(savePart[1]):null;
    const dc=body.match(/(?:Сл|DC)\s*(\d+)/i);const saveDC=dc?Number(dc[1]):(saveAbility?character.spellDC:null);
    const typeWords=['рубящ','колющ','дробящ','огонь','холод','кислот','электр','гром','яд','психичес','силов','излучен','некрот','slashing','piercing','bludgeoning','fire','cold','acid','lightning','thunder','poison','psychic','force','radiant','necrotic'];
    const damageType=typeWords.find(w=>new RegExp(w,'i').test(body))||'';
    const uses=clean.match(/\((\d+)\s*\/\s*(\d+)(?:,\s*([^)]+))?\)/);const currentUses=uses?Number(uses[1]):null;const maxUses=uses?Number(uses[2]):null;
    const recharge=body.match(/(?:перезарядка|recharge)\s*(\d)\s*[–—-]\s*(\d)/i);
    const range=body.match(/(?:дистанция|range)\s*[:—-]?\s*([^,;.]+)/i)?.[1]?.trim()||'';
    const explicitKind=body.match(/(?:тип|kind)\s*[:—-]?\s*(ближн|дальн|melee|ranged)/i)?.[1]||'';
    let kind=/дальн|ranged/i.test(explicitKind)||/дальнобойн|ranged weapon|дистанция\s+(?:[2-9]\d|\d{3,})/i.test(body)?'ranged':'melee';
    let type='utility';if(healing)type='heal';else if(saveAbility)type='save';else if(attackBonus!==null)type=/заклин|spell/i.test(clean)?'spell':'attack';else if(damage)type='damage';
    if(type==='spell'&&/дальн|луч|снаряд|bolt|ray|ranged/i.test(clean))kind='ranged';
    const cost=/бонусн|bonus action/i.test(body)?'bonus':/реакц|reaction/i.test(body)?'reaction':'action';
    return {id:id(),name,type,kind,cost,attackBonus,damage,damageType,saveAbility,saveDC,halfOnSave:/половин|half/i.test(body),concentration:/концентрац|concentration/i.test(body),range,currentUses,maxUses,recovery:recoveryFromText(uses?.[3]||body),recharge:recharge?`${recharge[1]}-${recharge[2]}`:null,targetSide:healing?'ally':type==='utility'?'self':'enemy',notes:body,sourceLine:line};
  }

  function parseCharacterText(sourceText,edition='2024') {
    const original=String(sourceText??'');const text=original.replace(/\r/g,'').trim();const c=blankCharacter();c.edition=edition;c.sourceText=original;
    const lines=text.split('\n').map(s=>s.trim()).filter(Boolean);const found=new Set();const warnings=[];
    const capture=rx=>text.match(rx)?.[1]?.trim()??null;const field=(k,v)=>{if(v!==null&&v!==undefined&&v!=='')found.add(k)};
    const explicitName=capture(/^(?:имя|name)\s*[:—-]\s*(.+)$/im);const first=lines[0]||'';
    if(explicitName)c.name=explicitName;else if(first&&!/(?:кд|ac|хиты|hp|класс|class|уров|level|сил|str)\s*[:\d]/i.test(first))c.name=first.replace(/^#+\s*/,'');field('Имя',c.name!=='Безымянный'?c.name:null);
    const classLine=capture(/^(?:класс|class)\s*[:—-]\s*(.+)$/im);const level=capture(/^(?:уровень|level)\s*[:—-]?\s*(\d+)/im);
    if(classLine){const lm=classLine.match(/(.+?)(?:\s+(\d+)(?:-?го)?\s*(?:уровня|level)?\s*)$/i);if(lm){c.className=lm[1].trim();c.level=Number(lm[2])}else c.className=classLine;field('Класс',c.className)}if(level)c.level=Number(level);field('Уровень',level||(classLine&&/\d/.test(classLine))?c.level:null);
    const race=capture(/^(?:раса|race|вид|species)\s*[:—-]\s*(.+)$/im);if(race)c.race=race;field('Раса',race);
    const ac=capture(/^(?:кд|ac|armor\s+class)\s*[:—-]?\s*(\d+)/im);if(ac)c.ac=Number(ac);field('КД',ac);
    const hp=text.match(/^(?:хиты|оз|hp|hit\s+points)\s*[:—-]?\s*(\d+)(?:\s*(?:\/|из)\s*(\d+))?/im);if(hp){c.hp=Number(hp[1]);c.maxHp=Number(hp[2]||hp[1])}field('Хиты',hp?.[1]);
    const speed=capture(/^(?:скорость|speed)\s*[:—-]?\s*(\d+)/im);if(speed)c.speed=Number(speed);field('Скорость',speed);
    const prof=capture(/^(?:бонус\s+мастерства|proficiency(?:\s+bonus)?)\s*[:—-]?\s*\+?(\d+)/im);c.proficiency=prof?Number(prof):Math.ceil(c.level/4)+1;field('Бонус мастерства',prof);
    const initiative=capture(/^(?:инициатива|initiative)\s*[:—-]?\s*\+?(-?\d+)/im);if(initiative!==null)c.initiative=Number(initiative);field('Инициатива',initiative);
    const abilityPatterns={str:/(?:\bСИЛ\b|\bSTR\b|сила)\s*[:—-]?\s*(\d+)/ig,dex:/(?:\bЛОВ\b|\bDEX\b|ловкость)\s*[:—-]?\s*(\d+)/ig,con:/(?:\bТЕЛ\b|\bCON\b|телосложение)\s*[:—-]?\s*(\d+)/ig,int:/(?:\bИНТ\b|\bINT\b|интеллект)\s*[:—-]?\s*(\d+)/ig,wis:/(?:\bМДР\b|\bWIS\b|мудрость)\s*[:—-]?\s*(\d+)/ig,cha:/(?:\bХАР\b|\bCHA\b|харизма)\s*[:—-]?\s*(\d+)/ig};
    for(const [key,rx] of Object.entries(abilityPatterns)){const m=[...text.matchAll(rx)].find(x=>Number(x[1])<=30);if(m){c.stats[key]=Number(m[1]);found.add(ABILITY_RU[key])}}if(initiative===null)c.initiative=abilityMod(c.stats.dex);
    const spellDC=capture(/(?:сл\s*(?:заклинаний|спасброска)?|spell\s+save\s+dc)\s*[:—-]?\s*(\d+)/im);if(spellDC)c.spellDC=Number(spellDC);field('Сл заклинаний',spellDC);
    const spellAttack=capture(/(?:атака\s+заклинани(?:ем|й)|spell\s+attack(?:\s+bonus)?)\s*[:—-]?\s*\+?(-?\d+)/im);if(spellAttack)c.spellAttack=Number(spellAttack);field('Атака заклинанием',spellAttack);
    const passive=capture(/(?:пассивн(?:ая|ое)\s+(?:внимательность|восприятие)|passive\s+perception)\s*[:—-]?\s*(\d+)/im);if(passive)c.passivePerception=Number(passive);field('Пассивное восприятие',passive);
    const saves=capture(/^(?:спасброски|saving\s+throws|saves)\s*[:—-]\s*(.+)$/im);if(saves){for(const key of ABILITIES){const aliases={str:'СИЛ|STR',dex:'ЛОВ|DEX',con:'ТЕЛ|CON',int:'ИНТ|INT',wis:'МДР|WIS',cha:'ХАР|CHA'}[key];const m=saves.match(new RegExp(`(?:${aliases})\\s*([+-]\\d+)`,'i'));if(m)c.saves[key]=Number(m[1])}found.add('Спасброски')}
    const parseList=(rx,key)=>{const raw=capture(rx);if(!raw)return[];found.add(key);return raw.split(/[,;]/).map(x=>x.trim().toLowerCase()).filter(Boolean)};
    c.resistances=parseList(/^(?:сопротивления|resistances?|damage\s+resistances?)\s*[:—-]\s*(.+)$/im,'Сопротивления');c.vulnerabilities=parseList(/^(?:уязвимости|vulnerabilities?|damage\s+vulnerabilities?)\s*[:—-]\s*(.+)$/im,'Уязвимости');c.immunities=parseList(/^(?:иммунитеты|immunities?|damage\s+immunities?)\s*[:—-]\s*(.+)$/im,'Иммунитеты');
    const resources=capture(/^(?:ресурсы|resources?|использования)\s*[:—-]\s*(.+)$/im);if(resources){for(const part of resources.split(/;|,(?=\s*[^,]+\d+\s*\/\s*\d+)/)){const m=part.trim().match(/^(.+?)\s+(\d+)\s*\/\s*(\d+)(?:\s*\(([^)]+)\))?/i);if(m)c.resources.push({id:id(),name:m[1].trim(),current:Number(m[2]),max:Number(m[3]),recovery:recoveryFromText(m[4]||'')})}if(c.resources.length)found.add('Ресурсы')}
    const hitDice=text.match(/(?:кости?\s+хитов|hit\s+dice)\s*[:—-]?\s*(\d+)\s*[dк]\s*(\d+)/i);if(hitDice){c.hitDice={current:Number(hitDice[1]),max:Number(hitDice[1]),die:Number(hitDice[2])};found.add('Кости хитов')}
    const actionLines=lines.filter(line=>{if(/^(?:имя|name|класс|class|раса|race|вид|species|кд|ac|armor class|хиты|hp|hit points|скорость|speed|бонус мастерства|proficiency|уровень|level|сопротивления|resistances|уязвимости|vulnerabilities|иммунитеты|immunities|ресурсы|resources|спасброски|saving throws|сила|ловкость|телосложение|интеллект|мудрость|харизма)\s*[:—-]/i.test(line))return false;if(/^(?:действия|actions|заклинания|spells|бонусные действия|реакции)\s*:??$/i.test(line))return false;return /\d+d\d+|\d+к\d+|\(\s*\d+\s*\/\s*\d+|к попаданию|to hit|спасбросок|saving throw|лечение|healing/i.test(line)});
    for(const line of actionLines){const action=parseActionLine(line,c);if(action)c.actions.push(action)}if(c.actions.length)found.add('Действия');
    if(!ac)warnings.push('КД не найдена — оставлено 10.');if(!hp)warnings.push('Хиты не найдены — оставлено 1/1.');if(!ABILITIES.some(k=>found.has(ABILITY_RU[k])))warnings.push('Характеристики не найдены — оставлены значения 10.');if(!c.actions.length)warnings.push('Боевые действия не распознаны. Исходник сохранён дословно.');if(!explicitName&&c.name!=='Безымянный')warnings.push('Имя взято из первой строки — проверьте.');
    c.audit=[...[...found].map(label=>({label,status:'ok',note:'найдено в исходнике'})),...warnings.map(note=>({label:'Проверка',status:'warn',note}))];return {character:c,warnings,found:[...found]};
  }

  function randomDie(sides){sides=Number(sides);const range=0x100000000,limit=range-(range%sides),a=new Uint32Array(1);let n;do{globalThis.crypto.getRandomValues(a);n=a[0]}while(n>=limit);return n%sides+1}
  function rollExpression(expression,{crit=false}={}){const expr=String(expression||'').toLowerCase().replace(/к/g,'d').replace(/−/g,'-').replace(/\s+/g,'');if(!expr||!/^[+\-]?\d+(?:d\d+)?(?:[+\-]\d+(?:d\d+)?)*$/.test(expr))throw new Error('Формат: 2d6+3');const terms=expr.match(/[+\-]?\d+(?:d\d+)?/g)||[];let total=0;const details=[];for(const term of terms){const sign=term.startsWith('-')?-1:1,core=term.replace(/^[+\-]/,'');if(core.includes('d')){let[count,sides]=core.split('d').map(Number);if(count>100||sides>1000||count<1||sides<2)throw new Error('Слишком большая кость');if(crit)count*=2;const rolls=Array.from({length:count},()=>randomDie(sides));total+=sign*rolls.reduce((a,b)=>a+b,0);details.push(`${sign<0?'−':''}[${rolls.join(', ')}]`)}else{total+=sign*Number(core);details.push(`${sign<0?'−':'+'}${core}`)}}return{total,detail:details.join(' '),expression:expr}}
  function d20(mod=0,mode='normal'){const rolls=mode==='normal'?[randomDie(20)]:[randomDie(20),randomDie(20)];const natural=mode==='adv'?Math.max(...rolls):mode==='dis'?Math.min(...rolls):rolls[0];return{natural,total:natural+Number(mod||0),rolls,detail:`d20 [${rolls.join(', ')}] ${signed(mod)}${mode==='adv'?' · преимущество':mode==='dis'?' · помеха':''}`}}
  function actionDetail(a){const p=[];if(a.attackBonus!==null&&a.attackBonus!==undefined)p.push(`попадание ${signed(a.attackBonus)}`);if(a.saveAbility)p.push(`${ABILITY_RU[a.saveAbility]} Сл ${a.saveDC||'?'}`);if(a.damage)p.push(`${a.type==='heal'?'лечение':'урон'} ${a.damage}${a.damageType?' '+a.damageType:''}`);if(a.maxUses!==null&&a.maxUses!==undefined)p.push(`${a.currentUses}/${a.maxUses}`);return p.join(' · ')||a.notes||'особое действие'}
  globalThis.DragonEngine={ABILITIES,ABILITY_RU,id,clamp,abilityMod,signed,blankCharacter,parseCharacterText,parseActionLine,randomDie,rollExpression,d20,actionDetail};
})();
