import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from delivery_quality import format_issues, length_instruction, word_maximum

class WordMaximumTests(unittest.TestCase):
    def test_inclusive_boundary_and_overflow(self):
        for task in ('At most 5 words.', 'No more than 5 words.', 'Maximum of 5 words.', 'Maximum 5 words.'):
            with self.subTest(task=task):
                self.assertEqual(format_issues(task, 'one two three four five'), [])
                self.assertIn('explicit word maximum exceeded', format_issues(task, 'one two three four five six'))

    def test_strict_boundary(self):
        for task in ('Under 5 words.', 'Fewer than 5 words.', 'Less than 5 words.'):
            with self.subTest(task=task):
                self.assertEqual(format_issues(task, 'one two three four'), [])
                self.assertTrue(format_issues(task, 'one two three four five'))

    def test_tightest_constraint(self):
        self.assertEqual(word_maximum('At most 10 words, preferably fewer than 7 words.'), 6)

    def test_unrelated_units(self):
        for task in ('Latency under 50 ms.', 'At most 5 requests.', 'Explain maximum word size.', 'Use the word maximum.'):
            self.assertIsNone(word_maximum(task))
            self.assertEqual(format_issues(task, 'one two three four five six'), [])

    def test_combined_range_cap_and_sentence(self):
        task = 'Write 3-8 words, at most 5 words, in one sentence.'
        self.assertEqual(format_issues(task, 'These are four words.'), [])
        self.assertTrue(format_issues(task, 'This is one. This is two.'))
        instruction = length_instruction(task)
        self.assertIn('3–8', instruction)
        self.assertIn('at most 5', instruction)
        self.assertIn('exactly one sentence', instruction)

    def test_declared_count_does_not_hide_overflow(self):
        self.assertIn('explicit word maximum exceeded', format_issues('At most 3 words.', 'Word count: 4. These are four words.'))

    def test_whitespace_and_case(self):
        self.assertEqual(word_maximum('AT MOST\n5 WORDS'), 5)
        self.assertEqual(format_issues('Under 5 words.', 'one\ttwo\nthree four'), [])

if __name__ == '__main__':
    unittest.main()
