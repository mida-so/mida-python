from mida import Mida

# replace 'your-project-key' with your actual key
mida_instance = Mida('your-project-key')

# replace 'your-experiment-key' and 'your-distinct-id' with actual values
experiment = mida_instance.get_experiment('first-key', '123')

if experiment == 'Control':
    print('Control variant execute')
elif experiment == 'Variant 1':
    print('Variant 1 variant execute')
elif experiment == 'Variant 2':
    print('Variant 2 variant execute')
