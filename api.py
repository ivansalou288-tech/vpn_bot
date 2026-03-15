import requests
import urllib3
import json
import random
import datetime
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
BASE_URL = 'https://ezh-dev.ru:45618/NDytSmlXITQ2e4MMnc'



def login():

    admin_login = {
        "username": "2p9UguXWvb",
        "password": "RyR2wN0M9f"
    }

    response = requests.post(f"{BASE_URL}/login", json=admin_login, verify=False)
    return response.json()

def get_clients():
    # First login to get session
    admin_login = {
        "username": "2p9UguXWvb",
        "password": "RyR2wN0M9f"
    }
    
    # Create session and login
    session = requests.Session()
    login_response = session.post(f"{BASE_URL}/login", json=admin_login, verify=False)
    
    if login_response.json().get('success'):
        # Use the authenticated session to get clients
        response = session.get(f"{BASE_URL}/panel/api/inbounds/list", verify=False)
        return response.json()
    else:
        return {"error": "Login failed"}


def add_inbrouds(name: str, client_name: str, client_id: str):
    # Get generated keys from API
    mldsa65_result = getNewmldsa65()
    x25519_result = getNewX25519Cert()
    
    mldsa65_seed = mldsa65_result.get('mldsa65_seed', '')
    mldsa65_verify = mldsa65_result.get('mldsa65_verify', '')
    x25519_private_key = x25519_result.get('x25519_private_key', '')
    x25519_public_key = x25519_result.get('x25519_public_key', '')
    data = {
    "up": 0,
    "down": 0,
    "total": 0,
    "remark": name,
    "enable": True,
    "expiryTime": 0,
    "listen": "",
    "port": random.randint(10000, 60000),
    "protocol": "vless",
    "settings": json.dumps(json.loads("{\"clients\": [{\"id\": \"b86c0cdc-8a02-4da4-8693-72ba27005587\",\"flow\": \"\",\"email\": \"" + client_name + "\",\"limitIp\": 0,\"totalGB\": 0,\"expiryTime\": 0,\"enable\": true,\"tgId\": \"" + client_id + "\",\"subId\": \"rqv5zw1ydutamcp0\",\"reset\": 0}],\"decryption\": \"none\",\"fallbacks\": []}")),
    "streamSettings": json.dumps(json.loads("{\"network\": \"tcp\",\"security\": \"reality\",\"externalProxy\": [],\"realitySettings\": {\"show\": false,\"xver\": 0,\"target\": \"yahoo.com:443\",\"serverNames\": [\"yahoo.com\",\"www.yahoo.com\"],\"privateKey\": \"" + x25519_private_key + "\",\"minClient\": \"\",\"maxClient\": \"\",\"maxTimediff\": 0,\"shortIds\": [\"47595474\",\"7a5e30\",\"810c1efd750030e8\",\"99\",\"9c19c134b8\",\"35fd\",\"2409c639a707b4\",\"c98fc6b39f45\"], \"mldsa65Seed\": \"" + mldsa65_seed + "\", \"settings\": {\"publicKey\": \"" + x25519_public_key + "\",\"fingerprint\": \"random\",\"serverName\": \"\",\"spiderX\": \"/\", \"mldsa65Verify\": \"" + mldsa65_verify + "\"}},\"tcpSettings\": {\"acceptProxyProtocol\": false,\"header\": {\"type\": \"none\"}}}")),
    "sniffing": json.dumps(json.loads("{\"enabled\": true,\"destOverride\": [\"http\",\"tls\",\"quic\",\"fakedns\"],\"metadataOnly\": false,\"routeOnly\": false}")),
    "allocate": json.dumps(json.loads("{\"strategy\": \"always\",\"refresh\": 5,\"concurrency\": 3}"))
    }

    admin_login = {
        "username": "2p9UguXWvb",
        "password": "RyR2wN0M9f"
    }
    
    # Create session and login
    session = requests.Session()
    session.verify = False
    login_response = session.post(f"{BASE_URL}/login", json=admin_login)
    
    if login_response.json().get('success'):
        # Use the authenticated session to add inbound
            print(data)
            response = session.post("https://ezh-dev.ru:45618/NDytSmlXITQ2e4MMnc/panel/api/inbounds/add", json=data)
            
            print(f"Status Code: {response.status_code}")
            print(f"Response Text: {response.text}")
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}", "response": response.text}
    else:
        return {"error": "Login failed"}

def getNewmldsa65():
    # First login to get session
    admin_login = {
        "username": "2p9UguXWvb",
        "password": "RyR2wN0M9f"
    }
    
    # Create session and login
    session = requests.Session()
    login_response = session.post(f"{BASE_URL}/login", json=admin_login, verify=False)
    
    if login_response.json().get('success'):
        # Use the authenticated session to get new mldsa65 keys
        response = session.get(f"{BASE_URL}/panel/api/server/getNewmldsa65", verify=False)
        result = response.json()
        if result.get('success'):
            # Extract generated keys
            mldsa65_seed = result['obj']['seed']
            mldsa65_verify = result['obj']['verify']
            return {
                'mldsa65_seed': mldsa65_seed,
                'mldsa65_verify': mldsa65_verify
            }
        else:
            return result
    else:
        return {"error": "Login failed"}



def getNewX25519Cert():
    # First login to get session
    admin_login = {
        "username": "2p9UguXWvb",
        "password": "RyR2wN0M9f"
    }
    
    # Create session and login
    session = requests.Session()
    login_response = session.post(f"{BASE_URL}/login", json=admin_login, verify=False)
    
    if login_response.json().get('success'):
        # Use the authenticated session to get new X25519 certificate
        response = session.get(f"{BASE_URL}/panel/api/server/getNewX25519Cert", verify=False)
        result = response.json()
        if result.get('success'):
            # Extract generated keys
            x25519_private_key = result['obj']['privateKey']
            x25519_public_key = result['obj']['publicKey']
            return {
                'x25519_private_key': x25519_private_key,
                'x25519_public_key': x25519_public_key
            }
        else:
            return result
    else:
        return {"error": "Login failed"}


def getSubById(telegram_id):
    # Get all clients/inbounds
    clients_data = get_clients()
    
    # Check if we got valid data
    if not clients_data.get('success'):
        return {"error": "Failed to get clients", "details": clients_data}
    
    # Get the list of inbounds
    inbounds = clients_data.get('obj', [])
    
    # Search through all inbounds for clients with matching tgId
    for inbound in inbounds:
        # Check if this inbound has settings
        if 'settings' in inbound:
            settings = inbound['settings']
            
            # Parse settings if it's a string
            if isinstance(settings, str):
                try:
                    settings = json.loads(settings)
                except json.JSONDecodeError:
                    continue
            
            # Check if settings has clients
            if 'clients' in settings:
                clients = settings['clients']
                
                # Search for client with matching tgId
                for client in clients:
                    client_tgId = client.get('tgId')
                    # Convert both to string for comparison to handle different types
                    if str(client_tgId) == str(telegram_id):
                        # Return the subId if found
                        return {
                            "success": True,
                            "subId": client.get('subId'),
                            "client_info": {
                                "id": client.get('id'),
                                "email": client.get('email'),
                                "enable": client.get('enable'),
                                "expiryTime": client.get('expiryTime'),
                                "totalGB": client.get('totalGB')
                            }
                        }
    
    # If no client found with matching tgId
    return {"error": f"No client found with tgId: {telegram_id}"}
    


def convert_timestamp_to_human_readable(timestamp_ms):
    """Конвертирует timestamp в миллисекундах в читаемый формат"""
    if timestamp_ms == 0:
        return "Не ограничено"
    
    try:
        # Конвертируем миллисекунды в секунды
        timestamp_s = timestamp_ms / 1000
        # Создаем datetime объект
        dt = datetime.datetime.fromtimestamp(timestamp_s)
        # Форматируем в читаемый вид
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError) as e:
        return f"Ошибка конвертации: {e}"


def convert_date_to_timestamp(date_str):
    """Конвертирует дату из формата ДД.ММ.ГГГГ в timestamp в миллисекундах"""
    try:
        # Парсим дату в формате ДД.ММ.ГГГГ
        dt = datetime.datetime.strptime(date_str, "%d.%m.%Y")
        # Устанавливаем время на 00:00:00
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        # Конвертируем в timestamp в миллисекундах
        timestamp_ms = int(dt.timestamp() * 1000)
        return timestamp_ms
    except ValueError as e:
        return f"Ошибка формата даты: {e}"


def add_client(inbound_id: int, username: str, tg_id: int, date: str):
    """Добавляет клиента с конвертацией даты в timestamp"""
    # Конвертируем дату в timestamp
    expiry_timestamp = convert_date_to_timestamp(date)
    
    if isinstance(expiry_timestamp, str):  # Если вернулась ошибка
        return {"error": expiry_timestamp}
    
    # Генерируем новый UUID для клиента
    import uuid
    client_id = str(uuid.uuid4())
    
    # Формируем данные клиента
    client_data = {
        "id": client_id,
        "flow": "",
        "email": f"{username}_{tg_id}",  # Уникальный email с доменом
        "limitIp": 0,
        "totalGB": 0,
        "expiryTime": expiry_timestamp,
        "enable": True,
        "tgId": tg_id,
        "subId": f"{client_id[:8]}",  # Генерируем subId
        "comment": "",
        "reset": 0
    }
    
    # Получаем текущие данные inbound
    clients_data = get_clients()
    if not clients_data.get('success'):
        return {"error": "Failed to get current inbound data"}
    
    # Находим нужный inbound
    target_inbound = None
    for inbound in clients_data.get('obj', []):
        if inbound.get('id') == inbound_id:
            target_inbound = inbound
            break
    
    if not target_inbound:
        return {"error": f"Inbound with id {inbound_id} not found"}
    
    # Парсим текущие settings
    current_settings = target_inbound.get('settings', '{}')
    if isinstance(current_settings, str):
        try:
            settings_obj = json.loads(current_settings)
        except json.JSONDecodeError:
            return {"error": "Failed to parse current settings"}
    else:
        settings_obj = current_settings
    
    # Создаем новые settings только с новым клиентом
    new_settings = {
        "clients": [client_data],  # Только новый клиент
        "decryption": "none",
        "encryption": "none"
    }
    
    print(f"Creating new client only: {client_data}")
    
    # Подготавливаем данные для API - только с новым клиентом
    settings_data = {
        "id": inbound_id,
        "settings": json.dumps(new_settings)
    }
    
    print(f"Settings data being sent: {settings_data}")
    
    admin_login = {
        "username": "2p9UguXWvb",
        "password": "RyR2wN0M9f"
    }
    
    # Create session and login
    session = requests.Session()
    login_response = session.post(f"{BASE_URL}/login", json=admin_login, verify=False)
    
    if login_response.json().get('success'):
        # Используем только addClient endpoint с правильными данными
        response = session.post(f"{BASE_URL}/panel/api/inbounds/addClient", json=settings_data, verify=False)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}", "response": response.text}
    else:
        return {"error": "Login failed"}


