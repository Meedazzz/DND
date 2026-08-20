const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');

class ClassList{add(){} remove(){} toggle(){} contains(){return false;}}
class Element{
  constructor(id=''){this.id=id;this.dataset={};this.classList=new ClassList();this.style={};this.listeners={};this.children=[];this.value='';this.textContent='';this._html='';}
  set innerHTML(value){this._html=String(value);}
  get innerHTML(){return this._html;}
  addEventListener(type,fn){this.listeners[type]=fn;}
  querySelector(selector){if(selector==='span')return this.span||(this.span=new Element());return null;}
  querySelectorAll(){return [];}
  closest(){return this;}
  hasAttribute(){return false;}
  appendChild(child){this.children.push(child);return child;}
  remove(){}
  click(){}
}
const ids=['campaignTitle','navRound','navCharacters','syncStatus','roomBtn','mainContent','toastHost','modalHost','campaignImportInput','autosaveLabel','settingsBtn','gmMenuBtn','saveExportBtn','quickDiceBtn'];
const elements=Object.fromEntries(ids.map(id=>[id,new Element(id)]));
const navViews=['combat','expedition','hub','characters','scene','library','workshop','rules'].map(view=>{const el=new Element();el.dataset.view=view;return el;});
const documentListeners={};
const document={
  getElementById:id=>elements[id]||(elements[id]=new Element(id)),
  querySelectorAll:selector=>selector==='[data-view]'?navViews:[],
  querySelector:()=>null,
  addEventListener:(type,fn)=>{documentListeners[type]=fn;},
  createElement:()=>new Element(),
  fullscreenElement:null,
  exitFullscreen(){}
};
const storage=new Map();
global.document=document;
global.window={grimdiceDesktop:null};
global.localStorage={getItem:k=>storage.has(k)?storage.get(k):null,setItem:(k,v)=>storage.set(k,String(v)),removeItem:k=>storage.delete(k)};
global.location={search:'',href:'http://localhost/'};
global.history={replaceState(){}};
global.navigator={clipboard:{writeText(){}}};
global.confirm=()=>true;
global.prompt=()=>null;
global.EventSource=class{};
global.Audio=class{};
global.indexedDB={open(){throw new Error('IndexedDB should not be opened in empty demo smoke test');}};
if(!global.crypto)global.crypto=require('node:crypto').webcrypto;
vm.runInThisContext(fs.readFileSync(require.resolve('../public/app.js'),'utf8'),{filename:'app.js'});
assert.equal(typeof documentListeners.click,'function');
const clickButton=dataset=>documentListeners.click({target:Object.assign(new Element(),{dataset})});
const clickView=view=>clickButton({view});
const expected={
  combat:'Боевой стол готов', expedition:'Дорога под багровой звездой', hub:'Бастион Углей', characters:'Персонажи и существа',
  scene:'Собор Пепла', library:'Визуальные эффекты', workshop:'Конструктор контента и модов', rules:'Что считает движок'
};
for(const [view,needle] of Object.entries(expected)){
  clickView(view);
  assert.ok(elements.mainContent.innerHTML.includes(needle),`${view} should contain ${needle}`);
}
clickView('expedition');
clickButton({action:'start-expedition'});
clickButton({action:'advance-expedition'});
assert.ok(elements.mainContent.innerHTML.includes('branch-choice'),'expedition should render branch choices at the seeded fork');
const routeChoices=[...elements.mainContent.innerHTML.matchAll(/data-route-choice="([^"]+)"/g)].map(match=>match[1]);
assert.equal(routeChoices.length,2,'seeded fork should offer two destinations');
clickButton({routeChoice:routeChoices[1]});
clickButton({action:'advance-expedition'});
assert.match(elements.mainContent.innerHTML,/route-node [^"]*skipped/,'branch jump should mark bypassed node as skipped');
assert.ok(elements.mainContent.innerHTML.includes('Забытая часовня'),'branch jump should reach authored destination');
clickButton({action:'advance-expedition'});
assert.ok(elements.mainContent.innerHTML.includes('data-assign-loot'),'leaving a reward node should generate assignable loot');
clickView('hub');
assert.ok(elements.mainContent.innerHTML.includes('relationship-track'),'hub should render relationship tracks');
assert.ok(elements.mainContent.innerHTML.includes('data-hub-assignment'),'hub should render assignments');
const assignment=elements.mainContent.innerHTML.match(/data-hub-assignment="([^"]+)"[^>]*>[\s\S]*?<option value="([^"]+)"/);
assert.ok(assignment,'hub should expose hero and building assignment IDs');
documentListeners.change({target:{id:'',dataset:{hubAssignment:assignment[1]},value:assignment[2]}});
assert.ok(elements.mainContent.innerHTML.includes(`data-hub-assignment="${assignment[1]}"`),'assignment change should rerender hub');
clickView('library');
for(const label of ['Спрайты и токены','Портреты','Боевые фоны','Карты маршрутов','Визуальные эффекты','Звуки','Музыка','Шрифты','Определения анимаций','Темы','Локализация'])assert.ok(elements.mainContent.innerHTML.includes(label),`library should contain ${label}`);
console.log('headless renderer smoke: PASS (8 views + expansion UI)');
