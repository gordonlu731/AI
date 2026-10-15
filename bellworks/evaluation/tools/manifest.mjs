import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {PROTOCOL_ID} from './protocol.mjs';
const root=new URL('../input/',import.meta.url);
const names=['PROMPT.zh-CN.md','SCENE.zh-CN.md','PHYSICS.json','RESPONSE_TEMPLATE.json','01_REFERENCE_OVERVIEW.png','02_REFERENCE_OVERHEAD.png','03_BARRIER_INITIAL.png','04_DOMINO_REMOVED_INITIAL.png'];
const files={};for(const name of names)files[name]=createHash('sha256').update(await readFile(new URL(name,root))).digest('hex');
await writeFile(new URL('MANIFEST.json',root),JSON.stringify({protocol_id:PROTOCOL_ID,input_track:'images plus initial geometry and physical parameters',reference_fact:'REF is known to complete all nine stages within the same 30s observation window. No other configuration measurements are supplied.',files},null,2)+'\n');
console.log('Recorded eight input file hashes; no answer labels included.');
