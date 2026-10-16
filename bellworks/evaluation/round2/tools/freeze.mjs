import {freezePrediction} from './lib.mjs';
const [file,...rest]=process.argv.slice(2);
if(!file){console.error('Usage: node tools/freeze.mjs response.json [--model GPT-name] [--session fresh-chat-id] [--exposure none|unknown|seen] [--tools disabled]');process.exit(1);}
const options={};for(let i=0;i<rest.length;i+=2){if(!rest[i].startsWith('--')||rest[i+1]===undefined)throw Error('Options require --name value');options[rest[i].slice(2)]=rest[i+1];}
console.log('Prediction locked at:',await freezePrediction(file,options));
