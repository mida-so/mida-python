# mida-python
Mida server-side A/B testing for Python


# How to use
Here's an example:

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

# replace 'your-event-name' and 'your-distinct-id' with actual values
mida_instance.set_event('your-event-name', 'your-distinct-id')
```