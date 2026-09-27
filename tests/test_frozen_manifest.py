import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('smoke_frozen', ROOT/'scripts/smoke-frozen.py')
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)

class FrozenManifestTests(unittest.TestCase):
    def test_complete_current_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp)
            shutil.copytree(ROOT/'engine', profile/'engine', ignore=shutil.ignore_patterns('__pycache__'))
            smoke.verify_engine(profile, ROOT)

    def test_missing_validator_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp)
            shutil.copytree(ROOT/'engine', profile/'engine', ignore=shutil.ignore_patterns('__pycache__'))
            (profile/'engine/validator_board.py').unlink()
            with self.assertRaises(FileNotFoundError):
                smoke.verify_engine(profile, ROOT)

    def test_outdated_quality_gate_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp)
            shutil.copytree(ROOT/'engine', profile/'engine', ignore=shutil.ignore_patterns('__pycache__'))
            (profile/'engine/delivery_quality.py').write_text('VERSION = "old"\n')
            with self.assertRaisesRegex(AssertionError, 'delivery_quality.py'):
                smoke.verify_engine(profile, ROOT)
