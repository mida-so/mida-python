import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mida import Mida  # noqa: E402


def fake_post(url, data=None, headers=None, **kwargs):
    import json
    payload = json.loads(data)
    flags = ['beta'] if payload.get('user_id') == 'alice' else ['other']
    resp = mock.Mock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = flags
    return resp


class FeatureFlagCacheTest(unittest.TestCase):
    def test_flags_are_cached_per_user(self):
        mida = Mida('pk')
        with mock.patch('mida.requests.post', side_effect=fake_post):
            mida.on_feature_flags('alice')
            mida.on_feature_flags('bob')

        self.assertTrue(mida.is_feature_enabled('beta', 'alice'))
        self.assertFalse(mida.is_feature_enabled('beta', 'bob'))
        self.assertTrue(mida.is_feature_enabled('other', 'bob'))
        # Users whose flags were never loaded get nothing.
        self.assertFalse(mida.is_feature_enabled('beta', 'carol'))
        self.assertFalse(mida.is_feature_enabled('beta'))


if __name__ == '__main__':
    unittest.main()
