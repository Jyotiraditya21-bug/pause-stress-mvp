import test from 'node:test';
import assert from 'node:assert/strict';
import {ALGO_VERSION,BASELINE_KEY,BASELINE_MAX_AGE_MS,readBaseline,resetBaseline,saveBaseline} from './baselineStorage.js';
import {advanceScanState,createScanState,HARD_CAP_SECONDS} from './scanState.js';
import {BASELINE_KEYS,GENERIC_KEYS,QuickIndex} from './liveIndex.js';
import {ScanReliability} from './scanReliability.js';

function storage(){
  const values=new Map();return {getItem:key=>values.get(key)||null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key),values};
}

test('generic mode removes jaw geometry and baseline mode retains all four features',()=>{
  assert.deepEqual(GENERIC_KEYS,['brow_furrow','lip_press','lip_corner']);
  assert.deepEqual(BASELINE_KEYS,['brow_furrow','lip_press','lip_corner','jaw_clench']);
  assert.deepEqual(new QuickIndex().keys,GENERIC_KEYS);
  const baseline={algoVersion:ALGO_VERSION,features:Object.fromEntries(BASELINE_KEYS.map(key=>[key,{median:0,mad:1}]))};
  assert.deepEqual(new QuickIndex({baseline}).keys,BASELINE_KEYS);
});

test('baseline storage handles save, expiry, version mismatch and reset',()=>{
  const store=storage(),now=Date.UTC(2026,0,1);
  const features=Object.fromEntries(BASELINE_KEYS.map(key=>[key,{median:1,mad:.1}]));
  assert.equal(saveBaseline(features,store,now).algoVersion,ALGO_VERSION);
  assert.equal(readBaseline(store,now+1000).createdAt,new Date(now).toISOString());
  assert.equal(readBaseline(store,now+BASELINE_MAX_AGE_MS+1),null);
  store.setItem(BASELINE_KEY,JSON.stringify({createdAt:new Date(now).toISOString(),algoVersion:'old',features}));
  assert.equal(readBaseline(store,now),null);
  saveBaseline(features,store,now);assert.equal(resetBaseline(store),true);assert.equal(readBaseline(store,now),null);
});

test('uncertainty range uses scaled MAD and preserves gaps',()=>{
  const scan=new ScanReliability(['x'],row=>row.x);
  for(let i=0;i<100;i++){
    const time=i/10;
    const missing=time>=4&&time<5;
    scan.add(time,missing?null:{x:time<7?5:5.4});
  }
  const result=scan.finish();
  assert.equal(result.windowScores.length,9);assert.equal(result.windowScores[3],null);
  assert.ok(result.range[0]<=result.average&&result.range[1]>=result.average);
  assert.equal(result.status,'ok');
});

test('quality clock positions, pauses, resumes and enforces the wall cap',()=>{
  let state=createScanState(0);
  state=advanceScanState(state,.5,true);assert.equal(state.state,'positioning');
  state=advanceScanState(state,1.6,true);assert.equal(state.state,'countdown');
  state=advanceScanState(state,2.1,true);assert.equal(state.goodElapsed,.5);
  state=advanceScanState(state,2.8,false);assert.equal(state.paused,false);
  state=advanceScanState(state,3.5,false);assert.equal(state.paused,true);
  const held=state.goodElapsed;state=advanceScanState(state,4,true);assert.equal(state.paused,false);assert.ok(state.goodElapsed>held);
  state=advanceScanState(state,HARD_CAP_SECONDS+.01,true);assert.equal(state.state,'analyzing');assert.equal(state.capped,true);
});

test('failed scans never return a score',()=>{
  const scan=new ScanReliability(['x'],row=>row.x);
  const result=scan.finish();assert.equal(result.status,'failed');assert.equal(result.average,null);assert.equal(result.range,null);
});
