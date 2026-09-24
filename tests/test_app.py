import importlib.util,json,os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('floppy_app',ROOT/'app.py');app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
class AppTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.patches=[patch.object(app,'HOME',self.root),patch.object(app,'ENGINE',self.root/'engine'),patch.object(app,'STATE',self.root/'engine'/'state'),patch.object(app,'DL',self.root/'downloads')]
  for p in self.patches:p.start();self.addCleanup(p.stop)
  app.ensure_engine_files();app.WORKER.update(proc=None,wanted=False,since=None);app.THERMAL['paused']=False;app.BG['machine']={}
 def test_engine_replaces_newer_stale_copy_but_keeps_identity(self):
  f=app.ENGINE/'delivery_quality.py';f.write_text('old');os.utime(f,(time.time()+10000,time.time()+10000));(app.ENGINE/'seed.hex').write_text('test-identity')
  app.ensure_engine_files();self.assertEqual(f.read_bytes(),(ROOT/'engine'/'delivery_quality.py').read_bytes());self.assertEqual((app.ENGINE/'seed.hex').read_text(),'test-identity')
 def test_validator_reader_installed_and_updated(self):
  target=app.ENGINE/'validator_board.py'
  self.assertEqual(target.read_bytes(),(ROOT/'engine'/'validator_board.py').read_bytes())
  target.write_text('stale reader')
  app.ensure_engine_files()
  self.assertEqual(target.read_bytes(),(ROOT/'engine'/'validator_board.py').read_bytes())
 def test_power_and_thermal_interaction(self):
  app.save_state({'options':{'ac_only':'1','temp_limit':'80'}});app.BG['machine']={'gpu_temp':82,'ac_power':False}
  self.assertEqual(app.pause_reason(),'thermal');app.BG['machine']['gpu_temp']=75;self.assertEqual(app.pause_reason(),'battery')
  app.BG['machine']['ac_power']=None;self.assertEqual(app.pause_reason(),'power_unknown');app.BG['machine']['ac_power']=True;self.assertIsNone(app.pause_reason())
 def test_user_pause_does_not_resume_on_mains(self):
  app.save_state({'options':{'ac_only':'1'}});app.BG['machine']={'ac_power':True}
  with patch.object(app,'start_worker') as start:app.thermal_guard();start.assert_not_called()
 def test_stats_ambiguous_duplicate_and_held(self):
  now=time.time();ds=[{'job_id':j,'ts':now-20,'seq':1,'engine':'ollama'} for j in ['own','shared']]
  att=[{'job_id':'own','ts':now-10,'attestor':'peer','verdict':'useful'}, {'job_id':'shared','ts':now-10,'attestor':'peer','verdict':'not','foreign':True}]
  (app.STATE/'dataset.jsonl').write_text('\n'.join(map(json.dumps,ds)));(app.STATE/'attest-received.jsonl').write_text('\n'.join(map(json.dumps,att+att)))
  (app.STATE/'bot.json').write_text(json.dumps({'claims':{'held':{'quality_hold':{'ts':now}}}}))
  st=app.stats();self.assertEqual(st['useful24'],1);self.assertEqual(st['not24'],0);self.assertEqual(st['ambiguous24'],1);self.assertEqual(st['held24'],1)
if __name__=='__main__':unittest.main()
