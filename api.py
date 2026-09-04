import requests
import urllib3
import json
import random
import datetime
import time
import secrets
import string
from urllib.parse import quote
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import PANEL_BASE_URL, PANEL_DOMAIN, PANEL_PORT, PANEL_PATH, REMOTE_SERVERS

BASE_URL = PANEL_BASE_URL

import secret

admn_username = secret.user
admn_pass = secret.password
api_token = secret.api_token


def generate_sub_prefix(length=8):
    """
    Генерирует случайный prefix для sub_id без буквы 't'
    Использует буквы и цифры, но без 't'
    """
    # Исключаем букву 't' и 'T' из доступных символов
    available_chars = string.ascii_letters.replace('t', '').replace('T', '') + string.digits
    return ''.join(secrets.choice(available_chars) for _ in range(length))


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
    """Удаляет клиента: сначала новый API /clients/del, затем legacy delClientByEmail."""
    if not email:
        return {"success": False, "msg": "empty email"}
    enc = quote(str(email), safe="")

    url = f"{BASE_URL}/panel/api/clients/del/{enc}"
    print(f"[API] DELETE client (new API): {url}")
    r = session.post(url, verify=False)
    print(f"[API] DELETE response: {r.status_code} - {r.text[:300]}")
    if r.status_code == 200:
        try:
            result = r.json()
            if result.get("success"):
                return result
        except json.JSONDecodeError:
            return {"success": True, "msg": r.text}

    url_legacy = f"{BASE_URL}/panel/api/inbounds/{inbound_id}/delClientByEmail/{enc}"
    print(f"[API] DELETE client (legacy API): {url_legacy}")
    r = session.post(url_legacy, verify=False)
    print(f"[API] DELETE legacy response: {r.status_code} - {r.text[:300]}")
    if r.status_code != 200:
        return {"success": False, "error": f"HTTP {r.status_code}", "msg": r.text}
    try:
        return r.json()
    except json.JSONDecodeError:
        return {"success": True, "msg": r.text}


def panel_update_client_by_email(session, email, client_data, inbound_ids=None):
    """Обновляет клиента через новый API /panel/api/clients/update/{email}."""
    if not email:
        return {"success": False, "msg": "empty email"}
    enc = quote(str(email), safe="")
    url = f"{BASE_URL}/panel/api/clients/update/{enc}"
    if inbound_ids:
        url += "?inboundIds=" + ",".join(str(i) for i in inbound_ids)

    print(f"[API] UPDATE client: {url}")
    print(f"[API] UPDATE body: {json.dumps(client_data, indent=2)}")
    r = session.post(url, json=client_data, verify=False)
    print(f"[API] UPDATE response: {r.status_code} - {r.text[:300]}")
    if r.status_code != 200:
        return {"success": False, "error": f"HTTP {r.status_code}", "msg": r.text}
    try:
        return r.json()
    except json.JSONDecodeError:
        return {"success": False, "msg": r.text}


def panel_add_client(client_dict, inbound_ids):
    """
    Добавляет клиента на несколько inbound одним запросом.
    Body: {"client": {...}, "inboundIds": [3, 5, ...]}
    """
    if not inbound_ids:
        return {"success": False, "error": "No inbound IDs provided"}

    body = {
        "client": dict(client_dict),
        "inboundIds": list(inbound_ids),
    }

    url = f"{BASE_URL}/panel/api/clients/add"
    print(f"[API] POST clients/add (batch): {url}")
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


def panel_add_inbound_client(session, inbound_id, client_dict, protocol):
    """Add client to a single inbound (wrapper over panel_add_client)."""
    client = dict(client_dict)

    if "id" not in client and protocol == "vless":
        client["id"] = client_dict.get("id", secrets.token_urlsafe(16))
    if "password" not in client and protocol == "trojan":
        client["password"] = secrets.token_urlsafe(16)

    if protocol == "vless" and "password" in client:
        del client["password"]
    if protocol == "trojan" and "id" in client:
        del client["id"]

    return panel_add_client(client, [inbound_id])


def build_subscription_client(prefix: str, tg_id: int, expiry_ms: int, sub_id: str = None):
    """Собирает объект client для batch-запроса clients/add."""
    sub_id = sub_id or f"{prefix}_{tg_id}"
    email = sub_id

    return {
        "id": secrets.token_urlsafe(16),
        "flow": "",
        "email": email,
        "limitIp": 0,
        "totalGB": 0,
        "expiryTime": expiry_ms,
        "enable": True,
        "tgId": tg_id,
        "subId": sub_id,
        "comment": "",
        "reset": 0,
    }


BOT_TOKEN = "8358697144:AAGppsqXjG9S08nGLUpghL-jUfTz9H4gj58"
ADMIN_CHAT_IDS = [1240656726, 1401086794]


def remote_error_text(webhook_result):
    """Человекочитаемое описание ошибки удалённого сервера."""
    if not webhook_result:
        return "нет ответа от удалённого сервера"
    err = webhook_result.get("error")
    if err == "timeout":
        return "таймаут запроса к удалённому серверу"
    if err == "connection_error":
        return "нет соединения с удалённым сервером"
    if err:
        return str(err)
    parsed = webhook_result.get("parsed")
    if isinstance(parsed, dict):
        details = parsed.get("error") or parsed.get("message")
        if details:
            return str(details)
    text = (webhook_result.get("response") or "").strip()
    code = webhook_result.get("status_code")
    snippet = text[:300] if text else "пустой ответ"
    if code:
        return f"HTTP {code}: {snippet}"
    return snippet


def notify_admin_remote_server_error(tg_id, sub_id, date, error, context="создание подписки", remote_results=None):
    """Пишет админам, что на удалённом сервере не получилось создать/обновить подписку."""
    import html as html_mod

    safe_error = html_mod.escape(str(error or "неизвестная ошибка")[:500])
    if remote_results:
        server_lines = []
        for r in remote_results:
            label = html_mod.escape(str(r.get("label") or r.get("name") or "Удалённый"))
            if r.get("success"):
                server_lines.append(f"✅ {label}: создано")
            else:
                err = html_mod.escape(str(r.get("error") or "неизвестная ошибка")[:500])
                server_lines.append(f"❌ {label}: не создано\n🔍 Ошибка: <code>{err}</code>")
        remotes_block = "\n".join(server_lines)
        failed_count = sum(1 for r in remote_results if not r.get("success"))
        title = "Ошибка на удалённых серверах" if failed_count > 1 else "Ошибка на удалённом сервере"
    else:
        remotes_block = (
            f"❌ Удалённый сервер: не создано\n"
            f"🔍 Ошибка: <code>{safe_error}</code>"
        )
        title = "Ошибка на удалённом сервере"

    text = (
        f"⚠️ <b>{title}</b>\n\n"
        f"Операция: {html_mod.escape(str(context))}\n"
        f"👤 TG ID: <code>{tg_id}</code>\n"
        f"🔑 SubID: <code>{html_mod.escape(str(sub_id or 'N/A'))}</code>\n"
        f"📅 Дата: <b>{html_mod.escape(str(date or 'N/A'))}</b>\n\n"
        f"✅ Основной сервер: создано\n"
        f"{remotes_block}\n\n"
        f"Клиенту показано, что операция успешна."
    )
    for chat_id in ADMIN_CHAT_IDS:
        try:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )
        except Exception as e:
            print(f"[API] Failed to notify admin {chat_id} about remote error: {e}")


def _post_remote_webhook(server, path: str, payload: dict, timeout: int = 60):
    """Один POST на webhook одного удалённого сервера."""
    label = server.get("label") or server.get("name") or "remote"
    name = server.get("name") or label
    base = str(server.get("base_url") or "").rstrip("/")
    webhook_url = f"{base}{path}"

    print(f"[API] Webhook POST {webhook_url} ({label})")
    print(f"[API] Payload: {json.dumps(payload)}")

    result = {
        "success": False,
        "name": name,
        "label": label,
        "url": webhook_url,
        "status_code": None,
        "response": "",
        "parsed": None,
        "error": None,
    }

    try:
        webhook_response = requests.post(webhook_url, json=payload, timeout=timeout, verify=False)
        print(f"[API] Webhook {label} status: {webhook_response.status_code}")
        print(f"[API] Webhook {label} response: {webhook_response.text}")

        raw = webhook_response.text or ""
        parsed = None
        try:
            parsed = webhook_response.json()
        except Exception:
            parsed = None

        if isinstance(parsed, dict) and "success" in parsed:
            success = bool(parsed.get("success"))
            error = None if success else (
                parsed.get("error") or parsed.get("message") or raw[:500] or f"HTTP {webhook_response.status_code}"
            )
        else:
            success = 200 <= webhook_response.status_code < 300
            error = None if success else (raw[:500] or f"HTTP {webhook_response.status_code}")

        result.update({
            "success": success,
            "status_code": webhook_response.status_code,
            "response": raw,
            "parsed": parsed,
            "error": error,
        })
        return result
    except requests.exceptions.Timeout:
        print(f"[API] Webhook timeout: {webhook_url}")
        result["error"] = "timeout"
        return result
    except requests.exceptions.ConnectionError:
        print(f"[API] Webhook connection error: {webhook_url}")
        result["error"] = "connection_error"
        return result
    except Exception as e:
        print(f"[API] Webhook error ({label}): {e}")
        result["error"] = str(e)
        return result


def send_webhooks_to_all_remotes(path: str, payload: dict, timeout: int = 60):
    """Параллельно дергает webhook на всех удалённых серверах."""
    servers = list(REMOTE_SERVERS or [])
    if not servers:
        return {"success": True, "results": [], "error": None}

    by_name = {}
    workers = max(1, len(servers))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_post_remote_webhook, server, path, payload, timeout): server
            for server in servers
        }
        for fut in as_completed(futures):
            server = futures[fut]
            name = server.get("name") or server.get("label")
            try:
                by_name[name] = fut.result()
            except Exception as e:
                by_name[name] = {
                    "success": False,
                    "name": name,
                    "label": server.get("label") or name,
                    "error": str(e),
                }

    results = [by_name[s.get("name") or s.get("label")] for s in servers]
    failed = [r for r in results if not r.get("success")]
    return {
        "success": not failed,
        "results": results,
        "error": None if not failed else "; ".join(
            f"{r.get('label')}: {r.get('error') or 'ошибка'}" for r in failed
        ),
    }


def send_add_client_webhook(tg_id: int, sub_id: str, end_date: str = None):
    """Создаёт подписку на всех удалённых серверах."""
    webhook_payload = {"tg_id": tg_id, "sub_id": sub_id}
    if end_date:
        webhook_payload["end_date"] = end_date
    return send_webhooks_to_all_remotes("/add_client", webhook_payload, timeout=60)


def send_dell_client_webhook(tg_id: int, sub_id: str):
    """Удаляет подписку на всех удалённых серверах."""
    return send_webhooks_to_all_remotes(
        "/dell_client",
        {"tg_id": tg_id, "sub_id": sub_id},
        timeout=30,
    )


def cleanup_clients_for_subscription(sub_id: str, tg_id: int):
    """Удаляет старых клиентов с тем же sub_id/tg_id перед batch-созданием."""
    clients_data = get_clients()
    if not clients_data.get("success"):
        return {"success": False, "deleted": 0}

    emails_to_delete = set()
    for inbound in clients_data.get("obj", []):
        settings_obj = parse_inbound_settings(inbound)
        if not settings_obj:
            continue
        for client in settings_obj.get("clients", []):
            if client.get("subId") == sub_id or str(client.get("tgId")) == str(tg_id):
                email = client.get("email")
                if email:
                    emails_to_delete.add(email)

    if not emails_to_delete:
        return {"success": True, "deleted": 0}

    session, err = panel_session()
    if session is None:
        return {"success": False, "error": err or "Login failed", "deleted": 0}

    deleted = 0
    for email in emails_to_delete:
        del_result = panel_del_client_by_email(session, 0, email)
        if del_result.get("success"):
            deleted += 1
        print(f"[API] Cleanup delete email={email}: {del_result}")

    return {"success": True, "deleted": deleted, "emails": list(emails_to_delete)}


def create_subscription_on_panel(tg_id: int, date: str, sub_id: str, cleanup: bool = True):
    """
    Создаёт одного клиента на всех inbound одним запросом POST /panel/api/clients/add.
    Используется на основном и удалённом сервере.
    """
    expiry_ms = convert_date_to_timestamp(date)
    if isinstance(expiry_ms, str):
        return {"success": False, "error": expiry_ms, "subId": sub_id}

    parts = sub_id.rsplit("_", 1)
    sub_prefix = parts[0] if len(parts) > 1 else sub_id

    cleanup_result = None
    if cleanup:
        cleanup_result = cleanup_clients_for_subscription(sub_id, tg_id)

    clients_data = get_clients()
    if not clients_data.get("success"):
        return {
            "success": False,
            "error": "Failed to get inbounds list",
            "subId": sub_id,
            "cleanup_result": cleanup_result,
        }

    inbound_ids = [inbound.get("id") for inbound in clients_data.get("obj", []) if inbound.get("id") is not None]
    if not inbound_ids:
        return {
            "success": False,
            "error": "No inbounds found",
            "subId": sub_id,
            "cleanup_result": cleanup_result,
        }

    client_data = build_subscription_client(sub_prefix, tg_id, expiry_ms, sub_id)
    print(f"[API] Batch create: subId={sub_id}, inbounds={inbound_ids}")
    panel_result = panel_add_client(client_data, inbound_ids)

    success = bool(panel_result.get("success"))
    return {
        "success": success,
        "message": f"Client added to {len(inbound_ids)} inbounds" if success else "Failed to add client to panel",
        "subId": sub_id,
        "client_prefix": sub_prefix,
        "inbound_ids": inbound_ids,
        "client": client_data,
        "panel_result": panel_result,
        "cleanup_result": cleanup_result,
    }


def update_subscription_on_panel(tg_id: int, sub_id: str, expiry_ms: int):
    """Fallback: одним запросом обновить клиента на всех inbound."""
    parts = sub_id.rsplit("_", 1)
    sub_prefix = parts[0] if len(parts) > 1 else sub_id
    email = sub_id

    clients_data = get_clients()
    if not clients_data.get("success"):
        return {"success": False, "error": "Failed to get inbounds list"}

    inbound_ids = [inbound.get("id") for inbound in clients_data.get("obj", []) if inbound.get("id") is not None]
    if not inbound_ids:
        return {"success": False, "error": "No inbounds found"}

    client_data = build_subscription_client(sub_prefix, tg_id, expiry_ms, sub_id)
    session, err = panel_session()
    if session is None:
        return {"success": False, "error": err or "Login failed"}

    update_result = panel_update_client_by_email(session, email, client_data, inbound_ids)
    return {
        "success": bool(update_result.get("success")),
        "method": "update",
        "subId": sub_id,
        "inbound_ids": inbound_ids,
        "update_result": update_result,
    }


def panel_update_inbound_client(session, inbound_id, protocol, route_client_id, settings_obj, updated_client):
    """Обновляет клиента через /inbounds/{id}/updateClient"""
    client_email = updated_client.get("email")
    if not client_email:
        return {"success": False, "error": "No email in updated client"}

    enc_email = quote(str(client_email), safe="")
    url = f"{BASE_URL}/panel/api/inbounds/{inbound_id}/updateClient/{enc_email}"

    patch = {k: v for k, v in settings_obj.items() if k != "clients"}
    patch["clients"] = [updated_client]
    body = {"id": inbound_id, "settings": json.dumps(patch)}

    print(f"[DEBUG update] URL: {url}")
    print(f"[DEBUG update] client_email: {client_email}, protocol: {protocol}")
    print(f"[DEBUG update] client data: {json.dumps(updated_client, indent=2)}")

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


def dell_client_from_all_inbounds(tg_id: int, inbound_ids=None):
    """Удаляет клиента со всех указанных инбаундов (по умолчанию — со всех существующих)."""
    clients_data = get_clients()
    if not clients_data.get("success"):
        return {"success": False, "error": "Failed to get inbounds"}

    if inbound_ids is None:
        inbound_ids = {inbound.get("id") for inbound in clients_data.get("obj", []) if inbound.get("id") is not None}
    
    session, err = panel_session()
    if session is None:
        return {"success": False, "error": err or "Login failed"}
    
    results = []
    for inbound in clients_data.get("obj", []):
        iid = inbound.get("id")
        if iid not in inbound_ids:
            continue
        
        settings_obj = parse_inbound_settings(inbound)
        if not settings_obj:
            results.append({"inbound_id": iid, "error": "bad settings"})
            continue
        
        matches = find_clients_for_tg_on_inbound(settings_obj, tg_id, iid)
        if not matches:
            results.append({"inbound_id": iid, "skipped": "no client"})
            continue
        
        for client in matches:
            em = client.get("email")
            if em:
                del_result = panel_del_client_by_email(session, iid, em)
                results.append({"inbound_id": iid, "email": em, "result": del_result})
    
    return {"success": True, "results": results}


def _renew_by_updating_expiry(tg_id: int, new_expiry_ms: int):
    """Обновляет expiryTime у всех клиентов пользователя через новый API clients/update."""
    clients_data = get_clients()
    if not clients_data.get("success"):
        return {"success": False, "error": "Failed to get inbounds", "results": []}

    session, err = panel_session()
    if session is None:
        return {"success": False, "error": err or "Login failed", "results": []}

    results = []
    for inbound in clients_data.get("obj", []):
        iid = inbound.get("id")
        settings_obj = parse_inbound_settings(inbound)
        if not settings_obj:
            continue

        protocol = inbound.get("protocol", "vless")
        matches = find_clients_for_tg_on_inbound(settings_obj, tg_id, iid)
        for client in matches:
            email = client.get("email")
            if not email:
                continue

            updated = dict(client)
            updated["expiryTime"] = new_expiry_ms
            updated["enable"] = True
            if updated.get("tgId") is None:
                updated["tgId"] = tg_id
            if protocol == "trojan" and "id" in updated:
                del updated["id"]
            elif protocol != "trojan" and "password" in updated:
                del updated["password"]

            upd = panel_update_client_by_email(session, email, updated, [iid])
            results.append({"inbound_id": iid, "email": email, "update_result": upd})

    successfully_updated = [r for r in results if r.get("update_result", {}).get("success")]
    return {
        "success": len(successfully_updated) > 0,
        "new_expiry": new_expiry_ms,
        "results": results,
    }


def renew_subscription(tg_id: int, additional_months: int):
    """
    Продлевает подписку на указанное количество месяцев.
    
    Алгоритм:
    1. Найти клиента и запомнить sub_id
    2. Удалить клиента на основной панели
    3. Отправить webhook на все удалённые серверы для удаления
    4. Пересоздать клиента с тем же sub_id и новой датой
    5. Отправить webhook на все удалённые серверы для создания
    """
    import time
    
    # 1. Получаем информацию о клиенте и sub_id
    client_info = getSubById(tg_id)
    if not client_info.get("success"):
        return {"error": "Client not found", "details": client_info}
    
    sub_id = client_info.get("subId")
    if not sub_id:
        return {"error": "subId not found for client"}
    
    print(f"[RENEW] Found client sub_id={sub_id} for tg_id={tg_id}")
    
    # 2. Вычисляем новую дату окончания
    current_expiry = client_info["client_info"]["expiryTime"]
    current_time = int(time.time() * 1000)
    
    # Если подписка истекла (expiryTime = 0 или в прошлом), продлеваем от текущего времени
    base_time = current_time if current_expiry == 0 or current_expiry < current_time else current_expiry
    additional_ms = additional_months * 30 * 24 * 60 * 60 * 1000
    new_expiry_ms = base_time + additional_ms
    
    # Конвертируем в дату
    import datetime
    new_expiry_date = datetime.datetime.fromtimestamp(new_expiry_ms / 1000)
    new_date_str = new_expiry_date.strftime("%d.%m.%Y")
    
    print(f"[RENEW] Old expiry: {current_expiry}, new expiry: {new_expiry_ms} ({new_date_str})")
    
    # 3. Удаляем клиента на основной панели
    print(f"[RENEW] Deleting client from main panel...")
    del_result = dell_client_from_all_inbounds(tg_id)
    print(f"[RENEW] Delete from main panel result: {del_result}")
    
    # 4. Удаляем клиента на всех удалённых серверах
    print("[RENEW] Sending delete webhook to remote servers...")
    dell_webhook_result = send_dell_client_webhook(tg_id, sub_id)
    print(f"[RENEW] Delete remotes: {dell_webhook_result}")
    
    # 5. Пересоздаём: сначала основной сервер, затем все удалённые
    print(f"[RENEW] Recreating client with same sub_id={sub_id}...")
    from api_extended import add_client_to_all_inbounds
    add_result = add_client_to_all_inbounds("", tg_id, new_date_str, sub_id=sub_id)
    print(f"[RENEW] Recreate result: {add_result}")

    renew_method = "recreate"
    final_result = add_result
    remote_success = add_result.get("remote_success")
    remote_error = add_result.get("remote_error")
    remote_results = add_result.get("remote_results") or []

    if not add_result.get("success"):
        print("[RENEW] Recreate failed, falling back to update expiry via new API...")
        update_result = _renew_by_updating_expiry(tg_id, new_expiry_ms)
        print(f"[RENEW] Update fallback result: {update_result}")
        if not update_result.get("success"):
            return {
                "success": False,
                "error": "Failed to recreate or update client",
                "details": {"deleted": del_result, "created": add_result, "updated": update_result},
                "subId": sub_id,
                "main_success": False,
                "remote_success": False,
                "remote_results": [],
            }
        renew_method = "update"
        final_result = update_result
        webhook_result = send_add_client_webhook(tg_id, sub_id, new_date_str)
        remote_success = bool(webhook_result.get("success"))
        remote_results = webhook_result.get("results") or []
        if not remote_success:
            remote_error = remote_error_text(webhook_result)
            notify_admin_remote_server_error(
                tg_id=tg_id,
                sub_id=sub_id,
                date=new_date_str,
                error=remote_error,
                context="продление подписки",
                remote_results=remote_results,
            )
        final_result = {**update_result, "webhook_result": webhook_result, "remote_results": remote_results}

    return {
        "success": True,
        "message": f"Subscription renewed for {additional_months} months ({renew_method})",
        "subId": sub_id,
        "old_expiry": current_expiry,
        "new_expiry": new_expiry_ms,
        "new_date": new_date_str,
        "method": renew_method,
        "main_success": True,
        "remote_success": remote_success,
        "remote_error": remote_error,
        "remote_results": remote_results,
        "results": {
            "deleted": del_result,
            "created": add_result if renew_method == "recreate" else None,
            "updated": final_result if renew_method == "update" else None,
        },
    }

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
    Создание подписки на всех inbound (inbound_id сохранён для совместимости).
    Делегирует в add_client_to_all_inbounds — 1 запрос на панель + webhook на все удалённые серверы.
    """
    from api_extended import add_client_to_all_inbounds
    return add_client_to_all_inbounds(username, tg_id, date)

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


