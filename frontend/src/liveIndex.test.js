import test from 'node:test';
import assert from 'node:assert/strict';
import {geometry,normalize,FixedIndex,LiveIndex,headPose,FEATURES} from './liveIndex.js';
import canonical from './faceReference.json' with {type:'json'};
import {saveCameraSession,readCameraSessions,deleteCameraSession} from './cameraSessions.js';

const reference=()=>{
  const p=Array.from({length:478},()=>[0,0]);
  canonical.indices.forEach((i,n)=>{p[i]=[...canonical.reference[n]];});
  return p;
};

test('geometry is invariant to 2-D rotation, scale and translation',()=>{
  const p=reference(),original=geometry(p);
  for(const angle of [-2,-.7,.2,1,2.8]) {
    const c=Math.cos(angle),s=Math.sin(angle);
    const changed=p.map(([x,y])=>[(x*c-y*s)*3.7+100,(x*s+y*c)*3.7-27]);
    const actual=geometry(changed);
    for(const key of Object.keys(original)) assert.ok(Math.abs(original[key]-actual[key])/Math.max(Math.abs(original[key]),1e-6)<.01,key);
  }
  assert.throws(()=>normalize(Array.from({length:478},()=>[0,0])));
});

test('sigma floor and requested reversed scale use the fixed formula',()=>{
  const baseline=Array.from({length:10},()=>Object.fromEntries(FEATURES.map(k=>[k,10])));
  const model=new FixedIndex(baseline);
  assert.equal(model.sigma.blink_rate,.501);
  const base={...baseline[0],time:25};
  assert.equal(model.score(base),5);
  const high={...base,time:26};
  for(const k of FEATURES)high[k]+=model.sigma[k];
  assert.ok(new FixedIndex(baseline).score(high)<5);
  const low={...base,time:26};for(const k of FEATURES)low[k]-=model.sigma[k];
  assert.ok(new FixedIndex(baseline).score(low)>5);
  assert.equal(model.score({...high,gated:true}),null);
});

test('25-second calibration then live values; gated/pose/quality frames are missing',()=>{
  const session=new LiveIndex(),p=reference();
  for(let i=0;i<250;i++)assert.equal(session.update(i/10,p,[0,0,0],true).value,null);
  const first=session.update(25,p,[0,0,0],true);
  assert.equal(first.phase,'live');assert.ok(Math.abs(first.value-5)<1e-9);
  assert.equal(session.update(26,p,[0,36,0],true).value,null);
  assert.equal(session.update(27,p,[0,0,0],false).value,null);
  assert.equal(session.update(28,[],null,false).value,null);
  const speaking=reference();speaking[14][1]+=10;
  const gated=session.update(29,speaking,[0,0,0],true);
  assert.equal(gated.value,null);assert.match(gated.reason,/speaking/);
});

test('poor baseline fails without emitting a guessed number',()=>{
  const session=new LiveIndex();
  for(let i=0;i<250;i++)session.update(i/10,[],null,false);
  const result=session.update(25,reference(),[0,0,0],true);
  assert.equal(result.phase,'failed');assert.equal(result.value,null);
});

test('column-major pose matrix extracts yaw and rejects missing matrices',()=>{
  const angle=20*Math.PI/180,c=Math.cos(angle),s=Math.sin(angle);
  const pose=headPose({rows:4,columns:4,data:[c,0,-s,0,0,1,0,0,s,0,c,0,0,0,0,1]});
  assert.ok(Math.abs(pose[1]-20)<1e-10);assert.equal(pose[0],0);
  assert.equal(headPose(null),null);
});

test('camera sessions use separate storage and preserve old questionnaire records',()=>{
  const values=new Map([['pause-checkins-v1','[{"self_reported_stress":8}]']]);
  globalThis.localStorage={getItem:k=>values.get(k)||null,setItem:(k,v)=>values.set(k,v)};
  const session={id:'synthetic-test',created_at:'2026-01-01T00:00:00Z',average:5,points:[{time:25,value:5}]};
  saveCameraSession(session);saveCameraSession(session);
  assert.equal(readCameraSessions().length,1);
  deleteCameraSession(session.id);assert.equal(readCameraSessions().length,0);
  assert.equal(values.get('pause-checkins-v1'),'[{"self_reported_stress":8}]');
  delete globalThis.localStorage;
});

test('quick scan needs a complete stable acquisition but no personal baseline',async()=>{
  const {QuickIndex,SCAN_SECONDS}=await import('./liveIndex.js');assert.equal(SCAN_SECONDS,10);
  const scan=new QuickIndex();
  assert.equal(scan.update(0,reference(),[0,0,0],true).phase,'live');
  assert.equal(scan.finish().average,null);
  for(let i=1;i<100;i++)scan.update(i/10,reference(),[0,0,0],true);
  assert.ok(Number.isFinite(scan.finish().average));
  assert.equal(scan.finish().quality,'good');
  const changed=reference();changed[107][0]+=1;
  const second=new QuickIndex();
  for(let i=0;i<100;i++)second.update(i/10,changed,[0,0,0],true);
  assert.notEqual(second.finish().average,scan.finish().average);
});

test('insufficient scan reports the actual camera rejection reason',async()=>{
  const {QuickIndex}=await import('./liveIndex.js');const scan=new QuickIndex();
  for(let i=0;i<100;i++)scan.update(i/10,[],null,false,{qualityReason:'Only one person should be in view.'});
  const result=scan.finish();assert.equal(result.average,null);assert.match(result.reason,/Only one person/);
});
