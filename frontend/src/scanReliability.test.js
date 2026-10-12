import test from 'node:test';
import assert from 'node:assert/strict';
import {ScanReliability} from './scanReliability.js';
import {faceBrightness,assessQuickFrame} from './scanMetrics.js';

function run({fps=10,signal=()=>5,valid=()=>true,context=()=>({pitch:0,yaw:0,brightness:110})}={}){
  const scan=new ScanReliability(['x'],r=>r.x);
  for(let i=0;i<10*fps;i++){const t=i/fps;scan.add(t,valid(t)?{x:signal(t)}:null,context(t));}
  return scan.finish();
}
test('time windows have equal weight at different frame rates',()=>{
  for(const fps of [5,10,30])assert.equal(run({fps}).average,5);
});
test('settling noise and isolated spikes do not dominate the final score',()=>{
  assert.equal(run({signal:t=>t<1?0:t%1<.2?10:5}).average,5);
});
test('sustained changes remain detectable and are not anchored to prior scans',()=>{
  assert.equal(run({signal:()=>3}).average,3);
  assert.equal(run({signal:()=>7}).average,7);
});
test('contradictory scan halves cause retry, not a misleading middle score',()=>{
  const r=run({signal:t=>t<5?3:7});assert.equal(r.average,null);assert.match(r.reason,/conflicting/);
});
test('missing time counts against coverage even if every received frame was valid',()=>{
  const r=run({valid:t=>t<4});assert.equal(r.average,null);assert.ok(r.coveragePercent<40);
});
test('eighty percent coverage still requires enough usable one-second windows',()=>{
  const good=run({valid:t=>Math.floor((t-1)*5+1e-8)%5!==4});
  assert.equal(good.coveragePercent,80);assert.equal(good.quality,'good');
  assert.equal(run({valid:t=>t<8}).quality,'limited');
});
test('stable face measurements survive moderate lighting and pose changes with a warning',()=>{
  for(const context of [t=>({brightness:t<5?80:150}),t=>({yaw:t<5?-8:8})]){
    const r=run({context});assert.equal(r.average,5);assert.equal(r.quality,'limited');assert.match(r.reason,/lower confidence/);
  }
});
test('duplicate and backwards timestamps cannot inflate coverage',()=>{
  const s=new ScanReliability(['x'],r=>r.x);
  for(let i=0;i<100;i++)s.add(2,{x:5});
  s.add(1,{x:5});assert.equal(s.finish().reliability.usableSlots,1);assert.equal(s.finish().average,null);
});
test('face brightness excludes unrelated background pixels',()=>{
  const pixels=new Uint8ClampedArray(10*10*4);
  for(let y=3;y<7;y++)for(let x=3;x<7;x++)for(let c=0;c<3;c++)pixels[(y*10+x)*4+c]=120;
  assert.equal(faceBrightness(pixels,10,10,[{x:.3,y:.3},{x:.7,y:.7}]),120);
  assert.equal(assessQuickFrame([],0,NaN).good,false);
  assert.equal(assessQuickFrame([{x:.3,y:.3},{x:.7,y:.7}],2,120).good,false);
});

test('two unusual windows do not discard seven consistent windows',()=>{
  const r=run({signal:t=>t>=8?9:5});
  assert.equal(r.average,5);assert.equal(r.quality,'limited');assert.equal(r.reliability.consistentWindows,7);
});
test('no face and severe disagreement still cannot produce a score',()=>{
  assert.equal(run({valid:()=>false}).average,null);
  assert.equal(run({signal:t=>Math.floor(t)%2?2:8}).average,null);
});
