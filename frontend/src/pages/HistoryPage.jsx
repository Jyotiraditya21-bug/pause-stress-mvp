function Trend({sessions}){
  const rows=[...sessions].filter(s=>Number.isFinite(s.average)).sort((a,b)=>new Date(a.created_at)-new Date(b.created_at));
  if(!rows.length)return null;
  const W=600,H=180,P=18,x=i=>P+(rows.length===1?(W-2*P)/2:i*(W-2*P)/(rows.length-1)),y=v=>H-P-v/10*(H-2*P);
  return <svg className="history-trend" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Saved Calm index trend by date"><line x1={P} x2={W-P} y1={y(5)} y2={y(5)} className="pz-spark-ref"/><polyline className="pz-spark-line" points={rows.map((r,i)=>`${x(i)},${y(r.average)}`).join(' ')}/>{rows.map((r,i)=><circle key={r.id} className="pz-spark-dot" cx={x(i)} cy={y(r.average)} r="5"/>)}</svg>;
}

export default function HistoryPage({sessions,onView,onDelete,onScan}){
  return <main className="page history-page"><h1>History</h1>{!sessions.length?<section className="empty-state"><p>No saved scans yet. Run a scan and save it to see your trend.</p><button className="pz-btn pz-btn-primary" onClick={onScan}>Start 10-second scan</button></section>:<>
    <section className="pz-panel"><h2>Your Calm index trend</h2><Trend sessions={sessions}/></section>
    <ul className="history-list">{sessions.map(session=><li key={session.id}><button className="history-view" onClick={()=>onView(session)}><strong>{Number.isFinite(session.average)?`${session.average.toFixed(1)} /10`:'Incomplete scan'}</strong><span>{new Date(session.created_at).toLocaleString()} · {session.mode==='calibration'?'Baseline calibration':session.mode==='baseline'?'vs. your baseline':'vs. average face'}</span></button><button className="pz-btn pz-btn-quiet" onClick={()=>onDelete(session.id)} aria-label={`Delete scan from ${new Date(session.created_at).toLocaleString()}`}>Delete</button></li>)}</ul>
  </>}</main>;
}
