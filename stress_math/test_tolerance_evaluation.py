import csv,tempfile,unittest
from pathlib import Path
from copy import deepcopy
from .evaluate_tolerance import comparison,adoption,run,METHODS,repeat_stats,condition_shift

def records():
    rows=[]
    for s in range(3):
        for task,level in (('T1',7),('T2',4),('T3',3)):
            for condition in ('still','natural_movement'):
                for repeat,offset in enumerate((-.2,.2)):
                    # Synthetic unit-test numbers, never product accuracy results.
                    v=level+offset+s*.1+(0.05 if condition=='natural_movement' else 0)
                    methods={m:dict(average=v,tier='NORMAL') for m in METHODS}
                    rows.append(dict(subject_id=str(s),task=task,condition=condition,dataset='ubfc_phys',methods=methods))
    return rows

class ToleranceEvaluationTests(unittest.TestCase):
    def test_fixed_decision_passes_only_with_complete_synthetic_evidence(self):
        stats=comparison(records());d=adoption(stats)
        self.assertEqual(d['status'],'PASS');self.assertFalse(d['enable_frontalize3d'])
        changed=deepcopy(stats);changed['methods']['NEW']['conditions']['natural_movement']['acceptance_rate']=.89
        self.assertEqual(adoption(changed)['criteria']['movement_acceptance']['status'],'FAIL')
        changed=deepcopy(stats);changed['paired_ubfc_auc']['NEW']['T1_vs_T2']['auc_drop']=.021
        self.assertEqual(adoption(changed)['status'],'FAIL')
        self.assertEqual(adoption(stats,1)['status'],'FAIL')
    def test_shift_is_paired_by_subject_and_task_and_sd_removes_person_offsets(self):
        rows=records();shift=condition_shift(rows,'NEW','natural_movement')
        self.assertAlmostEqual(shift['mean_shift'],.05,places=8)
        still=[r for r in rows if r['condition']=='still'];a=repeat_stats(still,'OLD')
        for r in still:r['methods']['OLD']['average']+=int(r['subject_id'])*100
        self.assertAlmostEqual(a['within_condition_sd'],repeat_stats(still,'OLD')['within_condition_sd'],places=8)
    def test_empty_manifest_outputs_unavailable_metrics_and_fail_not_fabricated_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest=Path(temp)/'manifest.csv';manifest.write_text('video_path,subject_id,condition,task,dataset\n')
            out=Path(temp)/'out';result=run(manifest,out)
            self.assertEqual(result['decision']['status'],'FAIL');self.assertFalse(result['decision']['adopt_new'])
            for name in ('metrics.json','report.md','acceptance_vs_sd.png'):self.assertTrue((out/name).is_file())
            self.assertIn('tiers never fabricate', (out/'report.md').read_text())
    def test_extraction_failure_is_listed_and_blocks_adoption(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest=Path(temp)/'manifest.csv';manifest.write_text('video_path,subject_id,condition,task,dataset\nmissing.mp4,s1,still,T1,ubfc_phys\n')
            def failed(path):raise ValueError('unit fixture: decode failed')
            result=run(manifest,Path(temp)/'out',extractor=failed)
            self.assertEqual(len(result['failed_videos']),1);self.assertEqual(result['decision']['status'],'FAIL')

if __name__=='__main__':unittest.main()
