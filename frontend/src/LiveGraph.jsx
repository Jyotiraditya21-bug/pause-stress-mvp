import React from 'react';

export default function LiveGraph({points=[],live=false}) {
  const end=Math.max(10,points.at(-1)?.time||0),x=t=>58+t/end*610,y=v=>240-v*20;
  const paths=[];let segment=[];let previous=null;
  for(const point of points) {
    if(!Number.isFinite(point.value) || (previous!==null && point.time-previous>1.6)) {if(segment.length) paths.push(segment);segment=[];}
    if(Number.isFinite(point.value)) segment.push(point);
    previous=point.time;
  }
  if(segment.length) paths.push(segment);
  return <section className="panel trend live-graph">
    <h2>{live ? 'Live facial index' : 'Facial index over this session'}</h2>
    <p><strong>Calm index:</strong> higher means less tension-like geometry relative to the selected reference.</p>
    <svg viewBox="0 0 740 300" role="img" aria-label="Experimental Calm index versus elapsed seconds. Gaps indicate unavailable readings.">
      {[0,2.5,5,7.5,10].map(v=><g key={v}><line x1="58" x2="668" y1={y(v)} y2={y(v)} stroke="#dbe2d8" strokeDasharray={v===5?'5 5':undefined}/><text x="40" y={y(v)+4} textAnchor="end" fill="#506b61" fontSize="12">{v}</text></g>)}
      {paths.map((path,i)=>path.length===1 ? <circle key={i} cx={x(path[0].time)} cy={y(path[0].value)} r="3" fill="#406e50"/> : <polyline key={i} points={path.map(p=>`${x(p.time)},${y(p.value)}`).join(' ')} fill="none" stroke="#406e50" strokeWidth="3"/>)}
      {[0,.5,1].map(r=><text key={r} x={x(end*r)} y="264" textAnchor={r===0?'start':r===1?'end':'middle'} fill="#506b61" fontSize="12">{Math.round(end*r)}s</text>)}
      <text x="360" y="288" textAnchor="middle" fill="#506b61" fontSize="12">Elapsed time</text>
      {!points.some(p=>Number.isFinite(p.value))&&<text x="360" y="135" textAnchor="middle" fill="#506b61" fontSize="13">No usable camera readings</text>}
    </svg>
    <p className="fine">Poor framing, speaking or extreme head pose can create gaps. No pulse/HRV is estimated.</p>
    {points.length>0&&<details><summary>View exact graph values</summary><div className="graph-table"><table><caption>Experimental facial index samples</caption><thead><tr><th scope="col">Seconds</th><th scope="col">Index / 10</th></tr></thead><tbody>{points.map((p,i)=><tr key={i}><td>{p.time.toFixed(1)}</td><td>{Number.isFinite(p.value)?p.value.toFixed(2):'Unavailable'}</td></tr>)}</tbody></table></div></details>}
  </section>;
}
