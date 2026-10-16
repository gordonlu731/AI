// Extra diagnostic replays, read-only inspection of actual final contacts.
import {readFile,writeFile} from 'node:fs/promises';
import {initPhysics} from '../../../src/machine.js';
import {ExperimentMachine,REFERENCE,CASES,HORIZON,PROTOCOL_ID} from '../config/experiments.mjs';
await initPhysics();const runs=[];
for(const c of [REFERENCE,...CASES]){
 const m=new ExperimentMachine(c.id);try{
  m.release();for(let i=0;i<HORIZON*120;i++)m.step();
  const contacts=[];
  for(const piece of m.pieces){
   if(!piece.collider||piece.body===m.ball)continue;
   m.world.contactPair(m.ballCollider,piece.collider,(manifold,flipped)=>{
    const touching=Array.from({length:manifold.numContacts()},(_,i)=>({distance:manifold.contactDist(i)})).filter(x=>x.distance<=.002);
    if(touching.length){const ordinal=m.dominoOrdinals.get(piece.body.handle);contacts.push({object:ordinal?`domino_${String(ordinal).padStart(2,'0')}`:piece.body===m.obstacle?'barrier':Object.keys(m).find(k=>m[k]===piece.body)||'fixed_track',body_position:{...piece.body.translation()},shape:piece.shape,size:piece.size,material:piece.mat,contacts:touching});}
   });
  }
  runs.push({case:c.id,report:m.report(),final_touching_colliders:contacts,domino_final_states:m.dominoes.map(b=>({ordinal:m.dominoOrdinals.get(b.handle),position:{...b.translation()},rotation:{...b.rotation()},velocity:{...b.linvel()}}))});
 }finally{m.dispose();}
}
await writeFile(new URL('../operator/diagnostic-replays.json',import.meta.url),JSON.stringify({protocol_id:PROTOCOL_ID,generated_at:new Date().toISOString(),note:'One additional fresh 30s diagnostic replay per configuration. Distances are actual Rapier contact manifold distances; no outcome labels assigned.',runs},null,2)+'\n',{flag:'wx'});
console.log('Recorded five diagnostic replays with final ball contacts and domino poses.');
