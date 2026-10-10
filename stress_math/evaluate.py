import argparse, json, warnings, time
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve
from .core import Index, KEYS
from .datasets import load
from .video import extract, features
from .old_adapter import score_video, REASON
from .metrics import summarize, permutation_test, au_validity, auc_value

COVERAGE_MIN = .40
METHODS = {**{f'single_{k}': (k,) for k in KEYS},
           'new_without_rppg': tuple(k for k in KEYS if k not in ('hr','rmssd')),
           'new_all': KEYS}
METHOD_NAMES = {**{f'single_{k}': f'Single feature: {k}' for k in KEYS},
                'new_without_rppg': 'NEW without rPPG/HRV',
                'new_all': 'NEW with all available features'}

def clean(value):
    if isinstance(value, dict): return {k: clean(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [clean(v) for v in value]
    if isinstance(value, np.ndarray): return clean(value.tolist())
    if isinstance(value, (np.floating,float)): return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer): return int(value)
    if isinstance(value, np.bool_): return bool(value)
    return value

def read_video(path, cache):
    data = extract(path, cache)
    sidecar = Path(path).with_suffix('.timestamps.npy')
    if sidecar.exists():
        timestamps = np.load(sidecar, allow_pickle=False)
        if len(timestamps) != len(data['times']): raise ValueError('Timestamp sidecar/frame count mismatch')
        data = dict(data, times=timestamps)
    return data

def mean_score(scores):
    a = np.asarray(scores, float)
    return float(a[np.isfinite(a)].mean()) if np.isfinite(a).any() else np.nan

def feature_model(baseline, keys):
    return Index([{k:r[k] for k in keys if k in r} for r in baseline])

def coverage_report(records):
    def aggregate(items):
        total = sum(r['evaluation_frames'] for r in items)
        valid = sum(r['valid_frames'] for r in items)
        return {'videos':len(items), 'mean_video_percent':float(np.mean([r['coverage_percent'] for r in items])) if items else None,
                'frame_weighted_percent':100*valid/total if total else None,
                'excluded_videos':sum(r['excluded'] for r in items)}
    tasks = {t:aggregate([r for r in records if r['task_condition']==t]) for t in ('T1','T2','T3')}
    labels = {str(label):aggregate([r for r in records if r['label']==label]) for label in (0,1)}
    conditions = {c:aggregate([r for r in records if r['task_condition']==c]) for c in sorted({r['task_condition'] for r in records})}
    return {'denominator':'all decoded frames in the evaluation segment, including no-face/pose/gating rejections; calibration frames excluded',
            'minimum_percent':40, 'by_task':tasks, 'by_binary_label':labels, 'by_condition':conditions,
            'per_video':[{k:r[k] for k in ('video_path','subject_id','dataset','label','task_condition','evaluation_frames','valid_frames','coverage_percent','excluded','exclusion_reason')} for r in records]}

def method_metrics(records, method):
    cohort = [r for r in records if not r['excluded']]
    unavailable = [r['video_path'] for r in cohort if not np.isfinite(r['methods'][method])]
    # Keep the comparison cohort identical. Never silently drop missing-feature videos.
    if unavailable:
        return {'status':'unavailable on the fixed comparison cohort', 'n':0,
                'missing_feature_videos':unavailable, 'cohort_videos':len(cohort)}
    adapted = [{**r,'method_score':r['methods'][method]} for r in cohort]
    return summarize(adapted, 'method_score')

def group_metrics(records):
    methods = {m:method_metrics(records,m) for m in METHODS}
    permutation = permutation_test(records)
    return {'methods':methods, 'permutation':permutation,
            'NEW':methods['new_all'], 'OLD':{'status':'unavailable: OLD has no video scorer','n':0}}

def fmt(value):
    return f'{value:.3f}' if value is not None and np.isfinite(value) else 'N/A'

def interval_text(value, interval):
    return fmt(value)+(f' [{fmt(interval[0])}, {fmt(interval[1])}]' if interval else ' [N/A]')

def summary_table(result):
    records = [r for r in result['records'] if not r['excluded']]
    table = ['| Method | AUC [95% CI] | d_z | Coverage | ms/frame |',
             '|---|---|---|---|---|']
    for method in METHODS:
        metrics = result['pooled']['methods'][method]
        auc = interval_text(metrics.get('roc_auc'),metrics.get('subject_bootstrap_95ci',{}).get('roc_auc'))
        dz = fmt(metrics.get('within_subject',{}).get('cohen_dz'))
        # Method score availability is shown alongside the shared validity coverage.
        cov = float(np.mean([r['method_coverage_percent'][method] for r in records])) if records else None
        ms = float(np.mean([r['method_ms_frame'][method] for r in records])) if records else None
        table.append(f'| {METHOD_NAMES[method]} | {auc} | {dz} | {fmt(cov)}% | {fmt(ms)} |')
    perm=result['pooled']['permutation']
    table.append(f"| Shuffled-label NEW (null; 1000 permutations) | {interval_text(perm['null_auc_mean'],perm['null_auc_95_interval'])} | N/A | {fmt(float(np.mean([r['method_coverage_percent']['new_all'] for r in records])) if records else None)}% | N/A |")
    return '\n'.join(table)+'\n'

def save_outputs(result, series, out):
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    (out/'metrics.json').write_text(json.dumps(clean(result),indent=2,allow_nan=False))
    (out/'summary.md').write_text(summary_table(result))
    table=['| Dataset | Method | ROC-AUC [95% CI] | d_z [95% CI] | Wilcoxon p [95% CI] |','|---|---|---|---|---|']
    for name,group in [*result['datasets'].items(),('pooled',result['pooled'])]:
        for method,metrics in group['methods'].items():
            ci=metrics.get('subject_bootstrap_95ci',{}); paired=metrics.get('within_subject',{})
            table.append(f"| {name} | {METHOD_NAMES[method]} | {interval_text(metrics.get('roc_auc'),ci.get('roc_auc'))} | {interval_text(paired.get('cohen_dz'),ci.get('cohen_dz'))} | {interval_text(paired.get('wilcoxon_p'),ci.get('wilcoxon_p'))} |")
        perm=group['permutation']
        table.append(f"| {name} | Shuffled-label NEW null (p={fmt(perm['p_value'])}) | {interval_text(perm['null_auc_mean'],perm['null_auc_95_interval'])} | N/A | N/A |")
    comparison='\n'.join(table)+'\n\nNull intervals are permutation reference intervals, not subject-bootstrap confidence intervals.\n'
    (out/'comparison.md').write_text(comparison)
    fig,ax=plt.subplots()
    cohort=[r for r in result['records'] if not r['excluded']]
    for method in METHODS:
        scores=[r['methods'][method] for r in cohort]
        if cohort and np.isfinite(scores).all() and len({r['label'] for r in cohort})==2:
            fpr,tpr,_=roc_curve([r['label'] for r in cohort],scores)
            ax.plot(fpr,tpr,label=METHOD_NAMES[method])
    ax.plot([0,1],[0,1],'--',color='grey'); ax.set(xlabel='False positive rate',ylabel='True positive rate',title='NEW vs fixed baselines')
    if ax.get_legend_handles_labels()[0]: ax.legend(fontsize=6)
    fig.tight_layout(); fig.savefig(out/'roc_new_vs_baselines.png')
    # Keep the previous artifact filename usable; its content now compares baselines.
    fig.savefig(out/'roc_old_vs_new.png'); plt.close(fig)
    fig,ax=plt.subplots()
    for session,t,scores in series:
        ax.plot(t,scores,label=f"{session['subject_id']} {session.get('condition','')} {session['label']}")
        if session.get('stressor_onset') not in (None,''): ax.axvline(float(session['stressor_onset']),linestyle='--',color='red')
    ax.axhline(50,color='grey',linestyle=':'); ax.set(xlabel='Seconds',ylabel='Experimental index',ylim=(0,100))
    if 0<len(series)<9: ax.legend(fontsize=6)
    fig.tight_layout(); fig.savefig(out/'score_over_time.png'); plt.close(fig)
    fig,ax=plt.subplots(); available={k:v for k,v in result['ablation_auc_drop'].items() if v is not None}
    if available: ax.bar(list(available),list(available.values())); ax.tick_params(axis='x',rotation=45)
    else: ax.text(.5,.5,'No evaluable two-class data',ha='center',transform=ax.transAxes)
    ax.set_ylabel('AUC drop'); fig.tight_layout(); fig.savefig(out/'ablation_bar.png'); plt.close(fig)
    fig,ax=plt.subplots(); perm=result['pooled']['permutation']
    if perm['null_auc_distribution']:
        ax.hist(perm['null_auc_distribution'],bins=30); ax.axvline(perm['observed_auc'],color='red',label='Observed NEW'); ax.legend()
    else: ax.text(.5,.5,'Permutation unavailable',ha='center',transform=ax.transAxes)
    ax.set(xlabel='Null AUC',ylabel='Permutation count',title=f"Within-subject label permutation: p={fmt(perm['p_value'])}")
    fig.tight_layout(); fig.savefig(out/'permutation_null_auc.png'); plt.close(fig)
    coverage_table=['| Condition | Videos | Mean video coverage | Frame-weighted coverage | Excluded |','|---|---|---|---|---|']
    display_conditions={**result['coverage']['by_task'],**result['coverage']['by_condition']}
    for condition,c in display_conditions.items():
        coverage_table.append(f"| {condition} | {c['videos']} | {fmt(c['mean_video_percent'])}% | {fmt(c['frame_weighted_percent'])}% | {c['excluded_videos']} |")
    video_table=['| Video / segment | Condition | Valid / total frames | Coverage | Classification |','|---|---|---|---|---|']
    for r in result['records']:
        video_table.append(f"| {r['video_path']} ({r.get('start_seconds','default')}–{r.get('end_seconds','end')}) | {r['task_condition']} | {r['valid_frames']} / {r['evaluation_frames']} | {r['coverage_percent']:.2f}% | {'Excluded: '+r['exclusion_reason'] if r['excluded'] else 'Eligible'} |")
    excluded='\n'.join(f"- {r['video_path']} ({r['task_condition']}): {r['coverage_percent']:.2f}% — {r['exclusion_reason']}" for r in result['records'] if r['excluded']) or 'None.'
    failed='\n'.join(f"- {r['video_path']}: {r['reason']}" for r in result['failed_videos']) or 'None.'
    report='''# Experimental facial behavior evaluation

This is a stress-associated facial behavior index. Labels are task-based (rest vs stress task), not clinically measured stress. Nothing was trained or fitted to test labels. Thresholds, weights, the sigma floor and coverage exclusion were fixed before evaluation. Per-person baseline calibration uses the designated first 25 seconds of rest.

## Fixed rules

Before z-scoring, sigma_i = max(raw_sigma_i, 0.05 * |mu_i| + 1e-3). Then z_i = clip((f_i - mu_i) / (sigma_i + 1e-6), -3, 3). Both raw and effective sigma are recorded. Equal weights are an engineering default, not coefficients validated by Giannakakis (2017).

Coverage = 100 * valid post-pose/post-speaking-or-smiling-gate frames / all decoded frames in the evaluation segment. No-face and rejected-pose frames remain in the denominator; baseline calibration frames do not. Segments without a usable baseline are also ineligible, as in the original module. The fixed coverage rule excludes videos/segments with coverage <40% from every classification comparison, permutation and ablation. Exactly 40% remains eligible. All comparisons use this identical video cohort. A single-feature method absent on any eligible video is reported unavailable for the cohort, rather than silently evaluated on a smaller subset. All-features means all available baseline-calibrated features; missing pulse is never imputed. Per-method score coverage is also recorded.

## Metrics and inference

Primary metrics: ROC-AUC, paired Cohen's d_z, and paired Wilcoxon signed-rank p-value, each with percentile subject-cluster bootstrap 95% CI (1000 resamples, seed42). One mean score per evaluation segment; repeated subjects are resampled as intact clusters, with duplicate draws retaining their multiplicity. Paired differences are subject mean stress minus subject mean calm. Bootstrap draws without both classes or enough paired subjects are omitted for the affected metric; valid resample counts are recorded. Zero variance makes d_z undefined, not infinite. Subjects are namespaced by dataset. Every method uses the same fixed cohort and bootstrap seed/draw scheme.

Secondary metrics: accuracy, precision, recall, F1, balanced accuracy and confusion matrix under S>50. Baseline =50 by construction at baseline feature means; observed baseline frames may vary. This threshold is not a clinically validated cutoff or a percent-stress interpretation. PR-AUC uses average precision.

Permutation: freeze NEW scores and cohort, shuffle task labels within each subject 1000 times (seed42), preserving per-subject class counts. Report the full null AUC distribution and one-sided p=(1 + count(null AUC >= observed AUC))/1001. A permutation reference interval is not a bootstrap CI. Subjects without both labels cannot exchange labels; if no subject can exchange, the test is unavailable. No parameter is chosen from permutation results.

The summary table is pooled. AUC brackets on predictive methods are bootstrap CIs; the shuffled-label row shows null mean AUC and its central 95% reference interval. d_z and Wilcoxon CIs appear in comparison.md and metrics.json. Coverage in summary.md is mean per-video method score coverage across the fixed eligible cohort; report coverage below includes excluded videos. ms/frame includes the shared extraction and feature pass plus only that method's scoring time; all methods deliberately reuse the same extracted features (including pulse), so timing is not a specialized no-pulse implementation benchmark. Cached extraction timing may be reused. Permutations do not perform video inference, hence ms/frame and d_z are N/A for the null row.

Speaking/smiling gates may selectively suppress T2, so report both coverage and exclusions. HRV is a noisy camera pulse variability proxy; jaw and AU proxies are unvalidated. Unit tests do not establish real stress accuracy.

OLD has no video scorer. The adapter remains available, but OLD-vs-NEW is no longer the comparison protocol.

## Primary comparisons

'''+comparison+'\n## Condition coverage (including exclusions)\n\n'+'\n'.join(coverage_table)+'\n\n'+'\n'.join(video_table)+'\n\nT1/T2/T3 aggregates and binary-label aggregates, plus each video, are present in metrics.json.\n\n## Excluded videos\n\n'+excluded+'\n\n## Failed videos\n\n'+failed+'\n\n'+REASON+'\n'
    (out/'report.md').write_text(report)

def run(args):
    np.random.seed(42)
    if args.live:
        from .live import record
        args.manifest=record(Path(args.output)/'own_sessions')
        if not args.manifest: return
    sessions=load(args.root,args.manifest); records=[]; series=[]; validity=[]; efficiency=[]; failed=[]
    for session in sessions:
        try:
            data=read_video(session['video_path'],args.cache)
            feature_start=time.perf_counter(); rows=features(data)
            feature_ms=(time.perf_counter()-feature_start)*1000/max(len(rows),1)
            baseline_path=session.get('baseline_video_path') or session['video_path']
            base_rows=rows if baseline_path==session['video_path'] else features(read_video(baseline_path,args.cache))
            baseline=[r for r in base_rows if r['time']<25 and not r.get('gated',False)]
            model=Index(baseline)
            baseline_ok=bool(model.mu) and len([r for r in baseline if 'ear' in r])>=30
            models={m:feature_model(baseline,keys) for m,keys in METHODS.items()}
            ablations={k:Index(baseline) for k in KEYS}
            old=score_video(session['video_path'],data)
            default_start=25 if baseline_path==session['video_path'] else 0
            start=float(session['start_seconds']) if session.get('start_seconds') not in (None,'') else default_start
            end=float(session['end_seconds']) if session.get('end_seconds') not in (None,'') else float('inf')
            selected=[i for i,r in enumerate(rows) if start<=r['time']<end]
            selected_rows=[rows[i] for i in selected]
            valid=np.array(['ear' in r and np.isfinite(r['ear']) and not r.get('gated',False) for r in selected_rows])
            coverage=float(valid.mean()) if len(valid) else 0.
            reason='coverage <40%' if coverage<COVERAGE_MIN else ('insufficient baseline' if not baseline_ok else None)
            per_frame={}; timing={}
            for m,pipeline in models.items():
                tick=time.perf_counter()
                per_frame[m]=np.array([pipeline.score(r) if baseline_ok else np.nan for r in selected_rows])
                timing[m]=(time.perf_counter()-tick)*1000/max(len(selected_rows),1)
            scores=per_frame['new_all']; removed={k:[pipeline.score(r,omit=k) if baseline_ok else np.nan for r in selected_rows] for k,pipeline in ablations.items()}
            label=int(session['label'])
            if label not in (0,1): raise ValueError('Labels must be binary task labels 0/1')
            ms=float(data['ms_frame'])
            item={**session, 'subject_id':str(session['dataset'])+'::'+str(session['subject_id']), 'label':label,
                  'task_condition':str(session.get('condition') or ('T1' if label==0 else 'stress')),
                  'new':mean_score(scores), 'old':mean_score(old[selected]),
                  'methods':{m:mean_score(a) for m,a in per_frame.items()},
                  'method_coverage_percent':{m:100*float(np.isfinite(a).mean()) if len(a) else 0. for m,a in per_frame.items()},
                  'method_ms_frame':{m:ms+feature_ms+timing[m] for m in METHODS},
                  'evaluation_frames':len(selected), 'valid_frames':int(valid.sum()),
                  'coverage_percent':100*coverage,'usable_frames':int(np.isfinite(scores).sum()),
                  'scored_fraction':float(np.isfinite(scores).mean()) if len(scores) else 0.,
                  'excluded':reason is not None,'exclusion_reason':reason,
                  'calm_stability_std':float(np.std(scores[np.isfinite(scores)])) if label==0 and np.isfinite(scores).any() else None,
                  'response_latency_seconds':None,'ablation':{k:mean_score(a) for k,a in removed.items()},
                  'baseline':{'mu':model.mu,'sigma':model.sd,'raw_sigma':model.raw_sd}}
            onset=session.get('stressor_onset')
            if onset not in (None,'') and label==1:
                crossing=[r['time']-float(onset) for r,s in zip(selected_rows,scores) if r['time']>=float(onset) and s>50]
                item['response_latency_seconds']=min(crossing) if crossing else None
            records.append(item); series.append((session,[r['time'] for r in selected_rows],scores))
            efficiency.append({'video':session['video_path'],'landmark_count':75,'detector_output_landmarks':478,
                               'extraction_ms_frame':ms,'feature_ms_frame':feature_ms,'method_scoring_ms_frame':timing,
                               'method_total_ms_frame':item['method_ms_frame'],'cached_extraction_timing':True})
            if session.get('au_path'):
                p=Path(session['au_path']); p=p if p.is_absolute() else Path(args.manifest).parent/p
                validity.append({'video':session['video_path'],'metrics':au_validity(rows,p)})
        except Exception as exc:
            failed.append({'video_path':session['video_path'],'reason':str(exc)})
            warnings.warn(f"Skipping {session['video_path']}: {exc}")
    groups=sorted({str(r['dataset']) for r in records})
    result={'protocol':{'seed':42,'weights':'equal, fixed a priori','threshold':50,'decision':'S > 50',
                        'sigma_floor':'max(raw_sigma_i, 0.05 * abs(mu_i) + 1e-3)',
                        'coverage_exclusion':'coverage < 40%; fixed before evaluation',
                        'bootstrap_resamples':1000,'permutation_shuffles':1000,
                        'primary_metrics':['roc_auc','cohen_dz','wilcoxon_p'],'threshold_metrics':'secondary; baseline =50 by construction',
                        'unit':'one mean score per labeled video/segment; bootstrap by subject','trained':False},
            'old_unavailable_reason':'OLD has no video scorer. '+REASON,
            'datasets':{},'pooled':{},'records':records,'efficiency':efficiency,'au_validity':validity,'failed_videos':failed}
    for group in groups:
        result['datasets'][group]=group_metrics([r for r in records if str(r['dataset'])==group])
    result['pooled']=result['datasets'][groups[0]] if len(groups)==1 else group_metrics(records)
    result['coverage']=coverage_report(records)
    result['excluded_videos']=[{k:r[k] for k in ('video_path','subject_id','dataset','task_condition','coverage_percent','exclusion_reason')} for r in records if r['excluded']]
    result['robustness']={c:summarize([r for r in records if r['task_condition']==c]) for c in sorted({r['task_condition'] for r in records})}
    cohort=[r for r in records if not r['excluded']]; y=[r['label'] for r in cohort]
    full=auc_value(y,[r['new'] for r in cohort]) if cohort and all(np.isfinite(r['new']) for r in cohort) else None
    result['ablation_auc_drop']={}
    for k in KEYS:
        values=[r['ablation'][k] for r in cohort]
        a=auc_value(y,values) if values and np.isfinite(values).all() else None
        result['ablation_auc_drop'][k]=full-a if full is not None and a is not None else None
    save_outputs(result,series,args.output)
    print(f'Report: {Path(args.output).resolve()}/report.md; {len(records)} sessions, {len(cohort)} eligible')

def main():
    p=argparse.ArgumentParser(description='Test-only experimental facial index. Never trains or tunes.')
    p.add_argument('--dataset',choices=['ubfc_phys']); p.add_argument('--root'); p.add_argument('--manifest')
    p.add_argument('--live',action='store_true'); p.add_argument('--output',default='stress_math/results'); p.add_argument('--cache',default='stress_math/cache')
    run(p.parse_args())
if __name__=='__main__': main()
