import {readFile,writeFile,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {PROTOCOL_ID} from './protocol.mjs';
const dir=new URL('../input/',import.meta.url),files={};
for(const name of (await readdir(dir)).filter(n=>n!=='MANIFEST.json').sort())files[name]=createHash('sha256').update(await readFile(new URL(name,dir))).digest('hex');
if(Object.keys(files).length!==11)throw Error('Expected seven initial images and four text/JSON files');
await writeFile(new URL('MANIFEST.json',dir),JSON.stringify({protocol_id:PROTOCOL_ID,reference_fact:'REF completes all nine stages within 30 simulated seconds.',files},null,2)+'\n');
console.log('Hashed 11 initial input files.');
