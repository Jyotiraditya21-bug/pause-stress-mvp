import { useEffect, useState } from "react";
import {windowTransparency,normalizeCoverageDetails} from '../resultTransparency.js';
import {deriveScanQuality} from '../scanQuality.js';

const BANDS = [
  { max: 3.5, tone: "low", label: "Low facial index", note: "Your facial geometry produced a lower index relative to the reference." },
  { max: 6.5, tone: "mid", label: "Mid-range facial index", note: "Your facial geometry produced an index near the reference midpoint." },
  { max: 10.01, tone: "high", label: "High facial index", note: "Your facial geometry produced a higher index relative to the reference." },
];

const ARC_LENGTH = Math.PI * 80;

function bandFor(score) {
  return BANDS.find((b) => score < b.max) || BANDS[BANDS.length - 1];
}

function Gauge({ score, tone }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(score));
    return () => cancelAnimationFrame(id);
  }, [score]);
  const offset = ARC_LENGTH * (1 - Math.max(0, Math.min(10, shown)) / 10);
  return (
    <div className={`pz-gauge pz-tone-${tone}`} role="img" aria-label={`Experimental Calm index ${score.toFixed(1)} out of 10`}>
      <svg viewBox="0 0 200 112" aria-hidden="true">
        <path className="pz-gauge-track" d="M 20 100 A 80 80 0 0 1 180 100" fill="none" strokeWidth="8" strokeLinecap="round" />
        <path className="pz-gauge-fill" d="M 20 100 A 80 80 0 0 1 180 100" fill="none" strokeWidth="8" strokeLinecap="round" strokeDasharray={ARC_LENGTH} strokeDashoffset={offset} />
      </svg>
      <div className="pz-gauge-readout"><div className="pz-score">{score.toFixed(1)}<small> /10</small></div></div>
    </div>
  );
}

function Trend({ windows, excluded=[] }) {
  const W = 300, H = 72, PAD = 6;
  const n = windows.length;
  const x = (i) => PAD + (n === 1 ? (W - 2 * PAD) / 2 : (i * (W - 2 * PAD)) / (n - 1));
  const y = (v) => H - PAD - (v / 10) * (H - 2 * PAD);
  const segments = []; let current = [];
  windows.forEach((v, i) => { if (v == null) { if (current.length) segments.push(current); current = []; } else current.push([x(i), y(v)]); });
  if (current.length) segments.push(current);
  return <div className="pz-spark-wrapper">
    <svg className="pz-spark" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Score for each second of the scan">
      <line className="pz-spark-ref" x1={PAD} x2={W - PAD} y1={y(5)} y2={y(5)} />
      {segments.map((seg, i) => seg.length === 1 ? <circle key={i} className="pz-spark-dot" cx={seg[0][0]} cy={seg[0][1]} r="3.5" /> : <polyline key={i} className="pz-spark-line" points={seg.map((p) => p.join(",")).join(" ")} />)}
      {excluded.map(index=><circle key={index} cx={x(index-1)} cy={y(windows[index-1])} r="4" fill="white" stroke="currentColor" strokeWidth="2"><title>{`Window ${index} excluded from final score`}</title></circle>)}
    </svg>
    <div className="pz-spark-legend" aria-hidden="true">
      <span className="legend-item"><i className="legend-mark legend-dot"/> Measured second</span>
      {excluded.length > 0 && <span className="legend-item"><i className="legend-mark legend-excluded"/> Excluded outlier</span>}
      <span className="legend-item"><i className="legend-mark legend-ref"/> Midpoint (5.0)</span>
    </div>
    <table className="sr-only">
      <caption>Per-second scan readings</caption>
      <thead>
        <tr><th scope="col">Second</th><th scope="col">Calm Index</th><th scope="col">Status</th></tr>
      </thead>
      <tbody>
        {windows.map((v, i) => (
          <tr key={i}>
            <td>Second {i + 1}</td>
            <td>{v != null ? `${v.toFixed(1)} /10` : 'Unavailable'}</td>
            <td>{excluded.includes(i + 1) ? 'Excluded outlier' : v != null ? 'Included' : 'Missing'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>;
}

export default function ResultCard({ status, score, windows = [], reason, warnings = [], consensusMask, coverageDetails, onRetry, onDone, caption, actions, children, qualityFlags = {}, range, coveragePercent }) {
  const transparency=windowTransparency(windows,consensusMask);
  coverageDetails=normalizeCoverageDetails(coverageDetails);

  const agreeingWindows = Array.isArray(consensusMask)
    ? consensusMask.filter(Boolean).length
    : windows.filter(Number.isFinite).length;
  const totalWindows = windows.length || 9;
  const covPercent = coveragePercent ?? (coverageDetails?.timeSlotOccupancyPercent ?? 0);
  const validObs = coverageDetails?.validFrames ?? 0;
  const totalObs = coverageDetails?.observedFrames ?? 0;

  const qualityInfo = deriveScanQuality({
    coveragePercent: covPercent,
    agreeingWindows,
    totalWindows,
    validFrames: validObs,
    observedFrames: totalObs,
    status: status === 'failed' || score == null ? 'failed' : status
  });

  const spread = Array.isArray(range) && range.length === 2 && Number.isFinite(range[0]) && Number.isFinite(range[1])
    ? Math.abs(range[1] - range[0])
    : transparency.observedRange
    ? Math.abs(transparency.observedRange[1] - transparency.observedRange[0])
    : null;

  const qf = qualityFlags || {};

  const qualityBlock = (
    <div className="scan-quality-block" style={{marginTop:'10px',marginBottom:'12px',paddingTop:'10px',borderTop:'1px solid var(--line)'}}>
      <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'4px'}}>
        <strong>Scan quality:</strong>
        <span className={`pz-chip ${qualityInfo.quality === 'good' ? '' : 'is-limited'}`}>
          <i aria-hidden="true" />{qualityInfo.label}
        </span>
      </div>
      <p className="pz-fineprint" style={{marginTop:0,marginBottom:'8px'}}>
        Higher scan quality means the measurement was steadier. It does not mean the score is more accurate about your stress.
      </p>

      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit, minmax(130px, 1fr))',gap:'8px',margin:'8px 0'}}>
        <div style={{background:'var(--mist)',padding:'6px 10px',borderRadius:'8px'}}>
          <span className="pz-fineprint" style={{display:'block'}}>Coverage</span>
          <strong>{qualityInfo.coveragePercent.toFixed(0)}%</strong>
        </div>
        <div style={{background:'var(--mist)',padding:'6px 10px',borderRadius:'8px'}}>
          <span className="pz-fineprint" style={{display:'block'}}>Agreeing windows</span>
          <strong>{qualityInfo.agreeingWindows} of {qualityInfo.totalWindows}</strong>
        </div>
        <div style={{background:'var(--mist)',padding:'6px 10px',borderRadius:'8px'}}>
          <span className="pz-fineprint" style={{display:'block'}}>Valid frames</span>
          <strong>{qualityInfo.observedFrames > 0 ? `${qualityInfo.validFrames}/${qualityInfo.observedFrames}` : 'Unavailable'}</strong>
        </div>
        <div style={{background:'var(--mist)',padding:'6px 10px',borderRadius:'8px'}}>
          <span className="pz-fineprint" style={{display:'block'}}>Within-scan spread</span>
          <strong>{spread != null ? `${spread.toFixed(1)} pts` : 'N/A'}</strong>
          <span className="pz-fineprint" style={{display:'block',fontSize:'10px',lineHeight:'1.2'}}>not a confidence interval</span>
        </div>
      </div>

      <div style={{display:'flex',flexWrap:'wrap',gap:'6px',margin:'8px 0'}}>
        <span className={`pz-chip ${qf.lowLight ? 'is-limited' : ''}`}><i aria-hidden="true"/>{qf.lowLight ? 'Low light' : 'Lighting steady'}</span>
        <span className={`pz-chip ${qf.tooFar || qf.tooClose ? 'is-limited' : ''}`}><i aria-hidden="true"/>{qf.tooFar ? 'Face too far' : qf.tooClose ? 'Face too close' : 'Face size steady'}</span>
        <span className={`pz-chip ${qf.pose ? 'is-limited' : ''}`}><i aria-hidden="true"/>{qf.pose ? 'Head turned' : 'Head pose centered'}</span>
        <span className={`pz-chip ${qf.moving ? 'is-limited' : ''}`}><i aria-hidden="true"/>{qf.moving ? 'Movement detected' : 'Movement minimal'}</span>
      </div>

      <details className="pz-fineprint" style={{marginTop:'6px',marginBottom:'6px'}}>
        <summary style={{cursor:'pointer'}}>How scan quality is calculated</summary>
        <p style={{margin:'4px 0 0'}}>
          Derived deterministically from coverage percentage, agreeing window count, and valid processed frame ratio. Good requires &gt;=80% coverage, &gt;=6 agreeing windows, and &gt;=75% valid frame ratio. Limited requires &gt;=40% coverage, &gt;=2 agreeing windows, and &gt;=40% valid frame ratio.
        </p>
      </details>
    </div>
  );

  const coverage=<section className="pz-panel">
    <h3>Acquisition details</h3>
    {qualityBlock}
    {coverageDetails?<>
      <p>Valid processed observations: {coverageDetails.validFramePercent==null?'Unavailable':`${coverageDetails.validFramePercent.toFixed(1)}%`} ({coverageDetails.validFrames}/{coverageDetails.observedFrames}).</p>
      <p>Time-slot occupancy: {coverageDetails.timeSlotOccupancyPercent.toFixed(1)}% ({coverageDetails.occupiedSlots}/{coverageDetails.totalSlots}).</p>
      <p>Counts cover processed observations after the first second, not every camera frame. Slot occupancy does not measure accuracy.</p>
    </>:<p>Observation-validity counts were not recorded for this saved scan. Legacy coverage is not a valid-frame percentage.</p>}
  </section>;

  if (status === "failed" || score == null) return <div className="pz-result">
    <section className="pz-fail" aria-live="polite"><h2>We couldn't get a reading</h2><p>{reason || "The camera didn't see your face clearly enough for long enough."}</p><p>Face a light source, keep your whole face in the circle, and stay still for 10 seconds.</p></section>
    <div className="pz-actions"><button className="pz-btn pz-btn-primary" onClick={onRetry}>Scan again</button></div>
    {coverage}
    {children}
  </div>;

  const band = bandFor(score), limited = status === "limited", usable = windows.filter((v) => v != null).length;
  return <div className="pz-result">
    <Gauge score={score} tone={band.tone} />
    <div className={`pz-tone-${band.tone}`} style={{ textAlign: "center" }}><div className="pz-band">{band.label}</div></div>
    <p className="pz-meaning">{band.note}</p>
    {caption}
    <div className={`pz-chip ${limited ? "is-limited" : ""}`}><i aria-hidden="true" />{limited ? "Acquisition limitations" : "Acquisition checks passed"} · {usable} of {windows.length || 9} windows measured</div>
    <section className="pz-panel"><h3>During your scan</h3><p>Each point is one second. The dashed line is the reference midpoint.</p><Trend windows={windows} excluded={transparency.excluded||[]} />
      {transparency.observedRange&&<p>Full observed window range: {transparency.observedRange[0].toFixed(1)}–{transparency.observedRange[1].toFixed(1)}.</p>}
      <p>{transparency.excluded===null?'Excluded-window positions were not recorded for this saved scan.':transparency.excluded.length?`Windows excluded from the final score: ${transparency.excluded.join(', ')} (outlined on the graph). Their measurements remain visible.`:'No measured windows were excluded from the final score.'}</p>
      <p>Within-scan variation describes dispersion, not a confidence interval, stress accuracy or consistency between scans.</p>
    </section>
    {coverage}
    {limited && warnings.length > 0 && <section className="pz-panel" aria-live="polite"><h3>For a steadier reading</h3><ul className="pz-tips">{warnings.map((w) => <li key={w}>{w}</li>)}</ul></section>}
    <div className="pz-actions">{actions||<><button className="pz-btn pz-btn-primary" onClick={onRetry}>Scan again</button>{onDone && <button className="pz-btn pz-btn-quiet" onClick={onDone}>Done</button>}</>}</div>
    {children}
    <p className="pz-fineprint">An experimental facial index, not a medical measurement or a measure of how stressed you feel. Video stays on your device.</p>
  </div>;
}
