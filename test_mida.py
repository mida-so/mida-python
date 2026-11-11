"""Tests for the Mida Python SDK. Run with: python -m pytest  (or python -m unittest test_mida)

The live test runs only when MIDA_PROJECT_KEY is set. Optional: MIDA_REGION,
MIDA_EXPERIMENT_KEY (a live server-side experiment), MIDA_EVENT_NAME.
"""
import json
import os
import random
import socket
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from mida import Mida, MidaError


class FakeApi:
    """A fake of the Mida backend routes the SDK calls."""

    def __init__(self, handler):
        self.calls = []
        self.handler = handler
        api = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get('Content-Length') or 0))
                try:
                    body = json.loads(raw or b'{}')
                except ValueError:
                    body = {}
                api.calls.append({'path': self.path, 'headers': dict(self.headers), 'body': body})
                status, payload = api.handler(self.path, body)
                data = payload.encode() if isinstance(payload, str) else json.dumps(payload).encode()
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.host = f'http://127.0.0.1:{self.server.server_address[1]}'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class SdkTest(unittest.TestCase):
    def api(self, handler):
        api = FakeApi(handler)
        self.addCleanup(api.close)
        return api

    def test_get_experiment(self):
        api = self.api(lambda p, b: (200, {'version': 'Variant 1' if b['experiment_key'] == 'live' else None}))
        mida = Mida('pk', host=api.host)
        self.assertEqual(mida.get_experiment('live', 'user-1'), 'Variant 1')
        self.assertIsNone(mida.get_experiment('not-live', 'user-1'))
        call = api.calls[0]
        self.assertEqual(call['path'], '/experiment/query')
        self.assertEqual(call['body'], {'key': 'pk', 'experiment_key': 'live', 'distinct_id': 'user-1'})
        self.assertTrue(call['headers']['User-Agent'].startswith('mida-python/'))

    def test_numeric_distinct_id_sent_as_string(self):
        api = self.api(lambda p, b: (200, {'version': 'Control'}))
        Mida('pk', host=api.host).get_experiment('k', 42)
        self.assertEqual(api.calls[0]['body']['distinct_id'], '42')

    def test_http_error_fails_safe_or_raises(self):
        api = self.api(lambda p, b: (500, 'Internal Server Error'))
        with self.assertLogs('mida', level='WARNING'):
            self.assertIsNone(Mida('pk', host=api.host).get_experiment('k', 'u'))
        with self.assertRaises(MidaError) as ctx:
            Mida('pk', host=api.host, raise_errors=True).get_experiment('k', 'u')
        self.assertEqual(ctx.exception.status, 500)

    def test_network_failure_and_timeout_do_not_hang(self):
        # Closed port: connection refused.
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()
        mida = Mida('pk', host=f'http://127.0.0.1:{port}', timeout=1, raise_errors=True)
        with self.assertRaises(MidaError) as ctx:
            mida.get_experiment('k', 'u')
        self.assertIsNone(ctx.exception.status)

        # A server that accepts and never answers: must time out.
        silent = socket.socket()
        silent.bind(('127.0.0.1', 0))
        silent.listen(1)
        self.addCleanup(silent.close)
        mida = Mida('pk', host=f'http://127.0.0.1:{silent.getsockname()[1]}', timeout=0.3)
        started = time.monotonic()
        with self.assertLogs('mida', level='WARNING'):
            self.assertIsNone(mida.get_experiment('k', 'u'))
        self.assertLess(time.monotonic() - started, 3)

    def test_missing_arguments(self):
        api = self.api(lambda p, b: (200, {}))
        mida = Mida('pk', host=api.host)
        for call in (lambda: mida.get_experiment('', 'u'), lambda: mida.get_experiment('k'),
                     lambda: mida.set_event('', 'u'), lambda: mida.set_attribute('u'),
                     lambda: mida.is_feature_enabled('')):
            with self.assertRaises(AssertionError):
                call()
        self.assertEqual(api.calls, [])
        with self.assertRaises(AssertionError):
            Mida('')
        with self.assertRaises(AssertionError):
            Mida('pk', region='asia')

    def test_set_event_with_revenue_properties(self):
        api = self.api(lambda p, b: (200, 'OK'))
        mida = Mida('pk', host=api.host)
        self.assertTrue(mida.set_event('Purchase', 'user-1', {'revenue': 49.99, 'quantity': 1, 'currency': 'USD'}))
        self.assertTrue(mida.set_event('signup', 'user-1'))
        self.assertEqual(api.calls[0]['path'], '/experiment/event')
        self.assertEqual(json.loads(api.calls[0]['body']['properties']),
                         {'revenue': 49.99, 'quantity': 1, 'currency': 'USD'})
        self.assertEqual(api.calls[1]['body']['properties'], '{}')

    def test_set_event_failure_returns_false(self):
        api = self.api(lambda p, b: (503, 'down'))
        with self.assertLogs('mida', level='WARNING'):
            self.assertFalse(Mida('pk', host=api.host).set_event('e', 'u'))

    def test_set_attribute(self):
        api = self.api(lambda p, b: (200, 'OK'))
        attrs = {'plan': 'pro'}
        Mida('pk', host=api.host).set_attribute('user-1', attrs)
        self.assertEqual(api.calls[0]['path'], '/track/pk')
        self.assertEqual(api.calls[0]['body'], {'plan': 'pro', 'id': 'user-1'})
        self.assertEqual(attrs, {'plan': 'pro'})

    def test_feature_flags_read_keys_response(self):
        def handler(p, b):
            if b.get('user_id') == 'beta':
                return 200, {'keys': ['new-checkout'],
                             'flags': {'new-checkout': {'enabled': True, 'type': 'json', 'payload': {'color': 'red'}}}}
            return 200, {'keys': [], 'flags': {}}
        api = self.api(handler)
        mida = Mida('pk', host=api.host)
        self.assertTrue(mida.is_feature_enabled('new-checkout', 'beta'))
        self.assertFalse(mida.is_feature_enabled('missing', 'beta'))
        self.assertEqual(mida.get_feature_flags('beta'), ['new-checkout'])
        self.assertEqual(mida.get_feature_flag_payload('new-checkout', 'beta'), {'color': 'red'})
        self.assertIsNone(mida.get_feature_flag_payload('missing', 'beta'))
        self.assertEqual(api.calls[0]['path'], '/feature-flag')
        self.assertEqual(api.calls[0]['body']['user_id'], 'beta')

    def test_bare_list_response_still_accepted(self):
        api = self.api(lambda p, b: (200, ['legacy-flag']))
        self.assertTrue(Mida('pk', host=api.host).is_feature_enabled('legacy-flag', 'u'))

    def test_flags_cached_per_user(self):
        api = self.api(lambda p, b: (200, {'keys': ['f'] if b.get('user_id') == 'beta' else [], 'flags': {}}))
        mida = Mida('pk', host=api.host)
        self.assertTrue(mida.is_feature_enabled('f', 'beta'))
        self.assertFalse(mida.is_feature_enabled('f', 'other'))
        self.assertTrue(mida.is_feature_enabled('f', 'beta'))
        self.assertEqual(len(api.calls), 2)

    def test_flag_ttl_and_disable(self):
        state = {'on': False}
        api = self.api(lambda p, b: (200, {'keys': ['f'] if state['on'] else [], 'flags': {}}))
        mida = Mida('pk', host=api.host, feature_flag_ttl=0.05)
        self.assertFalse(mida.is_feature_enabled('f', 'u'))
        state['on'] = True
        self.assertFalse(mida.is_feature_enabled('f', 'u'))
        time.sleep(0.08)
        self.assertTrue(mida.is_feature_enabled('f', 'u'))
        no_cache = Mida('pk', host=api.host, feature_flag_ttl=0)
        no_cache.is_feature_enabled('f', 'u')
        self.assertEqual(len(no_cache.feature_flag_cache), 0)

    def test_flag_cache_bounded(self):
        api = self.api(lambda p, b: (200, {'keys': [], 'flags': {}}))
        mida = Mida('pk', {'maxCacheSize': 3}, host=api.host)
        for u in 'abcde':
            mida.is_feature_enabled('f', u)
        self.assertEqual(len(mida.feature_flag_cache), 3)

    def test_flag_failure_is_false(self):
        api = self.api(lambda p, b: (500, 'x'))
        with self.assertLogs('mida', level='WARNING'):
            self.assertFalse(Mida('pk', host=api.host).is_feature_enabled('f', 'u'))

    def test_legacy_on_feature_flags_flow(self):
        api = self.api(lambda p, b: (200, {'keys': ['f'] if b.get('user_id') == 'beta' else [], 'flags': {}}))
        mida = Mida('pk', host=api.host)
        self.assertTrue(mida.on_feature_flags('beta'))
        self.assertTrue(mida.is_feature_enabled('f'))
        self.assertEqual(mida.cached_feature_flag(), ['f'])
        self.assertEqual(len(api.calls), 1)

    def test_concurrent_users(self):
        def handler(p, b):
            time.sleep(random.random() * 0.02)
            return 200, {'keys': [f"flag-{b['user_id']}"], 'flags': {}}
        api = self.api(handler)
        mida = Mida('pk', host=api.host)
        with ThreadPoolExecutor(10) as pool:
            results = list(pool.map(lambda i: mida.is_feature_enabled(f'flag-u{i}', f'u{i}'), range(30)))
        self.assertTrue(all(results))

    def test_region(self):
        self.assertEqual(Mida('pk').host, 'https://api.mida.so')
        self.assertEqual(Mida('pk', region='eu').host, 'https://api-eu.mida.so')
        self.assertEqual(Mida('pk', {'region': 'EU'}).host, 'https://api-eu.mida.so')
        self.assertEqual(Mida('pk', host='http://localhost:1/').host, 'http://localhost:1')

    @unittest.skipUnless(os.environ.get('MIDA_PROJECT_KEY'), 'MIDA_PROJECT_KEY not set')
    def test_live_api(self):
        mida = Mida(os.environ['MIDA_PROJECT_KEY'], region=os.environ.get('MIDA_REGION', 'us'), raise_errors=True)
        prefix = os.environ.get('MIDA_USER_PREFIX', 'mida-python-live')
        self.assertIsNone(mida.get_experiment('mida-sdk-nonexistent-key', f'{prefix}-x'))
        self.assertIsInstance(mida.get_feature_flags(f'{prefix}-x'), list)
        exp_key = os.environ.get('MIDA_EXPERIMENT_KEY')
        if not exp_key:
            return
        for i in range(10):
            user = f'{prefix}-{i}'
            first = mida.get_experiment(exp_key, user)
            self.assertTrue(first)
            self.assertEqual(mida.get_experiment(exp_key, user), first)
            if i % 2 == 0 and os.environ.get('MIDA_EVENT_NAME'):
                self.assertTrue(mida.set_event(os.environ['MIDA_EVENT_NAME'], user, {'source': 'mida-python live test'}))


if __name__ == '__main__':
    unittest.main()
