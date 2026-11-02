import React from 'react';
import {groupCameraSessions,historyGroupKey} from '../cameraSessions.js';
import {computeGroupInsights} from '../historyInsights.js';

function exportHistory(sessions) {
  const url = URL.createObjectURL(new Blob([JSON.stringify({version: 1, exported_at: new Date().toISOString(), sessions}, null, 2)], {type: 'application/json'}));
  const link = document.createElement('a'); link.href = url; link.download = 'pause-history.json'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function GroupStats({ rows }) {
  const insights = computeGroupInsights(rows);
  if (!insights) return null;

  return (
    <div className="history-group-stats" style={{marginTop:'10px',marginBottom:'12px'}}>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit, minmax(130px, 1fr))',gap:'8px',marginBottom:'8px'}}>
        <div style={{background:'var(--mist)',padding:'6px 10px',borderRadius:'8px'}}>
          <span className="pz-fineprint" style={{display:'block'}}>Scans &amp; Days</span>
          <strong>{insights.scansSaved} scans</strong> · {insights.daysWithScans} {insights.daysWithScans === 1 ? 'day' : 'days'}
          <span className="pz-fineprint" style={{display:'block',fontSize:'10px',lineHeight:'1.2'}}>{insights.dateRange}</span>
        </div>
        <div style={{background:'var(--mist)',padding:'6px 10px',borderRadius:'8px'}}>
          <span className="pz-fineprint" style={{display:'block'}}>Median Calm index</span>
          <strong>{insights.medianScore != null ? insights.medianScore.toFixed(1) : 'N/A'}</strong>
          <span className="pz-fineprint" style={{display:'block',fontSize:'10px',lineHeight:'1.2'}}>
            MAD: {insights.madScore != null ? `±${insights.madScore.toFixed(1)}` : 'N/A'}
          </span>
        </div>
        <div style={{background:'var(--mist)',padding:'6px 10px',borderRadius:'8px'}}>
          <span className="pz-fineprint" style={{display:'block'}}>Repeat consistency</span>
          <strong>{insights.repeatConsistency != null ? `±${insights.repeatConsistency.toFixed(1)} pts` : 'Not enough repeat scans yet'}</strong>
          <span className="pz-fineprint" style={{display:'block',fontSize:'10px',lineHeight:'1.2'}}>
            {insights.repeatPairsCount >= 3 ? `${insights.repeatPairsCount} pairs ≤30m` : `${insights.repeatPairsCount}/3 pairs ≤30m`}
          </span>
        </div>
        <div style={{background:'var(--mist)',padding:'6px 10px',borderRadius:'8px'}}>
          <span className="pz-fineprint" style={{display:'block'}}>Good quality share</span>
          <strong>{Math.round(insights.goodQualityShare)}%</strong>
          <span className="pz-fineprint" style={{display:'block',fontSize:'10px',lineHeight:'1.2'}}>met acquisition checks</span>
        </div>
      </div>
      <details className="pz-fineprint" style={{marginTop:'6px',marginBottom:'6px'}}>
        <summary style={{cursor:'pointer'}}>About these group metrics</summary>
        <p style={{margin:'4px 0 0'}}>
          Metrics summarize scans within this specific algorithm and reference group. Median and MAD (median absolute deviation) describe the central value and typical variation. Repeat-scan consistency measures the median difference between scans taken within 30 minutes of each other (requires at least 3 pairs). Quality share is the percentage of scans meeting Good acquisition standards.
        </p>
      </details>
    </div>
  );
}

function Trend({sessions}){
  const rows=[...sessions].filter(s=>Number.isFinite(s.average)).sort((a,b)=>new Date(a.created_at)-new Date(b.created_at));
  if(!rows.length)return null;
  const W=600,H=180,P=18,start=Date.parse(rows[0].created_at),end=Date.parse(rows.at(-1).created_at),x=i=>P+(end===start?(W-2*P)/2:(Date.parse(rows[i].created_at)-start)*(W-2*P)/(end-start)),y=v=>H-P-v/10*(H-2*P);
  return <>
    <svg className="history-trend" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Saved Calm index trend by date">
      <line x1={P} x2={W-P} y1={y(5)} y2={y(5)} className="pz-spark-ref"/>
      <polyline className="pz-spark-line" points={rows.map((r,i)=>`${x(i)},${y(r.average)}`).join(' ')}/>
      {rows.map((r,i)=><circle key={r.id} className="pz-spark-dot" cx={x(i)} cy={y(r.average)} r="5"/>)}
    </svg>
    <div className="trend-dates">
      <span>{new Date(start).toLocaleString()}</span>
      <span>{new Date(end).toLocaleString()}</span>
    </div>
    <table className="sr-only">
      <caption>Saved Calm index data points</caption>
      <thead>
        <tr><th scope="col">Date and time</th><th scope="col">Calm index</th></tr>
      </thead>
      <tbody>
        {rows.map(r=><tr key={r.id}><td>{new Date(r.created_at).toLocaleString()}</td><td>Score: {r.average.toFixed(1)}</td></tr>)}
      </tbody>
    </table>
  </>;
}

export default function HistoryPage({sessions,onView,onDelete,onScan}){
  return <main className="page history-page">
    <div className="history-header">
      <h1>History</h1>
      {sessions.length > 0 && (
        <button className="pz-btn pz-btn-quiet export-btn" onClick={()=>exportHistory(sessions)}>Export saved results</button>
      )}
    </div>
    {!sessions.length ? (
      <section className="empty-state">
        <p>No saved scans yet. Run a scan and save it to see your trend.</p>
        <button className="pz-btn pz-btn-primary" onClick={onScan}>Start 10-second scan</button>
      </section>
    ) : (
      <>
        <p className="mode-line">Trends only connect scans with the same algorithm and reference. Calibration scans are listed below separately.</p>
        {groupCameraSessions(sessions).map((rows,i)=>(
          <section className="pz-panel" key={historyGroupKey(rows[0])}>
            <h2>{rows[0].mode==='baseline'?'Personal baseline':'Generic reference'} trend {i+1}</h2>
            <p>{rows[0].acquisitionVersion==='capture-clock-prospective-1'?'Prospective standard scan (unvalidated)':rows[0].acquisitionVersion==='legacy'?'Earlier scan method':rows[0].source.includes('tolerant')?'Movement-tolerant scan':'Standard scan'} · {rows[0].mode==='baseline'?(rows[0].baselineId?'Same saved personal reference':'Baseline identity unavailable; shown separately'):'Same generic face reference'}</p>
            <GroupStats rows={rows} />
            <Trend sessions={rows}/>
          </section>
        ))}
        <ul className="history-list">{sessions.map(session=><li key={session.id}><button className="history-view" onClick={()=>onView(session)}><strong>{Number.isFinite(session.average)?`${session.average.toFixed(1)} /10`:'Incomplete scan'}</strong><span>{new Date(session.created_at).toLocaleString()} · {session.mode==='calibration'?'Baseline calibration':session.mode==='baseline'?'vs. your baseline':'vs. generic reference'}</span></button><button className="pz-btn pz-btn-quiet" onClick={()=>onDelete(session.id)} aria-label={`Delete scan from ${new Date(session.created_at).toLocaleString()}`}>Delete</button></li>)}</ul>
      </>
    )}
  </main>;
}
