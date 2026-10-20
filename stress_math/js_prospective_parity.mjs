import fs from 'node:fs';
import {ProspectiveReliability} from '../frontend/src/prospectiveReliability.js';
const cases=JSON.parse(fs.readFileSync(0,'utf8'));
console.log(JSON.stringify(cases.map(samples=>{
 const s=new ProspectiveReliability(['x'],r=>r.x);
 for(const sample of samples)s.add(sample.time,sample.row,sample.context);
 const r=s.finish();return {status:r.status,average:r.average,windowScores:r.windowScores,
  coverageDetails:r.coverageDetails,consensusWindowMask:r.consensusWindowMask,acceptancePolicy:r.acceptancePolicy};
})));
