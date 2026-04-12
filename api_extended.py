# Extended API functions for VPN client management

from api import (
    add_client,
    get_clients,
    renew_subscription_on_panel,
    set_subscription_expiry_on_panel,
    find_clients_for_tg_on_inbound,
    parse_inbound_settings,
    panel_session,
    panel_del_client_by_email,
)
import json
import secrets


def add_client_to_all_inbounds(username: str, tg_id: int, date: str):
    """
    Один общий subId на всех 4 инбаундах: subId = {prefix}_{tg_id}.
    Разные email на каждом: {prefix}_{tg_id}_{inbound_id}.
    Префикс один раз на все вызовы (не случайный на каждый inbound).
    """
    sub_prefix = secrets.token_urlsafe(8)
    universal_sub_id = f"{sub_prefix}_{tg_id}"

    results = []
    all_ok = True
    for inbound_id in range(1, 5):
        print(f"[API] Adding client to inbound {inbound_id} subId={universal_sub_id}...")
        result = add_client(inbound_id, sub_prefix, tg_id, date)
        results.append({"inbound_id": inbound_id, "result": result})
        if result.get("success"):
            print(f"[API] Successfully added client to inbound {inbound_id}")
        else:
            all_ok = False
            print(f"[API] Failed to add client to inbound {inbound_id}: {result}")

    return {
        "success": all_ok,
        "message": "Client added to all inbounds",
        "subId": universal_sub_id,
        "client_prefix": sub_prefix,
        "results": results,
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
    """Админ: новый клиент на 4 инбаунда или выставить тот же срок существующему (не суммировать месяцы)."""
    from datetime import datetime
    import time

    try:
        months = int(months) if months is not None else 1

        if end_date:
            try:
                target_date = datetime.strptime(end_date, "%d.%m.%Y")
                new_expiry_ms = int(target_date.timestamp() * 1000)
                calculated_end_date = end_date
            except ValueError:
                return {"success": False, "error": f"Invalid date format: {end_date}. Use DD.MM.YYYY"}
        else:
            current_time_ms = int(time.time() * 1000)
            new_expiry_ms = current_time_ms + months * 30 * 24 * 60 * 60 * 1000
            calculated_end_date = datetime.fromtimestamp(new_expiry_ms / 1000).strftime("%d.%m.%Y")

        print(f"[ADMIN] TG ID: {tg_id}, end_date={calculated_end_date}, months={months}")

        existing_client = getSubById(tg_id)
        if existing_client.get("success"):
            print("[ADMIN] Client exists — выставляем абсолютную дату окончания (без +месяцев к остатку)")
            result = set_subscription_expiry_on_panel(tg_id, new_expiry_ms)
            sub_id = existing_client.get("subId") or ""
            display_user = f"user_{tg_id}"
            action = "updated"
        else:
            print("[ADMIN] Creating new client on all inbounds")
            result = add_client_to_all_inbounds("", tg_id, calculated_end_date)
            sub_id = result.get("subId", "")
            display_user = result.get("client_prefix", "")
            action = "added"

        ok = bool(result.get("success"))

        return {
            "success": ok,
            "message": f"Client {action} successfully" if ok else (result.get("error") or "Operation failed"),
            "tg_id": tg_id,
            "username": display_user,
            "subId": sub_id,
            "months": months,
            "end_date": calculated_end_date,
            "result": result,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
