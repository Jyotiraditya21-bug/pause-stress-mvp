import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from .core import REFERENCE
from .heuristic_mesh import StressEngine, FEATURES, GROUPS, TAU
from .extended_evaluate import holm, analyze, strata, decode_heuristics, write_outputs, METHODS, ABLATIONS

class HeuristicTests(unittest.TestCase):
    def test_300_frame_legacy_parity(self):
        # Drawing-only MediaPipe bindings can be stubbed: no detector is used.
        source=Path(__file__).with_name('legacy')/'face_stress_mesh.py'
        spec=importlib.util.spec_from_file_location('legacy_regression_reference',source)
        legacy=importlib.util.module_from_spec(spec)
        mp=SimpleNamespace(solutions=SimpleNamespace(face_mesh=SimpleNamespace(FACEMESH_TESSELATION=[])))
        with patch.dict(sys.modules,{'mediapipe':mp}):spec.loader.exec_module(legacy)
        self.assertEqual(FEATURES,legacy.FEATURES)
        self.assertEqual(set(FEATURES),set().union(*map(set,GROUPS.values())))
        rng=np.random.default_rng(42);frame=rng.integers(0,256,(160,200,3),dtype=np.uint8)
        pts=REFERENCE*10+[100,75]
        with patch.object(legacy.time,'time',return_value=0):old=legacy.StressEngine()
        new=StressEngine('H0')
        for i in range(300):
            t=i/30;p=pts+np.sin(i*.07)*.2
            if i%40 in (10,11):
                p=p.copy()
                for a,b in ((160,144),(158,153),(385,380),(387,373)):p[a]=p[b]+[0,.01]
            lm=SimpleNamespace(landmark=[SimpleNamespace(x=x/200,y=y/160) for x,y in p])
            with patch.object(legacy.time,'time',return_value=t):
                f,_=old.extract(lm,frame);old.update(f)
            g,_=new.extract(p,frame,t);new.update(g,t)
            for k in FEATURES:self.assertAlmostEqual(f[k],g[k],delta=1e-6,msg=f'{i}: {k}')
        self.assertEqual(new.base['blink_rate'],17)

    def test_time_ema_and_missing(self):
        base={k:0. for k in FEATURES};f={k:0. for k in FEATURES};f['brow_asym']=.02
        final=[]
        for fps in (15,30,60):
            e=StressEngine('H1',base);e.last_score_timestamp=0
            for t in np.arange(1,2*fps+1)/fps:e.update(f,float(t))
            final.append(e.score)
        np.testing.assert_allclose(final,final[0],atol=1e-12)
        e=StressEngine('H1',base);p=REFERENCE*10+[100,75];frame=np.zeros((160,200,3),np.uint8)
        s,_=e.process(p,frame,0,gated=True);self.assertTrue(np.isnan(s));self.assertEqual(e.score,10)
        s,_=e.process(p,frame,1,pose_valid=False);self.assertTrue(np.isnan(s))
        with self.assertRaises(ValueError):e.process(p,frame,.5)

    def test_holm(self):
        v=holm({str(i):{'p_value_two_sided_centered_bootstrap':p} for i,p in enumerate([.01,.03,.04,None])})
        self.assertEqual([v[str(i)]['holm_adjusted_p_value'] for i in range(3)],[.03,.06,.06])
        self.assertIsNone(v['3']['holm_adjusted_p_value'])

    def test_real_decode_and_h1_baseline(self):
        import cv2
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'synthetic.avi');writer=cv2.VideoWriter(path,cv2.VideoWriter_fourcc(*'MJPG'),30,(200,160))
            for i in range(110):writer.write(np.full((160,200,3),80+i%5,np.uint8))
            writer.release();p=np.column_stack((REFERENCE*10+[100,75],np.zeros(478)))
            data={'times':np.arange(110)/30,'landmarks':np.repeat(p[None],110,axis=0),'pose':np.zeros((110,3))}
            rows=[{'time':float(t),'gated':i==100} for i,t in enumerate(data['times'])]
            s,rest,_=decode_heuristics(path,data,rows)
            self.assertEqual(len(rest),109);self.assertTrue(np.isnan(s['H0'][:90]).all());self.assertTrue(np.isfinite(s['H0'][90:]).all())
            base=StressEngine.rest_baseline(rest)
            s,_,_=decode_heuristics(path,data,rows,base)
            self.assertTrue(np.isnan(s['H1'][100]));self.assertTrue(np.isfinite(s['H0'][100]))

    def test_complete_runner_no_hf_and_coverage_exclusion(self):
        import cv2
        from .extended_evaluate import run
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'rest.avi');writer=cv2.VideoWriter(path,cv2.VideoWriter_fourcc(*'MJPG'),5,(200,160))
            for i in range(150):writer.write(np.full((160,200,3),100,np.uint8))
            writer.release();p=np.column_stack((REFERENCE*10+[100,75],np.zeros(478)))
            data={'times':np.arange(150)/5,'landmarks':np.repeat(p[None],150,axis=0),'pose':np.zeros((150,3)),
                  'green':np.full(150,100.),'fps':np.array(5.),'ms_frame':np.array(1.)}
            sessions=[{'video_path':path,'subject_id':str(i),'label':label,'dataset':'UBFC-Phys','condition':task}
                      for i in range(2) for task,label in [('T1',0),('T2',1),('T3',1)]]
            args=SimpleNamespace(live=False,root=None,manifest=None,cache=str(Path(d)/'cache'),output=str(Path(d)/'results'),hf_models=False)
            with patch('stress_math.extended_evaluate.load',return_value=sessions),patch('stress_math.evaluate.read_video',return_value=data),patch('stress_math.metrics.RESAMPLES',10):
                run(args)
            import json
            result=json.loads((Path(args.output)/'metrics.json').read_text())
            self.assertEqual(len(result['records']),6)
            self.assertTrue(all(not r['excluded'] for r in result['records']))
            self.assertEqual(result['pooled']['methods']['H1']['roc_auc'],.5)
            self.assertEqual(result['pooled']['methods']['M1']['status'],'unavailable: missing score on fixed cohort')
            self.assertIn('single_blink_rate',result['math_baselines']['methods'])
            class DummyHF:
                def __init__(self,name,*a):
                    self.name=name;self._metadata={'model_name':name,'revision_hash':'synthetic-test-only','license_text':None,'params_count':1}
                @property
                def metadata(self):return self._metadata
                def score_video(self,path,data,cache):
                    from .hf_models import sample_indices
                    ids=sample_indices(data['times'])
                    return {'indices':ids,'scores':np.full(len(ids),.4),'ms_per_sample':1.,'crop_decode_ms_per_sample':.1}
            args.hf_models=True
            with patch('stress_math.extended_evaluate.HFModel',DummyHF),patch('stress_math.extended_evaluate.load',return_value=sessions),patch('stress_math.evaluate.read_video',return_value=data),patch('stress_math.metrics.RESAMPLES',10):
                run(args)
            result=json.loads((Path(args.output)/'metrics.json').read_text())
            self.assertEqual(result['pooled']['methods']['F2']['roc_auc'],.5)
            self.assertEqual(result['models']['M1']['revision_hash'],'synthetic-test-only')
            self.assertTrue(all(r['methods']['F2'] is not None for r in result['records']))
            args.hf_models=False
            for count,excluded in [(9,True),(10,False)]:
                bad={k:np.array(v,copy=True) for k,v in data.items()}
                bad['landmarks'][125+count:]=np.nan
                with patch('stress_math.extended_evaluate.load',return_value=sessions[:1]),patch('stress_math.evaluate.read_video',return_value=bad),patch('stress_math.metrics.RESAMPLES',10):
                    run(args)
                result=json.loads((Path(args.output)/'metrics.json').read_text())
                self.assertEqual(result['records'][0]['excluded'],excluded)
                self.assertEqual(result['records'][0]['coverage_percent'],count*4.)



    def test_reports_and_task_condition_metadata(self):
        records=[]
        for subject in range(3):
            for task,label in [('T1',0),('T2',1),('T3',1)]:
                score=20+40*label+subject
                records.append({'subject_id':str(subject),'dataset':'UBFC-Phys','label':label,'video_path':f'vid_s{subject}_{task}.avi',
                    'task_condition':task,'condition':'normal','methods':{m:score for m in (*METHODS,*ABLATIONS)},
                    'excluded':False,'coverage_percent':80.,'method_ms_frame':{m:1. for m in METHODS}})
        # Keep tiny bootstraps for output contract test; parity test uses actual 300 frames.
        with patch('stress_math.metrics.RESAMPLES',20):
            result={'pooled':analyze(records,pairs=False),'records':records,'group_ablation':analyze(records,tuple(ABLATIONS),False,False),
                    'ablation_auc_drop':{},'excluded_videos':[],'failed_videos':[],**strata(records)}
        result['pooled']['pairwise_auc_differences']={}
        self.assertEqual(result['task_split']['T1_vs_T2']['methods']['H1']['roc_auc'],1)
        self.assertEqual(result['skin_tone']['status'],'not available; never inferred')
        with tempfile.TemporaryDirectory() as d:
            write_outputs(result,d)
            for name in ('metrics.json','summary.md','comparison.md','report.md','group_ablation.png','task_split_auc.png','roc_all_methods.png'):
                self.assertGreater((Path(d)/name).stat().st_size,0)

if __name__=='__main__':unittest.main()
