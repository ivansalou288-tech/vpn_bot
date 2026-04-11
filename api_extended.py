# Extended API functions for VPN client management

from api import add_client, get_clients
import json

def add_client_to_all_inbounds(username: str, tg_id: int, date: str):
    """Adds client to all 4 inbound servers (1,2,3,4) with same subId"""
    # Generate same subId for all inbounds
    universal_subId = f"{username}_{tg_id}"
    
    results = []
    
    # Add client to each inbound
    for inbound_id in range(1, 5):  # 1, 2, 3, 4
        print(f"[API] Adding client to inbound {inbound_id}...")
        result = add_client(inbound_id, username, tg_id, date)
        results.append({
            "inbound_id": inbound_id,
            "result": result
        })
        
        if result.get('success'):
            print(f"[API] Successfully added client to inbound {inbound_id}")
        else:
            print(f"[API] Failed to add client to inbound {inbound_id}: {result}")
    
    return {
        "success": True,
        "message": "Client added to all inbounds",
        "subId": universal_subId,
        "results": results
    }

def renew_subscription_all_inbounds(tg_id: int, additional_months: int):
    """Renews subscription across all 4 inbound servers"""
    from datetime import datetime, timedelta
    import time
    
    try:
        # Get current client info
        client_info = getSubById(tg_id)
        
        if not client_info.get('success'):
            return {"error": "Client not found", "details": client_info}
        
        current_expiry = client_info['client_info']['expiryTime']
        current_time = int(time.time() * 1000)
        
        # If current time is expired, start from current time
        if current_expiry == 0:
            new_expiry = current_time
        else:
            new_expiry = current_expiry
        
        # Add specified months
        additional_time = additional_months * 30 * 24 * 60 * 60 * 1000  # Approximately months in milliseconds
        new_expiry += additional_time
        
        # Get username
        username = client_info['client_info']['email'].split('_')[0]
        new_date = datetime.fromtimestamp(new_expiry / 1000).strftime('%d.%m.%Y')
        
        results = []
        
        # Delete old client from all inbounds and create new one
        for inbound_id in range(1, 5):
            print(f"[API] Processing inbound {inbound_id}...")
            
            # Delete old client
            dell_result = dell_client(inbound_id, tg_id)
            
            # Create new client with updated time
            add_result = add_client(inbound_id, username, tg_id, new_date)
            
            results.append({
                "inbound_id": inbound_id,
                "delete_result": dell_result,
                "add_result": add_result
            })
                
        return {
            "success": True,
            "message": f"Subscription renewed for {additional_months} months across all inbounds",
            "old_expiry": current_expiry,
            "new_expiry": new_expiry,
            "results": results
        }
        
    except Exception as e:
        return {"error": str(e)}

def dell_client(inbound_id: int, tg_id: int):
    """Delete client from specific inbound"""
    from api import BASE_URL, admn_username, admn_pass
    import requests
    
    # Get current clients
    clients_data = get_clients()
    if not clients_data.get('success'):
        return {"error": "Failed to get clients"}
    
    # Find target inbound
    target_inbound = None
    for inbound in clients_data.get('obj', []):
        if inbound.get('id') == inbound_id:
            target_inbound = inbound
            break
    
    if not target_inbound:
        return {"error": f"Inbound {inbound_id} not found"}
    
    # Parse current settings
    current_settings = target_inbound.get('settings', '{}')
    if isinstance(current_settings, str):
        try:
            settings_obj = json.loads(current_settings)
        except json.JSONDecodeError:
            return {"error": "Failed to parse settings"}
    else:
        settings_obj = current_settings
    
    # Get current clients
    current_clients = settings_obj.get('clients', [])
    
    # Remove client with matching tgId
    updated_clients = [client for client in current_clients if str(client.get('tgId')) != str(tg_id)]
    
    # Create new settings
    new_settings = {
        "clients": updated_clients,
        "decryption": settings_obj.get('decryption', 'none'),
        "encryption": settings_obj.get('encryption', 'none')
    }
    
    # Update inbound
    admin_login = {
        "username": admn_username,
        "password": admn_pass
    }
    
    session = requests.Session()
    login_response = session.post(f"{BASE_URL}/login", json=admin_login, verify=False)
    
    if login_response.json().get('success'):
        settings_data = {
            "id": inbound_id,
            "settings": json.dumps(new_settings)
        }
        
        response = session.post(f"{BASE_URL}/panel/api/inbounds/updateClient", json=settings_data, verify=False)
        
        if response.status_code == 200:
            return {"success": True, "message": f"Client deleted from inbound {inbound_id}"}
        else:
            return {"error": f"HTTP {response.status_code}", "response": response.text}
    else:
        return {"error": "Login failed"}

def getSubById(telegram_id):
    """Get client info by Telegram ID across all inbounds"""
    clients_data = get_clients()
    
    if not clients_data.get('success'):
        return {"error": "Failed to get clients", "details": clients_data}
    
    inbounds = clients_data.get('obj', [])
    
    for inbound in inbounds:
        if 'settings' in inbound:
            settings = inbound['settings']
            
            if isinstance(settings, str):
                try:
                    settings = json.loads(settings)
                except json.JSONDecodeError:
                    continue
            
            if 'clients' in settings:
                clients = settings['clients']
                
                for client in clients:
                    client_tgId = client.get('tgId')
                    if str(client_tgId) == str(telegram_id):
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
                            "inbound_id": inbound.get('id')
                        }
    
    return {"error": f"No client found with tgId: {telegram_id}"}

def admin_add_client(tg_id: int, months: int = 1, end_date: str = None):
    """Админ функция: добавляет клиента по TG ID на все 4 подключения"""
    import random
    import string
    from datetime import datetime, timedelta
    import time
    
    try:
        # Генерируем случайный username (email)
        random_username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        
        # Генерируем уникальный subId для этого клиента
        import uuid
        unique_subId = f"admin_{uuid.uuid4().hex[:8]}"
        
        # Определяем дату окончания
        if end_date:
            # Используем переданную дату
            try:
                target_date = datetime.strptime(end_date, '%d.%m.%Y')
                new_expiry = int(target_date.timestamp() * 1000)
                calculated_end_date = end_date
            except ValueError:
                return {"error": f"Invalid date format: {end_date}. Use DD.MM.YYYY"}
        else:
            # Рассчитываем дату окончания по месяцам
            current_time = int(time.time() * 1000)
            additional_time = months * 30 * 24 * 60 * 60 * 1000  # месяцев в миллисекундах
            new_expiry = current_time + additional_time
            calculated_end_date = datetime.fromtimestamp(new_expiry / 1000).strftime('%d.%m.%Y')
        
        print(f"[ADMIN] Adding client for TG ID: {tg_id}")
        print(f"[ADMIN] Generated username: {random_username}")
        print(f"[ADMIN] Generated subId: {unique_subId}")
        print(f"[ADMIN] End date: {calculated_end_date}")
        
        # Проверяем, существует ли уже клиент
        existing_client = getSubById(tg_id)
        if existing_client.get('success'):
            print(f"[ADMIN] Client already exists, renewing...")
            # Клиент существует, продлеваем подписку
            result = renew_subscription_all_inbounds(tg_id, months)
        else:
            print(f"[ADMIN] Creating new client...")
            # Проверяем, есть ли клиенты с другими TG ID на этих inbound'ах
            # Если есть, используем тот же subId для консистентности
            clients_data = get_clients()
            if clients_data.get('success'):
                inbounds = clients_data.get('obj', [])
                for inbound in inbounds:
                    if 'settings' in inbound:
                        settings = inbound['settings']
                        if isinstance(settings, str):
                            try:
                                settings = json.loads(settings)
                            except json.JSONDecodeError:
                                continue
                        
                        if 'clients' in settings:
                            clients = settings['clients']
                            for client in clients:
                                client_tgId = client.get('tgId')
                                if str(client_tgId) == str(tg_id):
                                    # Нашли клиента с таким же TG ID, используем его subId
                                    existing_subId = client.get('subId')
                                    if existing_subId:
                                        unique_subId = existing_subId
                                        print(f"[ADMIN] Found existing client with same TG ID, using subId: {existing_subId}")
                                        break
            
            # Создаем нового клиента
            result = add_client_to_all_inbounds(random_username, tg_id, calculated_end_date)
        
        return {
            "success": True,
            "message": f"Client {'renewed' if existing_client.get('success') else 'added'} successfully",
            "tg_id": tg_id,
            "username": random_username,
            "subId": unique_subId,
            "months": months,
            "end_date": calculated_end_date,
            "result": result
        }
        
    except Exception as e:
        return {"error": str(e)}
