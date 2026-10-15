import config from './toleranceConfig.json' with {type:'json'};
import canonical from './faceReference.json' with {type:'json'};
import {geometry,FixedIndex} from './liveIndex.js';
import {median,mad} from './scanReliability.js';

// Provisional, predeclared. Production adoption requires evaluate_tolerance.py.
export const TOLERANCE_CONFIG=Object.freeze(config);
const C=TOLERANCE_CONFIG,clamp=v=>Math.max(0,Math.min(1,v));
const mean=a=>a.reduce((s,v)=>s+v,0)/a.length;
const sd=a=>a.length?Math.sqrt(mean(a.map(v=>(v-mean(a))**2))):0;
export function weightedMedian(values,weights){
  const rows=values.map((v,i)=>[v,weights[i]]).filter(([v,w])=>Number.isFinite(v)&&Number.isFinite(w)&&w>0).sort((a,b)=>a[0]-b[0]);
  const total=rows.reduce((s,r)=>s+r[1],0);let sum=0;
  for(let i=0;i<rows.length;i++){sum+=rows[i][1];if(Math.abs(sum-total/2)<1e-12&&i+1<rows.length)return(rows[i][0]+rows[i+1][0])/2;if(sum>=total/2)return rows[i][0];}
  return null;
}
function taper(v,full,soft,max){
  if(!Number.isFinite(v))return 0;
  if(v<=full)return 1;
  if(v<=soft)return 1-(1-C.softWeight)*(v-full)/(soft-full);
  if(v<=max)return C.softWeight*(max-v)/(max-soft);
  return 0;
}
export const poseWeight=pose=>!pose?C.missingPoseWeight:taper(Math.max(Math.abs(pose[0]),Math.abs(pose[1])),C.poseFull,C.poseSoft,C.poseMax);
export const speedWeight=speed=>taper(speed,C.speedFull,C.speedSoft,C.speedMax);
export const rangeWeight=(v,low,high,ramp)=>Number.isFinite(v)?clamp(Math.min((v-low)/ramp,(high-v)/ramp)):0;
export function landmarkSpeed(points,previous,dt){
  if(!previous||!Number.isFinite(dt)||dt<=0||points.length!==previous.length)return null;
  const eye=Math.hypot(points[33][0]-points[263][0],points[33][1]-points[263][1]);
  if(eye<=1e-8)return Infinity;
  return mean(points.map((p,i)=>Math.hypot(p[0]-previous[i][0],p[1]-previous[i][1])))/dt/eye;
}
export function frameWeight({points=[],faceCount=0,brightness,pose,speed=null,width=1,height=1}){
  if(faceCount!==1||points.length<478)return{weight:0,reason:faceCount>1?'multiple_faces':'no_face',hint:faceCount>1?'One face only':'Keep your face in the circle'};
  if(!points.every(p=>p.every(Number.isFinite))||width<=0||height<=0)return{weight:0,reason:'tracking',hint:'Keep your face visible'};
  const xs=points.map(p=>p[0]/width),ys=points.map(p=>p[1]/height);
  const factors={pose:poseWeight(pose),speed:speed===null?1:speedWeight(speed),light:rangeWeight(brightness,C.lightMin,C.lightMax,C.lightRamp),size:Math.min(rangeWeight(Math.max(...xs)-Math.min(...xs),C.widthMin,C.widthMax,C.sizeRamp),rangeWeight(Math.max(...ys)-Math.min(...ys),C.heightMin,C.heightMax,C.sizeRamp))};
  let reason='';
  if(factors.light<1)reason=brightness<(C.lightMin+C.lightMax)/2?'too_dark':'too_bright';
  else if(factors.size<1)reason=Math.max(...xs)-Math.min(...xs)<(C.widthMin+C.widthMax)/2?'too_far':'too_close';
  else if(factors.pose<1)reason='turned_away';
  else if(factors.speed<1)reason='movement';
  const hints={too_dark:'More light',too_bright:'Reduce bright light',too_far:'Move closer',too_close:'Move back',turned_away:'Face the camera a little more',movement:'Small movements are fine; keep your face in view'};
  const weight=Object.values(factors).reduce((a,b)=>a*b,1);
  return{weight:weight<C.minFrameWeight?0:weight,factors,reason,hint:hints[reason]||''};
}
export function featureMask(row,pose,frontalized=false){
  const out={...row};
  if(row.mar>C.mouthMax){out.lip_press=null;out.lip_corner=null;}
  if(!frontalized&&pose&&Math.abs(pose[1])>C.jawYawMax)out.jaw_clench=null;
  return out;
}
export function frontalize(points,matrix){
  const d=matrix?.data;
  if(matrix?.rows!==4||matrix?.columns!==4||d?.length!==16||!d.every(Number.isFinite))return{points,applied:false};
  const columns=[0,1,2].map(j=>[d[j*4],d[j*4+1],d[j*4+2]]);
  if(columns.some(c=>Math.hypot(...c)<1e-8))return{points,applied:false};
  const rotation=columns.map(c=>c.map(v=>v/Math.hypot(...c)));
  const center=[0,1,2].map(j=>mean(points.map(p=>p[j]??0)));
  return{points:points.map(p=>rotation.slice(0,2).map(c=>c.reduce((s,v,j)=>s+v*((p[j]??0)-center[j]),0))),applied:true};
}
export class OneEuro{
  constructor(){this.time=null;this.x=null;this.dx=0;this.raw=null;}
  update(value,time){
    if(this.time===null){this.time=time;this.x=value;this.raw=value;return value;}
    const dt=time-this.time;if(dt<=0)return this.x;
    const alpha=cut=>1/(1+1/(2*Math.PI*cut*dt));
    const a=alpha(C.dCutoff);this.dx=a*(value-this.raw)/dt+(1-a)*this.dx;
    const b=alpha(C.minCutoff+C.beta*Math.abs(this.dx));this.x=b*value+(1-b)*this.x;
    this.raw=value;this.time=time;return this.x;
  }
}
export class LandmarkFilter{
  constructor(){this.filters=[];this.lastFace=null;}
  update(points,time){
    if(!points?.length){if(this.lastFace!==null&&time-this.lastFace>C.faceLossReset)this.filters=[];return[];}
    if(this.lastFace!==null&&time-this.lastFace>C.faceLossReset)this.filters=[];
    this.lastFace=time;
    return points.map((p,i)=>p.map((v,j)=>{const n=i*3+j;this.filters[n]??=new OneEuro();return this.filters[n].update(v,time);}));
  }
}
export function adaptiveState(elapsed,coverage){
  return{state:elapsed>=C.maxDuration||(elapsed>=C.duration&&coverage>=C.normalCoverage)?'analyzing':'countdown',extended:elapsed>=C.duration,progress:Math.min(1,elapsed/(elapsed>=C.duration&&coverage<C.normalCoverage?C.maxDuration:C.duration)),capped:elapsed>=C.maxDuration};
}
export function resultTier(points,coverage){
  const scored=points.filter(p=>Number.isFinite(p.value));const values=scored.map(p=>p.value),center=median(values);
  const middle=points.length/2;
  const consensus=radius=>{
    const rows=scored.filter(p=>Math.abs(p.value-center)<=radius);
    const early=rows.filter(p=>p.window<middle).map(p=>p.value),late=rows.filter(p=>p.window>=middle).map(p=>p.value);
    return{rows,fraction:scored.length?rows.length/scored.length:0,difference:early.length&&late.length?Math.abs(median(early)-median(late)):null};
  };
  const normal=consensus(C.normalRadius),limited=consensus(C.limitedRadius);
  if(coverage>=C.normalCoverage&&scored.length>=C.normalWindows&&normal.fraction>=C.normalFraction&&normal.difference!==null&&normal.difference<=C.normalDifference)return{tier:'NORMAL',...normal};
  if(coverage>=C.limitedCoverage&&scored.length>=C.limitedWindows&&limited.fraction>=C.limitedFraction&&limited.difference!==null&&limited.difference<=C.limitedDifference)return{tier:'LIMITED',...limited};
  return{tier:'NONE',...limited};
}
export class TolerantScan{
  constructor({baseline=null,frontalize3d=C.frontalize3d}={}){
    this.baseline=baseline;this.frontalize3d=frontalize3d;this.filter=new LandmarkFilter();this.previous=null;this.lastTime=-Infinity;this.slots=new Map();this.reasons={};this.observations=[];this.elapsed=0;this.qualityFlags={lowLight:false,offCenter:false,tooFar:false,tooClose:false,moving:false,multipleFaces:false,mouthOpen:false,pose:false};
    const p=Array.from({length:478},()=>[0,0]);canonical.indices.forEach((i,n)=>p[i]=canonical.reference[n]);
    const g=geometry(p),spreads={brow_furrow:.06,lip_press:.04,lip_corner:.06,jaw_clench:.08};
    this.reference=[0,1,-1,.5,-.5].map(f=>Object.fromEntries(C.features.map(k=>[k,g[k]+f*spreads[k]])));
  }
  score(row){
    if(C.features.filter(k=>Number.isFinite(row[k])).length<C.minFeatures)return null;
    if(!this.baseline)return new FixedIndex(this.reference).score({...row,time:row.time??0});
    const z=C.features.filter(k=>Number.isFinite(row[k])&&this.baseline.features?.[k]).map(k=>{const s=this.baseline.features[k];return Math.max(-3,Math.min(3,(row[k]-s.median)/(Math.max(C.madScale*s.mad,.05*Math.abs(s.median)+.001)+1e-6)));});
    return z.length<C.minFeatures?null:10*(1-1/(1+Math.exp(-z.reduce((a,b)=>a+b,0)/Math.sqrt(z.length))));
  }
  update(time,points,pose,qualityGood=true,context={}){
    if(!Number.isFinite(time)||time<=this.lastTime||time<0||time>=C.maxDuration)return{valid:false,reason:'',weight:0};
    this.lastTime=time;this.elapsed=time;
    const width=context.width||1,height=context.height||1;
    const speed=landmarkSpeed(points,this.previous?.points,time-(this.previous?.time??time));
    this.previous=points.length>=478&&(context.faceCount??1)===1?{points,time}:null;
    const quality=frameWeight({points,pose,speed,faceCount:context.faceCount??(points.length>=478?1:0),brightness:context.brightness,width,height});
    const normalized=points.map(p=>[p[0]/width,p[1]/height,(p[2]??0)/width]);
    const smooth=this.filter.update(['no_face','multiple_faces','tracking'].includes(quality.reason)?[]:normalized,time).map(p=>[p[0]*width,p[1]*height,p[2]*width]);
    let row=null;
    if(quality.weight>0&&smooth.length){try{const corrected=this.frontalize3d?frontalize(smooth,context.matrix):{points:smooth,applied:false};row=featureMask(geometry(corrected.points),pose,corrected.applied);}catch{}}
    const flags={lowLight:quality.reason==='too_dark',tooFar:quality.reason==='too_far',tooClose:quality.reason==='too_close',moving:quality.factors?.speed<1,multipleFaces:quality.reason==='multiple_faces',mouthOpen:row?.mar>C.mouthMax,pose:quality.factors?.pose<1};
    for(const [key,value] of Object.entries(flags))this.qualityFlags[key]||=!!value;
    this.observations.push({time,weight:row?quality.weight:0,pose:pose?Math.max(Math.abs(pose[0]),Math.abs(pose[1])):null,speed});
    if(time>=C.settling){
      if(!row||quality.reason)this.reasons[quality.reason||'tracking']=(this.reasons[quality.reason||'tracking']||0)+1;
      const slot=Math.floor((time-C.settling)/C.slotSeconds+1e-8),samples=this.slots.get(slot)||[];
      if(row)samples.push({row,weight:quality.weight});this.slots.set(slot,samples);
    }
    return{valid:!!row,weight:row?quality.weight:0,reason:quality.hint,phase:'live'};
  }
  usableSlots(){
    const slots=new Map();for(const [i,rows] of this.slots){if(!rows.length)continue;const row=Object.fromEntries(C.features.map(k=>[k,weightedMedian(rows.map(r=>r.row[k]),rows.map(r=>r.weight))]));slots.set(i,{row,weight:Math.max(...rows.map(r=>r.weight))});}return slots;
  }
  coverage(){return Math.min(1,[...this.usableSlots().values()].reduce((s,r)=>s+r.weight,0)/C.coverageSlots);}
  rollingCoverage(time){const a=this.observations.filter(r=>r.time>time-C.hintSeconds),weights=new Map();for(const r of a){const i=Math.floor(r.time/C.slotSeconds);weights.set(i,Math.max(weights.get(i)||0,r.weight));}return [...weights.values()].reduce((a,b)=>a+b,0)/(C.hintSeconds/C.slotSeconds);}
  finish(duration=Math.max(C.duration,this.elapsed)){
    duration=Math.min(C.maxDuration,Math.max(C.duration,duration));const slots=this.usableSlots(),points=[],rows=[];
    const count=Math.floor((duration-C.settling)/C.windowSeconds+1e-8);
    for(let window=0;window<count;window++){
      const block=[...slots.entries()].filter(([i])=>Math.floor(i*C.slotSeconds/C.windowSeconds)===window).map(([,v])=>v);
      const row=Object.fromEntries(C.features.map(k=>[k,weightedMedian(block.map(b=>b.row[k]),block.map(b=>b.weight))]));
      const used=C.features.filter(k=>Number.isFinite(row[k])).length;
      const value=block.length>=C.minWindowSlots&&used>=C.minFeatures?this.score({...row,time:window+1.5}):null;
      if(Number.isFinite(value))rows.push(row);
      points.push({window,time:window+1.5,value,featuresUsed:Number.isFinite(value)?used:0});
    }
    const coverage=this.coverage(),assigned=resultTier(points,coverage),none=assigned.tier==='NONE';
    const average=none?null:median(assigned.rows.map(p=>p.value)),values=points.map(p=>p.value).filter(Number.isFinite);
    const spread=values.length?Math.max(C.rangeFloor,C.madScale*mad(values))*(assigned.tier==='LIMITED'?C.limitedWiden:1):null;
    const poses=this.observations.map(r=>r.pose).filter(Number.isFinite),speeds=this.observations.map(r=>r.speed).filter(Number.isFinite);
    const variability=clamp(Math.max(sd(poses)/C.poseMax,sd(speeds)/C.speedMax));
    const confidence=clamp(C.confidenceCoverage*Math.min(1,coverage/C.normalCoverage)+C.confidenceConsensus*assigned.fraction+C.confidenceStability*(1-variability));
    const top=Object.entries(this.reasons).sort((a,b)=>b[1]-a[1])[0]?.[0]||'no_face';
    const failures={no_face:'No face was tracked. Keep your face in the circle and retry.',multiple_faces:'More than one face was visible. Scan with one person in view.',too_dark:'Your face was too dark. Face a light source and retry.',too_bright:'Your face was overexposed. Reduce bright light and retry.',too_far:'Your face was too far away. Move closer and retry.',too_close:'Your face was too close. Move back and retry.',turned_away:'Your face was turned away. Face the camera and retry.',movement:'Too much movement obscured the landmarks. Make smaller movements and retry.',tracking:'The landmarks could not be tracked. Keep your face visible and retry.'};
    const failReason=none?(values.length>=C.limitedWindows?'The readings did not agree enough. Keep a similar expression and retry.':failures[top]):'';
    return{average,latest:none?null:points.at(-1)?.value??null,tier:assigned.tier,status:none?'failed':assigned.tier==='LIMITED'?'limited':'ok',quality:none?'poor':assigned.tier==='LIMITED'?'limited':'good',confidence,range:none?null:[Math.max(0,average-spread),Math.min(10,average+spread)],warnings:assigned.tier==='LIMITED'?['Movement or expressions reduced reliability']:[],reason:failReason||(assigned.tier==='LIMITED'?'Movement or expressions reduced reliability':''),failReason,reasonCode:none?top:'',points,windowScores:points.map(p=>p.value),windowFeaturesUsed:points.map(p=>p.featuresUsed),effectiveCoverage:coverage,coveragePercent:coverage*100,features:rows.length?Object.fromEntries(C.features.map(k=>[k,median(rows.map(r=>r[k]).filter(Number.isFinite))])):null,featureStats:rows.length?Object.fromEntries(C.features.map(k=>{const a=rows.map(r=>r[k]).filter(Number.isFinite);return[k,{median:median(a),mad:mad(a)}];})):null,mode:this.baseline?'baseline':'generic',algoVersion:C.version,frontalize3d:this.frontalize3d,qualityFlags:{...this.qualityFlags},reliability:{usableSlots:slots.size,totalSlots:C.coverageSlots,usableWindows:values.length,totalWindows:count,consensusFraction:assigned.fraction,consensusHalfDifference:assigned.difference,poseSpeedVariability:variability,rejectionReasons:this.reasons,ruleVersion:C.version}};
  }
}
