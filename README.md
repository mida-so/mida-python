# Mida Python Client
This repository contains a Python client for interacting with the [Mida.so](https://app.mida.so/).
## Installation
Clone the repository:
```bash
git clone https://github.com/mida-so/mida-python.git
```
Install the required dependencies:
```bash
pip install requests
```
## Usage
Import the `Mida` class to your Python project. Create an instance of `Mida` using the project key from your Mida.so account. Use the available methods to interact with the Mida API.
Example usage:
```python
from mida import Mida
# replace 'your-project-key' with your actual key
mida_instance = Mida('your-project-key')
# replace 'your-experiment-key' and 'your-distinct-id' with actual values
experiment = mida_instance.get_experiment('your-experiment-key', 'your-distinct-id')
if experiment == 'Control':
    print('Control variant execute')
elif experiment == 'Variant 1':
    print('Variant 1 variant execute')
elif experiment == 'Variant 2':
    print('Variant 2 variant execute')
# set an event
mida_instance.set_event('event_name', 'your-distinct-id')

# reload feature flags for a user
mida_instance.on_feature_flags('your-distinct-id')

# check if a feature flag is enabled
is_enabled = mida_instance.is_feature_enabled('feature_flag_key')
if is_enabled:
    print('Feature flag is enabled')
else:
    print('Feature flag is disabled')

# set user attributes
attributes = {
    'name': 'John Doe',
    'email': 'john@example.com'
}
mida_instance.set_attribute('your-distinct-id', attributes)
```
## Methods
- `get_experiment(experiment_key, distinct_id)`: Retrieves the assigned variant for the specified experiment and user.
- `set_event(event_name, distinct_id)`: Sets an event for the specified user.
- `is_feature_enabled(key)`: Checks if a specific feature flag is enabled for the current user.
- `on_feature_flags(distinct_id)`: Reloads the feature flags for the specified user.
- `set_attribute(distinct_id, properties)`: Sets user attributes for the specified user with the given properties.
## Contributing
Contributions are welcome! If you find any issues or have suggestions for improvement, please create a pull request.
## Support
For support, please contact us at hello@mida.so.
## License
This project is licensed under the MIT License - see the `LICENSE.md` file for details.
