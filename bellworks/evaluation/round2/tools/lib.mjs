import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {createHash,randomUUID} from 'node:crypto';
import {resolve,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {CASES,PROTOCOL_ID,CONTACTS} from './protocol.mjs';
export const ROOT=fileURLToPath(new URL('../',import.meta.url));
export const sha=data=>createHash('sha256').update(data).digest('hex');
export function parseResponse(raw){let text=raw.toString('utf8').replace(/^\uFEFF/,'').trim();if(/^```(?:json)?\s/i.test(text)&&text.endsWith('```'))text=text.replace(/^```(?:json)?\s*/i,'').slice(0,-3).trim();return JSON.parse(text);}
export function validatePrediction(p){
 if(p?.protocol_id!==PROTOCOL_ID)throw Error('Wrong protocol_id');
 if(!Array.isArray(p.cases)||p.cases.length!==CASES.length)throw Error('Exactly four cases are required');
 const ids=new Set();
 for(const c of p.cases){
  if(!CASES.some(x=>x.id===c.id)||ids.has(c.id))throw Error('Unknown or duplicate case id');ids.add(c.id);
  if(typeof c.bell_by_30s!=='boolean')throw Error(`${c.id}: bell_by_30s must be boolean`);
  if(typeof c.p_bell_by_30s!=='number'||!Number.isFinite(c.p_bell_by_30s)||c.p_bell_by_30s<0||c.p_bell_by_30s>1)throw Error(`${c.id}: probability must be a finite number from 0 to 1`);
  if(!Array.isArray(c.stages)||c.stages.length!==9||c.stages.some(v=>typeof v!=='boolean'))throw Error(`${c.id}: nine boolean stage flags required`);
  if(!c.contacts||Object.keys(c.contacts).length!==CONTACTS.length||CONTACTS.some(k=>typeof c.contacts[k]!=='boolean'))throw Error(`${c.id}: six named boolean contact flags required`);
  if(typeof c.first_interruption!=='string'||!c.first_interruption.trim())throw Error(`${c.id}: first_interruption is required`);
  if(typeof c.reasoning!=='string'||!c.reasoning.trim())throw Error(`${c.id}: reasoning is required`);
  if(c.predicted_first_bell_seconds!==undefined&&c.predicted_first_bell_seconds!==null&&(typeof c.predicted_first_bell_seconds!=='number'||!Number.isFinite(c.predicted_first_bell_seconds)||c.predicted_first_bell_seconds<0||c.predicted_first_bell_seconds>30))throw Error(`${c.id}: optional time must be null or 0..30 seconds`);
 }
 return p;
}
export async function verifyInputDataset(inputRoot=join(ROOT,'input')){
 const bytes=await readFile(join(inputRoot,'MANIFEST.json')),manifest=JSON.parse(bytes);
 if(manifest.protocol_id!==PROTOCOL_ID||!manifest.files||Object.keys(manifest.files).length!==11)throw Error('Invalid input manifest');
 for(const [name,hash] of Object.entries(manifest.files)){
  if(name==='..'||name==='MANIFEST.json'||name.includes('/')||name.includes('\\'))throw Error('Invalid manifest file name');
  if(sha(await readFile(join(inputRoot,name)))!==hash)throw Error(`Input file was modified: ${name}`);
 }
 return bytes;
}
export async function freezePrediction(source,options={}){
 const bytes=await readFile(source);validatePrediction(parseResponse(bytes));
 const manifest=await verifyInputDataset();
 const id=options.id||new Date().toISOString().replace(/[:.]/g,'-')+'-'+randomUUID().slice(0,8);
 if(!/^[a-zA-Z0-9_-]+$/.test(id))throw Error('Attempt id must use only letters, digits, underscores and hyphens');
 const parent=options.outputRoot||join(ROOT,'operator/attempts');await mkdir(parent,{recursive:true});
 const dir=join(parent,id);await mkdir(dir,{recursive:false});
 await writeFile(join(dir,'prediction.json'),bytes,{flag:'wx'});
 const receipt={protocol_id:PROTOCOL_ID,frozen_at:new Date().toISOString(),forecast_sha256:sha(bytes),input_manifest_sha256:sha(manifest),model:options.model||'unspecified',model_version:options.version||'unspecified',reasoning_effort:options.reasoning||'unspecified',session_id:options.session||'unspecified',prior_answer_exposure:options.exposure||'unknown',tools_used:options.tools||'not recorded',note:'Local integrity receipt, not an independent trusted timestamp; model provenance and exposure are operator declarations.'};
 await writeFile(join(dir,'receipt.json'),JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});return dir;
}
export function scorePrediction(prediction,truth){
 validatePrediction(prediction);
 if(truth.scoring_ready===false)throw Error("Dataset is unstable or baseline regressed; inspect all raw runs instead of assigning a deterministic score");
 if(truth.protocol_id!==PROTOCOL_ID||truth.cases?.length!==CASES.length)throw Error('Answer key protocol mismatch');
 let outcome=0,stage=0,contact=0,brier=0;const details=[];
 for(const def of CASES){
  const p=prediction.cases.find(c=>c.id===def.id),t=truth.cases.find(c=>c.id===def.id);
  if(!t||typeof t.bell_by_30s!=='boolean'||!Array.isArray(t.stages)||t.stages.length!==9||t.stages.some(v=>typeof v!=='boolean')||CONTACTS.some(k=>typeof t.contacts?.[k]!=='boolean'))throw Error('Malformed answer key');
  const bellCorrect=p.bell_by_30s===t.bell_by_30s;outcome+=Number(bellCorrect);
  const stageErrors=p.stages.map((v,i)=>v===t.stages[i]?null:i+1).filter(x=>x!==null);stage+=9-stageErrors.length;
  const contactErrors=CONTACTS.filter(k=>p.contacts[k]!==t.contacts[k]);contact+=CONTACTS.length-contactErrors.length;
  brier+=(p.p_bell_by_30s-Number(t.bell_by_30s))**2;
  const warnings=[];
  if(p.stages[8]!==p.bell_by_30s)warnings.push('Stage 9 contradicts predicted bell completion');
  if(p.bell_by_30s!==(p.p_bell_by_30s>=.5))warnings.push('Binary choice differs from a 0.5 probability threshold');
  details.push({id:def.id,bell_correct:bellCorrect,stage_mismatch_indices:stageErrors,contact_mismatches:contactErrors,predicted_bell:p.bell_by_30s,observed_bell:t.bell_by_30s,p_bell:p.p_bell_by_30s,predicted_first_bell_seconds:p.predicted_first_bell_seconds??null,observed_first_bell_seconds:t.first_bell_seconds,time_estimate_scored:false,first_interruption:p.first_interruption,reasoning:p.reasoning,consistency_warnings:warnings});
 }
 const points={bell:outcome/4*40,contacts:contact/24*36,stages:stage/36*24};
 return {protocol_id:PROTOCOL_ID,automatic_points:points,total_100:Object.values(points).reduce((a,b)=>a+b,0),bell_correct_out_of_4:outcome,contact_correct_out_of_24:contact,stage_correct_out_of_36:stage,brier_score:brier/4,brier_lower_is_better:true,reasoning_assessment:'NOT AUTOMATICALLY SCORED: use operator rubric; correct labels alone do not demonstrate causal reasoning.',details};
}
export async function scoreAttempt(directory,truthPath=join(ROOT,'operator/ground-truth.json')){
 const dir=resolve(directory),raw=await readFile(join(dir,'prediction.json')),receipt=JSON.parse(await readFile(join(dir,'receipt.json'),'utf8')),truth=JSON.parse(await readFile(truthPath,'utf8'));
 if(sha(raw)!==receipt.forecast_sha256)throw Error('Frozen prediction was modified');
 if(sha(await verifyInputDataset())!==receipt.input_manifest_sha256)throw Error('Input manifest has changed since freeze');
 if(truth.input_manifest_sha256!==receipt.input_manifest_sha256)throw Error('Answer key belongs to another input dataset');
 const report={...scorePrediction(parseResponse(raw),truth),scored_at:new Date().toISOString(),receipt};
 await writeFile(join(dir,'score.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});return report;
}
