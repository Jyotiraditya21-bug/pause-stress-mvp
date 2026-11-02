import React, { useState, useEffect } from 'react';

const CLAIMS = [
  {
    claim: 'Score is computed on-device, deterministically',
    status: 'Tested',
    statusTone: 'tested',
    evidence: 'Unit + repeatability regression + parity tests in CI'
  },
  {
    claim: 'Scan acquisition handles movement/lighting/pose',
    status: 'Tested',
    statusTone: 'tested',
    evidence: 'Playwright tolerance suite'
  },
  {
    claim: 'Score reflects self-reported stress',
    status: 'Not yet validated',
    statusTone: 'not-validated',
    evidence: 'No empirical participant calibration study yet'
  },
  {
    claim: 'Repeatable across minutes/days in real users',
    status: 'Not yet measured',
    statusTone: 'unmeasured',
    evidence: <span>Participant study pending (<a href="?study=1&policy=prospective-1">Guided Study protocol</a>)</span>
  },
  {
    claim: 'Clinical validity',
    status: 'Not validated',
    statusTone: 'not-validated',
    evidence: 'Non-clinical wellbeing tool; not a medical device or diagnostic instrument'
  },
  {
    claim: 'Fairness across skin tone / device / lighting',
    status: 'Not yet evaluated',
    statusTone: 'unmeasured',
    evidence: 'Independent multi-demographic dataset evaluation pending'
  },
  {
    claim: 'Optional neural comparator',
    status: 'Historical',
    statusTone: 'unmeasured',
    evidence: 'Historical acted dataset benchmark: ROC-AUC 0.906 (95% CI 0.860–0.959), accuracy 79.39% on RAVDESS acted expressions across 1,344 videos and six checkpoints. Explicitly does not apply to the visible score or to live experienced stress.'
  }
];

export function PrivacyPage(){
  return <main className="page info-page">
    <h1>Privacy</h1>
    <p>Pause processes your camera feed in your browser while you scan. No video, audio or face landmarks are uploaded or stored by default. Camera access stops when the scan ends or you cancel. The optional guided study saves derived records only after separate consent. Exporting results downloads a file to your device. Saved results stay in this browser only; clearing site data removes them. If you recover damaged history, the original data is backed up on this device. That copy may include scans later deleted from History; remove it using Delete recovery backups in Settings. The GitHub Pages release has analytics and error reporting disabled. The site host still receives ordinary asset requests and may keep access logs; scans are processed locally. Fonts are hosted with the app. Local history is not encrypted. Other deployments that enable monitoring must review their privacy notice before collecting error reports.</p>
  </main>;
}

export function AboutPage(){
  const [evidence, setEvidence] = useState(null);
  const [changelog, setChangelog] = useState([]);
  const [copiedAsset, setCopiedAsset] = useState(null);

  useEffect(() => {
    fetch('./evidence.json')
      .then(res => res.ok ? res.json() : null)
      .then(data => setEvidence(data))
      .catch(() => {});

    fetch('./changelog.json')
      .then(res => res.ok ? res.json() : [])
      .then(data => Array.isArray(data) ? setChangelog(data) : [])
      .catch(() => {});
  }, []);

  const copyHash = (name, hash) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(hash).then(() => {
        setCopiedAsset(name);
        setTimeout(() => setCopiedAsset(null), 1500);
      }).catch(() => {});
    }
  };

  return <main className="page info-page">
    <h1>About this index</h1>
    <p>The Calm index is an experimental number from 0 to 10 based on the shape of your face during a 10-second scan. Higher means your face showed less tension-like geometry compared with a reference. It is not a medical or psychological measurement and cannot tell how stressed you feel. Lighting, camera angle, expression and the shape of your face all affect it. Use similar lighting and camera position when comparing scans. Similar conditions do not guarantee similar scores. The optional neural classifier is a separate experimental image model; its image-test accuracy does not establish live stress accuracy.</p>

    <section className="pz-panel" style={{marginTop:'24px'}}>
      <h2>Evidence and validation status</h2>
      <p className="pz-fineprint">
        We believe transparency builds trust. Below is an honest audit of tested capabilities, unvalidated claims, release build metadata, and privacy guarantees.
      </p>

      {/* 4a. Validation Status Table */}
      <h3 style={{marginTop:'16px'}}>Scientific &amp; Technical Claims</h3>
      <div style={{overflowX:'auto'}}>
        <table style={{width:'100%',borderCollapse:'collapse',fontSize:'13px',marginTop:'8px'}}>
          <thead>
            <tr style={{borderBottom:'1px solid var(--line)',textAlign:'left'}}>
              <th scope="col" style={{padding:'6px 8px'}}>Claim</th>
              <th scope="col" style={{padding:'6px 8px'}}>Status</th>
              <th scope="col" style={{padding:'6px 8px'}}>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {CLAIMS.map((row, idx) => {
              const bg = row.statusTone === 'tested' ? 'var(--tide-soft)' : row.statusTone === 'unmeasured' ? 'var(--amber-soft)' : 'var(--rose-soft)';
              const dot = row.statusTone === 'tested' ? 'var(--tide)' : row.statusTone === 'unmeasured' ? 'var(--amber)' : 'var(--rose)';
              return (
                <tr key={idx} style={{borderBottom:'1px solid var(--line)'}}>
                  <td style={{padding:'8px',fontWeight:500}}>{row.claim}</td>
                  <td style={{padding:'8px',whiteSpace:'nowrap'}}>
                    <span className="pz-chip" style={{background:bg,color:'var(--ink)',padding:'4px 8px'}}>
                      <i aria-hidden="true" style={{background:dot}}/>{row.status}
                    </span>
                  </td>
                  <td style={{padding:'8px',color:'var(--ink-soft)'}}>{row.evidence}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* 4b. Release and Test Evidence */}
      <h3 style={{marginTop:'20px'}}>Release &amp; Build Evidence</h3>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit, minmax(130px, 1fr))',gap:'8px',margin:'10px 0'}}>
        <div style={{background:'var(--mist)',padding:'8px 10px',borderRadius:'8px'}}>
          <span className="pz-fineprint" style={{display:'block'}}>App version</span>
          <strong>v{evidence?.appVersion || '0.1.0'}</strong> · <code>{evidence?.commit || 'local'}</code>
        </div>
        <div style={{background:'var(--mist)',padding:'8px 10px',borderRadius:'8px'}}>
          <span className="pz-fineprint" style={{display:'block'}}>Automated tests</span>
          <strong>{evidence?.tests?.unitTestCount != null ? `${evidence.tests.unitTestCount} unit` : 'Not yet measured'}</strong>
          <span className="pz-fineprint" style={{display:'block',fontSize:'10px',lineHeight:'1.2'}}>
            {evidence?.tests?.playwrightSpecCount != null ? `${evidence.tests.playwrightSpecCount} e2e specs` : ''} · {evidence?.tests?.axeStatus || 'Axe checked'}
          </span>
        </div>
        <div style={{background:'var(--mist)',padding:'8px 10px',borderRadius:'8px'}}>
          <span className="pz-fineprint" style={{display:'block'}}>Lighthouse CI</span>
          <strong>{evidence?.lighthouse ? `Perf ${(evidence.lighthouse.performance * 100).toFixed(0)} · A11y ${(evidence.lighthouse.accessibility * 100).toFixed(0)}` : 'Not measured for this build'}</strong>
          <span className="pz-fineprint" style={{display:'block',fontSize:'10px',lineHeight:'1.2'}}>
            {evidence?.lighthouse ? `Best ${(evidence.lighthouse.bestPractices * 100).toFixed(0)} · SEO ${(evidence.lighthouse.seo * 100).toFixed(0)}` : 'Local/preview build'}
          </span>
        </div>
      </div>

      {/* Model & Asset Checksums */}
      <h4 style={{marginTop:'14px',marginBottom:'6px'}}>Frozen Asset Checksums (SHA-256)</h4>
      <p className="pz-fineprint" style={{marginTop:0}}>
        Model weights, WASM runtimes, and engineering configurations are cryptographically verified before build.
      </p>
      <ul style={{listStyle:'none',padding:0,margin:'8px 0',fontSize:'12px'}}>
        {(evidence?.releaseAssets || []).slice(0, 6).map(asset => (
          <li key={asset.name} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'4px 0',borderBottom:'1px dashed var(--line)'}}>
            <span><code>{asset.name}</code></span>
            <span>
              <code style={{fontSize:'11px'}}>{asset.sha256.slice(0, 12)}…</code>
              <button
                type="button"
                className="pz-btn pz-btn-quiet"
                style={{padding:'2px 6px',fontSize:'11px',marginLeft:'6px'}}
                onClick={() => copyHash(asset.name, asset.sha256)}
                aria-label={`Copy SHA-256 for ${asset.name}`}
              >
                {copiedAsset === asset.name ? 'Copied' : 'Copy'}
              </button>
            </span>
          </li>
        ))}
      </ul>

      {/* 4d. Researcher Section */}
      <details className="pz-panel" style={{marginTop:'16px',background:'var(--mist)',borderRadius:'12px',padding:'12px 14px'}}>
        <summary style={{fontWeight:600,cursor:'pointer'}}>For Researchers: Methodology &amp; Guided Study</summary>
        <div style={{marginTop:'8px',fontSize:'13px',lineHeight:1.5}}>
          <p><strong>Pipeline methodology (deterministic 7-step sequence):</strong></p>
          <ol style={{paddingLeft:'18px',margin:'6px 0'}}>
            <li><strong>Landmark extraction:</strong> 478 3D landmarks via on-device MediaPipe Face Landmarker.</li>
            <li><strong>Geometric alignment:</strong> 2D similarity transform invariance with 3D matrix frontalization.</li>
            <li><strong>4 geometric channels:</strong> Brow furrow, lip press, lip corner depression, and jaw clench proxy.</li>
            <li><strong>Reference z-scoring:</strong> Normalization against generic 3D reference (or personal calm baseline).</li>
            <li><strong>Sigmoid mapping:</strong> Scaled to a continuous 0–10 index where 10 indicates relaxed geometry.</li>
            <li><strong>Independent temporal windows:</strong> Aggregated into 1-second independent windows.</li>
            <li><strong>Outlier consensus &amp; median:</strong> Outlier filtering discards transient spikes; final index is the median.</li>
          </ol>
          <p style={{margin:'8px 0'}}>
            Researchers can launch the <a href="?study=1&policy=prospective-1">Guided Study Protocol</a> to collect structured repeat-scan data across rest and cognitive tasks under explicit consent. Empirical validation results will be published directly in this section when finalized.
          </p>
        </div>
      </details>

      {/* 4e. Support, Changelog, and Privacy Facts */}
      <h3 style={{marginTop:'20px'}}>Accountability &amp; Support</h3>
      <p className="pz-fineprint">
        Found an incorrect reading or have a privacy concern? Open an issue on our GitHub repository:
      </p>
      <p style={{marginTop:'4px'}}>
        <a href={evidence?.support?.githubIssuesUrl || 'https://github.com/jyotiraditya21-bug/pause-stress-mvp/issues'} target="_blank" rel="noopener noreferrer">
          GitHub Issue Tracker
        </a>
        {evidence?.support?.contactEmail && <> · <a href={`mailto:${evidence.support.contactEmail}`}>{evidence.support.contactEmail}</a></>}
      </p>

      <h4 style={{marginTop:'14px',marginBottom:'6px'}}>Privacy Guarantees</h4>
      <ul className="pz-fineprint" style={{paddingLeft:'16px',margin:'6px 0'}}>
        <li>Zero video or audio recorded, uploaded, or transmitted from your device.</li>
        <li>Derived results are stored locally only if you tap "Save this result".</li>
        <li>Browser local storage is not encrypted; clear your browser site data at any time to delete all records.</li>
        <li>GitHub Pages receives standard web server request logs when downloading static application assets.</li>
      </ul>

      {changelog.length > 0 && (
        <details className="pz-fineprint" style={{marginTop:'14px'}}>
          <summary style={{cursor:'pointer',fontWeight:500}}>Recent Changes (Changelog)</summary>
          <div style={{marginTop:'6px'}}>
            {changelog.slice(0, 4).map(entry => (
              <div key={entry.version} style={{marginBottom:'8px'}}>
                <strong>v{entry.version} ({entry.date})</strong>
                <ul style={{paddingLeft:'16px',margin:'2px 0'}}>
                  {entry.changes.map((c, i) => <li key={i}>{c}</li>)}
                </ul>
              </div>
            ))}
          </div>
        </details>
      )}

      <p className="pz-fineprint" style={{marginTop:'14px',color:'var(--ink-soft)'}}>
        Page last updated: {evidence?.lastUpdated || '2026-11-02'}
      </p>
    </section>
  </main>;
}
