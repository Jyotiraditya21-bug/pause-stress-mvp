import test from 'node:test';
import assert from 'node:assert/strict';
import {TolerantScan,TOLERANCE_CONFIG as C,poseWeight,speedWeight,rangeWeight,landmarkSpeed,weightedMedian,featureMask,adaptiveState,resultTier,OneEuro,LandmarkFilter,frontalize} from './tolerantScan.js';
import {fixtureFace,toleranceFixtures} from './toleranceFixtures.js';
import {geometry} from './liveIndex.js';

test('soft weights have predeclared boundaries and no hard jump after the soft limit',()=>{
  assert.equal(poseWeight(null),.6);assert.equal(poseWeight([20,0]),1);assert.ok(Math.abs(poseWeight([40,0])-.2)<1e-12);assert.equal(poseWeight([51,0]),0);
  assert.equal(speedWeight(.15),1);assert.ok(Math.abs(speedWeight(.6)-.2)<1e-12);assert.equal(speedWeight(1.01),0);
  for(const [low,high,ramp] of [[18,240,10],[.15,.85,.05],[.20,.95,.05]]){
    assert.equal(rangeWeight(low,low,high,ramp),0);assert.ok(Math.abs(rangeWeight(low+ramp,low,high,ramp)-1)<1e-12);assert.equal(rangeWeight(high,low,high,ramp),0);
  }
});
test('speed uses elapsed timestamps and interocular scale',()=>{
  const p=fixtureFace(),shift=p.map(v=>[v[0]+2,v[1],v[2]]);
  const a=landmarkSpeed(shift,p,.1),b=landmarkSpeed(shift,p,.2);
  assert.ok(Math.abs(a-2*b)<1e-12);assert.equal(landmarkSpeed(p,p,0),null);
});
test('weighted median ignores missing values and downweights outliers',()=>{
  assert.equal(weightedMedian([1,5,9],[1,10,1]),5);assert.equal(weightedMedian([1,3],[1,1]),2);assert.equal(weightedMedian([null,5],[10,1]),5);assert.equal(weightedMedian([],[]),null);
});
test('mouth mask preserves brow and frontalization controls the jaw yaw mask',()=>{
  const row={...geometry(fixtureFace()),mar:.5};
  const mask=featureMask(row,[0,30,0]);assert.equal(mask.brow_furrow,row.brow_furrow);assert.equal(mask.lip_press,null);assert.equal(mask.lip_corner,null);assert.equal(mask.jaw_clench,null);
  assert.equal(featureMask(row,[0,30,0],true).jaw_clench,row.jaw_clench);
});
test('two features required; talking keeps brow and jaw; NONE never exposes a number',()=>{
  const scan=new TolerantScan();assert.equal(scan.score({brow_furrow:0}),null);assert.ok(Number.isFinite(scan.score({brow_furrow:0,jaw_clench:1})));
  const f=toleranceFixtures().find(f=>f.name==='talking');for(const r of f.frames)scan.update(r.time,r.points,r.pose,true,r.context);
  const result=scan.finish();assert.ok(result.windowFeaturesUsed.every(n=>n===2));assert.notEqual(result.average,null);
  const empty=new TolerantScan().finish();assert.equal(empty.tier,'NONE');assert.equal(empty.average,null);assert.equal(empty.range,null);
});
test('adaptive duration extends after ten, stops when coverage reaches target, caps at twenty',()=>{
  assert.equal(adaptiveState(9.9,1).state,'countdown');assert.equal(adaptiveState(10,.59).extended,true);assert.equal(adaptiveState(10,.59).state,'countdown');assert.equal(adaptiveState(13,.6).state,'analyzing');assert.equal(adaptiveState(20,0).capped,true);
});
test('constructed series assign NORMAL LIMITED and NONE without imputation',()=>{
  const points=Array.from({length:9},(_,window)=>({window,value:5}));
  assert.equal(resultTier(points,.6).tier,'NORMAL');assert.equal(resultTier(points,.2).tier,'LIMITED');assert.equal(resultTier(points,.14).tier,'NONE');
  assert.equal(resultTier(points.slice(0,8).map(p=>({...p,value:p.window<4?1:9})),1).tier,'NONE');
});
test('One Euro reduces jitter; face-loss reset and missing transform fallback are deterministic',()=>{
  const filter=new OneEuro(),raw=Array.from({length:100},(_,i)=>1+.01*(i%2?1:-1));const smooth=raw.map((v,i)=>filter.update(v,i/10));
  const variance=a=>a.reduce((s,v)=>s+(v-1)**2,0)/a.length;assert.ok(variance(smooth.slice(10))<variance(raw.slice(10)));
  const landmarks=new LandmarkFilter();landmarks.update([[1,1,0]],0);landmarks.update([],1);assert.deepEqual(landmarks.update([[2,2,0]],1.1),[[2,2,0]]);
  const p=fixtureFace();assert.deepEqual(frontalize(p,null),{points:p,applied:false});assert.equal(C.frontalize3d,false);assert.equal(C.adopted,false);
});
test('coverage uses weighted slots and extension adds evidence, never repeats or holds scores',()=>{
  const scan=new TolerantScan(),p=fixtureFace();
  for(let i=0;i<100;i++)scan.update(i/10,p,null,true,{width:640,height:480,brightness:120,faceCount:1});
  assert.ok(Math.abs(scan.coverage()-.6)<1e-12);
  const prior=scan.coverage();scan.update(9.9,p,null,true,{width:640,height:480,brightness:120,faceCount:1});assert.equal(scan.coverage(),prior);
  assert.equal(scan.finish().points.length,9);
});
test('gaps remain missing and LIMITED has the prescribed wider MAD range',()=>{
  const fixture=toleranceFixtures().find(f=>f.name==='gap'),scan=new TolerantScan();
  for(const r of fixture.frames)scan.update(r.time,r.points,r.pose,true,r.context);
  const result=scan.finish();assert.equal(result.windowScores[3],null);assert.equal(result.windowScores[4],null);
  const limited=new TolerantScan();
  for(const r of fixture.frames)limited.update(r.time,r.points,[0,40,0],true,r.context);
  // At high yaw jaw is masked, but three other features can remain valid.
  const low=limited.finish();assert.equal(low.tier,'LIMITED');assert.ok(Math.abs(low.range[1]-low.average-.6)<1e-6);
  assert.equal(low.warnings[0],'Movement or expressions reduced reliability');
});
