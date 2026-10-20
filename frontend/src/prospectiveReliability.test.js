import test from 'node:test';
import assert from 'node:assert/strict';
import {ProspectiveReliability} from './prospectiveReliability.js';
import {ScanReliability} from './scanReliability.js';
function run(sequence=Array(9).fill(5),valid=i=>true,Class=ProspectiveReliability){
  const scan=new Class(['x'],r=>r.x);
  for(let i=100;i<1000;i++)scan.add(i/100,valid(i)?{x:sequence[Math.floor(i/100)-1]}:null);
  return scan.finish();
}
test('candidate accepts stable sampling, default legacy remains intact',()=>{
  assert.equal(run().average,5);assert.equal(run().status,'ok');
  assert.equal(run(undefined,i=>i%20===0,ScanReliability).average,5);
  const sparse=run(undefined,i=>i%20===0);
  assert.equal(sparse.average,null);assert.equal(sparse.status,'failed');
  assert.ok(sparse.acceptancePolicy.failureCodes.includes('insufficient_valid_observations'));
});
test('candidate rejects terminal shifts but retains isolated interior outlier tolerance',()=>{
  for(const seq of [[9,9,9,9,9,9,9,6,4],[4,6,9,9,9,9,9,9,9]])assert.equal(run(seq).average,null);
  const isolated=run([5,5,5,9,5,5,5,5,5]);
  assert.equal(isolated.average,5);assert.equal(isolated.status,'limited');
});
test('80 percent per-slot validity is inclusive; below boundary is rejected',()=>{
  assert.equal(run(undefined,i=>i%5!==0).average,5);
  assert.equal(run(undefined,i=>i%20<15).average,null);
});
test('missing samples and duplicate timestamps cannot manufacture candidate coverage',()=>{
  const scan=new ProspectiveReliability(['x'],r=>r.x);
  for(let i=0;i<100;i++)scan.add(2,{x:5});
  scan.add(1.9,{x:5});const r=scan.finish();
  assert.equal(r.average,null);assert.equal(r.coverageDetails.observedFrames,1);
});

test('candidate policy fingerprint matches the frozen file',async()=>{
  const fs=await import('node:fs');const crypto=await import('node:crypto');
  const expected=fs.readFileSync(new URL('../../training/prospective-policy.sha256',import.meta.url),'utf8').split(' ')[0];
  const actual=crypto.createHash('sha256').update(fs.readFileSync(new URL('./prospectivePolicy.json',import.meta.url))).digest('hex');
  assert.equal(actual,expected);assert.equal(run().acceptancePolicy.policySha256,actual);
});
