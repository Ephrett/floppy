import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
import unittest
from unittest.mock import MagicMock
from validator_board import read_jobs, BoardUnavailable, MAX_BYTES


class BoardTests(unittest.TestCase):
    def opener(self, raw=b'{"jobs": []}', status=200):
        opener = MagicMock()
        response = opener.return_value.__enter__.return_value
        response.status = status
        response.read.return_value = raw
        return opener

    def test_empty_is_valid(self):
        opener = self.opener()
        self.assertEqual(read_jobs('https://example.invalid', opener), [])
        opener.assert_called_once_with('https://example.invalid', timeout=15)
        opener.return_value.__enter__.return_value.read.assert_called_once_with(MAX_BYTES + 1)

    def test_bad_schema(self):
        for raw in (b'{}', b'[]', b'null', b'{"jobs":{}}', b'{"jobs":[null]}', b'{"jobs":[{"result":3}]}', b'{"jobs":[],"ok":false}', b'{"jobs":[],"error":"stale"}', b'<html>error</html>'):
            with self.subTest(raw=raw), self.assertRaises(BoardUnavailable):
                read_jobs('unused', self.opener(raw))

    def test_http_error(self):
        with self.assertRaises(BoardUnavailable):
            read_jobs('unused', self.opener(status=503))

    def test_size_limit(self):
        with self.assertRaises(BoardUnavailable):
            read_jobs('unused', self.opener(b' ' * (MAX_BYTES + 1)))

    def test_timeout_once_no_sensitive_error(self):
        opener = MagicMock(side_effect=TimeoutError('secret body'))
        with self.assertRaisesRegex(BoardUnavailable, '^TimeoutError$'):
            read_jobs('unused', opener)
        self.assertEqual(opener.call_count, 1)

    def test_preserve_jobs(self):
        self.assertEqual(read_jobs('unused', self.opener(b'{"jobs":[{"job_id":"k1234567890","result":"text"}]}'))[0]['result'], 'text')

class RoundTests(unittest.TestCase):
    def test_invalid_board_cannot_reach_judge(self):
        import ast
        import time
        from unittest.mock import Mock
        source = (Path(__file__).resolve().parents[1] / 'engine' / 'kibble-bot.py').read_text()
        fn = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'validate_round')
        judge, send, log = Mock(), Mock(), Mock()
        env = dict(_load_env=lambda: {}, read_jobs=Mock(side_effect=BoardUnavailable('invalid jobs list')),
                   BoardUnavailable=BoardUnavailable, BOARD='unused', time=time, VALIDATE_EVERY=1800,
                   log=log, _judge=judge, say=send)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<isolated-round>', 'exec'), env)
        state = {}
        env['validate_round'](state)
        judge.assert_not_called()
        send.assert_not_called()
        self.assertAlmostEqual(state['last_validate'] + 1800 - time.time(), 300, delta=2)
        log.assert_called_once()
