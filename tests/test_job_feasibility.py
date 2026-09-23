import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
import unittest
from delivery_quality import job_block_reason
class Feasibility(unittest.TestCase):
 def test_unavailable_live_task(self):
  self.assertIsNotNone(job_block_reason('Confirm current pharmacy hours','Check each official website and record the verification date.'))
 def test_explanation_is_allowed(self):
  self.assertIsNone(job_block_reason('Opening hours workflow','Explain how staff can verify current hours on an official website; do not perform the verification.'))
 def test_unrelated_knobs(self):
  self.assertIsNotNone(job_block_reason('Unicode','Identify Linux sysctl settings for normalizing Unicode before comparison.'))
 def test_real_network_tuning_allowed(self):
  self.assertIsNone(job_block_reason('Network tuning','Explain socket buffer settings for TCP throughput and the measurements required before changing them.'))
 def test_real_attestation_allowed(self):
  self.assertIsNone(job_block_reason('Attestation','Explain how a TPM quote verifies binary integrity of a bootloader.'))
if __name__=='__main__':unittest.main()
