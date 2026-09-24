import ast,json,re,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from delivery_quality import job_block_reason,output_issues,one_sentence
class EvidenceTests(unittest.TestCase):
 def test_invented_measurement(self):
  self.assertTrue(output_issues('Analyze the workload.','The flamegraph analysis reveals that 42% of CPU time is spent in formatting.'))
  self.assertFalse(output_issues('Measured formatting: 42% of CPU time.','The analysis shows 42% of CPU time is spent in formatting.'))
  self.assertFalse(output_issues('Suggest a threshold.','For example, assume 42% of CPU time is spent in formatting.'))
 def test_unverified_percentage_improvement(self):
  self.assertTrue(output_issues('Analyze allocation pressure.', 'This refactoring reduces the frequency of garbage collection cycles by 40 percent.'))
  self.assertFalse(output_issues('Measured reduction: 40 percent.', 'This refactoring reduces the frequency of garbage collection cycles by 40 percent.'))
  self.assertFalse(output_issues('Suggest a target.', 'For example, assume this reduces garbage collection cycles by 40 percent.'))
 def test_missing_artifact(self):
  self.assertIsNotNone(job_block_reason('Profiling','Analyze bottlenecks using flamegraphs. Success: isolates the hot execution path.'))
  self.assertIsNone(job_block_reason('Profiling','Explain how to record and read a flamegraph.'))
 def test_reference_without_source(self):
  self.assertTrue(output_issues('TLS renewal','Use RFC 5928 for certificate lifetime.'))
  self.assertFalse(output_issues('Compare against RFC 5280.','Use RFC 5280.'))
 def generator(self, engine):
  source=Path(__file__).resolve().parents[1]/'engine'/'kibble-bot.py'
  node=next(n for n in ast.parse(source.read_text(encoding="utf-8")).body if isinstance(n,ast.FunctionDef) and n.name=='generate')
  ns=dict(re=re,one_sentence=one_sentence,job_block_reason=job_block_reason,output_issues=output_issues,SEED_HEX='TEST_SECRET',_load_env=lambda:{'BOT_ENGINES':'mlx,claude'},_prompt=lambda *a:'prompt',_finish_sentence=lambda x:x,ENGINES={'mlx':engine,'claude':lambda *a: (_ for _ in ()).throw(AssertionError('Claude disabled'))})
  exec(compile(ast.Module(body=[node],type_ignores=[]),'generate','exec'),ns);return ns['generate']
 def test_repair_is_bounded_and_claude_off(self):
  calls=[]
  def engine(*args):calls.append(args);return 'Use RFC 5928 for TLS certificate lifetime. '+('Unsupported statement. '*8),'ok'
  answer,why=self.generator(engine)('review','TLS','Choose a standard for TLS renewal.',lane='claude')
  self.assertIsNone(answer);self.assertTrue(why.startswith('quality-held:'));self.assertEqual(len(calls),2)
 def test_repair_can_succeed(self):
  answers=iter(['Use RFC 5928. '+('unsupported. '*12),'Check the certificate served by each backend and compare its fingerprint with the expected certificate. Record failures and retry after fixing the affected backend.'])
  answer,why=self.generator(lambda *a:(next(answers),'ok'))('review','TLS','Describe a certificate rotation check.')
  self.assertIsNotNone(answer);self.assertEqual(why,'mlx')
 def test_two_bad_formats_are_held(self):
  calls=[]
  def engine(*args):calls.append(args);return 'One complete sentence here. Another complete sentence here.','ok'
  answer,why=self.generator(engine)('explain','Short','Success: exactly one sentence.')
  self.assertIsNone(answer);self.assertIn('one sentence requested',why);self.assertEqual(len(calls),2)
 def test_short_valid_sentence_is_allowed(self):
  answer,why=self.generator(lambda *a:('Ruby is a language whereas SMTP is an email protocol.','ok'))('explain','Short','Success: exactly one sentence.')
  self.assertIsNotNone(answer)
if __name__=='__main__':unittest.main()
