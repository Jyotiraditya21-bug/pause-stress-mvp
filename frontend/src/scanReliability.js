// Fixed engineering quality rules, selected before repeatability evaluation.
// These rules assess acquisition stability; they do not validate stress accuracy.
export const SCAN_RULES=Object.freeze({duration:10,settling:1,slotSeconds:.2,minCoverage:.8,
  minWindows:8,maxScoreSpread:1,maxHalfDifference:.75,maxPoseSpan:6,maxBrightnessSpan:30});
export function quantile(values,q) {
  if(!values.length)return null;
  const a=[...values].sort((x,y)=>x-y),p=(a.length-1)*q,i=Math.floor(p);
  return a[i]+(a[Math.min(i+1,a.length-1)]-a[i])*(p-i);
}
export const median=values=>quantile(values,.5);
const span=a=>quantile(a,.9)-quantile(a,.1);
export const mad=values=>values.length?median(values.map(v=>Math.abs(v-median(values)))):null;

export class ScanReliability {
  constructor(keys,score,featureKeys=keys){this.keys=keys;this.featureKeys=featureKeys;this.score=score;this.slots=new Map();this.lastTime=-Infinity;this.qualityFlags={lowLight:false,offCenter:false,tooFar:false,tooClose:false,moving:false,multipleFaces:false,mouthOpen:false,pose:false};}
  add(time,row,context={}) {
    if(!Number.isFinite(time)||time<=this.lastTime||time<0||time>=SCAN_RULES.duration)return false;
    this.lastTime=time;
    if(time<SCAN_RULES.settling)return false;
    const slot=Math.min(44,Math.floor((time-SCAN_RULES.settling)/SCAN_RULES.slotSeconds+1e-8));
    for(const key of Object.keys(this.qualityFlags))this.qualityFlags[key] ||= !!context.qualityFlags?.[key];
    const samples=this.slots.get(slot)||[];
    // Retain invalid observations for diagnostics. Legacy occupancy still accepts
    // any slot containing a valid observation; this is not frame-validity coverage.
    samples.push(row&&this.keys.every(k=>Number.isFinite(row[k]))?{row,context}:null);
    this.slots.set(slot,samples);
    return true;
  }
  usableSlots() {
    const slots=new Map();
    for(const [i,samples] of this.slots){
      const valid=samples.filter(Boolean);
      if(!valid.length)continue;
      const row=Object.fromEntries(this.featureKeys.map(k=>[k,median(valid.map(s=>s.row[k]).filter(Number.isFinite))]));
      const context={};
      for(const k of ['pitch','yaw','brightness']){
        const values=valid.map(s=>s.context[k]).filter(Number.isFinite);
        if(values.length)context[k]=median(values);
      }
      slots.set(i,{row,context});
    }
    return slots;
  }
  finish() {
    const slots=this.usableSlots(),points=[],context=[],featureRows=[],windowDiagnostics=[];
    const observations=[...this.slots.values()].flat();
    const validObservations=observations.filter(Boolean).length;
    for(let window=0;window<9;window++){
      const block=[];
      for(let i=window*5;i<(window+1)*5;i++)if(slots.has(i))block.push(slots.get(i));
      let value=null,row=null;
      if(block.length>=2){
        row=Object.fromEntries(this.featureKeys.map(k=>[k,median(block.map(s=>s.row[k]).filter(Number.isFinite))]));
        value=this.score({...row,time:window+1.5});
        featureRows.push(row);
      }
      context.push(...block.map(s=>s.context));
      points.push({time:window+1.5,value});
      const acquisition={};
      for(const key of ['pitch','yaw','brightness']){
        const a=block.map(s=>s.context[key]).filter(Number.isFinite);
        acquisition[key]=a.length?{median:median(a),p10:quantile(a,.1),p90:quantile(a,.9),slots:a.length}:null;
      }
      windowDiagnostics.push({start:window+1,end:window+2,time:window+1.5,
        usableSlots:block.length,totalSlots:5,features:row,score:value,acquisition});
    }
    const values=points.map(p=>p.value).filter(Number.isFinite),coverage=slots.size/45;
    const first=points.slice(0,4).map(p=>p.value).filter(Number.isFinite);
    const last=points.slice(5).map(p=>p.value).filter(Number.isFinite);
    const spread=values.length?span(values):null;
    const halfDifference=first.length&&last.length?Math.abs(median(first)-median(last)):null;
    let fatalReason='',warningReason='';
    // Reject contradictory measurements, but allow isolated outlier windows.
    // The consensus uses only this scan; no previous score is reused.
    const centre=values.length?median(values):null;
    const consistent=points.filter(p=>Number.isFinite(p.value)&&Math.abs(p.value-centre)<=SCAN_RULES.maxScoreSpread);
    for(const window of windowDiagnostics)window.inConsensus=consistent.some(p=>p.time===window.time);
    const early=consistent.filter(p=>p.time<5).map(p=>p.value);
    const late=consistent.filter(p=>p.time>=6).map(p=>p.value);
    const consensusDifference=early.length&&late.length?Math.abs(median(early)-median(late)):null;
    if(coverage<.35||values.length<3)
      fatalReason='Not enough clear camera signal. Keep your face inside the circle for the full scan and retry.';
    else if(!first.length||!last.length)
      fatalReason='Your face was not visible throughout the scan. Keep it inside the circle and retry.';
    else if(consistent.length<Math.max(3,Math.ceil(values.length*.6))||consensusDifference===null||consensusDifference>SCAN_RULES.maxHalfDifference)
      fatalReason='The scan contained conflicting readings. Keep your face still and retry.';
    else {
      const warnings=[];
      if(coverage<SCAN_RULES.minCoverage||values.length<SCAN_RULES.minWindows)warnings.push('Some camera frames were unclear.');
      if(consistent.length<values.length)warnings.push('Brief unusual readings were filtered out.');
      for(const k of ['pitch','yaw','brightness']){
        const a=context.map(c=>c[k]).filter(Number.isFinite);
        if(a.length&&span(a)>(k==='brightness'?SCAN_RULES.maxBrightnessSpan:SCAN_RULES.maxPoseSpan))
          warnings.push(k==='brightness'?'Lighting varied during the scan.':'Head position varied during the scan.');
      }
      if(warnings.length)warningReason=warnings.join(' ')+' Treat this estimate with lower confidence.';
    }
    const reason=fatalReason||warningReason;
    const warnings=warningReason?warningReason.replace(' Treat this estimate with lower confidence.','').split('. ').map(v=>v.replace(/\.$/,'')).filter(Boolean).map(v=>v==='Some camera frames were unclear'?'Keep your face in the circle with even lighting.':v==='Brief unusual readings were filtered out'?'Hold still and keep a neutral expression.':v==='Lighting varied during the scan'?'Use steady light facing you.':'Keep your head facing the camera.'):[];
    const features=featureRows.length?Object.fromEntries(this.featureKeys.map(k=>[k,median(featureRows.map(r=>r[k]).filter(Number.isFinite))])):null;
    const featureStats=featureRows.length?Object.fromEntries(this.featureKeys.map(k=>{const a=featureRows.map(r=>r[k]).filter(Number.isFinite);return[k,{median:median(a),mad:mad(a)}];})):null;
    const finalScore=fatalReason?null:median(consistent.map(p=>p.value));
    const uncertainty=finalScore===null?null:1.4826*mad(values);
    const status=fatalReason?'failed':warningReason?'limited':'ok';
    return {quality:fatalReason?'poor':warningReason?'limited':'good',status,reason,failReason:fatalReason||'',warnings,average:finalScore,
      latest:fatalReason?null:points.at(-1)?.value??null,points,coveragePercent:100*coverage,features,
      featureStats,windowScores:points.map(p=>Number.isFinite(p.value)?p.value:null),range:finalScore===null?null:[Math.max(0,finalScore-uncertainty),Math.min(10,finalScore+uncertainty)],qualityFlags:{...this.qualityFlags},
      windowDiagnostics:{version:'derived-windows-1',contextScope:'Usable slot medians only; rejected or missing observations are not reconstructed.',windows:windowDiagnostics},
      consensusWindowMask:points.map(p=>consistent.some(c=>c.time===p.time)),
      coverageDetails:{version:'coverage-denominators-1',scope:'Processed observations after the first second; not all camera frames.',
        observedFrames:observations.length,validFrames:validObservations,
        validFramePercent:observations.length?100*validObservations/observations.length:null,
        occupiedSlots:slots.size,totalSlots:45,timeSlotOccupancyPercent:100*coverage},
      reliability:{usableSlots:slots.size,totalSlots:45,usableWindows:values.length,totalWindows:9,
        scoreSpread:spread,uncertaintySpread:uncertainty,halfDifference,consistentWindows:consistent.length,consensusHalfDifference:consensusDifference,ruleVersion:'window-quality-v3'}};
  }
}
