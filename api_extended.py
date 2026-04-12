# Extended API functions for VPN client management

from api import (
    add_client,
    get_clients,
    renew_subscription_on_panel,
    find_clients_for_tg_on_inbound,
    parse_inbound_settings,
    panel_session,
    panel_del_client_by_email,
)
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
    """Продление на инбаундах 1–4: только новый expiryTime через updateClient/{id} (3x-ui)."""
    try:
        return renew_subscription_on_panel(tg_id, additional_months)
    except Exception as e:
        return {"error": str(e)}

def dell_client(inbound_id: int, tg_id: int):
    """Удаляет всех клиентов с данным tgId на указанном inbound (delClientByEmail)."""
    clients_data = get_clients()
    if not clients_data.get("success"):
        return {"error": "Failed to get clients"}

    target_inbound = None
    for inbound in clients_data.get("obj", []):
        if inbound.get("id") == inbound_id:
            target_inbound = inbound
            break
    if not target_inbound:
        return {"error": f"Inbound {inbound_id} not found"}

    settings_obj = parse_inbound_settings(target_inbound)
    if not settings_obj:
        return {"error": "Failed to parse settings"}

    matches = find_clients_for_tg_on_inbound(settings_obj, tg_id, inbound_id)
    if not matches:
        return {"success": True, "message": f"No client tgId={tg_id} on inbound {inbound_id}"}

    session, err = panel_session()
    if session is None:
        return {"error": err or "Login failed"}

    last = None
    for m in matches:
        em = m.get("email")
        if em:
            last = panel_del_client_by_email(session, inbound_id, em)
    return last or {"success": True, "message": f"Client deleted from inbound {inbound_id}"}

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
