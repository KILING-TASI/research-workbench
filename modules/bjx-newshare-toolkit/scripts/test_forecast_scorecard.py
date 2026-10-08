import tempfile,unittest
from pathlib import Path
from prediction_review import store,scorecard,LABELS


class Scorecard(unittest.TestCase):
    def record(self):
        return {'mode':'first-live-capture','eligibleForFrozenComparison':True,
                'evidenceGrade':'original-rate-text-matched-publication-time-declared','modelVersion':'teaching-source',
                'code':'920022','decisionCutoff':'2026-10-01T09:00:00+08:00',
                'metrics':{k:{'predictedThresholdFunds':'110','actualConditionalThresholdFunds':'100'} for k in LABELS}}

    def test_signed_bias_and_small_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'r.json';store(path,self.record());result=scorecard({'reviews':[str(path)]})
            row=result['summary']['teaching-source']['P50']
            self.assertEqual(row['meanSignedErrorPct'],'10.0');self.assertEqual(row['meanAbsoluteErrorPct'],'10.0')
            self.assertIsNone(row['sampleErrorStdPct']);self.assertFalse(result['automaticFusion'])
            with self.assertRaises(ValueError):scorecard({'reviews':[str(path),str(path)]})

    def test_replay_and_unmatched_actual_not_counted(self):
        with tempfile.TemporaryDirectory() as directory:
            paths=[]
            for i,key in enumerate(('mode','evidenceGrade')):
                record=self.record();record[key]='unverified';path=Path(directory)/(str(i)+'.json');store(path,record);paths.append(str(path))
            result=scorecard({'reviews':paths});self.assertEqual(result['summary'],{});self.assertEqual(len(result['excluded']),2)

if __name__=='__main__':unittest.main()
