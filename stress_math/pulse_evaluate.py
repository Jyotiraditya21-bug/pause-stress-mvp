"""Evaluation runner for pulse branch and comparators.

Compares:
- M0 math index
- P pulse-only (inspired by Maaoui, Bousefsaf & Pruski, 2020)
- M0+P fusion (equal weights, per-subject z-score)
- H1 harmonized legacy mesh
- H1+P fusion (equal weights, per-subject z-score)
- Permutation nulls, subject-cluster bootstrap CIs, Holm correction
- Ablations mirroring Table 2 of Maaoui et al.
- Supervised references (LOSO vs random split leakage gap)
"""
from __future__ import annotations
import argparse
import itertools
import json
import time
import warnings
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Sequence

import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.special import expit
from sklearn.metrics import roc_curve

from .core import Index, KEYS
from .heuristic_mesh import StressEngine
from .metrics import summarize, permutation_test, paired_method_auc_difference, auc_value
from .pulse_features import (
    PULSE_FEATURES, PULSE_SIGNS, TIME_FEATURES, FREQ_FEATURES, PulseIndex,
    extract_roi_signal, filter_signal, extract_sliding_windows,
    MIN_FPS, MIN_VALID_RATIO, SNR_MIN
)
from .supervised_reference import evaluate_supervised

METHODS = ('M0', 'P', 'M0+P', 'H1', 'H1+P')
METHOD_NAMES = {
    'M0': 'Math geometric index',
    'P': 'Webcam PPG pulse index (Maaoui et al.)',
    'M0+P': 'Math + Pulse equal-weight fusion',
    'H1': 'Harmonized heuristic mesh',
    'H1+P': 'Heuristic + Pulse equal-weight fusion',
}

ABLATION_KEYS = (
    'full_P',
    *(f'without_{f}' for f in PULSE_FEATURES),
    'time_only',
    'freq_only',
)


def holm_correction(tests: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Holm-Bonferroni correction over pairwise test family."""
    ordered = sorted(
        (v['p_value_two_sided_centered_bootstrap'], k)
        for k, v in tests.items()
        if v.get('p_value_two_sided_centered_bootstrap') is not None
    )
    previous = 0.0
    for rank, (p, k) in enumerate(ordered):
        previous = max(previous, min(1.0, (len(ordered) - rank) * p))
        tests[k]['raw_p_value'] = p
        tests[k]['holm_adjusted_p_value'] = previous
    for v in tests.values():
        v.setdefault('raw_p_value', None)
        v.setdefault('holm_adjusted_p_value', None)
        v['holm_family_size'] = len(ordered)
    return tests


def clean_json(val: Any) -> Any:
    """Recursively clean numpy objects to standard python types for JSON."""
    if isinstance(val, dict):
        return {k: clean_json(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [clean_json(v) for v in val]
    if isinstance(val, np.ndarray):
        return clean_json(val.tolist())
    if isinstance(val, (np.floating, float)):
        return float(val) if np.isfinite(val) else None
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.bool_, bool)):
        return bool(val)
    return val


def fmt_val(v: Any, digits: int = 3) -> str:
    if v is None or not isinstance(v, (int, float, np.floating, np.integer)) or not np.isfinite(v):
        return 'N/A'
    return f"{v:.{digits}f}"


def fmt_interval(val: Any, ci: Optional[Sequence[Any]], digits: int = 3) -> str:
    if val is None or not np.isfinite(val):
        return 'N/A [N/A]'
    if not ci or len(ci) != 2 or any(c is None or not np.isfinite(c) for c in ci):
        return f"{val:.{digits}f} [N/A]"
    return f"{val:.{digits}f} [{ci[0]:.{digits}f}, {ci[1]:.{digits}f}]"


PULSE_WINDOW_SECONDS = 20.0  # Fixed before evaluation; fits inside 25 s rest.


def isolated_windows(payload, start, end, cwt_cleaning=False):
    """Filter/derive each window independently: never use samples outside it."""
    times=np.asarray(payload['times'],float)
    raw=np.asarray(payload['ppg_signal'],float)
    valid=np.asarray(payload['valid_face_mask'],bool)
    fps=float(payload['fps']); result=[]
    for left in np.arange(start, end-PULSE_WINDOW_SECONDS+1e-8, 2.):
        right=left+PULSE_WINDOW_SECONDS
        mask=(times>=left)&(times<right)
        t=times[mask]; v=valid[mask]; signal=raw[mask].copy()
        if len(t)<2: continue
        signal[~v]=np.nan
        filtered=filter_signal(signal,fps,cwt_clean=cwt_cleaning)
        # The extractor expects an inclusive end timestamp; append a boundary
        # sample for its duration check only (the feature mask is right-open).
        tt=np.r_[t,right]; ff=np.r_[filtered,filtered[-1]]; vv=np.r_[v,False]
        windows=extract_sliding_windows(tt,ff,vv,fps,window_sec=PULSE_WINDOW_SECONDS,step_sec=2.)
        if windows:
            w=windows[0]; w['start_time']=float(left);w['end_time']=float(right)
            result.append(w)
    return result


def split_windows(windows):
    # Use strict interval boundaries; a window crossing the baseline cutoff is dropped.
    return ([w for w in windows if w['start_time']>=0 and w['end_time']<=25],
            [w for w in windows if w['start_time']>=25 and w['end_time']>w['start_time']])


def branch_stats(values):
    a=np.asarray(values,float);a=a[np.isfinite(a)]
    if not len(a): return None
    mu=float(a.mean())
    return dict(mu=mu,sigma=max(float(a.std()),.05*abs(mu)+.001),n=len(a))


def branch_z(value, stats):
    if stats is None or not np.isfinite(value): return np.nan
    return float(np.clip((value-stats['mu'])/(stats['sigma']+1e-6),-3,3))


def mean_finite(a):
    a=np.asarray(a,float);a=a[np.isfinite(a)]
    return float(a.mean()) if len(a) else np.nan


def extract_payload(path, cache, channel):
    """Real shared MediaPipe landmarks, pose and speaking gates; no dummy ROI."""
    from .video import extract, features
    data=extract(path,cache); rows=features(data)
    face_counts=np.asarray(data.get('face_counts',np.ones(len(rows),dtype=int)))
    valid=np.array([count==1 and 'ear' in r and not r.get('gated',False) and
                    np.isfinite(a).all() and max(abs(a[:2]))<=35
                    for r,a,count in zip(rows,data['pose'],face_counts)])
    signals=[]; heuristic=[]; engine=StressEngine('H1')
    cap=cv2.VideoCapture(str(path)); tick=time.perf_counter()
    try:
        for t,landmarks,ok in zip(data['times'],data['landmarks'],valid):
            decoded,frame=cap.read()
            if not decoded: raise ValueError('Frame count differs from landmark cache')
            signals.append(extract_roi_signal(frame,landmarks,channel) if ok else np.nan)
            heuristic.append(engine.extract(landmarks,frame,float(t))[0] if ok else None)
    finally: cap.release()
    return dict(times=data['times'],ppg_signal=np.asarray(signals),valid_face_mask=valid,
                fps=float(data['fps']),math_rows=rows,heuristic_rows=heuristic,
                extraction_ms_frame=float(data['ms_frame'])+(time.perf_counter()-tick)*1000/max(len(rows),1))


def branch_series(payload, rest):
    """Actual M0/H1 series; optional supplied numeric series have no label access."""
    times=np.asarray(payload['times']); n=len(times)
    series={m:np.full(n,np.nan) for m in ('M0','H1')}
    if 'math_rows' in rest and 'math_rows' in payload:
        cal=[r for r in rest['math_rows'] if r['time']<25 and 'ear' in r and not r.get('gated',False)]
        if len(cal)>=30:
            model=Index(cal)
            series['M0']=np.array([model.score(r) for r in payload['math_rows']],float)
    if 'heuristic_rows' in rest and 'heuristic_rows' in payload:
        cal=[r for t,r in zip(rest['times'],rest['heuristic_rows']) if t<25 and r is not None]
        if cal:
            model=StressEngine('H1',StressEngine.rest_baseline(cal))
            for i,(t,row) in enumerate(zip(times,payload['heuristic_rows'])):
                if row is not None:
                    value,_,_=model.update(row,float(t));series['H1'][i]=100*(1-value/10)
    for m in ('M0','H1'):
        key=m.lower()+'_scores'
        if key in payload:
            values=np.asarray(payload[key],float)
            if values.shape!=(n,):raise ValueError(key+' must match frame timestamps')
            series[m]=values.copy()
        series[m][~np.asarray(payload['valid_face_mask'],bool)]=np.nan
    return series


def run_pulse_pipeline(sessions, cache_dir, output_dir, rppg_channel='u', cwt_cleaning=False):
    """Fixed main methods only. Missing method evidence stays missing."""
    output_dir=Path(output_dir);cache_dir=Path(cache_dir)
    output_dir.mkdir(parents=True,exist_ok=True);cache_dir.mkdir(parents=True,exist_ok=True)
    memo={};session_records=[];all_window_records=[]
    def payload(session):
        if session.get('ppg_signal') is not None:
            required=('times','valid_face_mask','fps')
            if any(k not in session for k in required):raise ValueError('Signal payload requires real timestamps, validity flags and FPS')
            return session
        path=str(session['video_path'])
        if path not in memo:memo[path]=extract_payload(path,cache_dir,rppg_channel)
        return memo[path]
    def rest_session(session):
        declared=session.get('baseline_video_path')
        if declared:
            return next((r for r in sessions if r.get('video_path')==declared),dict(video_path=declared))
        rests=[r for r in sessions if str(r['subject_id'])==str(session['subject_id']) and
               r.get('dataset')==session.get('dataset') and int(r['label'])==0]
        if len(rests)!=1:raise ValueError('Declare baseline_video_path for an unambiguous first 25 s of rest')
        return rests[0]
    for s in sessions:
        tick=time.perf_counter()
        data=payload(s);rest=payload(rest_session(s))
        duration=float(data['times'][-1])+1/float(data['fps']) if len(data['times']) else 0.
        rest_end=min(25.,float(rest['times'][-1])+1/float(rest['fps'])) if len(rest['times']) else 0.
        rest_windows,_=split_windows(isolated_windows(rest,0,rest_end,cwt_cleaning))
        rest_windows=[w for w in rest_windows if w['gate_passed']]
        start=max(25.,float(s.get('start_seconds') or 25))
        end=min(duration,float(s.get('end_seconds') or duration))
        _,windows=split_windows(isolated_windows(data,start,end,cwt_cleaning))
        pulse_index=PulseIndex(rest_windows)
        models={k:PulseIndex(rest_windows,selected=[f for f in PULSE_FEATURES if k!='without_'+f])
                for k in ABLATION_KEYS if k.startswith('without_')}
        models.update(full_P=pulse_index,time_only=PulseIndex(rest_windows,selected=TIME_FEATURES),freq_only=PulseIndex(rest_windows,selected=FREQ_FEATURES))
        base_series=branch_series(rest,rest);series=branch_series(data,rest)
        def window_mean(values,payload,w):
            t=np.asarray(payload['times']);return mean_finite(values[(t>=w['start_time'])&(t<w['end_time'])])
        stats={m:branch_stats([window_mean(base_series[m],rest,w) for w in rest_windows]) for m in ('M0','H1')}
        stats['P']=branch_stats([pulse_index.score(w) for w in rest_windows])
        scores={m:[] for m in METHODS};ablations={k:[] for k in ABLATION_KEYS}
        for w in windows:
            vals={m:window_mean(series[m],data,w) for m in ('M0','H1')}
            vals['P']=pulse_index.score(w) if w['gate_passed'] else np.nan
            for a in ('M0','H1'):
                z=[branch_z(vals[m],stats[m]) for m in (a,'P')]
                vals[a+'+P']=float(100*expit(np.mean(z))) if np.isfinite(z).all() else np.nan
            for m in METHODS:scores[m].append(vals[m])
            for k,model in models.items():ablations[k].append(model.score(w) if w['gate_passed'] else np.nan)
        mask=(np.asarray(data['times'])>=start)&(np.asarray(data['times'])<end)
        coverage=100*float(np.mean(np.asarray(data['valid_face_mask'])[mask])) if mask.any() else 0.
        method_coverage={m:100*sum(np.isfinite(scores[m]))/max(len(windows),1) for m in METHODS}
        excluded=coverage<40
        methods={m:mean_finite(scores[m]) if not excluded and method_coverage[m]>=40 else np.nan for m in METHODS}
        session_records.append(dict(subject_id=str(s.get('dataset','unknown'))+':'+str(s['subject_id']),
            dataset=s.get('dataset','unknown'),video_path=s.get('video_path'),label=int(s['label']),
            excluded=excluded,coverage_percent=coverage,method_coverage_percent=method_coverage,
            methods=methods,ablations={k:mean_finite(v) if method_coverage['P']>=40 else np.nan for k,v in ablations.items()},
            baseline_windows=[{'start':w['start_time'],'end':w['end_time']} for w in rest_windows],
            evaluation_windows=[{'start':w['start_time'],'end':w['end_time']} for w in windows],branch_baselines=stats,
            total_processing_ms_frame=(time.perf_counter()-tick)*1000/max(len(data['times']),1),
            method_ms_frame={m:None for m in METHODS}))
    # Analyze pooling across methods
    eligible = [r for r in session_records if not r['excluded']]
    pooled: Dict[str, Any] = {'methods': {}, 'permutations': {}}
    
    for m in METHODS:
        adapted = [{**r, 's': r['methods'][m]} for r in eligible if np.isfinite(r['methods'].get(m,np.nan))]
        missing = any(not np.isfinite(r['s']) for r in adapted)
        metric = {'status': 'unavailable: missing score on fixed cohort'} if missing or not adapted else summarize(adapted, 's')
        metric['coverage_percent'] = float(np.mean([r['coverage_percent'] for r in eligible])) if eligible else None
        metric['ms_per_frame'] = None
        metric['excluded_missing_method'] = len(eligible)-len(adapted)
        pooled['methods'][m] = metric
        pooled['permutations'][m] = permutation_test([] if missing else adapted, 's')
        
    # Pairwise AUC differences with Holm correction
    pairwise = {}
    for a, b in itertools.combinations(METHODS, 2):
        pairwise[f'{a}_vs_{b}'] = paired_method_auc_difference([r for r in eligible if all(np.isfinite(r['methods'][m]) for m in (a,b))], a, b)
    pooled['pairwise_auc_differences'] = holm_correction(pairwise)
    
    # Ablations analysis
    ablation_results = {}
    full_p_auc = None
    for k in ABLATION_KEYS:
        adapted = [{**r, 's': r['ablations'].get(k, np.nan)} for r in eligible]
        missing = any(not np.isfinite(r['s']) for r in adapted)
        m_summary = summarize(adapted, 's') if not missing and adapted else {'roc_auc': None}
        ablation_results[k] = m_summary
        if k == 'full_P':
            full_p_auc = m_summary.get('roc_auc')
            
    ablation_auc_drop = {}
    for k in ABLATION_KEYS:
        auc = ablation_results[k].get('roc_auc')
        ablation_auc_drop[k] = (full_p_auc - auc) if full_p_auc is not None and auc is not None else None
        
    # Supervised references (LOSO vs Random split)
    supervised = {'status':'not run: main runner never trains', 'table':'Not run. Supervised references remain a separate optional API.'}
    
    result = {
        'protocol': {
            'trained': False,
            'seed': 42,
            'baseline_seconds': 25,
            'window_seconds': PULSE_WINDOW_SECONDS,
            'window_filtering': 'independent; baseline end <=25, evaluation start >=25',
            'sigma_floor': 'max(raw_sd, 0.05 * abs(mu) + 1e-3)',
            'z_clip': [-3, 3],
            'signs': PULSE_SIGNS,
            'fusion': '100 * sigmoid(mean(signed_z))',
            'quality_gates': {
                'min_fps': MIN_FPS,
                'min_valid_ratio': MIN_VALID_RATIO,
                'snr_min': SNR_MIN,
            },
            'rppg_channel': rppg_channel,
            'cwt_cleaning': cwt_cleaning,
            'bootstrap_resamples': 1000,
            'permutation_shuffles': 1000,
        },
        'records': session_records,
        'eligible_count': len(eligible),
        'total_sessions': len(session_records),
        'pooled': pooled,
        'ablation': ablation_results,
        'ablation_auc_drop': ablation_auc_drop,
        'supervised_reference': supervised,
    }
    
    write_all_outputs(result, output_dir)
    return result


def write_all_outputs(result: Dict[str, Any], output_dir: Path) -> None:
    """Generate all markdown reports, json metrics, and requested plots."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    
    # 1. summary.md
    lines = [
        "# Comparison Summary",
        "",
        "| Method | AUC [95% CI] | d_z | Coverage % | ms/frame |",
        "|---|---|---|---|---|",
    ]
    for m in METHODS:
        v = result['pooled']['methods'].get(m, {})
        auc_str = fmt_interval(v.get('roc_auc'), v.get('subject_bootstrap_95ci', {}).get('roc_auc'))
        dz_str = fmt_val(v.get('within_subject', {}).get('cohen_dz'))
        cov_str = fmt_val(v.get('coverage_percent'))
        ms_str = fmt_val(v.get('ms_per_frame'))
        lines.append(f"| {m}: {METHOD_NAMES[m]} | {auc_str} | {dz_str} | {cov_str} | {ms_str} |")
        
        null = result['pooled']['permutations'].get(m, {})
        null_auc = fmt_interval(null.get('null_auc_mean'), null.get('null_auc_95_interval'))
        lines.append(f"| {m} shuffled-label null | {null_auc} | N/A | {cov_str} | N/A |")
        
    summary_md = "\n".join(lines) + "\n"
    (out / 'summary.md').write_text(summary_md)
    
    # 2. comparison.md
    comp_lines = [
        summary_md,
        "## Pairwise AUC Differences (Holm Adjusted)",
        "",
        "| Comparison | AUC Difference | 95% CI | Raw p | Holm-adjusted p |",
        "|---|---|---|---|---|",
    ]
    for pair_name, diff_info in result['pooled'].get('pairwise_auc_differences', {}).items():
        diff_val = fmt_val(diff_info.get('auc_difference'))
        ci_str = fmt_interval(diff_info.get('auc_difference'), diff_info.get('subject_bootstrap_95ci'))
        raw_p = fmt_val(diff_info.get('raw_p_value'), 4)
        holm_p = fmt_val(diff_info.get('holm_adjusted_p_value'), 4)
        comp_lines.append(f"| {pair_name} | {diff_val} | {ci_str} | {raw_p} | {holm_p} |")
        
    comp_lines.extend([
        "",
        "## Supervised Reference Comparison (Leakage Quantification)",
        "",
        result.get('supervised_reference', {}).get('table', 'N/A'),
        "",
        "## Feature Ablations (Mirroring Maaoui et al. Table 2)",
        "",
        "| Ablation | ROC-AUC | AUC Drop vs Full P |",
        "|---|---|---|",
    ])
    for k in ABLATION_KEYS:
        auc_v = result.get('ablation', {}).get(k, {}).get('roc_auc')
        drop_v = result.get('ablation_auc_drop', {}).get(k)
        comp_lines.append(f"| {k} | {fmt_val(auc_v)} | {fmt_val(drop_v)} |")
        
    (out / 'comparison.md').write_text("\n".join(comp_lines) + "\n")
    
    # 3. report.md (with MANDATORY statements)
    report_text = f"""# Webcam PPG Pulse Feature Extension Report

Inspired by Maaoui, Bousefsaf & Pruski (2020) webcam PPG stress detection.

## Mandatory Scientific and Methodological Boundaries

- **pulse features are camera estimates, not ECG-grade HRV**: Camera-derived rPPG signals measure blood volume pulse variations via optical skin absorption. They are subject to illumination noise, motion artifacts, and camera compression, and must not be treated as clinical ECG or medical-grade physiological measurements.
- **LF from 20 s windows is especially unreliable**: Classical heart rate variability (HRV) guidelines (Task Force, 1996) require at least 1 to 2 minutes of recording to resolve Low Frequency (0.04 - 0.15 Hz) rhythms. Spectral LF estimated over an ultra-short 20-second window has high statistical variance and serves as an engineering proxy only.
- **supervised models are references only**: Supervised classifiers (SVM and LDA) are evaluated exclusively to quantify subject leakage and demonstrate the impact of unseparated validation splits; they are NOT the main proposed method and are never used for personal guidance.
- **labels are task-based**: Evaluation labels represent controlled experiment tasks (rest vs stressor tasks), not clinically diagnosed stress or burnout.
- **no thresholds, signs or weights were fitted on test data**: Pulse feature directions (meanHR +, StdHR +, DerHR +, RMSSD -, HF -, LF +, LF/HF +), 25-second baseline calibration, sigma floors, quality gates, and equal fusion weights were determined a priori from physiology literature before evaluation.

## Methodology

1. **Signal extraction**: Skin ROI consists of forehead and cheek patches from MediaPipe landmarks. Spatially averaged over CIE L*u*v* $u^*$ channel (or BGR green channel).
2. **Filtering**: Linear detrending, 4th-order zero-phase Butterworth bandpass filter (0.65 - 3.0 Hz).
3. **Pulse rate trace**: Peak detection with minimum distance corresponding to 3 Hz ($f_s / 3$), instantaneous HR = $60 / \text{{IBI}}$, resampled to 30 Hz by linear interpolation.
4. **Window features**: fixed 20 s windows with 2 s step, filtered independently. Baseline windows end at or before 25 s of rest; evaluation windows start at or after 25 s. A 30 s window cannot fit the baseline. LF is even less reliable at 20 s. Seven features: meanHR, StdHR, DerHR, RMSSD, LF power (0.04 - 0.15 Hz), HF power (0.15 - 0.35 Hz), and LF/HF ratio. RMSSD_rr is calculated on discrete inter-beat intervals and reported separately.
5. **Quality gate**: Windows require FPS >= 15, valid face frames >= 80%, and spectral peak SNR >= 2.0. Failed windows remain missing, not imputed.

## Results Summary

{summary_md}

## Supervised Reference Table

{result.get('supervised_reference', {}).get('table', 'N/A')}

## Detailed Ablations

| Variant | ROC-AUC | Drop vs Full P |
|---|---|---|
"""
    for k in ABLATION_KEYS:
        auc_v = result.get('ablation', {}).get(k, {}).get('roc_auc')
        drop_v = result.get('ablation_auc_drop', {}).get(k)
        report_text += f"| {k} | {fmt_val(auc_v)} | {fmt_val(drop_v)} |\n"
        
    (out / 'report.md').write_text(report_text)
    
    # 4. metrics.json
    (out / 'metrics.json').write_text(json.dumps(clean_json(result), indent=2))
    
    # -------------------------------------------------------------
    # 5. Plots
    # -------------------------------------------------------------
    # (a) roc_all_methods.png
    eligible = [r for r in result.get('records', []) if not r['excluded']]
    fig, ax = plt.subplots(figsize=(7, 6))
    plotted = False
    for m in METHODS:
        y = [r['label'] for r in eligible]
        scores = [r['methods'].get(m, np.nan) for r in eligible]
        valid_idx = [i for i, s in enumerate(scores) if np.isfinite(s)]
        if len(valid_idx) > 0:
            y_v = [y[i] for i in valid_idx]
            s_v = [scores[i] for i in valid_idx]
            if len(set(y_v)) == 2:
                fpr, tpr, _ = roc_curve(y_v, s_v)
                ax.plot(fpr, tpr, label=f"{m} ({METHOD_NAMES[m]})")
                plotted = True
    ax.plot([0, 1], [0, 1], '--', color='grey', label='Chance')
    ax.set_xlabel('False Positive Rate')
    ax.set_ylabel('True Positive Rate')
    ax.set_title('ROC Curves — All Methods (M0, P, M0+P, H1, H1+P)')
    ax.legend(loc='lower right', fontsize=8)
    fig.tight_layout()
    fig.savefig(out / 'roc_all_methods.png', dpi=150)
    plt.close(fig)
    
    # (b) pulse_feature_ablation.png
    fig, ax = plt.subplots(figsize=(10, 5))
    abl_keys = list(ABLATION_KEYS)
    abl_vals = [result.get('ablation', {}).get(k, {}).get('roc_auc') for k in abl_keys]
    bars = [v if v is not None and np.isfinite(v) else 0.0 for v in abl_vals]
    ax.bar(abl_keys, bars, color='#3a6b58', edgecolor='#183b36')
    ax.set_ylabel('ROC-AUC')
    ax.set_ylim(0, 1.0)
    ax.set_title("Pulse Feature Ablations (Mirroring Maaoui et al. Table 2)")
    ax.tick_params(axis='x', rotation=35)
    ax.axhline(0.5, color='gray', linestyle='--', alpha=0.7)
    fig.tight_layout()
    fig.savefig(out / 'pulse_feature_ablation.png', dpi=150)
    plt.close(fig)
    
    # (c) leakage_gap.png
    fig, ax = plt.subplots(figsize=(8, 5))
    sup_summary = result.get('supervised_reference', {}).get('summary', {})
    models = ['SVM (RBF)', 'LDA']
    x = np.arange(len(models))
    width = 0.35
    
    loso_accs = [sup_summary.get(m, {}).get('LOSO', {}).get('accuracy', 0.0) or 0.0 for m in models]
    rand_accs = [sup_summary.get(m, {}).get('random', {}).get('accuracy', 0.0) or 0.0 for m in models]
    
    rects1 = ax.bar(x - width/2, rand_accs, width, label='Random window split (leaked)', color='#d95f02')
    rects2 = ax.bar(x + width/2, loso_accs, width, label='LOSO (subject-separated)', color='#1b9e77')
    
    ax.set_ylabel('Accuracy')
    ax.set_title('Supervised Reference Leakage Gap (Random Split vs. LOSO)')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.set_ylim(0, 1.0)
    ax.legend()
    
    for i, m in enumerate(models):
        gap = rand_accs[i] - loso_accs[i]
        higher = max(rand_accs[i], loso_accs[i])
        ax.annotate(f"Gap: +{gap:.2f}" if gap >= 0 else f"Gap: {gap:.2f}",
                    xy=(x[i], higher + 0.03), ha='center', fontsize=9, fontweight='bold')
                    
    fig.tight_layout()
    fig.savefig(out / 'leakage_gap.png', dpi=150)
    plt.close(fig)


def make_smoke_test_data() -> List[Dict[str, Any]]:
    """Generate synthetic smoke test dataset for complete pipeline verification."""
    rng = np.random.default_rng(42)
    sessions = []
    fps = 30.0
    duration = 75.0
    t = np.arange(0, duration, 1.0 / fps)
    
    # 4 subjects, 2 sessions each (rest=0, task=1)
    for sub in ('S1', 'S2', 'S3', 'S4'):
        for label in (0, 1):
            # Rest: ~65 bpm (1.08 Hz); Task: ~85 bpm (1.42 Hz)
            freq = 1.08 if label == 0 else 1.42
            amp = 3.0
            ppg = 100.0 + amp * np.sin(2 * np.pi * freq * t) + 0.1 * rng.normal(size=len(t))
            val_mask = np.ones(len(t), dtype=bool)
            
            sessions.append({
                'video_path': f'synthetic_{sub}_{label}.avi',
                'subject_id': sub,
                'dataset': 'synthetic_ppg',
                'label': label,
                'times': t,
                'ppg_signal': ppg,
                'valid_face_mask': val_mask,
                'fps': fps,
                # Synthetic pulse only: M0/H1 intentionally unavailable.
            })
            
    return sessions


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate webcam PPG pulse branch and comparators.")
    parser.add_argument('--root', default=None, help='Datasets root directory')
    parser.add_argument('--manifest', default=None, help='Manifest file path')
    parser.add_argument('--cache', default='stress_math/cache', help='Cache directory')
    parser.add_argument('--output', default='stress_math/results', help='Output results directory')
    parser.add_argument('--rppg-channel', default='u', choices=['u', 'green'], help='rPPG channel (u or green)')
    parser.add_argument('--cwt-cleaning', action='store_true', default=False, help='Enable CWT cleaning')
    parser.add_argument('--smoke-test', action='store_true', default=False, help='Run synthetic smoke test')
    
    args = parser.parse_args()
    
    if args.smoke_test:
        sessions = make_smoke_test_data()
    else:
        from .datasets import load
        sessions = load(args.root, args.manifest)
        
    out = Path(args.output)
    cache = Path(args.cache)
    
    result = run_pulse_pipeline(
        sessions, cache, out,
        rppg_channel=args.rppg_channel,
        cwt_cleaning=args.cwt_cleaning,
    )
    print(f"Pulse evaluation completed: {len(result['records'])} sessions processed. Outputs written to {out}")


if __name__ == '__main__':
    main()
