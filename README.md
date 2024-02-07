# Mida Python Client

This repository contains a Python client for interacting with the [Mida.so](https://app.mida.so/).

## Installation

Clone the repository:
```bash
git clone https://github.com/mida-so/mida-python.git
```

## Usage

Import the `Mida` class to your Python project. Create an instance of `Mida` using the project key from your Mida.so account. Use the `get_experiment` and `set_event` methods to interact with the Mida API.

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
```

## Contributing

Contributions are welcome! If you find any issues or have suggestions for improvement, please create a pull request.

## Support

For support, please contact us at hello@mida.so.

## License

This project is licensed under the MIT License - see the `LICENSE.md` file for details.