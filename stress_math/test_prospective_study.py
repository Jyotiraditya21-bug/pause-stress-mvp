import unittest
from .evaluate_prospective_study import analyse,POLICY_SHA
class StudyEvaluationTests(unittest.TestCase):
    def test_empty_and_failed_data_cannot_pass(self):
        r=analyse([{'pairs':[]}]);self.assertNotIn('PASS',r['decision'])
        pair=dict(id='p',subject_id='synthetic',condition='rest',records=[dict(id=str(i),created_at=f'2026-10-20T00:0{i*7}:00Z',status='failed',average=None,acceptancePolicy={'version':'prospective-acquisition-1','policySha256':POLICY_SHA}) for i in range(2)])
        r=analyse([{'pairs':[pair]}]);self.assertEqual(r['coverage']['rest']['attempts'],2);self.assertEqual(r['coverage']['rest']['percent'],0)
        self.assertFalse(r['methods']['geometry']['passed'])

class FullSyntheticGateTests(unittest.TestCase):
    def test_incomplete_pair_is_retained_without_adding_an_undeclared_global_veto(self):
        from .evaluate_prospective_study import NUISANCES
        pairs=[];nuisance=[]
        for subject in range(20):
            sid=f'synthetic-{subject}'
            for condition,base in [('rest',7.),('speech',3.),('arithmetic',3.)]:
                score=base+subject*.02
                records=[dict(id=f'{sid}-{condition}-{i}',created_at=f'2026-10-20T00:0{i*7}:00Z',status='ok',average=score,acceptancePolicy={'version':'prospective-acquisition-1','policySha256':POLICY_SHA},mlResult={'averageStressProbability':1-score/10}) for i in range(2)]
                pairs.append(dict(id=sid+condition,subject_id=sid,condition=condition,records=records))
            for method in ('geometry','neural'):
                for name in NUISANCES:nuisance.append(dict(method=method,nuisance=name,subject_id=sid,clip_id=sid+'-rest',accepted=True,baseline_score=7.,perturbed_score=7.01))
        extra=dict(pairs[0]);extra['id']='synthetic-incomplete';extra['records']=[dict(pairs[0]['records'][0],id='synthetic-extra')];pairs.append(extra)
        result=analyse([{'pairs':pairs}],nuisance)
        self.assertEqual(len(result['invalid_pairs']),1)
        self.assertEqual(result['coverage']['rest']['attempts'],41)
        self.assertEqual(result['decision'],'PASS engineering pilot gates only')
