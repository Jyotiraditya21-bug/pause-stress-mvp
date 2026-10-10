import {api, browserOnly} from './api';
import React, {useState, useRef} from 'react';

export default function Questionnaire({scan, onSaved}) {
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const submitting = useRef(false);
  async function submit(event) {
    event.preventDefault(); if(submitting.current) return; submitting.current=true; setBusy(true); setError('');
    const data = new FormData(event.currentTarget);
    try {
      const response = await api('/api/sessions', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        self_reported_stress:Number(data.get('stress')), sleep_hours:Number(data.get('sleep')),
        workload:data.get('workload'), caffeine:data.get('caffeine')==='yes', recent_exercise:data.get('exercise')==='yes',
        storage_consent:data.get('consent')==='on', camera_metrics:scan
      })});
      if(!response.ok) throw new Error(response.status===422 ? 'Please check your answers and storage consent.' : 'Could not save. Your answers are still here; please retry.');
      const saved=await response.json(); onSaved(saved);
    } catch(e) {setError(e.message || 'Connection failed. Please retry.');}
    finally {submitting.current=false;setBusy(false);}
  }
  return <section className="panel questionnaire"><h2>How are you feeling right now?</h2><p>This brief check-in records your experience. It is not a standardized clinical assessment.</p>
    <p>{scan ? `Camera scan complete (${scan.quality} quality).` : 'Camera skipped. You can still save a self-report.'}</p>
    <form onSubmit={submit}>
      <fieldset disabled={busy}><label>Current stress · 0 = none, 10 = highest you can imagine<select name="stress" required defaultValue=""><option value="" disabled>Select a rating</option>{Array.from({length:11},(_,i)=><option key={i} value={i}>{i}</option>)}</select></label>
      <label>Hours slept last night<input name="sleep" type="number" min="0" max="24" step="0.5" required placeholder="e.g. 7.5"/></label>
      <label>Current workload<select name="workload" required defaultValue=""><option value="" disabled>Select workload</option><option value="light">Light</option><option value="moderate">Moderate</option><option value="heavy">Heavy</option></select></label>
      <label>Caffeine in the past 4 hours?<select name="caffeine" required defaultValue=""><option value="" disabled>Select an answer</option><option value="no">No</option><option value="yes">Yes</option></select></label>
      <label>Exercise in the past hour?<select name="exercise" required defaultValue=""><option value="" disabled>Select an answer</option><option value="no">No</option><option value="yes">Yes</option></select></label>
      <label className="consent"><input name="consent" type="checkbox" required/> {browserOnly ? 'Save my answers and camera metrics in this browser on this device. Anyone using this browser profile can view them; clearing site data erases them. I can delete them from History.' : 'Save my answers and camera metrics, if available, on this Mac. Local storage is not encrypted; anyone with access to this app can view these sessions. I can delete them from History.'}</label>
      <button className="primary" type="submit">{busy ? 'Saving…' : 'Save check-in →'}</button></fieldset>
      {error && <p role="alert" className="camera-error">{error}</p>}
    </form></section>;
}
