import {scoreAttempt} from './lib.mjs';
const [directory]=process.argv.slice(2);if(!directory){console.error('Usage: node tools/score.mjs operator/attempts/<id>');process.exit(1);}
const r=await scoreAttempt(directory);console.log(JSON.stringify({score:r.total_100,bell_accuracy:`${r.bell_correct_out_of_4}/4`,brier:r.brier_score,note:r.reasoning_assessment},null,2));
