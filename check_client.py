"""Краткая сводка о клиенте по серверам для команды /check."""
import datetime
import html
import time

import api


def _fmt_date(ms):
    if not ms:
        return "без срока"
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%d.%m.%Y")


def _collect_panel(tg_id):
    """Клиенты tg_id на текущей панели: список {inbound, client}."""
    data = api.get_clients()
    if not data.get("success"):
        return None, str(data.get("error") or data.get("msg") or "не удалось получить inbounds")
    rows = []
    for inbound in data.get("obj", []):
        settings = api.parse_inbound_settings(inbound) or {}
        for c in settings.get("clients") or []:
            if str(c.get("tgId")) == str(tg_id) or str(c.get("email", "")).endswith(f"_{tg_id}"):
                rows.append({"inbound": inbound, "client": c})
    return rows, None


def _summary(title, rows, err):
    title = html.escape(str(title))
    if err:
        return f"❌ <b>{title}</b>: ошибка — {html.escape(err[:200])}"
    if not rows:
        return f"➖ <b>{title}</b>: клиента нет"

    now = int(time.time() * 1000)
    groups = {}
    for r in rows:
        c = r["client"]
        key = (c.get("subId"), c.get("expiryTime") or 0, bool(c.get("enable")))
        groups.setdefault(key, []).append(r["inbound"].get("id"))

    lines = []
    for (sub, exp, enabled), ids in groups.items():
        active = enabled and (exp == 0 or exp > now)
        left = f" ({(exp - now) // 86400000} дн.)" if exp and exp > now else ""
        lines.append(
            f"{'✅' if active else '⛔'} <b>{title}</b>: до {_fmt_date(exp)}{left} · "
            f"inbound {','.join(str(i) for i in sorted(ids))} · <code>{html.escape(str(sub))}</code>"
        )
    if len(groups) > 1:
        lines.append("   ⚠️ разные subId/сроки — возможны дубли")
    elif len(rows) > len(next(iter(groups.values()))):
        lines.append("   ⚠️ повторяющиеся записи на inbound — дубли")
    return "\n".join(lines)


def build_report(tg_id: int):
    """Возвращает список HTML-блоков."""
    lines = [f"🔎 <b>Клиент {tg_id}</b>"]
    rows, err = _collect_panel(tg_id)
    lines.append(_summary("Основной", rows, err))

    for server in api.active_remote_servers():
        label = api.server_title(server)
        try:
            with api.use_server(server):
                srows, serr = _collect_panel(tg_id)
        except Exception as e:
            srows, serr = None, str(e)
        lines.append(_summary(label, srows, serr))
    return ["\n".join(lines)]
