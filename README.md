# Mida Python SDK

Server-side A/B testing and feature flags for Python, for use with [Mida](https://www.mida.so).

- Python 3.8 or later
- Depends only on `requests`
- Safe to share across threads

## Install

```bash
pip install git+https://github.com/mida-so/mida-python.git
```

## Quick start

Create one client per process and share it.

```python
from mida import Mida

mida = Mida('YOUR_PROJECT_KEY')  # Dashboard → Settings → API
user_id = 'user_42'

variant = mida.get_experiment('YOUR_EXPERIMENT_KEY', user_id)
if variant == 'Variant 1':
    ...  # treatment
else:
    ...  # 'Control', or None when the user is not in the experiment

# When the user converts:
mida.set_event('signup_completed', user_id)
```

EU accounts must select the EU region:

```python
mida = Mida('YOUR_PROJECT_KEY', region='eu')
```

## Methods

### `get_experiment(experiment_key, distinct_id)`

Returns the variant for this user: `'Control'`, `'Variant 1'`, `'Variant 2'`, and so on.
Returns `None` when the user is not in the experiment, which happens when the experiment is not
live or the key does not match one in the project. The assignment is sticky: the same
`distinct_id` always gets the same variant.

If the request fails, it logs a warning and returns `None`, so your code shows the original
experience.

### `set_event(event_name, distinct_id, properties=None)`

Records a conversion event. `event_name` must match the goal's event name in Mida, and
`distinct_id` must be the same value passed to `get_experiment`. Returns `True` when recorded.

```python
mida.set_event('Purchase', user_id, {'revenue': 49.99, 'quantity': 1, 'currency': 'USD'})
```

### `set_attribute(distinct_id, properties)`

Sets user attributes for targeting and segmentation.

```python
mida.set_attribute(user_id, {'plan': 'pro', 'country': 'US'})
```

### `is_feature_enabled(key, distinct_id)`

Returns whether a feature flag is on for this user. Always pass `distinct_id`, since flags with a
rollout percentage or user targeting differ per user. If the request fails, it logs a warning and
returns `False`.

Flags are cached per user for 60 seconds. `get_feature_flags(distinct_id)` lists a user's
enabled flags, `get_feature_flag_payload(key, distinct_id)` returns a flag's payload, and
`reload_feature_flags(distinct_id)` skips the cache.

## Options

Pass as keyword arguments, or as a dict in the second argument.

| Option | Default | Purpose |
|---|---|---|
| `region` | `'us'` | `'eu'` for EU accounts |
| `timeout` | `10` | Request timeout in seconds |
| `feature_flag_ttl` | `60` | Seconds a user's flags are cached; `0` disables caching |
| `max_cache_size` | `50000` | Maximum number of users whose flags are cached |
| `raise_errors` | `False` | Raise `MidaError` instead of logging and failing safe |
| `session` | | A `requests.Session` to reuse, for proxies or retries |
| `host` | | Override the API host, for tests |

## Upgrading from 1.0

- `is_feature_enabled` works now. Earlier versions misread the API response and always
  returned `False`.
- Requests time out after 10 seconds. Earlier versions could wait forever.
- Errors are logged through the `mida` logger instead of printed.
- `is_feature_enabled(key)` without a `distinct_id` still uses the user from the last
  `on_feature_flags(distinct_id)` call, but passing `distinct_id` is safer when one client
  serves many users.

## Tests

```bash
python -m unittest test_mida
```

To also run against the real API, set `MIDA_PROJECT_KEY` (and `MIDA_REGION=eu` for EU
accounts). Set `MIDA_EXPERIMENT_KEY` to a live server-side experiment to check assignment, and
`MIDA_EVENT_NAME` to record its goal event.

## License

MIT
