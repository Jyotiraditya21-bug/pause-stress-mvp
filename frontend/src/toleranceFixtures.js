import canonical from './faceReference.json' with {type:'json'};
import {geometry} from './liveIndex.js';

// Same fixture generator is consumed by Node tests and the Python parity runner.
export function fixtureFace(){
  const p=Array.from({length:478},()=>[0,0,0]);canonical.indices.forEach((id,n)=>p[id]=[...canonical.reference[n],0]);
  const xs=p.map(v=>v[0]),ys=p.map(v=>v[1]),x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
  const scale=Math.min(320/(x1-x0),290/(y1-y0));
  return p.map(([x,y,z])=>[(x-(x0+x1)/2)*scale+320,(y-(y0+y1)/2)*scale+240,z]);
}
export function toleranceFixtures(){
  const face=fixtureFace();
  const identity={rows:4,columns:4,data:[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]};
  const stats=Object.fromEntries(['brow_furrow','lip_press','lip_corner','jaw_clench'].map(k=>[k,{median:geometry(face)[k],mad:.01}]));
  return ['still','movement','talking','missing','extended','turned','frontal','personal','gap'].map(name=>({name,baseline:name==='personal'?{features:stats}:null,frontalize3d:name==='frontal',frames:Array.from({length:name==='extended'?200:100},(_,i)=>{
    const time=i/10,missing=name==='missing'||(name==='extended'&&time<8)||(name==='gap'&&time>=4&&time<6);
    const points=missing?[]:face.map((p,j)=>[p[0]+(name==='movement'?2*Math.sin(time*2):0),p[1]+(name==='movement'?Math.sin(time):0),p[2]]);
    if(name==='talking'&&points.length){points[13][1]-=25;points[14][1]+=25;}
    return{time,points,pose:name==='turned'?[0,35,0]:[0,0,0],context:{width:640,height:480,brightness:120,faceCount:missing?0:1,matrix:identity}};
  })}));
}
