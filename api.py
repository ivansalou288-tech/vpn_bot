import requests
import urllib3
import json
import random
import datetime
import time
from urllib.parse import quote
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
BASE_URL = 'https://www.ezhqpy.ru/fHvt2YpAP8'

import secret

admn_username = secret.user
admn_pass = secret.password
def login():

    admin_login = {
        "username": admn_username,
        "password": admn_pass
    }

    response = requests.post(f"{BASE_URL}/login", json=admin_login, verify=False)
    return response.json()

def get_clients():
    # First login to get session
    admin_login = {
        "username": admn_username,
        "password": admn_pass
    }
    
    print(f"[DEBUG] Attempting login to: {BASE_URL}/login")
    print(f"[DEBUG] Login data: {admin_login}")
    
    # Create session and login
    session = requests.Session()
    
    try:
        login_response = session.post(f"{BASE_URL}/login", json=admin_login, verify=False, timeout=10)
        
        print(f"[DEBUG] Login response status: {login_response.status_code}")
        print(f"[DEBUG] Login response: {login_response.text[:500]}")  # Ограничиваем вывод
        
        if login_response.status_code != 200:
            print(f"[DEBUG] HTTP error on login: {login_response.status_code}")
            return {"error": f"HTTP {login_response.status_code} on login"}
            
        login_result = login_response.json()
        if login_result.get('success'):
            # Use the authenticated session to get clients
            api_url = f"{BASE_URL}/panel/api/inbounds/list"
            print(f"[DEBUG] Getting clients from: {api_url}")
            
            response = session.get(api_url, verify=False, timeout=10)
            
            print(f"[DEBUG] Clients response status: {response.status_code}")
            print(f"[DEBUG] Clients response: {response.text[:500]}")  # Ограничиваем вывод
            
            if response.status_code != 200:
                print(f"[DEBUG] HTTP error on get clients: {response.status_code}")
                return {"error": f"HTTP {response.status_code} on get clients"}
                
            return response.json()
        else:
            print(f"[DEBUG] Login failed for user: {admn_username}")
            return {"error": "Login failed"}
            
    except requests.exceptions.RequestException as e:
        print(f"[DEBUG] Request exception: {e}")
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        print(f"[DEBUG] Unexpected error: {e}")
        return {"error": f"Unexpected error: {str(e)}"}


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
        "username": admn_username,
        "password": admn_pass
    }
    
    # Create session and login
    session = requests.Session()
    session.verify = False
    login_response = session.post(f"{BASE_URL}/login", json=admin_login)
    
    if login_response.json().get('success'):
        # Use the authenticated session to add inbound
            print(data)
            response = session.post("https://www.ezhqpy.ru/5WKqaFPoxu/panel/api/inbounds/add", json=data)
            
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
        "username": admn_username,
        "password": admn_pass
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

def dell_client(inboundId: int, telegramId: int):
    # Get client info first
    client_info = getSubById(telegramId)
    
    if not client_info.get('success'):
        return {"error": "Client not found", "details": client_info}
    
    email = client_info['client_info']['email']
    
    # First login to get session
    admin_login = {
        "username": admn_username,
        "password": admn_pass
    }
    
    # Create session and login
    session = requests.Session()
    login_response = session.post(f"{BASE_URL}/login", json=admin_login, verify=False)
    
    if login_response.json().get('success'):
        # Use the authenticated session to delete client
        enc = quote(str(email), safe="")
        response = session.post(
            f"{BASE_URL}/panel/api/inbounds/{inboundId}/delClientByEmail/{enc}",
            verify=False,
        )
        result = response.json()
        if result.get('success'):
            return result
        else:
            return result
    else:
        return {"error": "Login failed"}

def getNewX25519Cert():
    # First login to get session
    admin_login = {
        "username": admn_username,
        "password": admn_pass
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
                        # Return subId if found
                        return {
                            "success": True,
                            "subId": client.get('subId'),
                            "client_info": {
                                "id": client.get('id'),
                                "email": client.get('email'),
                                "enable": client.get('enable'),
                                "expiryTime": client.get('expiryTime'),
                                "totalGB": client.get('totalGB')
                            },
                            "inbound_id": inbound.get('id')  # Добавляем inbound_id для удаления
                        }
    
    # If no client found with matching tgId
    return {"error": f"No client found with tgId: {telegram_id}"}


def panel_session():
    session = requests.Session()
    session.verify = False
    login_response = session.post(
        f"{BASE_URL}/login",
        json={"username": admn_username, "password": admn_pass},
        verify=False,
    )
    if login_response.status_code != 200:
        return None, "login http error"
    try:
        body = login_response.json()
    except json.JSONDecodeError:
        return None, "login invalid json"
    if not body.get("success"):
        return None, "login failed"
    return session, None


def parse_inbound_settings(inbound):
    raw = inbound.get("settings", "{}")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return raw if isinstance(raw, dict) else None


def _client_route_id(protocol, client):
    if protocol == "trojan":
        v = client.get("password")
    elif protocol == "shadowsocks":
        v = client.get("email")
    else:
        v = client.get("id")
    if v is None or v == "":
        return None
    return str(v)


def find_clients_for_tg_on_inbound(settings_obj, tg_id, inbound_id):
    matches = []
    suffix = f"_{tg_id}_{inbound_id}"
    for c in settings_obj.get("clients") or []:
        matched = False
        raw_tg = c.get("tgId")
        if raw_tg is not None and raw_tg != "" and raw_tg != 0:
            try:
                if int(raw_tg) == int(tg_id):
                    matched = True
            except (TypeError, ValueError):
                pass
        if not matched:
            em = str(c.get("email", ""))
            if em.endswith(suffix):
                matched = True
        if matched:
            matches.append(c)
    return matches


def panel_del_client_by_email(session, inbound_id, email):
    if not email:
        return {"success": False, "msg": "empty email"}
    enc = quote(str(email), safe="")
    r = session.post(
        f"{BASE_URL}/panel/api/inbounds/{inbound_id}/delClientByEmail/{enc}",
        verify=False,
    )
    if r.status_code != 200:
        return {"success": False, "error": f"HTTP {r.status_code}", "msg": r.text}
    try:
        return r.json()
    except json.JSONDecodeError:
        return {"success": True, "msg": r.text}


def panel_add_inbound_client(session, inbound_id, client_dict, protocol):
    fragment = {"clients": [client_dict]}
    if protocol == "vless":
        fragment.setdefault("decryption", "none")
        fragment.setdefault("encryption", "none")
    elif protocol == "trojan":
        fragment.setdefault("fallbacks", [])
    body = {"id": inbound_id, "settings": json.dumps(fragment)}
    r = session.post(f"{BASE_URL}/panel/api/inbounds/addClient", json=body, verify=False)
    if r.status_code != 200:
        return {"success": False, "error": f"HTTP {r.status_code}", "msg": r.text}
    try:
        return r.json()
    except json.JSONDecodeError:
        return {"success": False, "msg": r.text}


def panel_update_inbound_client(session, inbound_id, protocol, route_client_id, settings_obj, updated_client):
    patch = {k: v for k, v in settings_obj.items() if k != "clients"}
    patch["clients"] = [updated_client]
    body = {"id": inbound_id, "settings": json.dumps(patch)}
    enc = quote(str(route_client_id), safe="")
    url = f"{BASE_URL}/panel/api/inbounds/updateClient/{enc}"
    r = session.post(url, json=body, verify=False)
    if r.status_code != 200:
        return {"success": False, "error": f"HTTP {r.status_code}", "msg": r.text}
    try:
        return r.json()
    except json.JSONDecodeError:
        return {"success": False, "msg": r.text}


def _apply_expiry_to_user_inbounds(tg_id: int, new_expiry_ms: int, inbound_ids=None):
    """Обновляет expiryTime у клиента на указанных inbound (без смены subId / UUID)."""
    if inbound_ids is None:
        inbound_ids = {1, 2, 3, 4}

    clients_data = get_clients()
    if not clients_data.get("success"):
        return {"success": False, "error": "Failed to get inbounds", "details": clients_data, "results": []}

    session, err = panel_session()
    if session is None:
        return {"success": False, "error": err or "Login failed", "results": []}

    results = []
    for inbound in clients_data.get("obj", []):
        iid = inbound.get("id")
        if iid not in inbound_ids:
            continue

        settings_obj = parse_inbound_settings(inbound)
        if not settings_obj:
            results.append({"inbound_id": iid, "error": "bad settings"})
            continue

        protocol = inbound.get("protocol", "vless")
        matches = find_clients_for_tg_on_inbound(settings_obj, tg_id, iid)
        if not matches:
            results.append({"inbound_id": iid, "skipped": "no client for this tg_id"})
            continue

        primary = matches[0]
        for extra in matches[1:]:
            em = extra.get("email")
            if em:
                panel_del_client_by_email(session, iid, em)

        route_id = _client_route_id(protocol, primary)
        if not route_id:
            results.append({"inbound_id": iid, "error": "cannot resolve client id for API path"})
            continue

        updated = dict(primary)
        updated["expiryTime"] = new_expiry_ms
        updated["enable"] = True
        if updated.get("tgId") is None:
            updated["tgId"] = tg_id

        upd = panel_update_inbound_client(
            session, iid, protocol, route_id, settings_obj, updated
        )
        results.append({"inbound_id": iid, "update_result": upd})

    updated_rows = [r for r in results if "update_result" in r]
    if not updated_rows:
        success = False
    else:
        success = all(r["update_result"].get("success") for r in updated_rows)

    return {"success": success, "results": results}


def renew_subscription_on_panel(tg_id: int, additional_months: int, inbound_ids=None):
    """
    Продление: текущий срок (или сейчас, если истёк) + N месяцев по 30 суток.
    """
    if inbound_ids is None:
        inbound_ids = {1, 2, 3, 4}

    client_info = getSubById(tg_id)
    if not client_info.get("success"):
        return {"error": "Client not found", "details": client_info}

    current_expiry = client_info["client_info"]["expiryTime"]
    current_time = int(time.time() * 1000)
    new_expiry = current_time if current_expiry == 0 else current_expiry
    additional_ms = additional_months * 30 * 24 * 60 * 60 * 1000
    new_expiry += additional_ms

    core = _apply_expiry_to_user_inbounds(tg_id, new_expiry, inbound_ids)
    out = {
        "success": core["success"],
        "message": f"Subscription renewed for {additional_months} months (expiry update)",
        "old_expiry": current_expiry,
        "new_expiry": new_expiry,
        "results": core["results"],
    }
    if core.get("error"):
        out["error"] = core["error"]
    if core.get("details"):
        out["details"] = core["details"]
    return out


def set_subscription_expiry_on_panel(tg_id: int, new_expiry_ms: int, inbound_ids=None):
    """
    Выставить дату окончания подписки в абсолютное время (на всех инбаундах 1–4).
    Для админки: «на 1 месяц» = до now+30d, а не продление поверх остатка.
    """
    if inbound_ids is None:
        inbound_ids = {1, 2, 3, 4}

    client_info = getSubById(tg_id)
    old_expiry = 0
    if client_info.get("success"):
        old_expiry = client_info["client_info"].get("expiryTime") or 0

    core = _apply_expiry_to_user_inbounds(tg_id, new_expiry_ms, inbound_ids)
    out = {
        "success": core["success"],
        "message": "Subscription expiry set",
        "old_expiry": old_expiry,
        "new_expiry": new_expiry_ms,
        "results": core["results"],
    }
    if core.get("error"):
        out["error"] = core["error"]
    if core.get("details"):
        out["details"] = core["details"]
    return out


def renew_subscription(tg_id: int, additional_months: int):
    """Продлевает подписку на указанное количество месяцев (все инбаунды 1–4)."""
    return renew_subscription_on_panel(tg_id, additional_months)

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
        return dt.strftime("%d.%m.%Y %H:%M:%S")
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
    """
    Новый клиент через POST .../addClient.
    Параметр username — общий префикс для subId на всех инбаундах: subId = {username}_{tg_id},
    email/id на инбаунде = {username}_{tg_id}_{inbound_id}. Если username пустой — генерируется случайный префикс.
    """
    import secrets

    expiry_timestamp = convert_date_to_timestamp(date)
    if isinstance(expiry_timestamp, str):
        return {"error": expiry_timestamp}

    prefix_raw = (username or "").strip() if username is not None else ""
    prefix = prefix_raw if prefix_raw else secrets.token_urlsafe(8)
    sub_id = f"{prefix}_{tg_id}"
    email = f"{prefix}_{tg_id}_{inbound_id}"
    client_id = f"{prefix}_{tg_id}_{inbound_id}"

    clients_data = get_clients()
    if not clients_data.get("success"):
        return {"error": "Failed to get current inbound data"}

    target_inbound = None
    for inbound in clients_data.get("obj", []):
        if inbound.get("id") == inbound_id:
            target_inbound = inbound
            break
    if not target_inbound:
        return {"error": f"Inbound with id {inbound_id} not found"}

    protocol = target_inbound.get("protocol", "vless")
    settings_obj = parse_inbound_settings(target_inbound)
    if not settings_obj:
        return {"error": "Failed to parse current settings"}

    if protocol == "trojan":
        password = secrets.token_urlsafe(16)
        client_data = {
            "password": password,
            "flow": "",
            "email": email,
            "limitIp": 0,
            "totalGB": 0,
            "expiryTime": expiry_timestamp,
            "enable": True,
            "tgId": tg_id,
            "subId": sub_id,
            "comment": "",
            "reset": 0,
        }
        print(f"[API] Creating trojan client for inbound {inbound_id} subId={sub_id}")
    else:
        client_data = {
            "id": client_id,
            "flow": "",
            "email": email,
            "limitIp": 0,
            "totalGB": 0,
            "expiryTime": expiry_timestamp,
            "enable": True,
            "tgId": tg_id,
            "subId": sub_id,
            "comment": "",
            "reset": 0,
        }
        print(f"[API] Creating vless client id={client_id} inbound={inbound_id} subId={sub_id}")

    session, err = panel_session()
    if session is None:
        return {"error": err or "Login failed"}

    for old in find_clients_for_tg_on_inbound(settings_obj, tg_id, inbound_id):
        em = old.get("email")
        if em:
            panel_del_client_by_email(session, inbound_id, em)

    return panel_add_inbound_client(session, inbound_id, client_data, protocol)

def check_cantfree(tg_id):
    """Проверяет есть ли пользователь в CantFree"""
    admin_login = {
        "username": admn_username,
        "password": admn_pass
    }
    
    # Create session and login
    session = requests.Session()
    session.verify = False
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        # Login
        login_response = session.post(f"{BASE_URL}/login", json=admin_login)
        if login_response.status_code != 200:
            return {"error": "Login failed"}
        
        # Get CantFree users
        cantfree_response = session.get(f"{BASE_URL}/cantfree")
        if cantfree_response.status_code == 200:
            cantfree_users = cantfree_response.json()
            
            # Check if user exists in CantFree
            for user in cantfree_users:
                if str(user.get('tgId')) == str(tg_id):
                    return {"exists": True, "user": user}
            
            return {"exists": False}
        else:
            return {"error": "Failed to get CantFree users"}
            
    except Exception as e:
        return {"error": str(e)}

def add_to_cantfree(tg_id, username):
    """Добавляет пользователя в CantFree"""
    admin_login = {
        "username": admn_username,
        "password": admn_pass
    }
    
    # Create session and login
    session = requests.Session()
    session.verify = False
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        # Login
        login_response = session.post(f"{BASE_URL}/login", json=admin_login)
        if login_response.status_code != 200:
            return {"error": "Login failed"}
        
        # Add to CantFree
        cantfree_data = {
            "tgId": tg_id,
            "username": username or f"user_{tg_id}"
        }
        
        add_response = session.post(f"{BASE_URL}/cantfree", json=cantfree_data)
        if add_response.status_code == 200:
            return {"success": True, "message": "User added to CantFree"}
        else:
            return {"error": f"Failed to add to CantFree: {add_response.status_code}"}
            
    except Exception as e:
        return {"error": str(e)}


