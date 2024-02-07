import json
import requests

class Mida:
    def __init__(self, public_key, options=None):
        if not public_key:
            raise AssertionError("You must pass your Mida project key")

        self.public_key = public_key
        self.host = 'https://api.mida.so'
        self.user_id = None

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