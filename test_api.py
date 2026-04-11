import sys
sys.path.append('.')
from api import get_clients

try:
    result = get_clients()
    print('Result:', result)
except Exception as e:
    print('Error:', e)
