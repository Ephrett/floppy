import ast, threading, unittest
from pathlib import Path
class DeliveryGuard(unittest.TestCase):
    def test_concurrent_recovery_and_retry_only_send_once(self):
        source=Path(__file__).resolve().parents[1]/'engine'/'kibble-bot.py'
        node=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='deliver')
        started=threading.Event(); release=threading.Event(); calls=[]
        def worker(st,jid,*args):
            calls.append(jid);started.set();release.wait(2);st['claims'][jid]['delivered']=1
        ns=dict(DELIVERY_LOCK=threading.Lock(),ACTIVE_DELIVERIES=set(),_deliver=worker)
        exec(compile(ast.Module(body=[node],type_ignores=[]),'guard','exec'),ns)
        st={'claims':{'job':{}}};args=(st,'job','build','title','text')
        t=threading.Thread(target=ns['deliver'],args=args);t.start();self.assertTrue(started.wait(1))
        ns['deliver'](*args);release.set();t.join();ns['deliver'](*args)
        self.assertEqual(calls,['job']);self.assertFalse(ns['ACTIVE_DELIVERIES'])
if __name__=='__main__': unittest.main()
