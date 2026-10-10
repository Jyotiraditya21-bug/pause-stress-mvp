"""Optional pretrained comparisons on a common 5fps complete-case timeline."""
import json,time,warnings
from pathlib import Path
import numpy as np
from scipy.special import expit
from .core import Index
from .video import features
from .hf_models import HFModel,MODEL_A,MODEL_B,sample_indices
from .datasets import load
from .metrics import summarize,permutation_test,paired_method_auc_difference,method_correlations

METHODS=('M0','M1','M2','M3','M4','M5')
NAMES={'M0':'Math index','M1':'fer-stress-vit alone','M2':'Emotion-derived alone',
       'M3':'Math + stress ViT + emotion (equal fusion)','M4':'Math + stress ViT (equal fusion)',
       'M5':'Math + emotion (equal fusion)'}
COMPONENTS={'M0':('M0',),'M1':('M1',),'M2':('M2',),'M3':('M0','M1','M2'),'M4':('M0','M1'),'M5':('M0','M2')}


def calibrate(values):
    a=np.asarray(values,float);a=a[np.isfinite(a)]
    if len(a)<5: return None
    mu=float(a.mean());raw=float(a.std())
    return {'mu':mu,'raw_sigma':raw,'sigma':max(raw,.05*abs(mu)+1e-3),'n':len(a)}


def zscore(values,baseline):
    a=np.asarray(values,float)
    if baseline is None: return np.full_like(a,np.nan)
    return np.clip((a-baseline['mu'])/(baseline['sigma']+1e-6),-3,3)


def fuse(math,a,b,baselines):
    z={key:zscore(values,baselines.get(key)) for key,values in [('M0',math),('M1',a),('M2',b)]}
    return {'M0':np.asarray(math,float),'M1':100*expit(z['M1']),'M2':100*expit(z['M2']),
            'M3':100*expit((z['M0']+z['M1']+z['M2'])/3),
            'M4':100*expit((z['M0']+z['M1'])/2),'M5':100*expit((z['M0']+z['M2'])/2)}


def grouped(records):
    metrics={};nulls={};differences={}
    eligible=[r for r in records if not r['excluded']]
    for method in METHODS:
        adapted=[{**r,'method_score':r['methods'][method]} for r in eligible]
        metrics[method]=summarize(adapted,'method_score')
        nulls[method]=permutation_test(adapted,'method_score')
        differences[method]=paired_method_auc_difference(records,method)
    return {'methods':metrics,'permutations':nulls,'auc_difference_vs_M0':differences,
            'score_correlations':method_correlations(records)}


def run(args):
    from .evaluate import read_video,clean,fmt,interval_text,coverage_report
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from sklearn.metrics import roc_curve
    np.random.seed(42)
    if args.live:
        from .live import record
        args.manifest=record(Path(args.output)/'own_sessions')
        if not args.manifest: return
    sessions=load(args.root,args.manifest);cache=Path(args.cache)
    model_cache=Path(getattr(args,'hf_cache',None) or cache/'hf_weights')
    batch_size=getattr(args,'hf_batch_size',8)
    models={'M1':HFModel(MODEL_A,'stress',getattr(args,'hf_revision_a',None),model_cache,batch_size),
            'M2':HFModel(MODEL_B,'emotion',getattr(args,'hf_revision_b',None),model_cache,batch_size)}
    metadata={}; errors={}
    for key,model in models.items():
        try: metadata[key]=dict(model.metadata)
        except Exception as exc:
            errors[key]=str(exc);metadata[key]={'model_name':model.name,'revision_hash':None,'license_text':None,'params_count':None,'error':str(exc)}
    records=[];series=[];failed=[]; video_memo={}; baseline_memo={}
    def video(path):
        if path not in video_memo:
            data=read_video(path,args.cache);tick=time.perf_counter();rows=features(data)
            feature_ms_total=(time.perf_counter()-tick)*1000
            probs={}; timings={}; statuses={}
            ids=sample_indices(data['times'])
            for key,model in models.items():
                try:
                    if key in errors: raise RuntimeError(errors[key])
                    output=model.score_video(path,data,cache/'hf_scores')
                    if not np.array_equal(output['indices'],ids): raise ValueError('Comparator sampling does not match common frame timeline')
                    probs[key]=output['scores'];timings[key]=float(output['ms_per_sample']+output['crop_decode_ms_per_sample']);statuses[key]={'cached':output['cached']}
                except Exception as exc:
                    probs[key]=np.full(len(ids),np.nan);timings[key]=None;statuses[key]={'error':str(exc)}
                    warnings.warn(f'{key} unavailable on {path}: {exc}')
            video_memo[path]=(data,rows,ids,probs,timings,statuses,feature_ms_total)
        return video_memo[path]
    def baseline(path):
        if path not in baseline_memo:
            data,rows,ids,prob,_,_,_=video(path)
            calibration=[r for r in rows if r['time']<25 and not r.get('gated',False)]
            index=Index(calibration)
            usable=sum('ear' in r for r in calibration)>=30 and bool(index.mu)
            mask=np.asarray([rows[i]['time']<25 and 'ear' in rows[i] and not rows[i].get('gated',False) for i in ids],bool)
            score_all=np.asarray([index.score(r) if r['time']<25 and usable else np.nan for r in rows])
            components={'M0':score_all[ids],'M1':prob['M1'],'M2':prob['M2']}
            # Same rest frames for every component's personal normalization.
            common=mask.copy()
            for values in components.values():common &= np.isfinite(values)
            stats={key:calibrate(values[common]) for key,values in components.items()}
            baseline_memo[path]=(calibration,stats,usable and all(s is not None for s in stats.values()))
        return baseline_memo[path]
    for session in sessions:
        try:
            path=session['video_path'];data,rows,ids,probs,hf_ms,statuses,feature_total=video(path)
            base_path=session.get('baseline_video_path') or path
            calibration,baselines,base_ok=baseline(base_path)
            index=Index(calibration)
            start=float(session['start_seconds']) if session.get('start_seconds') not in (None,'') else (25 if base_path==path else 0)
            end=float(session['end_seconds']) if session.get('end_seconds') not in (None,'') else float('inf')
            selected_raw=[i for i,r in enumerate(rows) if start<=r['time']<end]
            tick=time.perf_counter();math_all=np.full(len(rows),np.nan)
            for i in selected_raw:math_all[i]=index.score(rows[i])
            math_ms_total=(time.perf_counter()-tick)*1000
            sample_positions=np.array([j for j,i in enumerate(ids) if start<=rows[i]['time']<end],int)
            selected_ids=ids[sample_positions];times=np.asarray(data['times'])[selected_ids]
            math=math_all[selected_ids];a=probs['M1'][sample_positions];b=probs['M2'][sample_positions]
            gating=np.asarray(['ear' in rows[i] and np.isfinite(rows[i]['ear']) and not rows[i].get('gated',False) for i in selected_ids],bool)
            masks={'M0':gating&np.isfinite(math),'M1':gating&np.isfinite(a),'M2':gating&np.isfinite(b)}
            common=masks['M0']&masks['M1']&masks['M2']
            coverage=float(common.mean()) if len(common) else 0.
            reason='insufficient shared baseline' if not base_ok else ('common coverage <40%' if coverage<.4 else None)
            tick=time.perf_counter();scores=fuse(math,a,b,baselines);fusion_ms=(time.perf_counter()-tick)*1000/max(len(times),1)
            for method in METHODS:scores[method][~common]=np.nan
            raw_count=max(len(data['times']),1);sample_count=max(len(ids),1)
            shared=(float(data['ms_frame'])*raw_count+feature_total)/sample_count
            math_ms=math_ms_total/max(len(times),1)
            component_ms={'M0':math_ms,'M1':hf_ms['M1'],'M2':hf_ms['M2']}
            timing={m:shared+sum(component_ms[k] for k in COMPONENTS[m])+fusion_ms if all(component_ms[k] is not None for k in COMPONENTS[m]) else None for m in METHODS}
            label=int(session['label'])
            if label not in (0,1):raise ValueError('Binary task labels required')
            means={m:float(values[np.isfinite(values)].mean()) if np.isfinite(values).any() else np.nan for m,values in scores.items()}
            item={**session,'subject_id':str(session['dataset'])+'::'+str(session['subject_id']),'label':label,
                  'task_condition':str(session.get('condition') or ('T1' if label==0 else 'stress')),
                  'methods':means,'new':means['M0'],'baseline':baselines,'evaluation_frames':len(times),
                  'valid_frames':int(common.sum()),'coverage_percent':100*coverage,
                  'component_available_coverage_percent':{k:100*float(v.mean()) if len(v) else 0. for k,v in masks.items()},
                  'method_coverage_percent':{m:100*coverage for m in METHODS},'method_ms_frame':timing,
                  'excluded':reason is not None,'exclusion_reason':reason,'model_status':statuses}
            records.append(item);series.append((session,times,scores,item['excluded']))
        except Exception as exc:
            failed.append({'video_path':session['video_path'],'reason':str(exc)});warnings.warn(f'Skipping {session["video_path"]}: {exc}')
    for key,model in models.items():
        if model._metadata is not None:metadata[key]=dict(model.metadata)
    params={'M0':0,'M1':metadata['M1'].get('params_count'),'M2':metadata['M2'].get('params_count')}
    params.update({m:sum(params[k] for k in COMPONENTS[m]) if all(params[k] is not None for k in COMPONENTS[m]) else None for m in ('M3','M4','M5')})
    datasets=sorted({str(r['dataset']) for r in records});by_dataset={d:grouped([r for r in records if str(r['dataset'])==d]) for d in datasets}
    pooled=by_dataset[datasets[0]] if len(datasets)==1 else grouped(records)
    result={'protocol':{'mode':'optional pretrained comparators','seed':42,'sample_fps':5,'face_margin_each_side':.15,
                        'weights':'equal and fixed a priori','fusion':'100 * sigmoid(mean(component baseline z-scores))',
                        'M0':'existing raw 0-100 math index; z_M0 used only in fusion',
                        'M1_M2':'100 * sigmoid(clipped baseline-normalized pretrained probability)',
                        'sigma_floor':'max(raw_sigma, 0.05 * abs(mu) + 1e-3)','z_clip':[-3,3],
                        'baseline':'same usable shared first 25 s of designated rest','bootstrap_resamples':1000,
                        'permutation_shuffles_per_method':1000,'cohort':'same videos and complete-case 5fps frames for every method',
                        'coverage_exclusion':'common frame coverage <40%; fixed before evaluation','trained':False,
                        'params_count':'comparator learned parameters; shared MediaPipe detector excluded'},
            'models':metadata,'method_params_count':params,'datasets':by_dataset,'pooled':pooled,'records':records,
            'coverage':coverage_report(records),'failed_videos':failed,'metadata_errors':errors,
            'excluded_videos':[{k:r[k] for k in ('video_path','subject_id','coverage_percent','exclusion_reason')} for r in records if r['excluded']],
            'old_unavailable_reason':'OLD has no video scorer'}
    eligible=[r for r in records if not r['excluded']]
    for group_name,group in [*by_dataset.items(),('pooled',pooled)]:
        cohort=eligible if group_name=='pooled' else [r for r in eligible if str(r['dataset'])==group_name]
        for m,metric in group['methods'].items():
            metric.update(coverage_percent=float(np.mean([r['method_coverage_percent'][m] for r in cohort])) if cohort else None,
                          ms_per_frame=float(np.mean([r['method_ms_frame'][m] for r in cohort if r['method_ms_frame'][m] is not None])) if any(r['method_ms_frame'][m] is not None for r in cohort) else None,
                          params_count=params[m])
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    (out/'metrics.json').write_text(json.dumps(clean(result),indent=2,allow_nan=False))
    table=['| Dataset | Method | ROC-AUC [95% CI] | d_z [95% CI] | Wilcoxon p [95% CI] | Coverage | ms/frame | Params |','|---|---|---|---|---|---|---|---|']
    summary=['| Method | ROC-AUC [95% CI] | d_z | Wilcoxon p | Coverage | ms/frame | Params |','|---|---|---|---|---|---|---|']
    for name,group in [*by_dataset.items(),('pooled',pooled)]:
        for m,metric in group['methods'].items():
            ci=metric.get('subject_bootstrap_95ci',{});paired=metric.get('within_subject',{})
            auc=interval_text(metric.get('roc_auc'),ci.get('roc_auc'))
            table.append(f"| {name} | {m}: {NAMES[m]} | {auc} | {interval_text(paired.get('cohen_dz'),ci.get('cohen_dz'))} | {interval_text(paired.get('wilcoxon_p'),ci.get('wilcoxon_p'))} | {fmt(metric['coverage_percent'])}% | {fmt(metric['ms_per_frame'])} | {params[m] if params[m] is not None else 'N/A'} |")
            if name=='pooled':summary.append(f"| {m}: {NAMES[m]} | {auc} | {fmt(paired.get('cohen_dz'))} | {fmt(paired.get('wilcoxon_p'))} | {fmt(metric['coverage_percent'])}% | {fmt(metric['ms_per_frame'])} | {params[m] if params[m] is not None else 'N/A'} |")
            null=group['permutations'][m]
            table.append(f"| {name} | {m} shuffled null (p={fmt(null['p_value'])}) | {interval_text(null['null_auc_mean'],null['null_auc_95_interval'])} | N/A | N/A | {fmt(metric['coverage_percent'])}% | N/A | N/A |")
            if name=='pooled':summary.append(f"| {m} shuffled-label null (1000) | {interval_text(null['null_auc_mean'],null['null_auc_95_interval'])} | N/A | N/A | {fmt(metric['coverage_percent'])}% | N/A | N/A |")
    (out/'summary.md').write_text('\n'.join(summary)+'\n');(out/'comparison.md').write_text('\n'.join(table)+'\n')
    fig,ax=plt.subplots()
    if len({r['label'] for r in eligible})==2:
        for m in METHODS:
            x,y,_=roc_curve([r['label'] for r in eligible],[r['methods'][m] for r in eligible]);ax.plot(x,y,label=m)
        ax.legend()
    ax.plot([0,1],[0,1],'--',color='grey');ax.set(xlabel='False positive rate',ylabel='True positive rate',title='Fixed pretrained comparators')
    fig.savefig(out/'roc_pretrained.png');plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(12,7))
    for m,ax in zip(METHODS,axes.flat):
        null=pooled['permutations'][m]
        if null['null_auc_distribution']:ax.hist(null['null_auc_distribution'],bins=25);ax.axvline(null['observed_auc'],color='red')
        ax.set(title=f"{m}: p={fmt(null['p_value'])}",xlabel='Null AUC')
    fig.tight_layout();fig.savefig(out/'permutation_null_auc.png');plt.close(fig)
    fig,ax=plt.subplots()
    for session,t,scores,excluded in series:
        ax.plot(t,scores['M0'],label=f"{session['subject_id']} M0{' (excluded)' if excluded else ''}")
        if session.get('stressor_onset') not in (None,''):ax.axvline(float(session['stressor_onset']),color='red',linestyle='--')
    ax.set(xlabel='Seconds',ylabel='Math index S',ylim=(0,100));fig.savefig(out/'score_over_time.png');plt.close(fig)
    report='''# Optional third-party pretrained comparator evaluation

These models are third-party pretrained models, not trained by us. No training, fine-tuning or fitting on test labels occurred. Per-subject baseline normalization is the fixed rest calibration only. Fusion weights are equal and fixed a priori. No fusion weights, thresholds, preprocessing or model choices were selected from test outcomes.

fer-stress-vit training data and splits are undocumented at the required participant/dataset level, so train/test overlap with UBFC-Phys cannot be excluded. Even a high score on UBFC-Phys would not establish independent generalization. Emotion probabilities are not stress measurements. Task labels are rest versus stress-task conditions, not clinically measured stress.

M0 is the existing math S on its 0-100 scale. M1 and M2 use 100*sigmoid(z) where z is the probability normalized against the same shared first 25 seconds of rest. For fusion, z_M0 is computed from math S against that rest segment. All z values use sigma=max(raw sigma,0.05*abs(mu)+1e-3), denominator sigma+1e-6, clip [-3,3]. M3=100*sigmoid((z_M0+z_M1+z_M2)/3); M4/M5 use the corresponding two-component mean. These remain behavior/label proxies, not clinical stress percentages.

The comparison uses one identical 5fps timeline and evaluation window per video. RGB crops come from pose-valid MediaPipe bounding boxes with 15% margin on each side, clipped to image bounds, then each model's AutoImageProcessor. Inference is batched fp32 under torch.no_grad(), eval mode, MPS if available else CPU. Each model/revision is pinned to the hash resolved by huggingface_hub. Missing labels/checkpoints fail explicitly; randomly initialized missing prediction weights are rejected. Scores are cached with video path/size/mtime, source fingerprints, timestamps, model identity/revision and fixed crop/sampling settings.

Every method uses the intersection of usable math and both pretrained predictions after pose/expression gating. Baseline calibration uses that same rest-frame intersection. Videos below 40% common sampled-frame coverage or without a shared usable baseline are excluded for every method. Component availability before intersection is also reported, so failure of one model is visible rather than a hidden cohort change. Calibration frames never enter classification metrics.

Primary metrics are ROC-AUC, paired Cohen d_z and paired Wilcoxon p, with 1000 subject-cluster bootstrap CIs, seed42. Bootstrap duplicates retain subject multiplicity; invalid resample counts are recorded. Paired AUC differences versus M0 use the same subject draws for both predictions; the two-sided centred-bootstrap p is an approximation. M0/M1/M2 Spearman agreement uses paired session mean scores and is descriptive, not an independent-frame significance test. Each method has its own 1000 within-subject shuffled-label null with scores frozen and corrected one-sided p=(1+null>=observed)/1001. Null brackets are reference intervals, not bootstrap confidence intervals. Threshold metrics S>50 are secondary; baseline feature means correspond to 50 by construction, not a validated cutoff.

Parameter counts cover pretrained comparator parameters, excluding the shared MediaPipe detector. ms/frame is per 5fps comparison sample and includes shared full-rate landmark/feature extraction, relevant model inference/crop/decode passes and scoring; one-time model initialization and rest-calibration costs are excluded. Cached timings represent the original inference run. Model-download time is not inference latency.

No license text is fabricated: metrics.json records full repository license documents when published, otherwise the model-card declaration or null. Missing/partial license text must not be interpreted as a grant. No inference-provider call uploads video or images; Hugging Face is contacted only to download model artifacts/metadata.

OLD has no video scorer. Optional pretrained comparators are not enabled in the GitHub Pages graph.

## Comparisons

'''+ '\n'.join(table)+'\n\n## Paired AUC differences versus M0\n\n'+json.dumps(clean(pooled['auc_difference_vs_M0']),indent=2)+'\n\n## M0/M1/M2 Spearman agreement\n\n'+json.dumps(clean(pooled['score_correlations']),indent=2)+'\n\n## Excluded/failed videos\n\n'+json.dumps(clean({'excluded':result['excluded_videos'],'failed':failed}),indent=2)+'\n\nCoverage details, model names, immutable revisions, available license text, parameter counts, baselines and complete permutation null distributions are in metrics.json.\n'
    (out/'report.md').write_text(report);print(f'Pretrained report: {out.resolve()}/report.md; {len(records)} sessions, {len(eligible)} eligible')
