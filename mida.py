import json
import requests

class Mida:
    def __init__(self, public_key, options=None):
        if not public_key:
            raise AssertionError("You must pass your Mida project key")
        self.public_key = public_key
        self.host = 'https://api.mida.so'
        self.user_id = None
        self.enabled_features = []
        self.max_cache_size = options.get('maxCacheSize', 50000) if options else 50000
        self.feature_flag_cache = {}

    def get_experiment(self, experiment_key, distinct_id=None):
        if not experiment_key or not (distinct_id or self.user_id):
            raise AssertionError("You must pass your Mida experiment key and user distinct ID")

        data = {
            'key': self.public_key,
            'experiment_key': experiment_key,
            'distinct_id': distinct_id or self.user_id
        }
        headers = {'Content-type': 'application/json', 'user-agent':'mida-python'}

        try:
            response = requests.post(f"{self.host}/experiment/query",
                                     data=json.dumps(data),
                                     headers=headers)
            response.raise_for_status()
            result = response.json()
            return result.get('version', None)
        
        except requests.HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
            return None
        
        except Exception as err:
            print(f'Other error occurred: {err}')
            return None

    def set_event(self, event_name, distinct_id):
        if not event_name or not (distinct_id or self.user_id):
            raise AssertionError("You need to set an event name and user distinct ID")

        data = {
            'key': self.public_key,
            'name': event_name,
            'distinct_id': distinct_id or self.user_id
        }
        headers = {'Content-type': 'application/json', 'user-agent':'mida-python'}

        try:
            response = requests.post(f"{self.host}/experiment/event",
                                     data=json.dumps(data),
                                     headers=headers)
            response.raise_for_status()
        except requests.HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
        except Exception as err:
            print(f'Other error occurred: {err}')


    def cached_feature_flag(self):
        cache_key = f"{self.public_key}:{self.user_id}"
        return self.feature_flag_cache.get(cache_key, [])

    def is_feature_enabled(self, key):
        self.enabled_features = self.cached_feature_flag()
        return key in self.enabled_features

    def on_feature_flags(self, distinct_id=None):
        cached_items = len(self.cached_feature_flag())
        try:
            self.reload_feature_flags(distinct_id)
            if not cached_items:
                return True
        except Exception as e:
            raise e
        if cached_items:
            return True

    def reload_feature_flags(self, distinct_id=None):
        data = {
            'key': self.public_key,
            'user_id': distinct_id
        }
        headers = {'Content-type': 'application/json', 'user-agent': 'mida-python'}
        try:
            response = requests.post(f"{self.host}/feature-flag",
                                     data=json.dumps(data),
                                     headers=headers)
            response.raise_for_status()
            result = response.json()
            self.enabled_features = result
            cache_key = f"{self.public_key}:{self.user_id}"
            self.feature_flag_cache[cache_key] = result

            if len(self.feature_flag_cache) > self.max_cache_size:
                oldest_key = next(iter(self.feature_flag_cache))
                del self.feature_flag_cache[oldest_key]

        except requests.HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
            raise http_err
        except Exception as err:
            print(f'Other error occurred: {err}')
            raise err

    def set_attribute(self, distinct_id, properties=None):
        if not (distinct_id or self.user_id):
            raise AssertionError("You must pass your user distinct ID")
        if not properties:
            raise AssertionError("You must pass your user properties")
        data = properties.copy() if properties else {}
        data['id'] = distinct_id or self.user_id
        headers = {'Content-type': 'application/json', 'user-agent': 'mida-python'}
        try:
            response = requests.post(f"{self.host}/track/{self.public_key}",
                                     data=json.dumps(data),
                                     headers=headers)
            response.raise_for_status()
        except requests.HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
            raise http_err
        except Exception as err:
            print(f'Other error occurred: {err}')
            raise err
