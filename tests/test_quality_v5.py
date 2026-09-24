import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from delivery_quality import format_issues,job_block_reason,length_instruction,output_issues
class QualityV5(unittest.TestCase):
 def test_incorrect_count(self): self.assertIn('incorrect declared word count',format_issues('', 'Word count: 50. These are four words.'))
 def test_correct_count(self): self.assertEqual(format_issues('', 'Word count: 4. These are four words.'),[])
 def test_explicit_range(self): self.assertTrue(format_issues('Write 80–100 words.', 'Too short.'))
 def test_good_range(self): self.assertEqual(format_issues('Write 3-5 words.', 'These are four words.'),[])
 def test_single_sentence(self): self.assertTrue(format_issues('Success: one sentence.', 'This is one. This is two.'))
 def test_abbreviation_decimal(self): self.assertEqual(format_issues('One sentence.', 'Use e.g. a 2.5 second delay.'),[])
 def test_long_job_declined(self): self.assertIsNotNone(job_block_reason('Science','Write a 500–700-word explainer.'))
 def test_short_job_allowed(self): self.assertIsNone(job_block_reason('Science','Write a 100–200-word explainer.'))
 def test_citations_missing(self): self.assertIsNotNone(job_block_reason('Science','Include at least three credible citations.'))
 def test_citations_provided(self): self.assertIsNone(job_block_reason('Science','Include at least three credible citations from provided sources.'))
 def test_mismatch(self): self.assertIsNotNone(job_block_reason('Build','Specify the SSTable compaction trigger for a monorepo build.'))
 def test_real_storage(self): self.assertIsNone(job_block_reason('Build','Specify the SSTable compaction trigger for a monorepo build backed by RocksDB.'))
 def test_length_rule(self): self.assertEqual(length_instruction('One sentence.'),'Write exactly one sentence.')
 def test_path_prefix_not_containment(self): self.assertTrue(output_issues('Keep deletion inside the allowed directory.', 'Verify that the path starts with the allowed directory prefix.'))
 def test_path_prefix_warning(self): self.assertEqual(output_issues('Prevent path traversal.', 'Never use a string prefix; compare path components and reject symlinks.'),[])
