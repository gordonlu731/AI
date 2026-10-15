import assert from 'node:assert/strict';
import RAPIER from '@dimforge/rapier3d-compat';
import { initPhysics, Machine, STAGES } from '../src/machine.js';
await initPhysics();
let failures=0;
const idle=new Machine();idle.started=true;
for(let i=0;i<120*15;i++)idle.step();
assert.ok(idle.stages.every(v=>!v));assert.equal(idle.bellHits,0);
console.log('PASS Unreleased ball: 15 seconds of physics cannot trigger the chain');idle.dispose();
const blocked=new Machine();
blocked.dominoes.at(-1).setBodyType(RAPIER.RigidBodyType.Fixed,true);blocked.release();
for(let i=0;i<120*22;i++)blocked.step();
assert.equal(blocked.stages[2],false);assert.equal(blocked.bellHits,0);
console.log('PASS Immobilizing the final domino physically blocks the downstream chain');blocked.dispose();
for(let run=1;run<=3;run++) {
  const machine=new Machine();
  machine.release();
  for(let i=0;i<120*90&&!machine.stages[8];i++) {
    machine.step();

  }
  const r=machine.report();
  console.log(`Run ${run}:`,JSON.stringify(r));
  r.stages.forEach((pass,i)=>console.log(`${pass?'PASS':'FAIL'} ${i+1}. ${STAGES[i][0]}`));
  if(!r.stages.every(Boolean)||r.bellHits<1||!r.stageTimes.every((t,i,a)=>i===0||t>a[i-1])) failures++;
  machine.dispose();
}
process.exitCode=failures?1:0;
