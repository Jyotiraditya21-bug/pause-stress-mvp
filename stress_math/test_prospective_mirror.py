import json,subprocess,unittest
from pathlib import Path
import numpy as np
from .prospective_mirror import ProspectiveReliability
class ProspectiveParityTests(unittest.TestCase):
    def test_cross_language_acceptance_and_scores(self):
        rng=np.random.default_rng(42);cases=[]
        specs=[([5]*9,1.),([9]*7+[6,4],1.),([5]*9,.05),([5,5,5,9,5,5,5,5,5],1.),([5]*9,.8)]
        specs += [(rng.uniform(1,9,9).tolist(),float(rng.choice([.5,.8,1.]))) for _ in range(12)]
        for seq,fraction in specs:
            samples=[]
            for i in range(100,1000):
                valid=i%20<round(20*fraction)
                samples.append(dict(time=i/100,row=dict(x=seq[i//100-1]) if valid else None,context=dict(yaw=0,pitch=0,brightness=100)))
            cases.append(samples)
        js=json.loads(subprocess.check_output(['node',str(Path(__file__).with_name('js_prospective_parity.mjs'))],input=json.dumps(cases).encode()))
        for samples,expected in zip(cases,js):
            s=ProspectiveReliability(['x'],lambda r:r['x'])
            for row in samples:s.add(row['time'],row['row'],row['context'])
            actual=s.finish()
            for k in ['status','consensusWindowMask','acceptancePolicy','coverageDetails']:self.assertEqual(actual[k],expected[k])
            self.assertEqual(actual['average'] is None,expected['average'] is None)
            if actual['average'] is not None:self.assertAlmostEqual(actual['average'],expected['average'],places=6)
            np.testing.assert_allclose(actual['windowScores'],expected['windowScores'],atol=1e-6) if all(v is not None for v in actual['windowScores']) else self.assertEqual(actual['windowScores'],expected['windowScores'])
if __name__=='__main__':unittest.main()
