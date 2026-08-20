import assert from 'node:assert/strict';
import { startServer } from '../server.mjs';

const {server,port}=await startServer({port:0,host:'127.0.0.1'});
const base=`http://127.0.0.1:${port}`;
const request=async(path,{token,method='GET',body}={})=>{
  const response=await fetch(base+path,{method,headers:{...(body?{'content-type':'application/json'}:{}),...(token?{authorization:`Bearer ${token}`}:{})},body:body?JSON.stringify(body):undefined});
  const data=await response.json();return {response,data};
};
try{
  const hero1={id:'h1',name:'A',role:'hero',visibility:'public',hp:20,maxHp:20,stress:0,relationships:{h2:10},inventory:[{id:'potion',name:'Potion',quantity:2,effects:[]}]};
  const hero2={id:'h2',name:'B',role:'hero',visibility:'public',hp:20,maxHp:20,stress:0,relationships:{h1:10},inventory:[]};
  const room='SMOKE42';
  const gmJoin=await request(`/api/rooms/${room}/session`,{method:'POST',body:{clientId:'gm-1',name:'GM',role:'gm'}});
  assert.equal(gmJoin.response.status,200);assert.equal(gmJoin.data.role,'gm');assert.ok(gmJoin.data.ownerKey);
  const gmToken=gmJoin.data.token;
  const initial={
    campaign:{title:'Test'},characters:[hero1,hero2],combat:{started:false,turnIndex:0,targetId:'h2'},rollLog:[],
    scene:{formation:[],tokens:[]},
    expedition:{light:80,inventory:[{id:'loot',name:'Loot',quantity:1}],route:[{id:'n1',name:'Start',type:'start',status:'current',branchTo:'n3',branchLabel:'Secret',selectedNextId:null},{id:'n2',name:'Locked Battle',type:'battle',status:'locked',reward:{name:'hidden'}},{id:'n3',name:'Locked Curio',type:'curio',status:'locked'}]},
    hub:{assignments:{h1:'b1'},inventory:[{id:'vault',name:'Vault',quantity:1}]},compendium:{creatures:[{id:'secret'}],events:[],locations:[],buildings:[]},
    network:{},media:{sprites:[{id:'sprite-1',name:'Hero.png'}]}
  };
  const gmWrite=await request(`/api/rooms/${room}/state`,{method:'POST',token:gmToken,body:{clientId:'gm-1',baseRevision:0,state:initial}});
  assert.equal(gmWrite.response.status,200);assert.equal(gmWrite.data.revision,1);
  const playerJoin=await request(`/api/rooms/${room}/session`,{method:'POST',body:{clientId:'p-1',name:'Player',role:'player',characterId:'h1'}});
  assert.equal(playerJoin.response.status,200);assert.equal(playerJoin.data.characterId,'h1');assert.equal(playerJoin.data.revision,2);
  const playerToken=playerJoin.data.token;
  const playerState=playerJoin.data.state;
  assert.equal(playerState.compendium.creatures.length,0,'GM compendium categories must be filtered');
  assert.deepEqual(playerState.expedition.route[1],{id:'n2',status:'locked',type:'unknown',name:'Неизведанный путь'},'locked route details must be filtered');
  const submitted=structuredClone(playerState);
  const own=submitted.characters.find(c=>c.id==='h1');
  own.relationships.h2=100;
  own.inventory=[{...own.inventory[0],quantity:1},{id:'forged',name:'Forged',quantity:99,effects:[]}];
  submitted.hub.assignments.h1='forged-building';
  submitted.expedition.route[0].selectedNextId='n3';
  const playerWrite=await request(`/api/rooms/${room}/state`,{method:'POST',token:playerToken,body:{clientId:'p-1',baseRevision:2,state:submitted}});
  assert.equal(playerWrite.response.status,200);assert.equal(playerWrite.data.revision,3);
  const gmRead=await request(`/api/rooms/${room}/state`,{token:gmToken});
  assert.equal(gmRead.response.status,200);
  const authoritative=gmRead.data.state;
  const savedHero=authoritative.characters.find(c=>c.id==='h1');
  assert.equal(savedHero.relationships.h2,10,'players cannot rewrite relationship authority');
  assert.deepEqual(savedHero.inventory.map(i=>[i.id,i.quantity]),[['potion',1]],'players may consume but cannot fabricate inventory');
  assert.equal(authoritative.hub.assignments.h1,'b1','players cannot alter Bastion assignments');
  assert.equal(authoritative.expedition.route[0].selectedNextId,null,'players cannot alter route branches');
  const stale=await request(`/api/rooms/${room}/state`,{method:'POST',token:playerToken,body:{clientId:'p-1',baseRevision:2,state:submitted}});
  assert.equal(stale.response.status,409,'stale writes must conflict');assert.equal(stale.data.revision,3);
  const duplicate=await request(`/api/rooms/${room}/session`,{method:'POST',body:{clientId:'p-2',name:'Other',role:'player',characterId:'h1'}});
  assert.equal(duplicate.data.characterId,null,'hero claim must be exclusive');assert.ok(duplicate.data.warning);
  const removed=await request(`/api/rooms/${room}/session`,{method:'DELETE',token:playerToken});
  assert.equal(removed.response.status,200);
  console.log('network authority integration: PASS (expansion filtering + sanitization)');
} finally {
  await new Promise(resolve=>server.close(resolve));
}
