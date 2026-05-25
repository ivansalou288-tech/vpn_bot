import requests
import urllib3
import json
import random
import datetime
import time
from urllib.parse import quote
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from config import PANEL_BASE_URL, PANEL_DOMAIN, PANEL_PORT, PANEL_PATH
import secret
BASE_URL = PANEL_BASE_URL

admn_username = secret.user
admn_pass = secret.password
def login():

    admin_login = {
        "username": admn_username,
        "password": admn_pass
    }

    response = requests.post(f"{BASE_URL}/login", json=admin_login, verify=False)
    print(response.json())
login()