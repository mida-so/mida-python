"""Mida server-side A/B testing and feature flags for Python.

    from mida import Mida

    mida = Mida('YOUR_PROJECT_KEY')            # region='eu' for EU accounts
    variant = mida.get_experiment('checkout-flow', user_id)
    if variant == 'Variant 1':
        ...                                     # treatment
    else:
        ...                                     # 'Control', or None when not in the experiment
    mida.set_event('Purchase', user_id, {'revenue': 49.99, 'currency': 'USD'})

Create one client per process and share it; it is safe to use from several threads.
"""
import json
import logging
import threading
import time
from collections import OrderedDict
from urllib.parse import quote

import requests

__version__ = '1.1.0'
__all__ = ['Mida', 'MidaError']

logger = logging.getLogger('mida')

HOSTS = {
    'us': 'https://api.mida.so',
    'eu': 'https://api-eu.mida.so',
}

DEFAULT_TIMEOUT = 10.0
DEFAULT_FLAG_TTL = 60.0
DEFAULT_MAX_CACHE_SIZE = 50000


class MidaError(Exception):
    """A Mida API request failed. status is the HTTP status code, or None for network errors."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class Mida:
    def __init__(self, public_key, options=None, **kwargs):
        """
        public_key: project key (Dashboard → Settings → API).

        Options, as a dict or keyword arguments:
          region          'us' (default) or 'eu'. EU accounts must pass 'eu'.
          host            override the API host (takes precedence over region)
          timeout         request timeout in seconds (default 10)
          feature_flag_ttl  seconds a user's flags are cached (default 60; 0 disables)
          max_cache_size  maximum number of users whose flags are cached (default 50000)
          raise_errors    if True, get_experiment / set_event / is_feature_enabled raise
                          MidaError instead of logging and failing safe (default False)
          session         a requests.Session to use
        """
        if not public_key:
            raise AssertionError('You must pass your Mida project key')
        opts = dict(options or {})
        opts.update(kwargs)
        # Accept the camelCase name earlier versions documented.
        if 'maxCacheSize' in opts and 'max_cache_size' not in opts:
            opts['max_cache_size'] = opts['maxCacheSize']

        self.public_key = public_key
        region = str(opts.get('region') or 'us').lower()
        host = opts.get('host')
        if not host and region not in HOSTS:
            raise AssertionError(f"Unknown Mida region {opts.get('region')!r}. Use 'us' or 'eu'.")
        self.host = (host or HOSTS[region]).rstrip('/')
        self.timeout = opts.get('timeout', DEFAULT_TIMEOUT)
        self.feature_flag_ttl = opts.get('feature_flag_ttl', DEFAULT_FLAG_TTL)
        self.max_cache_size = opts.get('max_cache_size') or DEFAULT_MAX_CACHE_SIZE
        self.raise_errors = bool(opts.get('raise_errors', False))
        self._session = opts.get('session') or requests.Session()

        self.user_id = None
        self.enabled_features = []
        self.feature_flag_cache = OrderedDict()
        self._lock = threading.Lock()

    # -- HTTP ---------------------------------------------------------------

    def _post(self, path, data):
        headers = {'Content-Type': 'application/json', 'User-Agent': f'mida-python/{__version__}'}
        try:
            response = self._session.post(self.host + path, data=json.dumps(data),
                                          headers=headers, timeout=self.timeout)
        except requests.RequestException as err:
            raise MidaError(f'Mida API request failed: {err}') from err
        if not 200 <= response.status_code < 300:
            raise MidaError(f'Mida API returned {response.status_code}', response.status_code)
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return None

    def _fail_safe(self, what, err, default):
        if self.raise_errors:
            raise err
        logger.warning('mida: %s failed: %s', what, err)
        return default

    # -- A/B testing --------------------------------------------------------

    def get_experiment(self, experiment_key, distinct_id=None):
        """The variant assigned to the user ('Control', 'Variant 1', ...), or None when the user
        is not in the experiment. On a failed request it logs and returns None, so the caller
        shows the original experience (pass raise_errors=True to raise instead)."""
        distinct_id = distinct_id if distinct_id is not None else self.user_id
        if not experiment_key or distinct_id in (None, ''):
            raise AssertionError('You must pass your Mida experiment key and user distinct ID')
        try:
            result = self._post('/experiment/query', {
                'key': self.public_key,
                'experiment_key': experiment_key,
                'distinct_id': str(distinct_id),
            })
        except MidaError as err:
            return self._fail_safe('get_experiment', err, None)
        return (result or {}).get('version') or None

    def set_event(self, event_name, distinct_id=None, properties=None):
        """Records an event. event_name must match the goal's event name in Mida. For revenue
        pass properties={'revenue': 49.99, 'quantity': 1, 'currency': 'USD'}.
        Returns True when recorded, False when the request failed (and raise_errors is off)."""
        distinct_id = distinct_id if distinct_id is not None else self.user_id
        if not event_name or distinct_id in (None, ''):
            raise AssertionError('You need to set an event name and user distinct ID')
        try:
            self._post('/experiment/event', {
                'key': self.public_key,
                'name': event_name,
                'distinct_id': str(distinct_id),
                'properties': json.dumps(properties or {}),
            })
        except MidaError as err:
            return self._fail_safe('set_event', err, False)
        return True

    def set_attribute(self, distinct_id, properties=None):
        """Sets user attributes for targeting and segmentation. Raises MidaError on failure.
        Does not modify `properties`."""
        distinct_id = distinct_id if distinct_id is not None else self.user_id
        if distinct_id in (None, ''):
            raise AssertionError('You must pass your user distinct ID')
        if not properties:
            raise AssertionError('You must pass your user properties')
        data = dict(properties)
        data['id'] = str(distinct_id)
        self._post(f'/track/{quote(self.public_key, safe="")}', data)

    # -- Feature flags ------------------------------------------------------

    def _cache_key(self, distinct_id):
        return f"{self.public_key}:{'' if distinct_id is None else distinct_id}"

    def _cached(self, distinct_id):
        if not self.feature_flag_ttl or self.feature_flag_ttl <= 0:
            return None
        with self._lock:
            entry = self.feature_flag_cache.get(self._cache_key(distinct_id))
        if entry and time.monotonic() - entry['fetched_at'] < self.feature_flag_ttl:
            return entry
        return None

    def _flags(self, distinct_id, force=False):
        if not force:
            hit = self._cached(distinct_id)
            if hit:
                return hit
        body = {'key': self.public_key}
        if distinct_id not in (None, ''):
            body['user_id'] = str(distinct_id)
        result = self._post('/feature-flag', body)

        # The API returns {"keys": [...], "flags": {key: {enabled, type, payload}}}.
        # Accept a bare list too, which older API versions returned.
        if isinstance(result, list):
            keys, flags = result, {}
        elif isinstance(result, dict):
            keys = result.get('keys') if isinstance(result.get('keys'), list) else []
            flags = result.get('flags') if isinstance(result.get('flags'), dict) else {}
        else:
            keys, flags = [], {}
        entry = {'keys': list(keys), 'flags': flags, 'fetched_at': time.monotonic()}

        if self.feature_flag_ttl and self.feature_flag_ttl > 0:
            cache_key = self._cache_key(distinct_id)
            with self._lock:
                self.feature_flag_cache.pop(cache_key, None)
                self.feature_flag_cache[cache_key] = entry
                while len(self.feature_flag_cache) > self.max_cache_size:
                    self.feature_flag_cache.popitem(last=False)
        return entry

    def _resolve_user(self, distinct_id):
        return self.user_id if distinct_id is None else distinct_id

    def is_feature_enabled(self, key, distinct_id=None):
        """Whether the flag is on for the user. Pass distinct_id: flags with a rollout
        percentage or user targeting differ per user. Without it, uses the user from the last
        on_feature_flags(distinct_id) call, as earlier versions did. On a failed request it
        logs and returns False (pass raise_errors=True to raise instead)."""
        if not key:
            raise AssertionError('You must pass a feature flag key')
        try:
            entry = self._flags(self._resolve_user(distinct_id))
        except MidaError as err:
            return self._fail_safe('is_feature_enabled', err, False)
        self.enabled_features = entry['keys']
        return key in entry['keys']

    def get_feature_flags(self, distinct_id=None):
        """Keys of all flags enabled for the user. Raises MidaError on failure."""
        return list(self._flags(self._resolve_user(distinct_id))['keys'])

    def get_feature_flag_payload(self, key, distinct_id=None):
        """The payload configured for a flag, or None when it is off or has none.
        Raises MidaError on failure."""
        flag = self._flags(self._resolve_user(distinct_id))['flags'].get(key)
        return flag.get('payload') if isinstance(flag, dict) else None

    def on_feature_flags(self, distinct_id=None):
        """Fetches the user's flags again, bypassing the cache, and remembers the user."""
        self.reload_feature_flags(distinct_id)
        return True

    def reload_feature_flags(self, distinct_id=None):
        if distinct_id is not None:
            self.user_id = distinct_id
        entry = self._flags(self.user_id if distinct_id is None else distinct_id, force=True)
        self.enabled_features = entry['keys']

    def cached_feature_flag(self):
        """Kept for compatibility: the cached flag keys for the last user loaded."""
        entry = self._cached(self.user_id)
        return entry['keys'] if entry else []
