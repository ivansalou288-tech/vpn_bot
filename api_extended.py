# Extended API functions for VPN client management

from api import (
    get_clients,
    set_subscription_expiry_on_panel,
    find_clients_for_tg_on_inbound,
    parse_inbound_settings,
    panel_session,
    panel_del_client_by_email,
    create_subscription_on_panel,
    send_add_client_webhook,
    convert_date_to_timestamp,
    generate_sub_prefix,
    remote_error_text,
    notify_admin_remote_server_error,
)
import json


def add_client_to_all_inbounds(
    username: str,
    tg_id: int,
    date: str,
    sub_id: str = None,
    notify_remote: bool = True,
    notify_admin_remote_error: bool = True,
):
    """
    Создаёт подписку строго по порядку:
    1. основной сервер (локальная панель)
    2. удалённый сервер (webhook)

    success=True если создалось на основном. Ошибка удалённого не ломает ответ клиенту.
    """
    if sub_id:
        universal_sub_id = sub_id
        parts = sub_id.rsplit("_", 1)
        sub_prefix = parts[0] if len(parts) > 1 else sub_id
        print(f"[API] Using provided sub_id: {universal_sub_id} (prefix: {sub_prefix})")
    else:
        sub_prefix = username if username and username.strip() else generate_sub_prefix(8)
        universal_sub_id = f"{sub_prefix}_{tg_id}"
        print(f"[API] Generated new sub_id: {universal_sub_id} (prefix: {sub_prefix})")

    print(f"[API] Creating subscription on MAIN server first: tg_id={tg_id}, sub_id={universal_sub_id}")
    result = create_subscription_on_panel(tg_id, date, universal_sub_id, cleanup=False)
    if not result.get("success"):
        print(f"[API] MAIN server create failed: {result}")
        return {
            "success": False,
            "message": result.get("message") or result.get("error") or "Failed to add client to panel",
            "subId": universal_sub_id,
            "client_prefix": sub_prefix,
            **{k: v for k, v in result.items() if k not in ("success", "message", "subId")},
            "main_success": False,
            "remote_success": False,
            "remote_error": None,
        }

    webhook_result = None
    remote_success = None
    remote_err = None
    if notify_remote:
        print(f"[API] Creating subscription on REMOTE server: tg_id={tg_id}, sub_id={universal_sub_id}")
        webhook_result = send_add_client_webhook(tg_id, universal_sub_id, date)
        remote_success = bool(webhook_result.get("success"))
        if not remote_success:
            remote_err = remote_error_text(webhook_result)
            print(f"[API] REMOTE server create failed: {remote_err}")
            if notify_admin_remote_error:
                notify_admin_remote_server_error(
                    tg_id=tg_id,
                    sub_id=universal_sub_id,
                    date=date,
                    error=remote_err,
                    context="создание подписки",
                )

    return {
        "success": True,
        "message": result.get("message"),
        "subId": universal_sub_id,
        "client_prefix": sub_prefix,
        "inbound_ids": result.get("inbound_ids"),
        "panel_result": result.get("panel_result"),
        "webhook_result": webhook_result,
        "main_success": True,
        "remote_success": remote_success,
        "remote_error": remote_err,
    }


def renew_subscription_all_inbounds(tg_id: int, additional_months: int):
    """Удаляет старую подписку со всех серверов и создаёт новую с продлённым сроком."""
    from api import renew_subscription
    try:
        return renew_subscription(tg_id, additional_months)
    except Exception as e:
        return {"success": False, "error": str(e)}


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

    if not clients_data.get("success"):
        return {"error": "Failed to get clients", "details": clients_data}

    inbounds = clients_data.get("obj", [])

    for inbound in inbounds:
        if "settings" in inbound:
            settings = inbound["settings"]

            if isinstance(settings, str):
                try:
                    settings = json.loads(settings)
                except json.JSONDecodeError:
                    continue

            if "clients" in settings:
                clients = settings["clients"]

                for client in clients:
                    client_tgId = client.get("tgId")
                    if str(client_tgId) == str(telegram_id):
                        return {
                            "success": True,
                            "subId": client.get("subId"),
                            "client_info": {
                                "id": client.get("id"),
                                "email": client.get("email"),
                                "enable": client.get("enable"),
                                "expiryTime": client.get("expiryTime"),
                                "totalGB": client.get("totalGB"),
                            },
                            "inbound_id": inbound.get("id"),
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
            main_success = bool(result.get("success"))
            remote_success = None
            remote_err = None
            webhook_result = None
            if main_success and sub_id:
                print(f"[ADMIN] Updating REMOTE server after main: sub_id={sub_id}")
                webhook_result = send_add_client_webhook(tg_id, sub_id, calculated_end_date)
                remote_success = bool(webhook_result.get("success"))
                if not remote_success:
                    remote_err = remote_error_text(webhook_result)
            result = {
                **result,
                "webhook_result": webhook_result,
                "main_success": main_success,
                "remote_success": remote_success,
                "remote_error": remote_err,
            }
        else:
            print("[ADMIN] Creating new client on all inbounds")
            result = add_client_to_all_inbounds(
                "", tg_id, calculated_end_date, notify_admin_remote_error=False
            )
            sub_id = result.get("subId", "")
            display_user = result.get("client_prefix", "")
            action = "added"
            main_success = bool(result.get("main_success", result.get("success")))
            remote_success = result.get("remote_success")
            remote_err = result.get("remote_error")

        ok = bool(main_success)

        return {
            "success": ok,
            "message": f"Client {action} successfully" if ok else (result.get("error") or "Operation failed"),
            "tg_id": tg_id,
            "username": display_user,
            "subId": sub_id,
            "months": months,
            "end_date": calculated_end_date,
            "main_success": main_success,
            "remote_success": remote_success,
            "remote_error": remote_err,
            "result": result,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
