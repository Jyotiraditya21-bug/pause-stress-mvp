import tempfile,unittest
from pathlib import Path
from .repeatability import icc21,condition_stats,repeated_measures_corr,own_within_subject_auc,run
class ValidationToolTests(unittest.TestCase):
 def test_icc21_is_one_for_identical_repeat_offsets(self):self.assertAlmostEqual(icc21([[1,1],[2,2],[3,3]]),1.)
 def test_repeatability_summary_and_correlation(self):
  rows=[]
  for subject,base in (('a',2.),('b',5.),('c',8.)):
   for session,delta in (('day1',0.),('day2',.2),('day3',-.1)):rows.append(dict(subject_id=subject,session_id=session,condition='rest',day=session,score=base+delta,self_report=base+delta))
  stats=condition_stats(rows);self.assertEqual(stats['rest']['subjects_with_repeats'],3);self.assertIsNotNone(stats['rest']['mdc95']);self.assertGreater(repeated_measures_corr(rows)['r'],.99)
 def test_rest_vs_arithmetic_and_speech_auc_use_subject_repeats(self):
  rows=[]
  for s,base in [('a',2.),('b',5.),('c',8.),('d',4.)]:
   for cond,score in [('rest',8.),('arithmetic',3.),('speech',4.)]:rows.append(dict(subject_id=s,condition=cond,score=score+base*.01))
  result=own_within_subject_auc(rows)
  self.assertEqual(result['T1_vs_T2']['subjects'],4);self.assertEqual(result['T1_vs_T3']['subjects'],4)
  self.assertGreater(result['T1_vs_T2']['ci95'][0],.99)
 def test_report_fails_if_predeclared_evidence_missing(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'sessions.csv';p.write_text('subject_id,session_id,day,condition,score,self_report\na,a,1,rest,2,2\na,b,2,rest,2.1,2\nb,a,1,rest,4,4\nb,b,2,rest,4.1,4\n')
   result=run(p,Path(d)/'out');self.assertEqual(result['decision']['status'],'FAIL');self.assertTrue((Path(d)/'out/report.md').is_file());self.assertTrue((Path(d)/'out/bland_altman.png').is_file())
if __name__=='__main__':unittest.main()
