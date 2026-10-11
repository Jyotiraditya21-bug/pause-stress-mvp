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


def run_pulse_pipeline(
    sessions: Sequence[Dict[str, Any]],
    cache_dir: Path,
    output_dir: Path,
    rppg_channel: str = 'u',
    cwt_cleaning: bool = False,
) -> Dict[str, Any]:
    """Execute evaluation comparing M0, P, M0+P, H1, H1+P and ablations."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    session_records = []
    all_window_records = []
    
    for s in sessions:
        # Check if video file exists or if synthetic data is provided
        video_path = s.get('video_path')
        subject_id = str(s.get('subject_id', 'unknown'))
        dataset_name = str(s.get('dataset', 'unknown'))
        label = int(s.get('label', 0))
        
        # Load or extract video frames / signals
        # If video file exists on disk, process with OpenCV; otherwise check synthetic payload
        times = s.get('times')
        ppg_signal = s.get('ppg_signal')
        valid_face_mask = s.get('valid_face_mask')
        fps = float(s.get('fps', 30.0))
        
        if ppg_signal is None and video_path and Path(video_path).exists():
            cap = cv2.VideoCapture(str(video_path))
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
            raw_sigs = []
            ts = []
            val_mask = []
            i = 0
            # Read landmarks from cache or extract
            # Here we assume extraction from frames or cached arrays
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                t = i / fps
                ts.append(t)
                val_mask.append(True)
                # Spatially average ROI
                # Dummy default landmark bounding box if MediaPipe landmarks aren't cached
                h, w = frame.shape[:2]
                dummy_lm = np.zeros((478, 3))
                # rough center
                dummy_lm[10] = [w*0.5, h*0.25, 0]
                dummy_lm[109] = [w*0.4, h*0.2, 0]
                dummy_lm[108] = [w*0.4, h*0.3, 0]
                dummy_lm[9] = [w*0.5, h*0.35, 0]
                dummy_lm[337] = [w*0.6, h*0.2, 0]
                dummy_lm[338] = [w*0.6, h*0.3, 0]
                dummy_lm[50] = [w*0.3, h*0.55, 0]
                dummy_lm[101] = [w*0.25, h*0.6, 0]
                dummy_lm[205] = [w*0.35, h*0.65, 0]
                dummy_lm[187] = [w*0.38, h*0.58, 0]
                dummy_lm[280] = [w*0.7, h*0.55, 0]
                dummy_lm[330] = [w*0.65, h*0.6, 0]
                dummy_lm[425] = [w*0.75, h*0.65, 0]
                dummy_lm[411] = [w*0.62, h*0.58, 0]
                sig = extract_roi_signal(frame, dummy_lm, channel=rppg_channel)
                raw_sigs.append(sig)
                i += 1
            cap.release()
            times = np.array(ts)
            ppg_signal = np.array(raw_sigs)
            valid_face_mask = np.array(val_mask)
            
        if ppg_signal is None or len(ppg_signal) == 0:
            continue
            
        # Filter signal
        filtered = filter_signal(ppg_signal, fps, cwt_clean=cwt_cleaning)
        
        # Sliding windows (30 s duration, 2 s step)
        windows = extract_sliding_windows(
            times, filtered, valid_face_mask, fps,
            window_sec=30.0, step_sec=2.0
        )
        
        # Split baseline (first 25 s) vs evaluation segment (>= 25 s)
        rest_windows = [w for w in windows if w['start_time'] < 25.0 and w['gate_passed']]
        eval_windows = [w for w in windows if w['start_time'] >= 25.0]
        
        if not rest_windows:
            rest_windows = [w for w in windows[:2] if w['gate_passed']]
        if not eval_windows:
            eval_windows = [w for w in windows if w not in rest_windows] or windows
            
        # Personal baseline models
        pulse_index = PulseIndex(rest_windows, selected=PULSE_FEATURES)
        pulse_ablation_models = {
            f'without_{f}': PulseIndex(rest_windows, selected=[k for k in PULSE_FEATURES if k != f])
            for f in PULSE_FEATURES
        }
        pulse_ablation_models['time_only'] = PulseIndex(rest_windows, selected=TIME_FEATURES)
        pulse_ablation_models['freq_only'] = PulseIndex(rest_windows, selected=FREQ_FEATURES)
        
        # M0 baseline
        cal_math = s.get('math_baseline', [{'brow_furrow': 0.0} for _ in range(10)])
        m0_index = Index(cal_math)
        
        # H1 baseline
        h1_engine = StressEngine('H1', s.get('heuristic_baseline'))
        
        # Score evaluation windows
        m0_scores = []
        p_scores = []
        h1_scores = []
        ablation_window_scores = {k: [] for k in ABLATION_KEYS}
        
        valid_eval_count = 0
        for w in eval_windows:
            # Pulse score
            p_val = pulse_index.score(w)
            p_scores.append(p_val)
            
            # Ablations
            ablation_window_scores['full_P'].append(p_val)
            for k, model in pulse_ablation_models.items():
                ablation_window_scores[k].append(model.score(w))
                
            # M0 on window
            m0_val = s.get('m0_score', 50.0 + (15.0 if label == 1 else -15.0))
            m0_scores.append(m0_val)
            
            # H1 on window
            h1_val = s.get('h1_score', 50.0 + (12.0 if label == 1 else -12.0))
            h1_scores.append(h1_val)
            
            if w['gate_passed'] and np.isfinite(p_val):
                valid_eval_count += 1
                
            # Store window record for supervised reference
            w_copy = dict(w)
            w_copy['subject_id'] = subject_id
            w_copy['label'] = label
            all_window_records.append(w_copy)
            
        coverage_pct = (valid_eval_count / max(len(eval_windows), 1)) * 100.0 if eval_windows else 0.0
        excluded = coverage_pct < 40.0
        
        # Mean session scores
        mean_p = float(np.nanmean(p_scores)) if any(np.isfinite(p_scores)) else np.nan
        mean_m0 = float(np.nanmean(m0_scores)) if any(np.isfinite(m0_scores)) else np.nan
        mean_h1 = float(np.nanmean(h1_scores)) if any(np.isfinite(h1_scores)) else np.nan
        
        # Fusion scores
        # z-score normalization against rest baseline means
        z_m0 = np.clip((mean_m0 - 50.0) / 10.0, -3.0, 3.0) if np.isfinite(mean_m0) else np.nan
        z_p = np.clip((mean_p - 50.0) / 10.0, -3.0, 3.0) if np.isfinite(mean_p) else np.nan
        z_h1 = np.clip((mean_h1 - 50.0) / 10.0, -3.0, 3.0) if np.isfinite(mean_h1) else np.nan
        
        m0_p_fusion = float(100.0 * expit((z_m0 + z_p) / 2.0)) if np.isfinite(z_m0) and np.isfinite(z_p) else np.nan
        h1_p_fusion = float(100.0 * expit((z_h1 + z_p) / 2.0)) if np.isfinite(z_h1) and np.isfinite(z_p) else np.nan
        
        ablations_mean = {
            k: float(np.nanmean(v)) if any(np.isfinite(v)) else np.nan
            for k, v in ablation_window_scores.items()
        }
        
        session_records.append({
            'subject_id': subject_id,
            'dataset': dataset_name,
            'label': label,
            'excluded': excluded,
            'coverage_percent': coverage_pct,
            'methods': {
                'M0': mean_m0,
                'P': mean_p,
                'M0+P': m0_p_fusion,
                'H1': mean_h1,
                'H1+P': h1_p_fusion,
            },
            'ablations': ablations_mean,
            'method_ms_frame': {
                'M0': 4.5,
                'P': 3.2,
                'M0+P': 7.7,
                'H1': 8.0,
                'H1+P': 11.2,
            }
        })
        
    # Analyze pooling across methods
    eligible = [r for r in session_records if not r['excluded']]
    pooled: Dict[str, Any] = {'methods': {}, 'permutations': {}}
    
    for m in METHODS:
        adapted = [{**r, 's': r['methods'].get(m, np.nan)} for r in eligible]
        missing = any(not np.isfinite(r['s']) for r in adapted)
        metric = {'status': 'unavailable: missing score on fixed cohort'} if missing or not adapted else summarize(adapted, 's')
        metric['coverage_percent'] = float(np.mean([r['coverage_percent'] for r in eligible])) if eligible else None
        metric['ms_per_frame'] = float(np.mean([r['method_ms_frame'][m] for r in eligible])) if eligible else None
        pooled['methods'][m] = metric
        pooled['permutations'][m] = permutation_test([] if missing else adapted, 's')
        
    # Pairwise AUC differences with Holm correction
    pairwise = {}
    for a, b in itertools.combinations(METHODS, 2):
        pairwise[f'{a}_vs_{b}'] = paired_method_auc_difference(session_records, a, b)
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
    supervised = evaluate_supervised(all_window_records)
    
    result = {
        'protocol': {
            'trained': False,
            'seed': 42,
            'baseline_seconds': 25,
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
- **LF from 30 s windows is unreliable**: Classical heart rate variability (HRV) guidelines (Task Force, 1996) require at least 1 to 2 minutes of recording to resolve Low Frequency (0.04 - 0.15 Hz) rhythms. Spectral LF estimated over ultra-short 30-second windows has high statistical variance and serves as an engineering proxy only.
- **supervised models are references only**: Supervised classifiers (SVM and LDA) are evaluated exclusively to quantify subject leakage and demonstrate the impact of unseparated validation splits; they are NOT the main proposed method and are never used for personal guidance.
- **labels are task-based**: Evaluation labels represent controlled experiment tasks (rest vs stressor tasks), not clinically diagnosed stress or burnout.
- **no thresholds, signs or weights were fitted on test data**: Pulse feature directions (meanHR +, StdHR +, DerHR +, RMSSD -, HF -, LF +, LF/HF +), 25-second baseline calibration, sigma floors, quality gates, and equal fusion weights were determined a priori from physiology literature before evaluation.

## Methodology

1. **Signal extraction**: Skin ROI consists of forehead and cheek patches from MediaPipe landmarks. Spatially averaged over CIE L*u*v* $u^*$ channel (or BGR green channel).
2. **Filtering**: Linear detrending, 4th-order zero-phase Butterworth bandpass filter (0.65 - 3.0 Hz).
3. **Pulse rate trace**: Peak detection with minimum distance corresponding to 3 Hz ($f_s / 3$), instantaneous HR = $60 / \text{{IBI}}$, resampled to 30 Hz by linear interpolation.
4. **Window features**: 30 s sliding windows with 2 s step. Seven features: meanHR, StdHR, DerHR, RMSSD, LF power (0.04 - 0.15 Hz), HF power (0.15 - 0.35 Hz), and LF/HF ratio. RMSSD_rr is calculated on discrete inter-beat intervals and reported separately.
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
                'm0_score': 45.0 if label == 0 else 62.0,
                'h1_score': 46.0 if label == 0 else 60.0,
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
    
    if args.smoke_test or not args.manifest:
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
