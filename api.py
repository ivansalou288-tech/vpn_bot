import requests
import urllib3
import json
import random
import datetime
import time
import secrets
from urllib.parse import quote
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from config import PANEL_BASE_URL, PANEL_DOMAIN, PANEL_PORT, PANEL_PATH

BASE_URL = PANEL_BASE_URL

import secret

admn_username = secret.user
admn_pass = secret.password
api_token = secret.api_token

def get_headers():
    """Return headers with Bearer token authentication"""
    return {
        "Authorization": f"Bearer {api_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

def get_clients():
    """Get list of clients using Bearer token authentication"""
    api_url = f"{BASE_URL}/panel/api/inbounds/list"
    
    print(f"\n[get_clients] Получаем список клиентов с API токеном...")
    print(f"[get_clients] URL: {api_url}")
    
    try:
        headers = get_headers()
        response = requests.get(api_url, headers=headers, verify=False, timeout=10)
        
        print(f"[get_clients] Статус ответа: {response.status_code}")
        print(f"[get_clients] Ответ (первые 500 chars): {response.text[:500]}")
        
        if response.status_code != 200:
            print(f"[get_clients] ✗ HTTP ошибка: {response.status_code}")
            return {"error": f"HTTP {response.status_code} on get clients", "response": response.text}
            
        result = response.json()
        if result.get('success'):
            print(f"[get_clients] ✓ Успешно получены клиенты")
            return result
        else:
            print(f"[get_clients] ✗ API ошибка: {result}")
            return result
            
    except requests.exceptions.RequestException as e:
        print(f"[get_clients] ✗ Request исключение: {e}")
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        print(f"[get_clients] ✗ Неожиданное исключение: {e}")
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

    try:
        headers = get_headers()
        response = requests.post(f"{BASE_URL}/panel/api/inbounds/add", json=data, headers=headers, verify=False)
        
        print(data)
        print(f"Status Code: {response.status_code}")
        print(f"Response Text: {response.text}")
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"HTTP {response.status_code}", "response": response.text}
    except Exception as e:
        return {"error": f"Failed to add inbound: {str(e)}"}

def getNewmldsa65():
    """Get new mldsa65 keys using Bearer token authentication"""
    try:
        headers = get_headers()
        response = requests.get(f"{BASE_URL}/panel/api/server/getNewmldsa65", headers=headers, verify=False)
        
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
    except Exception as e:
        return {"error": f"Failed to get mldsa65 keys: {str(e)}"}

def dell_client(inboundId: int, telegramId: int):
    """Delete client using Bearer token authentication"""
    # Get client info first
    client_info = getSubById(telegramId)
    
    if not client_info.get('success'):
        return {"error": "Client not found", "details": client_info}
    
    email = client_info['client_info']['email']
    
    try:
        headers = get_headers()
        enc = quote(str(email), safe="")
        response = requests.post(
            f"{BASE_URL}/panel/api/inbounds/{inboundId}/delClientByEmail/{enc}",
            headers=headers,
            verify=False,
        )
        result = response.json()
        if result.get('success'):
            return result
        else:
            return result
    except Exception as e:
        return {"error": f"Failed to delete client: {str(e)}"}

def getNewX25519Cert():
    """Get new X25519 certificate using Bearer token authentication"""
    try:
        headers = get_headers()
        response = requests.get(f"{BASE_URL}/panel/api/server/getNewX25519Cert", headers=headers, verify=False)
        
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
    except Exception as e:
        return {"error": f"Failed to get X25519 certificate: {str(e)}"}


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
    """Create a requests session with Bearer token authentication"""
    session = requests.Session()
    session.verify = False
    
    # Add Authorization header with Bearer token
    session.headers.update(get_headers())
    
    print(f"[DEBUG panel_session] Сессия создана с Bearer токеном")
    print(f"[DEBUG panel_session] Headers: {dict(session.headers)}")
    
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
    """Add client using new /panel/api/clients/add endpoint with Bearer token"""
    # Подготавливаем клиента для нового API
    client = dict(client_dict)
    
    # Убеждаемся, что есть все необходимые поля
    if "id" not in client and protocol == "vless":
        client["id"] = client_dict.get("id", secrets.token_urlsafe(16))
    if "password" not in client and protocol == "trojan":
        client["password"] = secrets.token_urlsafe(16)
    
    # Для VLESS не нужна password, для Trojan не нужен id
    if protocol == "vless" and "password" in client:
        del client["password"]
    if protocol == "trojan" and "id" in client:
        del client["id"]
    
    # Новый API endpoint: /panel/api/clients/add
    # Body format: {"client": {...}, "inboundIds": [inbound_id]}
    body = {
        "client": client,
        "inboundIds": [inbound_id]
    }
    
    url = f"{BASE_URL}/panel/api/clients/add"
    print(f"[API] POST запрос (новый API): {url}")
    print(f"[API] Body: {json.dumps(body, indent=2)}")
    
    headers = get_headers()
    r = requests.post(url, json=body, headers=headers, verify=False)
    
    print(f"[API] Ответ панели - статус: {r.status_code}")
    print(f"[API] Ответ панели - содержимое: {r.text}")
    
    if r.status_code != 200:
        return {"success": False, "error": f"HTTP {r.status_code}", "msg": r.text}
    
    try:
        result = r.json()
        print(f"[API] Парсед JSON ответ: {json.dumps(result, indent=2)}")
        return result
    except json.JSONDecodeError:
        return {"success": False, "msg": r.text}


def panel_update_inbound_client(session, inbound_id, protocol, route_client_id, settings_obj, updated_client):
    patch = {k: v for k, v in settings_obj.items() if k != "clients"}
    patch["clients"] = [updated_client]
    body = {"id": inbound_id, "settings": json.dumps(patch)}
    enc = quote(str(route_client_id), safe="")
    url = f"{BASE_URL}/panel/api/inbounds/updateClient/{enc}"
    print(f"[DEBUG update] URL: {url}")
    print(f"[DEBUG update] route_client_id: {route_client_id}, protocol: {protocol}")
    print(f"[DEBUG update] client_id from updated: {updated_client.get('id')}, email: {updated_client.get('email')}")
    r = session.post(url, json=body, verify=False)
    print(f"[DEBUG update] Response status: {r.status_code}")
    if r.status_code != 200:
        print(f"[DEBUG update] Error response: {r.text}")
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

        print(f"[DEBUG expire] Found {len(matches)} matches for tg_id={tg_id} on inbound {iid}")

        primary = matches[0]
        print(f"[DEBUG expire] Primary client: id={primary.get('id')}, email={primary.get('email')}, tgId={primary.get('tgId')}")
        
        for extra in matches[1:]:
            em = extra.get("email")
            if em:
                panel_del_client_by_email(session, iid, em)

        route_id = _client_route_id(protocol, primary)
        print(f"[DEBUG expire] route_id={route_id}, protocol={protocol}")
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

    # Считаем операцию успешной если обновлено хотя бы на одном инбаунде
    updated_rows = [r for r in results if "update_result" in r]
    successfully_updated = [r for r in updated_rows if r["update_result"].get("success")]
    success = len(successfully_updated) > 0

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
    Новый клиент через POST .../clients/add (новый API endpoint).
    Параметр username — общий префикс для subId на всех инбаундах: subId = {username}_{tg_id},
    email/id на инбаунде = {username}_{tg_id}_{inbound_id}. Если username пустой — генерируется случайный префикс.
    """
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

    print(f"[API] Подготовка клиента: email={email}, tg_id={tg_id}, sub_id={sub_id}")
    print(f"[API] Данные клиента: {json.dumps(client_data, indent=2)}")

    print(f"[API] Отправка клиента на панель (новый API)...")
    result = panel_add_inbound_client(None, inbound_id, client_data, protocol)
    print(f"[API] Итоговый результат: {json.dumps(result, indent=2)}")
    
    # Отправляем запрос на www.ezh-dev.ru:2500/add_client если клиент успешно создан
    if result.get("success"):
        sub_id = client_data.get("subId")
        try:
            webhook_url = "https://www.ezh-dev.ru:2500/add_client"
            webhook_payload = {
                "tg_id": tg_id,
                "sub_id": sub_id
            }
            print(f"[API] Отправляем вебхук: POST {webhook_url}")
            print(f"[API] Payload: {json.dumps(webhook_payload)}")
            webhook_response = requests.post(webhook_url, json=webhook_payload, timeout=60, verify=False)
            print(f"[API] Вебхук ответ статус: {webhook_response.status_code}")
            print(f"[API] Вебхук ответ: {webhook_response.text}")
        except requests.exceptions.Timeout:
            print(f"[API] Ошибка: Timeout при отправке вебхука на {webhook_url}")
        except requests.exceptions.ConnectionError:
            print(f"[API] Ошибка: Connection Error при отправке вебхука на {webhook_url}")
        except Exception as e:
            print(f"[API] Ошибка при отправке вебхука: {e}")
    
    return result

def check_cantfree(tg_id):
    """Проверяет есть ли пользователь в CantFree"""
    try:
        headers = get_headers()
        
        # Get CantFree users
        cantfree_response = requests.get(f"{BASE_URL}/cantfree", headers=headers, verify=False)
        if cantfree_response.status_code == 200:
            cantfree_users = cantfree_response.json()
            
            # Check if user exists in CantFree
            for user in cantfree_users:
                if str(user.get('tgId')) == str(tg_id):
                    return {"exists": True, "user": user}
            
            return {"exists": False}
        else:
            return {"error": f"Failed to get CantFree users: HTTP {cantfree_response.status_code}"}
            
    except Exception as e:
        return {"error": str(e)}

def add_to_cantfree(tg_id, username):
    """Добавляет пользователя в CantFree"""
    try:
        headers = get_headers()
        
        # Add to CantFree
        cantfree_data = {
            "tgId": tg_id,
            "username": username or f"user_{tg_id}"
        }
        
        add_response = requests.post(f"{BASE_URL}/cantfree", json=cantfree_data, headers=headers, verify=False)
        if add_response.status_code == 200:
            return {"success": True, "message": "User added to CantFree"}
        else:
            return {"error": f"Failed to add to CantFree: HTTP {add_response.status_code}", "response": add_response.text}
            
    except Exception as e:
        return {"error": str(e)}


