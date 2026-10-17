import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mida import Mida  # noqa: E402


class SetEventTest(unittest.TestCase):
    def _sent_payload(self, *args, **kwargs):
        with mock.patch('mida.requests.post') as post:
            Mida('pk').set_event(*args, **kwargs)
        return json.loads(post.call_args.kwargs['data'])

    def test_without_properties_payload_is_unchanged(self):
        payload = self._sent_payload('signup', 'u1')
        self.assertEqual(payload, {'key': 'pk', 'name': 'signup', 'distinct_id': 'u1'})

    def test_with_properties(self):
        payload = self._sent_payload('Purchase', 'u1', {'revenue': 9.99})
        self.assertEqual(json.loads(payload['properties']), {'revenue': 9.99})


if __name__ == '__main__':
    unittest.main()
