// Export ONLY unstepped initial state. Never release or run the solver here.
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {initPhysics} from '../../../src/machine.js';
import {ExperimentMachine,CASES,REFERENCE,PROTOCOL_ID,CONTACTS,HORIZON} from '../config/experiments.mjs';
const root=new URL('../',import.meta.url),sha=b=>createHash('sha256').update(b).digest('hex');
await mkdir(new URL('input/',root),{recursive:true});await mkdir(new URL('operator/',root),{recursive:true});
const sourcePaths=['src/machine.js','evaluation/round2/config/experiments.mjs','evaluation/round2/config/parameters.mjs'];
const sources=Object.fromEntries(await Promise.all(sourcePaths.map(async path=>[path,sha(await readFile(new URL('../../../'+path,import.meta.url)))])));
const original=JSON.parse(await readFile(new URL('../../input/PHYSICS.json',import.meta.url),'utf8'));
if(original.source_sha256!==sources['src/machine.js'])throw Error('Original physical source no longer matches the reference geometry specification.');
await initPhysics();
const vec=v=>[v.x,v.y,v.z],quat=q=>[q.x,q.y,q.z,q.w];
function shape(c){if(c.shapeType()===0)return {type:'sphere',radius:c.radius()};if(c.shapeType()===1)return {type:'box',full_size:vec(c.halfExtents()).map(n=>n*2)};return {type:'convex_hull',vertices_xyz:Array.from(c.vertices())};}
function inspect(m){
 if(m.time!==0||m.started||m.stages.some(Boolean))throw Error('Input must be an unstepped world');
 const bodies=new Map([[m.ball.handle,'ball'],...m.dominoes.map(b=>[b.handle,`domino_${String(m.dominoOrdinals.get(b.handle)).padStart(2,'0')}`]),...['gate','wheel','lever','bucket','hammer','bell'].map(k=>[m[k].handle,k]),...(m.obstacle?[[m.obstacle.handle,'barrier']]:[])]);
 const objects=[...bodies].map(([h,id])=>{const b=m.world.getRigidBody(h);return {id,initial_type:b.isFixed()?'fixed':'dynamic',position:vec(b.translation()),rotation_xyzw:quat(b.rotation()),linear_velocity:vec(b.linvel()),angular_velocity:vec(b.angvel()),mass:b.mass(),angular_damping:b.angularDamping(),ccd:b.isCcdEnabled(),colliders:Array.from({length:b.numColliders()},(_,i)=>{const c=b.collider(i);return {shape:shape(c),local_position:vec(c.translationWrtParent()),local_rotation_xyzw:quat(c.rotationWrtParent()),density:c.density(),friction:c.friction(),restitution:c.restitution(),friction_combine_rule:c.frictionCombineRule(),restitution_combine_rule:c.restitutionCombineRule(),sensor:c.isSensor()};})};});
 const joints=[];m.world.impulseJoints.forEach(j=>joints.push({type:'revolute',moving_object:bodies.get(j.body2().handle),fixed_anchor_position:vec(j.body1().translation()),fixed_anchor_rotation_xyzw:quat(j.body1().rotation()),local_axis:[0,0,1],local_anchor_1:vec(j.anchor1()),local_anchor_2:vec(j.anchor2()),limit_radians:j.limitsEnabled()?[j.limitsMin(),j.limitsMax()]:null,motor:false,contacts_between_attached_bodies:j.contactsEnabled()}));
 return {id:m.experimentId,initial_settings:m.experimentConfig,objects,joints};
}
const m=new ExperimentMachine('REF');
const common={coordinates:original.coordinates,engine:original.engine,start_action:original.start_action,track:{...original.track,centerline:m.path.map(vec)},other_fixed_colliders:original.other_fixed_colliders,observer:original.observer};
m.dispose();const configurations=[];
for(const c of [REFERENCE,...CASES]){const m=new ExperimentMachine(c.id);try{configurations.push(inspect(m));}finally{m.dispose();}}
const spec={protocol_id:PROTOCOL_ID,source_sha256:sources,export:'Unstepped initial states only. Values read from actual Rapier bodies/colliders, with no future states or experimental outcomes.',horizon_seconds:HORIZON,contact_keys:CONTACTS,reference_fact:'REF is the original nine-stage configuration, known to complete all nine stages within 30 simulated seconds.',...common,configurations};
await writeFile(new URL('input/PHYSICS.json',root),JSON.stringify(spec,null,2)+'\n');
const template={protocol_id:PROTOCOL_ID,cases:CASES.map(c=>({id:c.id,bell_by_30s:null,p_bell_by_30s:null,stages:Array(9).fill(null),contacts:Object.fromEntries(CONTACTS.map(k=>[k,null])),predicted_first_bell_seconds:null,first_interruption:'若有中断，指出首先无法传递运动的位置；否则填无。',reasoning:'根据实际几何和力学解释，并写明不确定性。'}))};
await writeFile(new URL('input/RESPONSE_TEMPLATE.json',root),JSON.stringify(template,null,2)+'\n');
const lock={protocol_id:PROTOCOL_ID,locked_at:new Date().toISOString(),source_sha256:sources,initial_configurations:[REFERENCE,...CASES],selection:'Y1 height=20% of original full barrier, retaining its bottom; Y2 width=25%, offset +0.65z; Y3 removes tile04 of08; Y4 density=10%. Fixed before collecting any round2 outcomes. No outcome-based tuning.'};
try{await writeFile(new URL('operator/design-lock.json',root),JSON.stringify(lock,null,2)+'\n',{flag:'wx'});}
catch(error){if(error.code!=='EEXIST')throw error;const previous=JSON.parse(await readFile(new URL('operator/design-lock.json',root),'utf8'));if(JSON.stringify(previous.source_sha256)!==JSON.stringify(lock.source_sha256)||JSON.stringify(previous.initial_configurations)!==JSON.stringify(lock.initial_configurations))throw Error('A different initial design is already locked. Create a new protocol/dataset directory rather than overwrite it.');}
console.log('Exported five unstepped configurations and locked the four initial variations; no solver steps executed.');
