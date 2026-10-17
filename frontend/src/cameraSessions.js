const KEY='pause-camera-sessions-v2';
const score=value=>Number.isFinite(value)&&value>=0&&value<=10;
function validate(row){
  if(!row||typeof row!=='object'||typeof row.id!=='string'||!row.id||!Number.isFinite(Date.parse(row.created_at))||!score(row.average))return null;
  if(row.status&&!['ok','limited'].includes(row.status))return null;
  return {...row,
    mode:['generic','baseline','calibration'].includes(row.mode)?row.mode:'generic',
    algoVersion:typeof row.algoVersion==='string'?row.algoVersion:'unknown',
    source:typeof row.source==='string'?row.source:'legacy',
    baselineId:typeof row.baselineId==='string'?row.baselineId:null,
    acquisitionVersion:typeof row.acquisitionVersion==='string'?row.acquisitionVersion:'legacy',
    windowScores:(Array.isArray(row.windowScores)?row.windowScores:[]).map(v=>score(v)?v:null),
    range:Array.isArray(row.range)&&row.range.length===2&&row.range.every(score)&&row.range[0]<=row.range[1]?row.range:null,
    qualityFlags:row.qualityFlags&&typeof row.qualityFlags==='object'?row.qualityFlags:{},
    warnings:Array.isArray(row.warnings)?row.warnings.filter(v=>typeof v==='string'):[],
    tier:['NORMAL','LIMITED'].includes(row.tier)?row.tier:null,
    confidence:Number.isFinite(row.confidence)?Math.max(0,Math.min(1,row.confidence)):0,
    windowFeaturesUsed:Array.isArray(row.windowFeaturesUsed)?row.windowFeaturesUsed.filter(Number.isFinite):[],
    coveragePercent:Number.isFinite(row.coveragePercent)?Math.max(0,Math.min(100,row.coveragePercent)):0,
  };
}
// Reading never rewrites damaged data. Recovery explicitly backs it up first.
export function readCameraSessionState(){
  try{
    const parsed=JSON.parse(localStorage.getItem(KEY)||'[]');
    if(!Array.isArray(parsed))return{sessions:[],invalidCount:0,unreadable:true};
    const sessions=[],seen=new Set();let invalidCount=0;
    for(const row of parsed){const valid=validate(row);if(valid&&!seen.has(valid.id)){sessions.push(valid);seen.add(valid.id);}else invalidCount++;}
    return{sessions,invalidCount,unreadable:false};
  }catch{return{sessions:[],invalidCount:0,unreadable:true};}
}
export function readCameraSessions(){return readCameraSessionState().sessions;}
function writableRows(){
  const state=readCameraSessionState();
  if(state.unreadable||state.invalidCount)throw new Error('Recover saved history before making changes.');
  return state.sessions;
}
export function saveCameraSession(session){
  const valid=validate(session);if(!valid)throw new Error('Invalid scan result.');
  const rows=writableRows();if(rows.some(r=>r.id===valid.id))return;
  localStorage.setItem(KEY,JSON.stringify([valid,...rows]));
}
export function deleteCameraSession(id){localStorage.setItem(KEY,JSON.stringify(writableRows().filter(r=>r.id!==id)));}
export function repairCameraSessions(){
  const state=readCameraSessionState(),raw=localStorage.getItem(KEY);
  if(!raw)return;
  // A failed backup leaves the original untouched. Preserve earlier backups too.
  localStorage.setItem(`${KEY}.recovery.${Date.now()}.${crypto.randomUUID()}`,raw);
  localStorage.setItem(KEY,JSON.stringify(state.sessions));
}
export function deleteRecoveryBackups(){
  const keys=Object.keys(localStorage).filter(key=>key.startsWith(`${KEY}.recovery.`));
  for(const key of keys)localStorage.removeItem(key);
}
export function historyGroupKey(row){
  const reference=row.mode==='baseline'?(row.baselineId||`unknown-${row.id}`):row.mode;
  return JSON.stringify([row.source,row.algoVersion,row.acquisitionVersion||'legacy',reference]);
}
export function groupCameraSessions(sessions){
  const groups=new Map();
  for(const row of sessions){if(row.mode==='calibration')continue;const key=historyGroupKey(row);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(row);}
  return [...groups.values()];
}
