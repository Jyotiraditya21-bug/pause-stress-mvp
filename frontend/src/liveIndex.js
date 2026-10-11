import {ScanReliability} from './scanReliability.js';
import canonical from './faceReference.json' with {type:'json'};

export const FEATURES = ['blink_rate','brow_furrow','lip_press','lip_corner','jaw_clench','jitter'];
export const BASELINE_SECONDS = 25;
const mean = values => values.reduce((a,b)=>a+b,0)/values.length;
const std = values => Math.sqrt(mean(values.map(v=>(v-mean(values))**2)));
const distance = (a,b) => Math.hypot(a[0]-b[0],a[1]-b[1]);

export function normalize(points) {
  if(points.length<478 || !canonical.indices.every(i=>points[i]?.every(Number.isFinite))) throw new Error('Incomplete landmarks');
  const centre=[0,1].map(j=>mean(canonical.indices.map(i=>points[i][j])));
  const refCentre=[0,1].map(j=>mean(canonical.reference.map(p=>p[j])));
  let dot=0,cross=0;
  canonical.indices.forEach((i,n)=>{
    const x=points[i][0]-centre[0],y=points[i][1]-centre[1];
    const a=canonical.reference[n][0]-refCentre[0],b=canonical.reference[n][1]-refCentre[1];
    dot+=x*a+y*b; cross+=x*b-y*a;
  });
  const angle=Math.atan2(cross,dot),c=Math.cos(angle),s=Math.sin(angle);
  const scale=distance(points[33],points[263]);
  if(scale<1e-8) throw new Error('Degenerate face geometry');
  return points.map(p=>[(c*(p[0]-centre[0])-s*(p[1]-centre[1]))/scale,(s*(p[0]-centre[0])+c*(p[1]-centre[1]))/scale]);
}

export function geometry(points) {
  const p=normalize(points),d=(a,b)=>distance(p[a],p[b]);
  const ear=(a,b,c,e,f,g)=>(d(b,g)+d(c,f))/(2*Math.max(d(a,e),1e-8));
  const width=Math.max(d(61,291),1e-8);
  let down=[-(p[263][1]-p[33][1]),p[263][0]-p[33][0]];
  const length=Math.hypot(...down); down=down.map(v=>v/length);
  if((p[152][0]-p[10][0])*down[0]+(p[152][1]-p[10][1])*down[1]<0) down=down.map(v=>-v);
  const corner=[0,1].map(j=>(p[61][j]+p[291][j]-p[13][j]-p[14][j])/2);
  return {ear:(ear(33,160,158,133,153,144)+ear(362,385,387,263,373,380))/2,
    mar:d(13,14)/width,lip_press:-(d(0,13)+d(14,17))/width,
    brow_furrow:-(d(107,336)+(d(105,158)+d(334,385))/2),
    lip_corner:Math.atan2(corner[0]*down[0]+corner[1]*down[1],width/2),
    jaw_clench:d(234,454)/Math.max(d(10,152),1e-8)};
}

// MediaPipe MatrixData defaults to column-major layout. Approximate Euler pose.
export function headPose(matrix) {
  const d=matrix?.data;
  if(matrix?.rows!==4 || matrix?.columns!==4 || !d || d.length!==16 || !d.every(Number.isFinite)) return null;
  const scale=Math.hypot(d[0],d[1],d[2]);
  if(scale<1e-8) return null;
  const yaw=Math.asin(Math.max(-1,Math.min(1,-d[2]/scale)))*180/Math.PI;
  const pitch=Math.atan2(d[6],d[10])*180/Math.PI;
  const roll=Math.atan2(d[1],d[0])*180/Math.PI;
  return [pitch,yaw,roll];
}

export class FixedIndex {
  constructor(baseline) {
    this.mu={};this.sigma={};this.rawSigma={};this.window=[];this.ema=null;this.lastTime=null;
    for(const key of FEATURES) {
      const values=baseline.map(r=>r[key]).filter(Number.isFinite);
      if(values.length>=5) {
        this.mu[key]=mean(values);this.rawSigma[key]=std(values);
        this.sigma[key]=Math.max(this.rawSigma[key],.05*Math.abs(this.mu[key])+1e-3);
      }
    }
  }
  score(row) {
    const keys=FEATURES.filter(k=>Object.hasOwn(this.mu,k)&&Number.isFinite(row[k]));
    if(row.gated || !keys.length) return null;
    const sum=keys.reduce((total,k)=>total+Math.max(-3,Math.min(3,(row[k]-this.mu[k])/(this.sigma[k]+1e-6))),0);
    this.window.push({time:row.time,raw:sum/Math.sqrt(keys.length)});
    this.window=this.window.filter(v=>v.time>=row.time-5);
    const s=100/(1+Math.exp(-mean(this.window.map(v=>v.raw))));
    if(this.lastTime!==null && row.time-this.lastTime<.1) return (100-this.ema)/10;
    this.lastTime=row.time;this.ema=this.ema===null?s:.1*s+.9*this.ema;
    return (100-this.ema)/10;
  }
}

export class LiveIndex {
  constructor() {this.baseline=[];this.total=0;this.valid=0;this.window=[];this.blinks=[];this.closed=null;this.previous=null;this.model=null;this.failure='';}
  update(time,points,pose,qualityGood) {
    const calibrating=time<BASELINE_SECONDS;
    if(calibrating) this.total++;
    let row=null;
    if(qualityGood && pose?.every(Number.isFinite) && Math.abs(pose[0])<=35 && Math.abs(pose[1])<=35) {
      try {
        row={...geometry(points),time};const q=normalize(points);
        if(row.ear<.2) {if(this.closed===null) this.closed=time;}
        else if(this.closed!==null) {if(time-this.closed>=.05&&time-this.closed<=.8) this.blinks.push({time,duration:time-this.closed});this.closed=null;}
        this.blinks=this.blinks.filter(v=>v.time>=time-20);
        const velocity=this.previous ? mean(canonical.indices.map(i=>distance(q[i],this.previous.q[i])))/Math.max(time-this.previous.time,1e-6) : 0;
        this.previous={time,q};this.window.push({time,pose,velocity});this.window=this.window.filter(v=>v.time>=time-5);
        row.blink_rate=this.blinks.length*60/Math.min(20,Math.max(time,.1));
        row.jitter=mean([0,1,2].map(i=>std(this.window.map(v=>v.pose[i]))))/180+std(this.window.map(v=>v.velocity));
        row.gated=row.mar>.35||row.lip_corner<-.12;
      } catch {row=null;}
    }
    if(!row) {this.previous=null;this.closed=null;}
    if(calibrating) {
      if(row&&!row.gated) {this.baseline.push(row);this.valid++;}
      return {value:null,phase:'baseline',remaining:Math.max(0,Math.ceil(BASELINE_SECONDS-time)),valid:!!row&&!row.gated};
    }
    if(!this.model&&!this.failure) {
      if(this.valid<30||this.valid/Math.max(this.total,1)<.4) this.failure='Not enough usable baseline frames. Improve lighting/framing and start again.';
      else this.model=new FixedIndex(this.baseline);
    }
    if(this.failure) return {value:null,phase:'failed',reason:this.failure,valid:false};
    const value=row ? this.model.score(row) : null;
    return {value,phase:'live',valid:Number.isFinite(value),reason:row?.gated?'Reading paused while speaking or smiling.':!qualityGood?'Reading paused: improve camera framing or lighting.':!pose||Math.abs(pose[0])>35||Math.abs(pose[1])>35?'Reading paused: face the camera.':''};
  }
}

// Fixed engineering reference; no personal calibration or fitting on task labels.
export const SCAN_SECONDS=10;
export class QuickIndex {
  constructor() {
    const p=Array.from({length:478},()=>[0,0]);
    canonical.indices.forEach((i,n)=>{p[i]=[...canonical.reference[n]];});
    const g=geometry(p),row=Object.fromEntries(['brow_furrow','lip_press','lip_corner','jaw_clench'].map(k=>[k,g[k]]));
    const stds={brow_furrow:.06,lip_press:.04,lip_corner:.06,jaw_clench:.08};
    this.reference=[
      {...row},
      Object.fromEntries(Object.keys(row).map(k=>[k,row[k]+stds[k]])),
      Object.fromEntries(Object.keys(row).map(k=>[k,row[k]-stds[k]])),
      Object.fromEntries(Object.keys(row).map(k=>[k,row[k]+stds[k]*.5])),
      Object.fromEntries(Object.keys(row).map(k=>[k,row[k]-stds[k]*.5]))
    ];
    this.measurements=new ScanReliability(Object.keys(row),r=>new FixedIndex(this.reference).score(r));
  }
  update(time,points,pose,qualityGood,context={}) {
    let row=null,reason='';
    if(qualityGood&&pose?.every(Number.isFinite)&&Math.abs(pose[0])<=15&&Math.abs(pose[1])<=15) {
      try {
        row={...geometry(points),time};
        if(row.mar>.25){row=null;reason='Keep your mouth relaxed and avoid speaking.';}
      } catch {row=null;}
    } else if(qualityGood)reason='Face straight ahead for a repeatable scan.';
    this.measurements.add(time,row,{...context,pitch:pose?.[0],yaw:pose?.[1]});
    // The score is calculated once from independent time windows at completion.
    return {value:null,phase:'live',valid:!!row,reason};
  }
  finish(){return this.measurements.finish();}
}
