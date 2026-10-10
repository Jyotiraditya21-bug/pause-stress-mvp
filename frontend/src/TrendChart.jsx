import React from 'react';

export default function TrendChart({sessions}) {
  const points=[...sessions].filter(s=>Number.isFinite(s.self_reported_stress)).sort((a,b)=>new Date(a.created_at)-new Date(b.created_at)).slice(-20);
  if(!points.length) return null;
  const first=Date.parse(points[0].created_at), last=Date.parse(points.at(-1).created_at);
  const x=s=>last===first ? 320 : 45+((Date.parse(s.created_at)-first)/(last-first))*540;
  const y=s=>220-s.self_reported_stress*18;
  const average=(points.reduce((sum,s)=>sum+s.self_reported_stress,0)/points.length).toFixed(1);
  return <section className="panel trend"><h2>Your reported stress over time</h2><p>Latest {points.length} check-ins. These are your ratings, not AI measurements or a diagnosis.</p>
    <div className="trend-stats"><p>Latest: <strong>{points.at(-1).self_reported_stress}/10</strong></p><p>Average shown: <strong>{average}/10</strong></p></div>
    <svg viewBox="0 0 640 265" role="img" aria-label={`Self-reported stress trend for ${points.length} check-ins. Latest rating ${points.at(-1).self_reported_stress} out of 10. Exact values are in the table below.`}>
      {[0,5,10].map(v=><g key={v}><line x1="45" x2="585" y1={220-v*18} y2={220-v*18} stroke="#dbe2d8"/><text x="18" y={225-v*18} fill="#506b61" fontSize="13">{v}</text></g>)}
      {points.length>1 && <polyline points={points.map(s=>`${x(s)},${y(s)}`).join(' ')} fill="none" stroke="#406e50" strokeWidth="3"/>}
      {points.map(s=><circle key={s.id} cx={x(s)} cy={y(s)} r="5" fill="#183b36"><title>{`${new Date(s.created_at).toLocaleString()}: ${s.self_reported_stress}/10`}</title></circle>)}
      <text x="45" y="250" fill="#506b61" fontSize="12">{new Date(first).toLocaleDateString()}</text><text x="585" y="250" textAnchor="end" fill="#506b61" fontSize="12">{new Date(last).toLocaleDateString()}</text>
    </svg>
    {points.length===1 && <p>Add another check-in to see change over time.</p>}
    <details><summary>View exact trend values</summary><table><caption>Self-reported stress, oldest to newest</caption><thead><tr><th scope="col">Check-in</th><th scope="col">Rating / 10</th></tr></thead><tbody>{points.map(s=><tr key={s.id}><td>{new Date(s.created_at).toLocaleString()}</td><td>{s.self_reported_stress}</td></tr>)}</tbody></table></details>
  </section>;
}
