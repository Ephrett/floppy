import ast,json,tempfile,unittest,urllib.request
from pathlib import Path
from unittest.mock import Mock,patch

class AdapterTests(unittest.TestCase):
 def function(self,env):
  source=(Path(__file__).resolve().parents[1]/'engine/llm.py').read_text()
  fn=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='mlx_generate')
  scope=dict(env=lambda:env,Path=Path,urllib=__import__('urllib'),json=json)
  exec(compile(ast.Module(body=[fn],type_ignores=[]),'isolated','exec'),scope)
  return scope['mlx_generate']
 def response(self):
  response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
  response.read.return_value=b'{"choices":[{"message":{"content":"answer"}}]}'
  return response
 def test_base_has_no_adapter(self):
  with patch('urllib.request.urlopen',return_value=self.response()) as call:
   self.assertEqual(self.function({'MLX_MODEL':'base'})('task'),'answer')
  body=json.loads(call.call_args.args[0].data);self.assertNotIn('adapters',body)
 def test_explicit_adapter_sent(self):
  with tempfile.TemporaryDirectory() as d:
   for n in ['adapters.safetensors','adapter_config.json']:(Path(d)/n).touch()
   with patch('urllib.request.urlopen',return_value=self.response()) as call:
    self.function({'MLX_MODEL':'base','MLX_ADAPTER_PATH':d})('task')
   body=json.loads(call.call_args.args[0].data);self.assertEqual(body['adapters'],str(Path(d).resolve()))
 def test_missing_adapter_fails_without_network(self):
  with tempfile.TemporaryDirectory() as d,patch('urllib.request.urlopen') as call:
   with self.assertRaisesRegex(RuntimeError,'refusing silent base fallback'):
    self.function({'MLX_ADAPTER_PATH':d})('task')
   call.assert_not_called()
if __name__=='__main__':unittest.main()
