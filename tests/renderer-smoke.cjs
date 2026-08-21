const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const crypto=require('node:crypto').webcrypto;
class ClassList{constructor(){this.values=new Set()}add(...x){x.forEach(v=>this.values.add(v))}remove(...x){x.forEach(v=>this.values.delete(v))}toggle(v,on){if(on===undefined)on=!this.values.has(v);on?this.values.add(v):this.values.delete(v);return on}contains(v){return this.values.has(v)}}
class Element{constructor(id=''){this.id=id;this.dataset={};this.classList=new ClassList();this.style={setProperty(){}};this.listeners={};this.children=[];this.value='';this.textContent='';this.hidden=false;this._html=''}set innerHTML(v){this._html=String(v)}get innerHTML(){return this._html}addEventListener(t,f){this.listeners[t]=f}querySelector(){return null}querySelectorAll(){return[]}closest(){return this}matches(){return false}hasAttribute(){return false}append(x){this.children.push(x)}remove(){}click(){}}
const ids=['app','roleBadge','roleHint','navRound','characterNavLabel','navCharacters','syncStatus','saveExportBtn','updateBtn','settingsBtn','campaignTitle','autosaveLabel','quickDiceBtn','roomBtn','profileBtn','mainContent','toastHost','modalHost','campaignImportInput'];
const elements=Object.fromEntries(ids.map(id=>[id,new Element(id)]));
const views=['dashboard','battle','characters','journal','world','cities','scene','library','photo','workshop','rules'].map(view=>Object.assign(new Element(),{dataset:{view},classList:new ClassList()}));
const editions=['2014','2024'].map(edition=>Object.assign(new Element(),{dataset:{edition},classList:new ClassList()}));
const listeners={};
const document={querySelector:s=>s==='#syncStatus span'?(elements.syncStatus.span||(elements.syncStatus.span=new Element())):s.startsWith('#')?elements[s.slice(1)]||null:null,querySelectorAll:s=>s==='.nav-item'?views:s==='[data-edition]'?editions:[],addEventListener:(t,f)=>{listeners[t]=f},createElement:()=>new Element()};
const storage=new Map();
Object.assign(global,{document,window:{dragonSagaDesktop:null,addEventListener(){}},localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,String(v))},requestAnimationFrame:f=>f(),confirm:()=>true,EventSource:class{},Audio:class{},CustomEvent:class{},FileReader:class{},Blob:global.Blob,URL:global.URL});
vm.runInThisContext(fs.readFileSync(require.resolve('../public/engine.js'),'utf8'),{filename:'engine.js'});window.DragonEngine=global.DragonEngine;
vm.runInThisContext(fs.readFileSync(require.resolve('../public/photo-editor.js'),'utf8'),{filename:'photo-editor.js'});
vm.runInThisContext(fs.readFileSync(require.resolve('../public/app.js'),'utf8'),{filename:'app.js'});
assert.equal(typeof listeners.click,'function');
assert.match(elements.mainContent.innerHTML,/Группа пока пуста/,'new campaign must be empty');
const clickView=view=>listeners.click({target:Object.assign(new Element(),{dataset:{view}})});
const expected={dashboard:'Обзор кампании',battle:'ТАКТИЧЕСКАЯ ЛИНИЯ',characters:'Персонажи и противники',journal:'Журнал',world:'Карта и маршруты',cities:'Поселения и торговцы',scene:'Сцены',library:'Медиатека',photo:'Редактор изображений',workshop:'Конструктор кампании',rules:'Правила мастера'};
for(const [view,needle]of Object.entries(expected)){clickView(view);assert.ok(elements.mainContent.innerHTML.includes(needle),`${view} should contain ${needle}`)}
const source=fs.readFileSync(require.resolve('../public/app.js'),'utf8');
for(const obsolete of ['start-expedition','advance-expedition','Бастион Углей','seededHeroes'])assert.ok(!source.includes(obsolete),`obsolete renderer token remains: ${obsolete}`);
assert.match(source,/['"]save-as['"]\s*:\s*exportCampaign/,'native Save As command must export the campaign');
assert.match(source,/GLTFLoader\.js/,'scene constructor must load GLB/GLTF models');
for(const file of ['../public/vendor/three.module.min.js','../public/vendor/loaders/GLTFLoader.js','../public/vendor/THREE-LICENSE.txt'])assert.ok(fs.existsSync(require.resolve(file)),`vendored 3D runtime is missing: ${file}`);
const sourceText='  Арвед\r\nКД: 16\r\nХиты: 22/22\r\nСИЛ 14 ЛОВ 12 ТЕЛ 15 ИНТ 10 МДР 13 ХАР 8\r\nУдар мечом. Атака +5, урон 1d8+3 рубящий.\r\nРывок (2/2, короткий отдых). Особое действие.\r\n';
const parsed=DragonEngine.parseCharacterText(sourceText,'2024');
assert.equal(parsed.character.name,'Арвед');assert.equal(parsed.character.ac,16);assert.equal(parsed.character.maxHp,22);assert.equal(parsed.character.sourceText,sourceText,'source text must be preserved byte-for-byte as a JS string');assert.ok(parsed.character.actions.some(a=>a.damage==='1d8+3'));assert.ok(parsed.character.actions.some(a=>a.currentUses===2&&a.maxUses===2));
console.log('renderer and deterministic importer smoke: PASS');
