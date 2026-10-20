import {useEffect,useState} from 'react';
import {STUDY_KEY,pairTiming,derivedStudyRecord} from '../guidedStudy.js';
function read(){
  try{const s=JSON.parse(localStorage.getItem(STUDY_KEY)||'{"pairs":[]}');
    if(!Array.isArray(s.pairs)||s.pairs.some(p=>!p||typeof p.id!=='string'||!Array.isArray(p.records)))throw Error('Invalid local study log');
    return {data:s,error:''};
  }catch{return {data:{pairs:[]},error:'The existing study log could not be read. It was preserved; no new records will overwrite it.'};}
}
export default function GuidedStudy({result,onStart}){
  const [state,setState]=useState(read),[subject,setSubject]=useState('P001'),[condition,setCondition]=useState('rest'),[now,setNow]=useState(Date.now());
  const current=state.data.pairs.at(-1),timing=pairTiming(current?.records||[],now);
  function persist(data){try{localStorage.setItem(STUDY_KEY,JSON.stringify(data));setState({data,error:''});}catch{setState(s=>({...s,error:'Local study save failed. Prior records were preserved; stop the study and check storage.'}));}}
  useEffect(()=>{const id=setInterval(()=>setNow(Date.now()),1000);return()=>clearInterval(id);},[]);
  useEffect(()=>{
    if(!current||state.error||!result)return;
    const r=derivedStudyRecord(result);
    if(!r||Date.parse(r.created_at)<Date.parse(current.started_at)||current.records.some(v=>v.id===r.id))return;
    persist({...state.data,pairs:state.data.pairs.map(p=>p.id===current.id?{...p,records:[...p.records,r]}:p)});
  },[result,current?.id]);
  function begin(){if(state.error||!subject.trim())return;
    persist({...state.data,pairs:[...state.data.pairs,{id:crypto.randomUUID(),subject_id:subject.trim(),condition,started_at:new Date().toISOString(),consent:'Begin button: local derived outcomes including failures; no raw media or uploads',records:[]}]});
  }
  function download(){const blob=new Blob([JSON.stringify(state.data,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='pause-local-study.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  return <section className="pz-panel guided-study" style={{margin:'1rem auto',maxWidth:760}} aria-label="Guided participant study">
    <h2>Guided local study · unvalidated candidate</h2>
    <p>Beginning a pair consents to saving derived scores, quality measurements, task labels and failed attempts in this browser. No video, images or landmarks are saved or uploaded. Each participant must consent. Keep the camera, lighting and expression consistent.</p>
    {state.error&&<p role="alert">{state.error}</p>}
    <label>Participant pseudonym <input value={subject} onChange={e=>setSubject(e.target.value)}/></label>{' '}
    <label>Task <select value={condition} onChange={e=>setCondition(e.target.value)}><option value="rest">Rest</option><option value="speech">Neutral speech</option><option value="arithmetic">Arithmetic</option></select></label>
    <p><button className="pz-btn pz-btn-quiet" disabled={!!state.error||!subject.trim()} onClick={begin}>Begin new pair and save derived outcomes locally</button></p>
    {current&&<><p>Active pair: {current.subject_id} · {current.condition}. Completed attempts: {current.records.length} (target: 2). Every completed attempt counts, including failures.</p>
      {timing.stage==='first'&&<p>Complete scan A, then keep this page open. The timer starts at its completion; no need to save again for the study log.</p>}
      {timing.stage==='waiting'&&<p role="status">Wait for the repeat window. Target repeat in {Math.floor(timing.remaining/60)}:{String(timing.remaining%60).padStart(2,'0')} (7 minutes after scan A). Scan B is eligible from 5–10 minutes.</p>}
      {timing.stage==='repeat'&&<p role="status">Repeat window is open. Complete scan B before 10 minutes have elapsed since scan A.</p>}
      {timing.stage==='expired'&&<p>Repeat window expired. Preserve this incomplete pair; begin a new pair when ready.</p>}
      {timing.stage==='complete'&&<p>Pair recorded. Interval: {Math.round(timing.elapsed)} seconds. Timing: {timing.elapsed>=300&&timing.elapsed<=600?'within protocol':'outside protocol'}. This does not establish reliability or stress accuracy.</p>}
      <button className="pz-btn pz-btn-primary" disabled={!timing.canStart||!!state.error} onClick={onStart}>{timing.stage==='first'?'Open scan A':'Open scan B'}</button>
    </>}
    <button className="pz-btn pz-btn-quiet" onClick={download}>Download derived study log</button>
    <p>The ordinary Scan navigation remains available; off-protocol attempts are retained and flagged, never treated as valid timed pairs.</p>
  </section>;
}
