import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
import unittest
from delivery_quality import job_block_reason
class Selection(unittest.TestCase):
 def test_repository_live_missing(self):
  self.assertIsNotNone(job_block_reason('Current maintenance','Inspect Redis GitHub. Report last commit date and maintenance health.'))
 def test_repository_explanation(self):
  self.assertIsNone(job_block_reason('Process','Explain how to check GitHub maintenance health using last commit dates.'))
 def test_repository_supplied(self):
  self.assertIsNone(job_block_reason('Snapshot','Check GitHub maintenance health using the provided snapshot: last commit 2026-08-12, 12 open issues.'))
 def test_crypto_missing(self):
  self.assertIsNotNone(job_block_reason('Signatures','Validate 32 independent Ed25519 multibase signatures in a batch.'))
 def test_crypto_explanation(self):
  self.assertIsNone(job_block_reason('Design','Explain how to verify 32 independent Ed25519 signatures in a batch.'))
 def test_crypto_code_requested(self):
  self.assertIsNone(job_block_reason('Implementation','Write Python code to verify 32 Ed25519 signatures from input files; do not execute it.'))
if __name__=='__main__':unittest.main()
