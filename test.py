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
        "password": admn_pass,
        
    }

    response = requests.post(f"{BASE_URL}/panel/login", json=admin_login, verify=False)
    print(f"[DEBUG] HTTP Status: {response.status_code}")
    print(f"[DEBUG] Response Headers: {dict(response.headers)}")
    print(f"[DEBUG] Response Body: {response.text[:500]}")
    print(f"[DEBUG] Response Length: {len(response.text)}")
    
    if response.status_code != 200:
        print(f"[ERROR] HTTP {response.status_code} - пытаемся POST на другой путь")
        # Попробуем другой путь
        response = requests.post(f"{BASE_URL}/api/login", json=admin_login, verify=False)
        print(f"[DEBUG api/login] HTTP Status: {response.status_code}")
        print(f"[DEBUG api/login] Response: {response.text[:500]}")
    
    if response.status_code == 200 and response.text:
        return response.json()
    else:
        return {"error": f"Login failed with status {response.status_code}", "body": response.text[:200]}
print(login())