import React from 'react';
import {groupCameraSessions,historyGroupKey} from '../cameraSessions.js';

function Trend({sessions}){
  const rows=[...sessions].filter(s=>Number.isFinite(s.average)).sort((a,b)=>new Date(a.created_at)-new Date(b.created_at));
  if(!rows.length)return null;
  const W=600,H=180,P=18,start=Date.parse(rows[0].created_at),end=Date.parse(rows.at(-1).created_at),x=i=>P+(end===start?(W-2*P)/2:(Date.parse(rows[i].created_at)-start)*(W-2*P)/(end-start)),y=v=>H-P-v/10*(H-2*P);
  return <><svg className="history-trend" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Saved Calm index trend by date"><line x1={P} x2={W-P} y1={y(5)} y2={y(5)} className="pz-spark-ref"/><polyline className="pz-spark-line" points={rows.map((r,i)=>`${x(i)},${y(r.average)}`).join(' ')}/>{rows.map((r,i)=><circle key={r.id} className="pz-spark-dot" cx={x(i)} cy={y(r.average)} r="5"/>)}</svg><div className="trend-dates"><span>{new Date(start).toLocaleString()}</span><span>{new Date(end).toLocaleString()}</span></div></>;
}

export default function HistoryPage({sessions,onView,onDelete,onScan}){
  return <main className="page history-page"><h1>History</h1>{!sessions.length?<section className="empty-state"><p>No saved scans yet. Run a scan and save it to see your trend.</p><button className="pz-btn pz-btn-primary" onClick={onScan}>Start 10-second scan</button></section>:<>
    <p className="mode-line">Trends only connect scans with the same algorithm and reference. Calibration scans are listed below separately.</p>
    {groupCameraSessions(sessions).map((rows,i)=><section className="pz-panel" key={historyGroupKey(rows[0])}><h2>{rows[0].mode==='baseline'?'Personal baseline':'Generic reference'} trend {i+1}</h2><p>{rows[0].acquisitionVersion==='legacy'?'Earlier scan method':rows[0].source.includes('tolerant')?'Movement-tolerant scan':'Standard scan'} · {rows[0].mode==='baseline'?(rows[0].baselineId?'Same saved personal reference':'Baseline identity unavailable; shown separately'):'Same generic face reference'}</p><Trend sessions={rows}/></section>)}
    <ul className="history-list">{sessions.map(session=><li key={session.id}><button className="history-view" onClick={()=>onView(session)}><strong>{Number.isFinite(session.average)?`${session.average.toFixed(1)} /10`:'Incomplete scan'}</strong><span>{new Date(session.created_at).toLocaleString()} · {session.mode==='calibration'?'Baseline calibration':session.mode==='baseline'?'vs. your baseline':'vs. generic reference'}</span></button><button className="pz-btn pz-btn-quiet" onClick={()=>onDelete(session.id)} aria-label={`Delete scan from ${new Date(session.created_at).toLocaleString()}`}>Delete</button></li>)}</ul>
  </>}</main>;
}
