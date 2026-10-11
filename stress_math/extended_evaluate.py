"""Fixed, test-only legacy/pretrained evaluation. No label-dependent fitting."""
import itertools
import json
import time
import warnings
from pathlib import Path
import cv2
import numpy as np
from scipy.special import expit
from .core import Index, KEYS
from .video import features
from .heuristic_mesh import StressEngine, FEATURES, GROUPS, MOUTH, TAU
from .hf_evaluate import calibrate, zscore, fuse, NAMES as HF_NAMES
from .hf_models import HFModel, MODEL_A, MODEL_B, sample_indices
from .datasets import load
from .metrics import summarize, permutation_test, paired_method_auc_difference, method_correlations, auc_value

METHODS = ('M0','M1','M2','M3','M4','M5','H0','H1','F1','F2')
NAMES = {**HF_NAMES, 'H0':'Legacy as written', 'H1':'Harmonized legacy',
         'F1':'Math + harmonized legacy', 'F2':'Math + legacy + both pretrained models'}
ABLATIONS = {**{f'{g}_alone': tuple(k) for g,k in GROUPS.items()},
             **{f'without_{g}':tuple(k for k in FEATURES if k not in group) for g,group in GROUPS.items()},
             **{f'X_feature_{k}_alone':(k,) for k in GROUPS['X']},
             'without_mouth':tuple(k for k in FEATURES if k not in MOUTH),
             **{f'without_{k}':tuple(x for x in FEATURES if x!=k) for k in FEATURES}}
MATH_BASELINES = {**{f'single_{k}': (k,) for k in KEYS}, 'new_without_rppg':tuple(k for k in KEYS if k not in ('hr','rmssd')), 'new_all':KEYS}
CONDITIONS = ('normal','low_light','glasses','yaw_plus15','yaw_minus15')


def holm(tests):
    """Holm across the complete family of available pairwise tests."""
    ordered=sorted((v['p_value_two_sided_centered_bootstrap'],k) for k,v in tests.items()
                   if v.get('p_value_two_sided_centered_bootstrap') is not None)
    previous=0.
    for rank,(p,k) in enumerate(ordered):
        previous=max(previous,min(1.,(len(ordered)-rank)*p))
        tests[k]['raw_p_value']=p
        tests[k]['holm_adjusted_p_value']=previous
    for v in tests.values():
        v.setdefault('raw_p_value',None);v.setdefault('holm_adjusted_p_value',None)
        v['holm_family_size']=len(ordered)
    return tests


def analyze(records, methods=METHODS, permutations=True, pairs=True):
    eligible=[r for r in records if not r['excluded']]
    result={'methods':{},'permutations':{}}
    for m in methods:
        # Refuse silent subset changes if any method is missing on the fixed cohort.
        adapted=[{**r,'s':r['methods'].get(m,np.nan)} for r in eligible]
        missing=any(not np.isfinite(r['s']) for r in adapted)
        metric={'status':'unavailable: missing score on fixed cohort'} if missing else summarize(adapted,'s')
        metric['coverage_percent']=float(np.mean([r['coverage_percent'] for r in eligible])) if eligible else None
        vals=[r.get('method_ms_frame',{}).get(m) for r in eligible]
        metric['ms_per_frame']=float(np.mean([v for v in vals if v is not None])) if any(v is not None for v in vals) else None
        result['methods'][m]=metric
        if permutations:
            result['permutations'][m]=permutation_test([] if missing else adapted,'s')
    if pairs:
        result['pairwise_auc_differences']=holm({f'{a}_vs_{b}':paired_method_auc_difference(records,a,b)
                                                for a,b in itertools.combinations(methods,2)})
        result['auc_difference_vs_M0']={m:paired_method_auc_difference(records,m) for m in methods}
        result['score_correlations']=method_correlations(records)
    return result


def task_name(record):
    explicit=str(record.get('task') or record.get('task_condition') or record.get('condition') or '')
    if explicit in ('T1','T2','T3'): return explicit
    stem=Path(record['video_path']).stem
    return next((t for t in ('T1','T2','T3') if stem.endswith('_'+t)),explicit)


def strata(records):
    ubfc=[r for r in records if str(r['dataset']).lower().replace('_','-')=='ubfc-phys']
    splits={name:analyze([r for r in ubfc if task_name(r) in tasks],pairs=False)
            for name,tasks in [('T1_vs_T2',('T1','T2')),('T1_vs_T3',('T1','T3')),('pooled',('T1','T2','T3'))]}
    flags={}
    for m in METHODS:
        a=splits['T1_vs_T2']['methods'][m].get('roc_auc')
        b=splits['T1_vs_T3']['methods'][m].get('roc_auc')
        p=splits['pooled']['methods'][m].get('roc_auc')
        flags[m]={'T2_only_flag':bool(a is not None and b is not None and p is not None and a>.5 and p>.5 and b<=.5),
                  'rule':'fixed descriptive flag: pooled and T2 AUC >0.5, T3 AUC <=0.5; not proof of causality'}
    robustness_methods=('M0','H1','X_alone',*(f'X_feature_{k}_alone' for k in GROUPS['X']))
    robustness={c:analyze([r for r in records if str(r.get('condition'))==c],robustness_methods,False,False) for c in CONDITIONS}
    drops={m:None for m in robustness_methods}
    for m in drops:
        normal=robustness['normal']['methods'][m].get('roc_auc');low=robustness['low_light']['methods'][m].get('roc_auc')
        if normal is not None and low is not None:drops[m]=low-normal
    skin=[r for r in records if r.get('skin_tone') not in (None,'')]
    skin_result={'status':'not available; never inferred'} if not skin else {
        'source':'manifest-provided skin_tone metadata only; never inferred',
        'groups':{v:analyze([r for r in skin if str(r['skin_tone'])==v],('M0','H1','X_alone'),False,False) for v in sorted({str(r['skin_tone']) for r in skin})}}
    speaking={t:{'mean_gated_percent':float(np.mean([r.get('speaking_gated_percent',0.) for r in ubfc if task_name(r)==t])) if any(task_name(r)==t for r in ubfc) else None, 'videos':[{'video_path':r['video_path'],'gated_percent':r.get('speaking_gated_percent'), 'valid_percent':r['coverage_percent']} for r in ubfc if task_name(r)==t]} for t in ('T1','T2','T3')}
    return {'speaking_coverage_by_task':speaking,'task_split':splits,'T2_only_flags':flags,'robustness':robustness,'low_light_auc_change':drops,'skin_tone':skin_result}


def decode_heuristics(path,data,rows,base=None):
    """Extract full-rate features once per variant; no windows or wall clock."""
    engines={'H0':StressEngine('H0'),'H1':StressEngine('H1',base)}
    engines.update({m:StressEngine('H1',base,selected=k) for m,k in ABLATIONS.items()})
    n=len(rows);scores={m:np.full(n,np.nan) for m in engines};rest=[]
    cap=cv2.VideoCapture(str(path));tick=time.perf_counter()
    if not cap.isOpened():cap.release();raise ValueError(f'Cannot decode {path}')
    try:
        for i,(t,p,a,row) in enumerate(zip(data['times'],data.get('raw_landmarks',data['landmarks']),data['pose'],rows)):
            ok,frame=cap.read()
            if not ok:raise ValueError('Decoded frame count differs from landmark cache')
            if not np.isfinite(p).all():continue
            h0,_=engines['H0'].process(p,frame,float(t));scores['H0'][i]=h0
            valid=np.isfinite(a).all() and max(abs(a[0]),abs(a[1]))<=35 and not row.get('gated',False)
            if not valid:continue
            f,_=engines['H1'].extract(p,frame,float(t))
            if t<25:rest.append(f)
            if base is not None:
                for m,engine in engines.items():
                    if m=='H0':continue
                    score,_,_=engine.update(f,float(t));scores[m][i]=100*(1-score/10)
    finally:cap.release()
    return scores,rest,(time.perf_counter()-tick)*1000/max(n,1)


def run(args):
    from .evaluate import read_video,clean,coverage_report
    if args.live:
        from .live import record
        args.manifest=record(Path(args.output)/'own_sessions')
        if not args.manifest:return
    sessions=load(args.root,args.manifest);cache=Path(args.cache)
    models={};metadata={};errors={}
    if getattr(args,'hf_models',False):
        for key,name,mode,revision in [('M1',MODEL_A,'stress',getattr(args,'hf_revision_a',None)),('M2',MODEL_B,'emotion',getattr(args,'hf_revision_b',None))]:
            model=HFModel(name,mode,revision,Path(getattr(args,'hf_cache',None) or cache/'hf_weights'),getattr(args,'hf_batch_size',8));models[key]=model
            try:metadata[key]=dict(model.metadata)
            except Exception as exc:errors[key]=str(exc);metadata[key]={'model_name':name,'revision_hash':None,'license_text':None,'error':str(exc)}
    memo={};base_memo={};records=[];failed=[]
    active=METHODS if models else ('M0','H0','H1','F1')
    def video(path):
        if path not in memo:
            data=read_video(path,args.cache);tick=time.perf_counter();rows=features(data);ms=(time.perf_counter()-tick)*1000/max(len(rows),1)
            ids=sample_indices(data['times']);prob={};timing={}
            for m,model in models.items():
                try:
                    if m in errors:raise RuntimeError(errors[m])
                    out=model.score_video(path,data,cache/'hf_scores')
                    if not np.array_equal(ids,out['indices']):raise ValueError('Sample timelines differ')
                    prob[m]=out['scores'];timing[m]=float(out['ms_per_sample']+out['crop_decode_ms_per_sample'])
                except Exception as exc:prob[m]=np.full(len(ids),np.nan);timing[m]=None;warnings.warn(str(exc))
            memo[path]=(data,rows,ids,prob,timing,ms)
        return memo[path]
    def baseline(path):
        if path not in base_memo:
            data,rows,ids,probs,_,_=video(path)
            _,rest,_=decode_heuristics(path,data,rows)
            base=StressEngine.rest_baseline(rest)
            hs,_,_=decode_heuristics(path,data,rows,base)
            cal=[r for r in rows if r['time']<25 and 'ear' in r and not r.get('gated',False)]
            if len(cal)<30:raise ValueError('Insufficient shared rest baseline')
            index=Index(cal);math=np.array([index.score(r) if r['time']<25 else np.nan for r in rows])[ids]
            mask=np.array([rows[i]['time']<25 and 'ear' in rows[i] and not rows[i].get('gated',False) for i in ids])
            comps={'M0':math,'H1':hs['H1'][ids],**probs}
            for v in comps.values():mask &= np.isfinite(v)
            stats={m:calibrate(v[mask]) for m,v in comps.items()}
            if any(v is None for v in stats.values()):raise ValueError('Insufficient shared scalar baseline')
            base_memo[path]=(base,cal,stats)
        return base_memo[path]
    for s in sessions:
        try:
            path=s['video_path'];data,rows,ids,prob,hf_ms,feature_ms=video(path)
            bp=s.get('baseline_video_path') or path;base,cal,stats=baseline(bp)
            hs,_,heur_ms=decode_heuristics(path,data,rows,base)
            start=float(s['start_seconds']) if s.get('start_seconds') not in (None,'') else (25 if bp==path else 0)
            if bp==path:start=max(start,25.)
            end=float(s['end_seconds']) if s.get('end_seconds') not in (None,'') else np.inf
            index=Index(cal);tick=time.perf_counter()
            math=np.array([index.score(r) if start<=r['time']<end else np.nan for r in rows])
            math_baselines={}
            for name,keys in MATH_BASELINES.items():
                model=Index([{k:v for k,v in r.items() if k in keys or k in ('time','gated')} for r in cal])
                math_baselines[name]=np.array([model.score({k:v for k,v in r.items() if k in keys or k in ('time','gated')}) if start<=r['time']<end else np.nan for r in rows])
            math_ms=(time.perf_counter()-tick)*1000/max(len(rows),1)
            positions=np.array([j for j,i in enumerate(ids) if start<=rows[i]['time']<end],int);selected=ids[positions]
            scores={**{m:v[selected] for m,v in math_baselines.items()},'M0':math[selected],**{m:v[selected] for m,v in hs.items()}}
            fusion_tick=time.perf_counter()
            h1=scores['H1'];zmath=zscore(scores['M0'],stats['M0']);zh=zscore(h1,stats['H1'])
            scores['F1']=100*expit((zmath+zh)/2)
            if models:
                a=prob['M1'][positions];b=prob['M2'][positions]
                scores.update(fuse(scores['M0'],a,b,stats))
                scores['F2']=100*expit((zmath+zh+zscore(a,stats['M1'])+zscore(b,stats['M2']))/4)
            else:
                for m in set(METHODS)-set(scores):scores[m]=np.full(len(selected),np.nan)
            fusion_ms=(time.perf_counter()-fusion_tick)*1000/max(len(selected),1)
            gated=np.array([bool(rows[i].get('gated',False)) for i in selected])
            valid=np.array(['ear' in rows[i] and not rows[i].get('gated',False) for i in selected])
            available={m:float(np.isfinite(scores[m]).mean()*100) if len(selected) else 0. for m in METHODS}
            for m in active:valid &= np.isfinite(scores[m])
            coverage=float(valid.mean()) if len(valid) else 0.
            for m in scores:scores[m][~valid]=np.nan
            raw_selected=[i for i,r in enumerate(rows) if start<=r['time']<end]
            raw_valid=sum('ear' in rows[i] and not rows[i].get('gated',False) for i in raw_selected)
            raw_coverage=raw_valid/max(len(raw_selected),1)
            speaking_percent=100*sum(bool(rows[i].get('gated',False)) for i in raw_selected)/max(len(raw_selected),1)
            excluded=coverage<.4 or raw_coverage<.4
            raw_per_sample=len(rows)/max(len(ids),1)
            shared=(float(data['ms_frame'])+feature_ms)*raw_per_sample
            timing={m:shared+math_ms*raw_per_sample+fusion_ms for m in scores}
            for m in scores:
                if m in hs or m in ('F1','F2'):timing[m]+=heur_ms*raw_per_sample
                branches={'M1':('M1',),'M2':('M2',),'M3':('M1','M2'),'M4':('M1',),'M5':('M2',),'F2':('M1','M2')}.get(m,())
                if any(hf_ms.get(k) is None for k in branches):timing[m]=None
                else:timing[m]+=sum(hf_ms[k] for k in branches)
            means={m:float(v[np.isfinite(v)].mean()) if np.isfinite(v).any() else np.nan for m,v in scores.items()}
            label=int(s['label'])
            if label not in (0,1):raise ValueError('Binary task labels required')
            item={**s,'subject_id':str(s['dataset'])+'::'+str(s['subject_id']),'label':label,'methods':means,'new':means['M0'],
                  'task_condition':task_name(s),'baseline':stats,'heuristic_baseline':base,'evaluation_frames':len(selected),
                  'valid_frames':int(valid.sum()),'coverage_percent':100*coverage,'component_available_coverage_percent':available,
                  'speaking_gated_percent':speaking_percent,'full_rate_evaluation_frames':len(raw_selected),
                  'full_rate_valid_frames_after_M0_gating':raw_valid,'full_rate_coverage_percent':100*raw_coverage,
                  'method_coverage_percent':{m:100*coverage for m in METHODS},'method_ms_frame':timing,
                  'excluded':excluded,'exclusion_reason':('full-rate gated coverage <40%' if raw_coverage<.4 else 'common sampled coverage <40%') if excluded else None}
            records.append(item)
        except Exception as exc:
            failed.append({'video_path':s['video_path'],'subject_id':s['subject_id'],'reason':str(exc)});warnings.warn(str(exc))
    pooled=analyze(records);extras=strata(records)
    eligible=[r for r in records if not r['excluded']];y=[r['label'] for r in eligible]
    full=auc_value(y,[r['methods']['H1'] for r in eligible]) if eligible else None
    ablation=analyze(records,tuple(ABLATIONS),False,False)
    drops={k:full-m.get('roc_auc') if full is not None and m.get('roc_auc') is not None else None for k,m in ablation['methods'].items()}
    for k,model in models.items():
        if model._metadata is not None:metadata[k]=dict(model.metadata)
    params={'M0':0,'H0':0,'H1':0,'F1':0,'M1':metadata.get('M1',{}).get('params_count'),'M2':metadata.get('M2',{}).get('params_count')}
    params.update({m:None if any(params[k] is None for k in branches) else sum(params[k] for k in branches)
                   for m,branches in {'M3':('M1','M2'),'M4':('M1',),'M5':('M2',),'F2':('M1','M2')}.items()})
    counts={'M0':8,'H0':24,'H1':24,'M1':1,'M2':4,'M3':13,'M4':9,'M5':12,'F1':32,'F2':37}
    for m in METHODS:pooled['methods'][m].update(params_count=params[m],features_count=counts[m])
    result={'protocol':{'trained':False,'seed':42,'baseline_seconds':25,'sigma_floor':'max(sigma, .05*abs(mu)+1e-3)',
                        'z_clip':[-3,3],'fusion':'100*sigmoid(equal-weight mean baseline z)','threshold':50,'threshold_metrics':'secondary',
                        'H0':'90-frame median in each video, blink 17/min, no feature gating; common comparison mask applied only for metrics',
                        'H1':'25s rest median, personal blink baseline, M0 MAR/smile and 35-degree pose gating',
                        'ema_tau_seconds':TAU,'groups':GROUPS,'mouth_ablation':MOUTH,'sample_fps':5,
                        'coverage_exclusion':'full-rate gated or common sampled coverage <40%; fixed before evaluation','bootstrap_resamples':1000,'permutation_shuffles':1000,
                        'active_common_cohort_methods':active,'pairwise_correction':'Holm over all available pooled pairwise tests; centred bootstrap p approximation',
                        'timing':'full-rate extraction amortized per 5fps sample; heuristic timing conservatively includes all ablations; excludes initialization/rest calibration',
                        'feature_count':'scalar input channels, not learned model dimensions; M2 = four emotion probabilities'},
            'math_baselines':analyze(records,tuple(MATH_BASELINES),True,False),'datasets':{d:analyze([r for r in records if str(r['dataset'])==d]) for d in sorted({str(r['dataset']) for r in records})},'models':metadata,'pooled':pooled,'records':records,'coverage':coverage_report(records),
            'failed_videos':failed,'excluded_videos':[r for r in records if r['excluded']],
            'old_unavailable_reason':'OLD has no video scorer','group_ablation':ablation,'ablation_auc_drop':drops,**extras}
    result['coverage']['denominator']='all 5fps comparison samples in the evaluation segment; full-rate decoded gating coverage separately recorded per video'
    write_outputs(result,args.output)
    print(f'Extended report: {Path(args.output).resolve()}/report.md; {len(records)} sessions, {len(eligible)} eligible')


def write_outputs(result,output):
    from .evaluate import clean,fmt,interval_text
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from sklearn.metrics import roc_curve
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    table=['| Method | AUC [95% CI] | d_z | Coverage % | ms/frame | #features |','|---|---|---|---|---|---|']
    for m,v in result['pooled']['methods'].items():
        table.append(f"| {m}: {NAMES[m]} | {interval_text(v.get('roc_auc'),v.get('subject_bootstrap_95ci',{}).get('roc_auc'))} | {fmt(v.get('within_subject',{}).get('cohen_dz'))} | {fmt(v.get('coverage_percent'))} | {fmt(v.get('ms_per_frame'))} | {v.get('features_count','N/A')} |")
        null=result['pooled']['permutations'][m]
        table.append(f"| {m} shuffled-label null | {interval_text(null['null_auc_mean'],null['null_auc_95_interval'])} | N/A | {fmt(v.get('coverage_percent'))} | N/A | N/A |")
    for m,v in result.get('math_baselines',{}).get('methods',{}).items():
        table.append(f"| {m} | {interval_text(v.get('roc_auc'),v.get('subject_bootstrap_95ci',{}).get('roc_auc'))} | {fmt(v.get('within_subject',{}).get('cohen_dz'))} | {fmt(v.get('coverage_percent'))} | {fmt(v.get('ms_per_frame'))} | {len(MATH_BASELINES[m])} |")
    summary='\n'.join(table)+'\n';(out/'summary.md').write_text(summary)
    details=['## Primary metrics by method','| Method | d_z [95% CI] | Wilcoxon p [95% CI] | Params |','|---|---|---|---|']
    for m,v in result['pooled']['methods'].items():
        ci=v.get('subject_bootstrap_95ci',{});paired=v.get('within_subject',{})
        details.append(f"| {m} | {interval_text(paired.get('cohen_dz'),ci.get('cohen_dz'))} | {interval_text(paired.get('wilcoxon_p'),ci.get('wilcoxon_p'))} | {v.get('params_count')} |")
    comparison=summary+'\n'+'\n'.join(details)+'\n\n## Task split, speaking gating, Holm paired comparisons, robustness and ablations\n\n'
    comparison+=json.dumps(clean({k:result[k] for k in ('speaking_coverage_by_task','task_split','T2_only_flags','robustness','low_light_auc_change','skin_tone','ablation_auc_drop') if k in result}),indent=2)
    comparison+='\n\n## Retained math baselines\n\n'+json.dumps(clean(result.get('math_baselines',{})),indent=2)
    comparison+='\n\n'+json.dumps(clean(result['pooled']['pairwise_auc_differences']),indent=2)
    (out/'comparison.md').write_text(comparison)
    report='''# Fixed training-free legacy and pretrained evaluation

H0/H1 scales and weights are hand-set engineering priors, not fitted or validated. Texture/colour features are confounded by lighting and skin tone. Mouth features are confounded by speech. Labels are task-based, not clinically measured stress. Thresholds, fusion weights and group definitions were fixed before evaluation. Nothing is trained, fine-tuned or tuned on test data.

H0 retains the original 90-frame median calibration, blink baseline 17/min, and ungated extraction. H1 uses median features from the first 25 seconds of designated rest, including the individual's blink baseline; M0 MAR/smile gating and |yaw| or |pitch| >35 rejection make frames missing, never held. Both extract full-rate video frames. Fair comparison then uses the same 5fps complete-case timeline for every active method; H0's unmasked availability is reported separately. First-25s rest frames used for normalization are excluded from classification. Videos below 40% full-rate gated coverage or common sampled coverage are excluded; both denominators are recorded. Failed baseline/videos are separately listed, never silently substituted.

The port uses video/capture timestamps only. EMA alpha=1-exp(-dt/0.316), GAIN=4, original deviation and smile relief; S_h=100*(1-score/10). Threshold S_h>50 corresponds to original score<5. Legacy gaze/head-jitter buffers remain 45 frames: only EMA smoothing is made FPS independent. Group and mouth ablations remove the selected features and their weights; removing smile_lift also removes its relief term to avoid leakage.

Fusion normalizes each branch against the same usable first 25s of rest: sigma=max(raw sigma,0.05*abs(mu)+1e-3), denominator sigma+1e-6, clipped [-3,3], equal mean then sigmoid to 0–100. H0/H1 have no sigma in their original deviation scoring; the sigma floor applies to M0 and fusion normalization. H0/H1 rest need not score 50: engineering-prior scale differs. Baseline=50 by construction describes normalized branches at their means, not a clinical cutoff. Threshold metrics >50 are secondary.

Primary metrics are ROC-AUC, Cohen d_z and Wilcoxon p with intact-subject bootstrap 95% CIs (1000 draws, seed42), using per-video/segment means, never independent frames. Each method has a within-subject shuffled-label null (1000, seed42) with fixed predictions. Pairwise paired-AUC differences use shared subject draws and approximate two-sided centred-bootstrap p-values. Holm-Bonferroni covers all available pooled pairwise tests. Null intervals are reference intervals, not bootstrap CIs. T2-only flags are fixed descriptive checks (T2 and pooled AUC>0.5 but T3<=0.5), not causal findings. Speaking coverage is the percentage rejected by the MAR/smile proxy; it does not establish that each frame contains speech.

Models are third-party pretrained, not trained by us. fer-stress-vit's training data and splits are undocumented so train/test overlap with UBFC-Phys cannot be excluded. Emotion probabilities are not stress measurements. M1–M5 are retained, with F1/F2 added. RGB 15%-margin crops, AutoImageProcessor, batched fp32 torch.no_grad(), MPS else CPU, immutable revisions and probability caches retain the original comparator protocol. License text and revision hashes are recorded in metrics.json; absent license text is never invented. Optional dependencies are lazy-loaded, and the core port runs without transformers.

Condition analysis uses provided manifest metadata only. No skin tone is inferred. Missing datasets/conditions produce unavailable metrics, never fabricated results. Runtime reports exclude initialization and baseline extraction and conservatively amortize full-rate heuristic/ablation work over comparison samples. Feature counts are explicit scalar channels, not transformer dimensions; learned parameter counts exclude the shared detector.

OLD has no video scorer. No new heuristic is enabled in the deployed browser graph by this offline evaluation extension.

'''+comparison+'\n\n## Excluded and failed videos\n\n'+json.dumps(clean({'excluded':result['excluded_videos'],'failed':result['failed_videos']}),indent=2)
    (out/'report.md').write_text(report)
    (out/'metrics.json').write_text(json.dumps(clean(result),indent=2,allow_nan=False))
    eligible=[r for r in result['records'] if not r['excluded']]
    fig,ax=plt.subplots()
    for m in METHODS:
        y=[r['label'] for r in eligible];s=[r['methods'][m] for r in eligible]
        if len(set(y))==2 and np.isfinite(s).all():
            x,t,_=roc_curve(y,s);ax.plot(x,t,label=m)
    ax.plot([0,1],[0,1],'--',color='grey');ax.set(xlabel='False positive rate',ylabel='True positive rate',title='Same-cohort ROC')
    if ax.get_legend_handles_labels()[0]:ax.legend()
    fig.savefig(out/'roc_all_methods.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,5));keys=[k for k in ABLATIONS if k in ('G_alone','T_alone','X_alone') or k in ('without_G','without_T','without_X','without_mouth')]
    vals=[result['group_ablation']['methods'][k].get('roc_auc') for k in keys]
    ax.bar(keys,[v if v is not None else np.nan for v in vals]);ax.set(ylabel='H1 ablation AUC',ylim=(0,1),title='Fixed groups and mouth ablation');ax.tick_params(axis='x',rotation=25)
    fig.tight_layout();fig.savefig(out/'group_ablation.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(12,5));x=np.arange(len(METHODS))
    for i,(key,split) in enumerate(result['task_split'].items()):
        v=[split['methods'][m].get('roc_auc') for m in METHODS];ax.bar(x+(i-1)*.25,[a if a is not None else np.nan for a in v],.25,label=key)
    ax.set_xticks(x,METHODS);ax.set(ylabel='ROC-AUC',ylim=(0,1),title='UBFC-Phys task splits');ax.legend();fig.tight_layout();fig.savefig(out/'task_split_auc.png');plt.close(fig)
