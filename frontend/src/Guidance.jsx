import {api, browserOnly} from './api';
import React, {useState} from 'react';
const REASONS = {missing_key:'Gemini key is not configured.', credential_rejected:'Gemini rejected the credentials.',timeout:'Gemini timed out.',provider_unavailable:'Gemini is unavailable or rate limited.',invalid_or_unavailable_response:'Gemini returned an unavailable or invalid response.'};
export default function Guidance({session, onUpdate}) {
  const [consent, setConsent] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function generate(cloud) {
    setBusy(true); setError('');
    try {
      const response=await api(`/api/sessions/${session.id}/guidance`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cloud_consent:cloud})});
      if(!response.ok) throw new Error(response.status===409 ? 'Another request is running. Please retry shortly.' : response.status===404 ? 'This session is no longer available.' : 'Could not load guidance. Please retry.');
      const updated=await response.json(); onUpdate(updated);
    } catch(e) {setError(e.message || 'Connection failed. Please retry.');}
    finally {setBusy(false);}
  }
  const g=session?.guidance;
  return <><h2>Wellbeing guidance</h2>{!session ? <p>Save a check-in to get guidance.</p> : <>
    {g && <div aria-live="polite"><p><strong>{g.source==='gemini' ? 'AI-selected suggestions · Gemini' : 'Local suggestions · not AI generated'}</strong></p>{REASONS[g.status] && <p>{REASONS[g.status]} Local suggestions are shown instead.</p>}<p className="fine">{g.model ? `Model: ${g.model} · ` : ""}Created {new Date(g.generated_at).toLocaleString()}</p><p>{g.summary}</p><ul>{g.actions.map(action=><li key={action}>{action}</li>)}</ul><p className="fine">{g.limitations}</p></div>}
    {!browserOnly && <><label className="consent"><input type="checkbox" checked={consent} disabled={busy} onChange={e=>setConsent(e.target.checked)}/> Send this check-in’s stress rating, sleep hours, workload, caffeine and exercise answers to Google Gemini for guidance. No video, facial metrics, identity or history is sent. Guidance is saved locally.</label>
    <button className="primary" disabled={!consent || busy} onClick={()=>generate(true)}>{busy ? 'Preparing guidance…' : g ? 'Retry AI guidance' : 'Get AI guidance'}</button>
    </> }{browserOnly && <p>Cloud AI is unavailable in the Pages demo. Suggestions run locally.</p>}<button className="secondary" disabled={busy} onClick={()=>generate(false)}>Use local suggestions</button>
    {error && <p role="alert" className="camera-error">{error}</p>}
  </>}</>;
}
