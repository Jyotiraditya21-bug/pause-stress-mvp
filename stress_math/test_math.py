import unittest
import numpy as np
from .core import REFERENCE,geometry,normalize,Index,pulse
from .metrics import basic,summarize,permutation_test

class MathTests(unittest.TestCase):
    def test_similarity_invariance(self):
        rng=np.random.default_rng(42); p=REFERENCE+ rng.normal(0,.01,REFERENCE.shape)
        original=geometry(p)
        for _ in range(30):
            angle=rng.uniform(-np.pi,np.pi); r=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
            q=p@r*rng.uniform(.2,5)+rng.uniform(-100,100,2)
            transformed=geometry(q)
            for k in original:
                self.assertLess(abs(original[k]-transformed[k])/max(abs(original[k]),1e-6),.01,k)
    def test_fixed_score_and_gate(self):
        base=[{'blink_rate':float(i)} for i in range(10)]
        self.assertAlmostEqual(Index(base).score({'blink_rate':4.5}),50)
        self.assertTrue(np.isnan(Index(base).score({'blink_rate':5,'gated':True})))
        self.assertGreater(Index(base).score({'blink_rate':100}),50)
    def test_hr_and_low_fps(self):
        t=np.arange(0,25,1/30); g=100+2*np.sin(2*np.pi*1.2*t)
        self.assertAlmostEqual(pulse(t,g)['hr'],72,delta=3)
        self.assertEqual(pulse(t[::3],g[::3]),{})
    def test_metrics_and_subject_bootstrap(self):
        records=[{'subject_id':s,'label':y,'new':float(20+60*y)} for s in ('a','b') for y in (0,1)]
        result=summarize(records)
        self.assertEqual(result['roc_auc'],1)
        self.assertEqual(result['subject_bootstrap_95ci']['accuracy'],[1,1])
        self.assertEqual(basic([0,1],[50,50])['confusion_matrix'],[[1,0],[1,0]])

    def test_evaluator_outputs_on_synthetic_landmarks(self):
        import tempfile, json
        from pathlib import Path
        from unittest.mock import patch
        from argparse import Namespace
        from .evaluate import run
        t=np.arange(0,35,.1)
        p=np.zeros((len(t),478,3)); p[:,:,:2]=REFERENCE
        p[:, :, :2]*=30
        data={'times':t,'landmarks':p,'pose':np.zeros((len(t),3)),
              'green':100+np.sin(t),'ms_frame':np.array(10.)}
        sessions=[dict(video_path='synthetic-rest.avi',subject_id='synthetic',label=0,dataset='synthetic'),
                  dict(video_path='synthetic-task.avi',subject_id='synthetic',label=1,dataset='synthetic')]
        with tempfile.TemporaryDirectory() as folder:
            args=Namespace(live=False,root=None,manifest=None,cache=folder,output=folder)
            with patch('stress_math.evaluate.load',return_value=sessions), patch('stress_math.evaluate.extract',return_value=data): run(args)
            result=json.loads((Path(folder)/'metrics.json').read_text())
            self.assertEqual(len(result['records']),2)
            self.assertIn('OLD has no video scorer',result['pooled']['OLD']['status'])
            self.assertIn('single_hr',result['pooled']['methods'])
            self.assertEqual(result['pooled']['methods']['single_hr']['status'],'unavailable on the fixed comparison cohort')
            self.assertEqual(len(result['pooled']['permutation']['null_auc_distribution']),1000)
            self.assertEqual(result['records'][0]['coverage_percent'],100)
            self.assertIn('0.05 * |mu_i| + 1e-3',(Path(folder)/'report.md').read_text())
            self.assertEqual((Path(folder)/'summary.md').read_text().count('| Method |'),1)
            for name in ('report.md','comparison.md','summary.md','roc_new_vs_baselines.png','roc_old_vs_new.png','score_over_time.png','ablation_bar.png','permutation_null_auc.png'):
                self.assertTrue((Path(folder)/name).exists())

    def test_sigma_floor(self):
        for mu in (0., -10., 20.):
            model=Index([{'brow_furrow':mu} for _ in range(6)])
            floor=.05*abs(mu)+1e-3
            self.assertEqual(model.raw_sd['brow_furrow'],0)
            self.assertAlmostEqual(model.sd['brow_furrow'],floor)
            score=model.score({'brow_furrow':mu+floor, 'time':1})
            self.assertAlmostEqual(score,100/(1+np.exp(-floor/(floor+1e-6))))
        model=Index([{'blink_rate':v} for v in (-100,0,100,200,300)])
        self.assertEqual(model.sd['blink_rate'],model.raw_sd['blink_rate'])

    def test_primary_intervals_and_exclusion(self):
        records=[{'subject_id':str(i),'label':label,'new':40.+label*(i+1)} for i in range(5) for label in (0,1)]
        records.append({'subject_id':'excluded','label':0,'new':100.,'excluded':True})
        m=summarize(records)
        self.assertEqual(m['n'],10)
        for key in ('roc_auc','cohen_dz','wilcoxon_p'):
            self.assertIsNotNone(m['primary'][key]['ci95'])
            self.assertEqual(m['primary'][key]['ci95'],m['subject_bootstrap_95ci'][key])
        self.assertIn('baseline = 50',m['secondary']['note'])

    def test_permutation_reproducibility(self):
        records=[{'subject_id':str(i),'label':label,'new':float(20+60*label)} for i in range(8) for label in (0,1)]
        a=permutation_test(records); b=permutation_test(records)
        self.assertEqual(a,b)
        self.assertEqual(len(a['null_auc_distribution']),1000)
        self.assertAlmostEqual(a['null_auc_mean'],.5,delta=.03)
        self.assertGreaterEqual(a['p_value'],1/1001)
        self.assertLess(a['p_value'],.05)
        expected=(1+sum(v>=a['observed_auc'] for v in a['null_auc_distribution']))/1001
        self.assertEqual(a['p_value'],expected)
        self.assertIn('unavailable',permutation_test([{'subject_id':'a','label':0,'new':20},{'subject_id':'b','label':1,'new':80}])['status'])

    def test_coverage_cutoff_and_fixed_cohort(self):
        import tempfile,json
        from pathlib import Path
        from unittest.mock import patch
        from argparse import Namespace
        from .evaluate import run,METHODS
        sessions=[dict(video_path=name+'.avi',subject_id='p',label=label,dataset='synthetic',condition=task) for name,label,task in [('rest',0,'T1'),('low',1,'T2'),('boundary',1,'T3')]]
        def extracted(path,cache): return {'times':np.arange(350)/10,'ms_frame':np.array(2.),'name':path}
        def rows(data):
            keep=39 if data['name']=='low.avi' else (40 if data['name']=='boundary.avi' else 100)
            return [dict(time=i/10,ear=.3,gated=(i>=250+keep), **{k:float(i%7) for k in ('blink_rate','brow_furrow','lip_press','lip_corner','jaw_clench','jitter')}) for i in range(350)]
        with tempfile.TemporaryDirectory() as folder:
            args=Namespace(live=False,root=None,manifest=None,cache=folder,output=folder)
            with patch('stress_math.evaluate.load',return_value=sessions),patch('stress_math.evaluate.extract',side_effect=extracted),patch('stress_math.evaluate.features',side_effect=rows): run(args)
            result=json.loads((Path(folder)/'metrics.json').read_text())
            self.assertTrue(result['records'][1]['excluded'])
            self.assertEqual(result['records'][1]['coverage_percent'],39)
            self.assertFalse(result['records'][2]['excluded'])
            self.assertEqual(result['records'][2]['coverage_percent'],40)
            self.assertEqual(result['pooled']['NEW']['n'],2)
            self.assertEqual(len(result['excluded_videos']),1)
            self.assertEqual(result['coverage']['by_task']['T2']['mean_video_percent'],39)
            self.assertEqual(result['coverage']['by_binary_label']['1']['mean_video_percent'],39.5)
            for method in METHODS:
                if method not in ('single_hr','single_rmssd'):
                    self.assertEqual(result['pooled']['methods'][method]['n'],2)
            self.assertEqual(len(result['pooled']['permutation']['null_auc_distribution']),1000)

if __name__=='__main__': unittest.main()
