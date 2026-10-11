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

export class ScanReliability {
  constructor(keys,score){this.keys=keys;this.score=score;this.slots=new Map();this.lastTime=-Infinity;}
  add(time,row,context={}) {
    if(!Number.isFinite(time)||time<=this.lastTime||time<0||time>=SCAN_RULES.duration)return false;
    this.lastTime=time;
    if(time<SCAN_RULES.settling)return false;
    const slot=Math.min(44,Math.floor((time-SCAN_RULES.settling)/SCAN_RULES.slotSeconds+1e-8));
    const samples=this.slots.get(slot)||[];
    // Store invalid observations too: a brief good frame cannot bless a bad slot.
    samples.push(row&&this.keys.every(k=>Number.isFinite(row[k]))?{row,context}:null);
    this.slots.set(slot,samples);
    return true;
  }
  usableSlots() {
    const slots=new Map();
    for(const [i,samples] of this.slots){
      const valid=samples.filter(Boolean);
      if(!valid.length)continue;
      const row=Object.fromEntries(this.keys.map(k=>[k,median(valid.map(s=>s.row[k]))]));
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
    const slots=this.usableSlots(),points=[],context=[],featureRows=[];
    for(let window=0;window<9;window++){
      const block=[];
      for(let i=window*5;i<(window+1)*5;i++)if(slots.has(i))block.push(slots.get(i));
      let value=null;
      if(block.length>=2){
        const row=Object.fromEntries(this.keys.map(k=>[k,median(block.map(s=>s.row[k]))]));
        value=this.score({...row,time:window+1.5});
        featureRows.push(row);
      }
      context.push(...block.map(s=>s.context));
      points.push({time:window+1.5,value});
    }
    const values=points.map(p=>p.value).filter(Number.isFinite),coverage=slots.size/45;
    const first=points.slice(0,4).map(p=>p.value).filter(Number.isFinite);
    const last=points.slice(5).map(p=>p.value).filter(Number.isFinite);
    const spread=values.length?span(values):null;
    const halfDifference=first.length&&last.length?Math.abs(median(first)-median(last)):null;
    let fatalReason='';
    let warningReason='';
    if(coverage<.35||values.length<3)
      fatalReason='Not enough clear, steady camera signal. Keep your face centred and try again.';
    else if(spread>SCAN_RULES.maxScoreSpread||halfDifference===null||halfDifference>SCAN_RULES.maxHalfDifference)
      fatalReason='The readings changed too much during this scan. Keep your expression relaxed and try again.';
    else {
      for(const k of ['pitch','yaw','brightness']){
        const a=context.map(c=>c[k]).filter(Number.isFinite);
        if(a.length&&span(a)>(k==='brightness'?SCAN_RULES.maxBrightnessSpan:SCAN_RULES.maxPoseSpan)){
          fatalReason=k==='brightness'?'Lighting changed during the scan. Use steady front lighting and retry.':'Head position changed during the scan. Face straight ahead and retry.';break;
        }
      }
    }
    if(!fatalReason && (coverage<SCAN_RULES.minCoverage||values.length<SCAN_RULES.minWindows)){
      warningReason='Slight movement during scan. The reading may be less stable.';
    }
    const reason=fatalReason||warningReason;
    const features=featureRows.length?Object.fromEntries(this.keys.map(k=>[k,median(featureRows.map(r=>r[k]))])):null;
    return {quality:reason?'poor':'good',reason,average:fatalReason?null:median(values),
      latest:fatalReason?null:points.at(-1)?.value??null,points,coveragePercent:100*coverage,features,
      reliability:{usableSlots:slots.size,totalSlots:45,usableWindows:values.length,totalWindows:9,
        scoreSpread:spread,halfDifference,ruleVersion:'window-quality-v1'}};
  }
}
