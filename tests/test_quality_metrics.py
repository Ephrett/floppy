import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'engine'))
from quality_metrics import attributed_votes
class QualityTests(unittest.TestCase):
    def test_attribution_and_repeated_votes(self):
        deliveries=[dict(job_id='ours',ts=10,seq=100,engine='mlx'),dict(job_id='shared',ts=10,seq=101,engine='mlx')]
        def vote(job,ts,verdict='not',foreign=False): return dict(job_id=job,ts=ts,attestor='peer',verdict=verdict,foreign=foreign)
        rows=[vote('ours',9),vote('ours',11),vote('ours',12,'useful'),vote('shared',11),vote('shared',12,foreign=True),vote('lost',12)]
        got={r['job_id']:r for r in attributed_votes(rows,deliveries)}
        self.assertEqual(set(got),{'ours','shared'})
        self.assertEqual(got['ours']['verdict'],'useful')
        self.assertFalse(got['ours']['ambiguous'])
        self.assertTrue(got['shared']['ambiguous'])
        self.assertEqual(got['ours']['engine'],'mlx')
if __name__=='__main__': unittest.main()
