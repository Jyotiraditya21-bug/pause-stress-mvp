// Synthetic acquisition regression only. No people, stress labels, training or fit.
import {QuickIndex,FixedIndex,geometry} from '../src/liveIndex.js';
import canonical from '../src/faceReference.json' with {type:'json'};
const reference=()=>{const p=Array.from({length:478},()=>[0,0]);canonical.indices.forEach((i,n)=>p[i]=[...canonical.reference[n]]);return p;};
const neutral=geometry(reference());
const baseline=Array.from({length:5},()=>Object.fromEntries(['brow_furrow','lip_press','lip_corner','jaw_clench'].map(k=>[k,neutral[k]])));
let state=42;const random=()=>{state=(1664525*state+1013904223)>>>0;return state/4294967296;};
const runs=[];
for(let scan=0;scan<20;scan++){
  const old=new FixedIndex(baseline),current=new QuickIndex(),scores=[];
  const startup=(random()-.5)*.8;
  for(let i=0;i<100;i++){
    const t=i/10,p=reference();
    for(const point of p){point[0]+=(random()-.5)*.01;point[1]+=(random()-.5)*.01;}
    if(t<1){p[61][1]+=startup;p[291][1]+=startup;}
    const row={...geometry(p),time:t};row.gated=row.mar>.35;
    const value=old.score(row);if(Number.isFinite(value))scores.push(value);
    current.update(t,p,[0,0,0],true,{brightness:110});
  }
  const result=current.finish();runs.push({old:scores.reduce((a,b)=>a+b,0)/scores.length,current:result.average,quality:result.quality});
}
const describe=key=>{const a=runs.map(r=>r[key]).filter(Number.isFinite),mean=a.reduce((x,y)=>x+y,0)/a.length;return {accepted:a.length,range:Math.max(...a)-Math.min(...a),standardDeviation:Math.sqrt(a.reduce((s,v)=>s+(v-mean)**2,0)/a.length)};};
console.log(JSON.stringify({description:'20 synthetic repeated scans: same geometry, seeded landmark jitter and startup perturbation; not clinical or human repeatability validation',seed:42,previous:describe('old'),updated:describe('current')},null,2));
