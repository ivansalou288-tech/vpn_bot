"""Админка бота. Текст принимается только после нажатия кнопки и не пишется в базу сам по себе."""

import html
import re

from aiogram import F, Router
from aiogram.filters import Command, Filter, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import runtime_settings as settings

router = Router(name="admin")


class AdminEdit(StatesGroup):
    info = State()
    contacts = State()
    add_price = State()
    edit_price = State()
    delete_price = State()
    add_client = State()
    broadcast = State()
    remove_cantfree = State()
    sub_link = State()
    index_link = State()
    index_domain = State()
    server_add_name = State()
    server_add_url = State()
    server_add_user = State()
    server_add_pass = State()
    server_creds = State()
    server_sub = State()
    proxy_add = State()
    server_label = State()
    server_panel = State()
    token_value = State()
    provision_domain = State()
    provision_host = State()
    provision_user = State()
    provision_password = State()
    provision_country = State()
    provision_confirm = State()


_INPUT_STATES = (
    AdminEdit.info,
    AdminEdit.contacts,
    AdminEdit.add_price,
    AdminEdit.edit_price,
    AdminEdit.delete_price,
    AdminEdit.add_client,
    AdminEdit.broadcast,
    AdminEdit.remove_cantfree,
    AdminEdit.sub_link,
    AdminEdit.index_link,
    AdminEdit.index_domain,
    AdminEdit.server_add_name,
    AdminEdit.server_add_url,
    AdminEdit.server_add_user,
    AdminEdit.server_add_pass,
    AdminEdit.server_creds,
    AdminEdit.server_sub,
    AdminEdit.proxy_add,
    AdminEdit.server_label,
    AdminEdit.server_panel,
    AdminEdit.token_value,
    AdminEdit.provision_domain,
    AdminEdit.provision_host,
    AdminEdit.provision_user,
    AdminEdit.provision_password,
    AdminEdit.provision_country,
    AdminEdit.provision_confirm,
)


class IsAdmin(Filter):
    async def __call__(self, event) -> bool:
        user = getattr(event, "from_user", None)
        if user is None:
            return False
        import main

        return main.is_admin(user.id)


class PlainText(Filter):
    async def __call__(self, message: Message) -> bool:
        return bool(message.text) and not message.text.startswith("/")


def _cb(pattern: str):
    compiled = re.compile(pattern)

    class _Match(Filter):
        async def __call__(self, callback: CallbackQuery) -> bool:
            return bool(callback.data and compiled.fullmatch(callback.data))

    return _Match()


router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def _kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _btn(text, data, style="primary"):
    return InlineKeyboardButton(text=text, callback_data=data, style=style)


admin_keyboard = _kb(
    [
        [_btn("Цены", "admin_prices"), _btn("Информация", "admin_info")],
        [_btn("Контакты", "admin_contacts"), _btn("Клиент", "admin_add_client")],
        [_btn("Рассылка", "admin_broadcast"), _btn("CantFree", "admin_remove_cantfree")],
        [_btn("Ссылка подписки", "admin_sub_link")],
        [_btn("Серверы", "admin_servers"), _btn("Прокси подписок", "admin_proxy")],
        [_btn("Токены", "admin_tokens")],
        [_btn("index.html на сайте", "admin_index_html")],
        [_btn("Merch", "admin_merch")],
        [_btn("Меню пользователя", "back_to_main", style="danger")],
    ]
)


def _back(data, label="Отмена"):
    return _kb([[_btn(label, data)]])


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def _html_of(message: Message) -> str:
    text = message.html_text or message.text or ""
    return text.replace("emoji_id=", "emoji-id=")


async def _show(callback: CallbackQuery, text: str, markup):
    await callback.answer()
    try:
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        return
    except Exception:
        pass
    try:
        await callback.message.answer(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await callback.message.answer("Не удалось показать текст с разметкой. Откройте раздел ещё раз.", reply_markup=markup)


async def _say(message: Message, text: str, markup=None):
    try:
        await message.answer(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await message.answer(html.escape(text), reply_markup=markup)


def _months_label(months: int) -> str:
    if months == 12:
        return "год"
    return f"{months} мес."


async def _prices_text():
    import main

    prices = await main.get_all_prices()
    lines = ["<b>Цены</b>", ""]
    if not prices:
        lines.append("Пока пусто.")
    for price in prices:
        lines.append(f"• {_months_label(price.time)}: {price.price}₽")
    lines.append("")
    lines.append("Добавление, изменение и удаление ждут отдельное сообщение и больше ничего не перехватывают.")
    return "\n".join(lines), _kb(
        [
            [_btn("Добавить", "add_price"), _btn("Изменить", "edit_price")],
            [_btn("Удалить", "delete_price")],
            [_btn("Назад", "admin_panel")],
        ]
    )


def _servers_view(data):
    lines = ["<b>Серверы для создания подписки</b>", ""]
    rows = []
    for index, server in enumerate(data["servers"]):
        mark = "★ " if server.get("is_primary") else ""
        role = "главный" if server.get("is_primary") else "дополнительный"
        state = "включён" if server.get("enabled", True) else "выключен"
        icon = "🟢" if server.get("enabled", True) else "⚪"
        lines.append(f"{icon} {mark}<b>{_esc(server.get('label') or server['name'])}</b> ({role}, {state})")
        lines.append(f"панель: <code>{_esc(server.get('panel_url') or '—')}</code>")
        lines.append("")
        rows.append([_btn(f"{icon} {mark}{server.get('label') or server['name']}"[:40], f"srv:{index}")])
    lines.append("Бот работает только на главном сервере. Подписка создаётся через API панели 3x-ui "
                 "на каждом включённом сервере, на всех его подключениях.")
    rows.append([_btn("Добавить сервер", "srv_add")])
    rows.append([_btn("Прокси подписок", "admin_proxy")])
    rows.append([_btn("Назад", "admin_panel")])
    return "\n".join(lines), _kb(rows)


def _server_card(data, index: int):
    server = data["servers"][index]
    role = "главный" if server.get("is_primary") else "дополнительный"
    password = "задан" if server.get("panel_password") else "—"
    if server.get("is_primary") and not server.get("panel_password"):
        password = "не нужен (API-токен)"
    text = (
        f"<b>{_esc(server.get('label') or server['name'])}</b>\n\n"
        f"Роль: {role}\n"
        f"Статус: {'включён' if server.get('enabled', True) else 'выключен'}\n"
        f"Имя: <code>{_esc(server['name'])}</code>\n"
        f"Панель: <code>{_esc(server.get('panel_url') or '—')}</code>\n"
        f"Логин: <code>{_esc(server.get('panel_user') or '—')}</code>\n"
        f"Пароль: {password}\n"
        f"Подписка в прокси: <code>{_esc(server.get('sub_url') or '—')}</code>"
    )
    rows = [
        [_btn("Проверить доступ", f"srv_chk:{index}"), _btn("Название", f"srv_lb:{index}")],
        [_btn("Ссылка панели", f"srv_pn:{index}"), _btn("Логин и пароль", f"srv_cr:{index}")],
        [_btn("Ссылка подписки", f"srv_sb:{index}")],
    ]
    if not server.get("is_primary"):
        toggle = "Выключить" if server.get("enabled", True) else "Включить"
        rows.append([_btn(toggle, f"srv_tg:{index}")])
        rows.append([_btn("Переименовать подключения", f"srv_rn:{index}")])
        rows.append([_btn("Скопировать клиентов с главного", f"srv_sync:{index}")])
        rows.append([_btn("Удалить", f"srv_rm:{index}", style="danger")])
    rows.append([_btn("К списку", "admin_servers")])
    return text, _kb(rows)


def _proxy_view():
    import sub_proxy

    urls, err = sub_proxy.list_urls()
    lines = ["<b>Прокси сбора подписок</b>", "", f"Папка: <code>{_esc(sub_proxy.proxy_dir())}</code>", ""]
    rows = []
    if err:
        lines.append(_esc(err))
    elif not urls:
        lines.append("Список пуст.")
    for index, url in enumerate(urls):
        tag = " (главный)" if sub_proxy.is_main_url(url) else ""
        lines.append(f"{index + 1}. <code>{_esc(url)}</code>{tag}")
        rows.append([_btn(f"Убрать {index + 1}", f"px_rm:{index}", style="danger")])
    lines.append("")
    lines.append("Пользователь получает подписку, собранную из всех этих ссылок.")
    rows.append([_btn("Добавить ссылку", "px_add")])
    rows.append([_btn("Оставить только главный", "px_main")])
    rows.append([_btn("Назад", "admin_servers")])
    return "\n".join(lines), _kb(rows)


def _tokens_view():
    lines = ["<b>Токены</b>", "", "Показаны только края. Новое значение пришлите следующим сообщением.", ""]
    rows = []
    for key, label in settings.TOKEN_LABELS.items():
        lines.append(f"{_esc(label)}: <code>{_esc(settings.mask_token(settings.effective_token(key)))}</code>")
        rows.append([_btn(label, f"tok:{key}"), _btn("Сброс", f"tok_reset:{key}")])
    lines.append("")
    lines.append("Пустое сохранённое значение возвращает токен из кода. Новый токен бота подхватывается после перезапуска процесса.")
    rows.append([_btn("Назад", "admin_panel")])
    return "\n".join(lines), _kb(rows)


def _sub_view():
    data = settings.get()
    base = data["subscription_base"]
    domain = data["web_domain"]
    ok, found = settings.read_index_subscription_base(domain)
    file_line = f"<code>{_esc(found)}</code>" if ok else _esc(found)
    text = (
        "<b>Ссылка подписки</b>\n\n"
        f"Бот выдаёт: <code>{_esc(base)}/ID</code>\n"
        f"Happ: <code>{_esc(settings.happ_link('ID'))}</code>\n\n"
        f"Файл <code>{_esc(settings.active_index_path(domain))}</code>:\n{file_line}"
    )
    markup = _kb(
        [
            [_btn("Изменить ссылку бота", "admin_sub_edit")],
            [_btn("Записать её в index.html", "admin_sub_to_index")],
            [_btn("Назад", "admin_panel")],
        ]
    )
    return text, markup


def _index_view():
    data = settings.get()
    domain = data["web_domain"]
    path = settings.active_index_path(domain)
    ok, found = settings.read_index_subscription_base(domain)
    file_line = f"<code>{_esc(found)}</code>" if ok else _esc(found)
    text = (
        "<b>index.html на основном сервере</b>\n\n"
        f"Путь: <code>{_esc(path)}</code>\n"
        f"Домен и папка: <code>{_esc(domain)}</code>\n"
        f"Ссылка в файле: {file_line}\n\n"
        "Меняется только адрес внутри файла на сервере, не копия в проекте."
    )
    markup = _kb(
        [
            [_btn("Изменить ссылку в файле", "admin_index_edit")],
            [_btn("Изменить домен папки", "admin_index_domain")],
            [_btn("Назад", "admin_panel")],
        ]
    )
    return text, markup


async def _open_admin(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await _show(callback, "<b>Админ панель</b>\n\nВыберите раздел. Текст бот примет только после кнопки редактирования.", admin_keyboard)


@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: CallbackQuery, state: FSMContext):
    await _open_admin(callback, state)


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    import main

    rows = list(main.keyboard.inline_keyboard) + [[main.admin_btn]]
    await callback.message.answer(
        "Меню, которое видит пользователь.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data == "admin_prices")
async def admin_prices_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text, markup = await _prices_text()
    await _show(callback, text, markup)


@router.callback_query(F.data == "admin_info")
async def admin_info_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    import main

    info_text = await main.get_info()
    await _show(
        callback,
        f"<b>Информация</b>\n\n{info_text}",
        _kb([[_btn("Изменить", "edit_info")], [_btn("Назад", "admin_panel")]]),
    )


@router.callback_query(F.data == "admin_contacts")
async def admin_contacts_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    import main

    contact_text = await main.get_contact()
    await _show(
        callback,
        f"<b>Контакты</b>\n\n{contact_text}",
        _kb([[_btn("Изменить", "edit_contacts")], [_btn("Назад", "admin_panel")]]),
    )


@router.callback_query(F.data == "edit_info")
async def edit_info_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminEdit.info)
    await _show(
        callback,
        "<b>Новая информация</b>\n\nПришлите одно сообщение. Форматирование и эмодзи сохранятся. Другие сообщения бот не трогает, пока открыт этот шаг.",
        _back("admin_info"),
    )


@router.callback_query(F.data == "edit_contacts")
async def edit_contacts_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminEdit.contacts)
    await _show(
        callback,
        "<b>Новые контакты</b>\n\nПришлите одно сообщение.",
        _back("admin_contacts"),
    )


@router.callback_query(F.data == "add_price")
async def add_price_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminEdit.add_price)
    await _show(
        callback,
        "<b>Новая цена</b>\n\nОдним сообщением: <code>месяцы цена</code>\nПример: <code>3 500</code>",
        _back("admin_prices"),
    )


@router.callback_query(F.data == "edit_price")
async def edit_price_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminEdit.edit_price)
    await _show(
        callback,
        "<b>Изменить цену</b>\n\nОдним сообщением: <code>месяцы новая_цена</code>\nПример: <code>3 600</code>",
        _back("admin_prices"),
    )


@router.callback_query(F.data == "delete_price")
async def delete_price_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminEdit.delete_price)
    await _show(
        callback,
        "<b>Удалить цену</b>\n\nПришлите число месяцев, например <code>3</code>",
        _back("admin_prices"),
    )


@router.callback_query(F.data == "admin_add_client")
async def admin_add_client_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminEdit.add_client)
    await _show(
        callback,
        "<b>Клиент</b>\n\n"
        "<code>TG_ID</code> — на 1 месяц\n"
        "<code>TG_ID 3</code> — на 3 месяца\n"
        "<code>TG_ID 31.12.2026</code> — до даты\n\n"
        "Команда <code>/add_client</code> по-прежнему работает.",
        _back("admin_panel"),
    )


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminEdit.broadcast)
    await _show(
        callback,
        "<b>Рассылка</b>\n\nПришлите текст. Сначала покажу, как он выглядит, и только потом отправлю по кнопке.\n\nКоманда <code>/notify</code> тоже работает.",
        _back("admin_panel"),
    )


@router.callback_query(F.data == "broadcast_go")
async def broadcast_go(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("pending_broadcast") or ""
    await state.clear()
    if not text:
        await _show(callback, "Текст рассылки потерялся. Начните заново.", _back("admin_broadcast", "К рассылке"))
        return
    await callback.answer("Отправляю")
    import main

    result = await main.broadcast_to_all_users(text)
    await callback.message.answer(
        f"Рассылка завершена: {result['success']} успешно, {result['errors']} ошибок",
        reply_markup=_back("admin_panel", "В админку"),
    )


@router.callback_query(F.data == "admin_remove_cantfree")
async def admin_remove_cantfree_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminEdit.remove_cantfree)
    await _show(
        callback,
        "<b>Удалить из CantFree</b>\n\nПришлите Telegram ID одним сообщением.\nКоманда <code>/remove_cantfree</code> тоже работает.",
        _back("admin_panel"),
    )


@router.callback_query(F.data == "admin_sub_link")
async def admin_sub_link_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text, markup = _sub_view()
    await _show(callback, text, markup)


@router.callback_query(F.data == "admin_sub_edit")
async def admin_sub_edit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminEdit.sub_link)
    await _show(
        callback,
        "<b>Новая ссылка подписки</b>\n\n"
        "Пришлите адрес без ID клиента.\n"
        "Пример: <code>https://panel.ezhqpy.ru:4567/sub</code>\n\n"
        "Если вставите полную ссылку с ID, хвост после /sub/ будет отброшен. "
        "Та же ссылка запишется в index.html на сервере.",
        _back("admin_sub_link"),
    )


@router.callback_query(F.data == "admin_sub_to_index")
async def admin_sub_to_index(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    data = settings.get()
    ok, detail = settings.write_index_subscription_base(data["web_domain"], data["subscription_base"])
    prefix = "Записано." if ok else "Не записано."
    text, markup = _sub_view()
    await _show(callback, f"{prefix}\n{_esc(detail)}\n\n{text}", markup)


@router.callback_query(F.data == "admin_servers")
async def admin_servers_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text, markup = _servers_view(settings.get())
    await _show(callback, text, markup)


@router.callback_query(F.data == "srv_add")
async def srv_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminEdit.server_add_name)
    await state.update_data(draft={})
    await _show(
        callback,
        "<b>Новый сервер</b>\n\nШаг 1 из 4. Название сервера, например <code>Нидерланды</code> или <code>ezh-dev</code>",
        _back("admin_servers"),
    )


@router.callback_query(F.data == "srv_provision")
async def srv_provision(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminEdit.provision_domain)
    await state.update_data(provision={})
    await _show(
        callback,
        "<b>Новый сервер</b>\n\n"
        "Шаг 1 из 5. Домен, который уже смотрит A-записью на этот сервер.\n"
        "Пример: <code>panel.example.ru</code>\n\n"
        "Запись создаётся в reg.ru до запуска.",
        _back("admin_servers"),
    )


@router.callback_query(F.data == "provision_go")
async def provision_go(callback: CallbackQuery, state: FSMContext):
    import asyncio

    import provision_server

    draft = dict((await state.get_data()).get("provision") or {})
    await state.clear()
    if not draft.get("domain") or not draft.get("host") or not draft.get("password"):
        await _show(callback, "Шаги сбились. Откройте «Поднять сервер» ещё раз.", _back("admin_servers", "К серверам"))
        return
    await callback.answer()
    status = await callback.message.answer("Начинаю установку. Обычно это 5–15 минут.")
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()

    def progress(text):
        loop.call_soon_threadsafe(queue.put_nowait, str(text))

    task = asyncio.create_task(
        asyncio.to_thread(
            provision_server.provision,
            draft["domain"],
            draft["host"],
            draft["user"],
            draft["password"],
            draft["country"],
            progress,
            False,
        )
    )
    last = ""
    while not task.done() or not queue.empty():
        try:
            line = await asyncio.wait_for(queue.get(), timeout=2)
        except asyncio.TimeoutError:
            continue
        if line == last:
            continue
        last = line
        try:
            await status.edit_text(_esc(line[:3500]))
        except Exception:
            pass
    try:
        result = task.result()
    except Exception as exc:
        await callback.message.answer(
            f"Сервер не поднялся.\n{_esc(exc)}\n\nЕсли установка оборвалась на середине, запустите её ещё раз с теми же данными.",
            parse_mode="HTML",
            reply_markup=_back("admin_servers", "К серверам"),
        )
        return

    name = result["slug"]
    taken = {item["name"] for item in settings.get()["servers"]}
    index = 2
    while name in taken:
        name = f"{result['slug']}-{index}"
        index += 1

    def mutate(data):
        data["servers"].append(
            {
                "name": name,
                "label": f"{result['flag']} {result['country']}",
                "panel_url": result["panel_url"],
                "panel_user": result["panel_user"],
                "panel_password": result["panel_password"],
                "webhook_url": result["webhook_url"],
                "is_primary": False,
            }
        )

    settings.update(mutate)
    panel_note = (
        "<b>Данные панели</b>\n\n"
        f"Сервер: {_esc(result['flag'])} {_esc(result['country'])}\n"
        f"Адрес: <code>{_esc(result['panel_url'])}</code>\n"
        f"Логин: <code>{_esc(result['panel_user'])}</code>\n"
        f"Пароль: <code>{_esc(result['panel_password'])}</code>"
    )
    import main
    try:
        await main.bot.send_message(main.OPERATOR_CHAT_ID, panel_note, parse_mode="HTML")
    except Exception as exc:
        panel_note += f"\n\nНе отправилось отдельным сообщением: {_esc(exc)}"
    warnings = "\n".join(f"• {_esc(item)}" for item in result.get("warnings") or [])
    warning_block = f"\n\nЗамечания:\n{warnings}" if warnings else ""
    await callback.message.answer(
        "<b>Сервер запущен</b>\n\n"
        f"Страна: {_esc(result['flag'])} {_esc(result['country'])}\n"
        f"Домен: <code>{_esc(result['domain'])}</code>\n"
        f"Панель: <code>{_esc(result['panel_url'])}</code>\n"
        f"Логин: <code>{_esc(result['panel_user'])}</code>\n"
        f"Пароль: <code>{_esc(result['panel_password'])}</code>\n"
        f"Webhook: <code>{_esc(result['webhook_url'])}</code>\n"
        f"Подключений: {result['inbounds']}\n"
        f"Клиентов с основного: {result['clients_added']} из {result['clients_total']}"
        f"{warning_block}",
        parse_mode="HTML",
        reply_markup=_back("admin_servers", "К серверам"),
    )


@router.callback_query(_cb(r"^srv:\d+$"))
async def srv_open(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    index = int(callback.data.split(":")[1])
    data = settings.get()
    if index < 0 or index >= len(data["servers"]):
        text, markup = _servers_view(data)
        await _show(callback, text, markup)
        return
    text, markup = _server_card(data, index)
    await _show(callback, text, markup)


@router.callback_query(_cb(r"^srv_lb:\d+$"))
async def srv_label(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.split(":")[1])
    await state.set_state(AdminEdit.server_label)
    await state.update_data(server_index=index)
    await _show(callback, "<b>Название сервера</b>\n\nПришлите подпись, как её показывать в списке.", _back(f"srv:{index}"))


@router.callback_query(_cb(r"^srv_pn:\d+$"))
async def srv_panel(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.split(":")[1])
    await state.set_state(AdminEdit.server_panel)
    await state.update_data(server_index=index, promote=False)
    await _show(
        callback,
        "<b>URL панели 3x-ui</b>\n\nПример: <code>https://panel.example.ru:17468/секретный_путь</code>",
        _back(f"srv:{index}"),
    )


def _server_index(callback, data):
    index = int(callback.data.split(":")[1])
    if index < 0 or index >= len(data["servers"]):
        return None
    return index


@router.callback_query(_cb(r"^srv_cr:\d+$"))
async def srv_creds(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.split(":")[1])
    await state.set_state(AdminEdit.server_creds)
    await state.update_data(server_index=index)
    await _show(
        callback,
        "<b>Логин и пароль панели</b>\n\nПришлите двумя строками:\n<code>логин\nпароль</code>",
        _back(f"srv:{index}"),
    )


@router.callback_query(_cb(r"^srv_sb:\d+$"))
async def srv_sub(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.split(":")[1])
    await state.set_state(AdminEdit.server_sub)
    await state.update_data(server_index=index)
    await _show(
        callback,
        "<b>Ссылка подписки сервера</b>\n\nТа, что стоит в прокси подписок. Пример: <code>https://домен:2096/sub/</code>",
        _back(f"srv:{index}"),
    )


@router.callback_query(_cb(r"^srv_chk:\d+$"))
async def srv_check(callback: CallbackQuery, state: FSMContext):
    import asyncio

    import api

    await state.clear()
    data = settings.get()
    index = _server_index(callback, data)
    if index is None:
        await _show(callback, "Сервера уже нет в списке.", _back("admin_servers", "К серверам"))
        return
    server = data["servers"][index]
    await callback.answer("Проверяю")
    if server.get("is_primary") and not server.get("panel_password"):
        def probe():
            with api.use_server(None):
                result = api.get_clients()
            return bool(result.get("success")), None if result.get("success") else str(result.get("error") or result)[:300]
        ok, err = await asyncio.to_thread(probe)
    else:
        ok, err = await asyncio.to_thread(api.server_login_check, server)
    note = "✅ Панель отвечает, вход выполнен." if ok else f"❌ Нет доступа: {_esc(err)}"
    text, markup = _server_card(settings.get(), index)
    await _show(callback, f"{note}\n\n{text}", markup)


@router.callback_query(_cb(r"^srv_tg:\d+$"))
async def srv_toggle(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    index = int(callback.data.split(":")[1])

    def mutate(data):
        server = _server_or_none(data, index)
        if server is not None and not server.get("is_primary"):
            server["enabled"] = not server.get("enabled", True)

    settings.update(mutate)
    text, markup = _server_card(settings.get(), index)
    await _show(callback, text, markup)


@router.callback_query(_cb(r"^srv_sync:\d+$"))
async def srv_sync(callback: CallbackQuery, state: FSMContext):
    import asyncio

    import api

    await state.clear()
    data = settings.get()
    index = _server_index(callback, data)
    if index is None or data["servers"][index].get("is_primary"):
        await _show(callback, "Сервер не найден.", _back("admin_servers", "К серверам"))
        return
    server = data["servers"][index]
    await callback.answer("Копирую, это может занять несколько минут")
    result = await asyncio.to_thread(api.sync_clients_to_server, server)
    note = f"Скопировано клиентов: {result['added']} из {result['total']} (уже были на сервере: {result.get('skipped', 0)})."
    if result.get("error"):
        note += f"\nПервая ошибка: {_esc(result['error'])}"
    text, markup = _server_card(settings.get(), index)
    await _show(callback, f"{note}\n\n{text}", markup)


@router.callback_query(_cb(r"^srv_rn:\d+$"))
async def srv_rename(callback: CallbackQuery, state: FSMContext):
    import asyncio

    import api

    await state.clear()
    data = settings.get()
    index = _server_index(callback, data)
    if index is None or data["servers"][index].get("is_primary"):
        await _show(callback, "Сервер не найден.", _back("admin_servers", "К серверам"))
        return
    await callback.answer("Переименовываю")
    result = await asyncio.to_thread(api.rename_server_inbounds, data["servers"][index])
    note = f"Переименовано подключений: {len(result['changed'])}."
    if result["errors"]:
        note += "\nОшибки: " + "; ".join(_esc(e) for e in result["errors"][:3])
    text, markup = _server_card(settings.get(), index)
    await _show(callback, f"{note}\n\n{text}", markup)


@router.callback_query(F.data == "admin_proxy")
async def admin_proxy(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text, markup = _proxy_view()
    await _show(callback, text, markup)


@router.callback_query(F.data == "px_add")
async def px_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminEdit.proxy_add)
    await _show(
        callback,
        "<b>Добавить ссылку в прокси</b>\n\nПришлите адрес подписки сервера, например <code>https://домен:2096/sub/</code>",
        _back("admin_proxy"),
    )


@router.callback_query(_cb(r"^px_rm:\d+$"))
async def px_remove(callback: CallbackQuery, state: FSMContext):
    import asyncio

    import sub_proxy

    await state.clear()
    index = int(callback.data.split(":")[1])
    urls, err = sub_proxy.list_urls()
    if err or index >= len(urls):
        text, markup = _proxy_view()
        await _show(callback, _esc(err or "Ссылки уже нет."), markup)
        return
    await callback.answer("Применяю")
    ok, msg = await asyncio.to_thread(sub_proxy.remove_url, urls[index])
    text, markup = _proxy_view()
    await _show(callback, f"{'✅' if ok else '❌'} {_esc(msg)}\n\n{text}", markup)


@router.callback_query(F.data == "px_main")
async def px_main(callback: CallbackQuery, state: FSMContext):
    import asyncio

    import sub_proxy

    await state.clear()
    await callback.answer("Применяю")
    ok, msg = await asyncio.to_thread(sub_proxy.keep_only_main)
    text, markup = _proxy_view()
    await _show(callback, f"{'✅' if ok else '❌'} {_esc(msg)}\n\n{text}", markup)


@router.callback_query(_cb(r"^srv_rm:\d+$"))
async def srv_remove_ask(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    index = int(callback.data.split(":")[1])
    data = settings.get()
    if index < 0 or index >= len(data["servers"]):
        text, markup = _servers_view(data)
        await _show(callback, text, markup)
        return
    server = data["servers"][index]
    if server.get("is_primary"):
        await _show(callback, "Сначала назначьте другой основной сервер.", _back("admin_servers", "К серверам"))
        return
    await _show(
        callback,
        f"Удалить <b>{_esc(server.get('label') or server['name'])}</b>?",
        _kb(
            [
                [_btn("Удалить", f"srv_rm_ok:{index}", style="danger")],
                [_btn("Отмена", f"srv:{index}")],
            ]
        ),
    )


@router.callback_query(_cb(r"^srv_rm_ok:\d+$"))
async def srv_remove_ok(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    index = int(callback.data.split(":")[1])

    import asyncio

    import sub_proxy

    removed_sub = []

    def mutate(data):
        if 0 <= index < len(data["servers"]) and not data["servers"][index].get("is_primary"):
            removed_sub.append(data["servers"][index].get("sub_url") or "")
            del data["servers"][index]

    settings.update(mutate)
    note = ""
    if removed_sub and removed_sub[0]:
        ok, msg = await asyncio.to_thread(sub_proxy.remove_url, removed_sub[0])
        note = f"Прокси подписок: {_esc(msg)}\n\n"
    text, markup = _servers_view(settings.get())
    await _show(callback, note + text, markup)


@router.callback_query(F.data == "admin_tokens")
async def admin_tokens_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text, markup = _tokens_view()
    await _show(callback, text, markup)


@router.callback_query(_cb(r"^tok:[a-z_]+$"))
async def token_edit(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    if key not in settings.TOKEN_LABELS:
        await callback.answer("Неизвестный токен")
        return
    await state.set_state(AdminEdit.token_value)
    await state.update_data(token_key=key)
    await _show(
        callback,
        f"<b>{_esc(settings.TOKEN_LABELS[key])}</b>\n\nПришлите новый токен одним сообщением. В чат целиком он больше не попадёт.",
        _back("admin_tokens"),
    )


@router.callback_query(_cb(r"^tok_reset:[a-z_]+$"))
async def token_reset(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    key = callback.data.split(":", 1)[1]
    if key not in settings.TOKEN_LABELS:
        await callback.answer("Неизвестный токен")
        return

    def mutate(data):
        data["tokens"][key] = ""

    settings.update(mutate)
    text, markup = _tokens_view()
    await _show(callback, f"Для «{_esc(settings.TOKEN_LABELS[key])}» снова используется токен из кода.\n\n{text}", markup)


@router.callback_query(F.data == "admin_index_html")
async def admin_index_html(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text, markup = _index_view()
    await _show(callback, text, markup)


@router.callback_query(F.data == "admin_index_edit")
async def admin_index_edit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminEdit.index_link)
    await _show(
        callback,
        "<b>Ссылка в index.html</b>\n\n"
        "Пришлите адрес подписки без ID. Он заменит https://…/sub/ в файле\n"
        f"<code>{_esc(settings.active_index_path(settings.get()['web_domain']))}</code>\n\n"
        "Ссылка, которую бот копирует клиенту, при этом не меняется.",
        _back("admin_index_html"),
    )


@router.callback_query(F.data == "admin_index_domain")
async def admin_index_domain(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminEdit.index_domain)
    await _show(
        callback,
        "<b>Домен сайта</b>\n\n"
        "Это имя папки в /var/www и хост кнопки Happ.\n"
        "Пример: <code>panel.ezhqpy.ru</code>",
        _back("admin_index_html"),
    )


@router.callback_query(F.data == "admin_merch")
async def admin_merch(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    import main
    from merch_tracking import get_merch_stats

    stats = get_merch_stats()
    bot_username = (await main.bot.get_me()).username
    merch_link = f"https://t.me/{bot_username}?start=merch"
    await callback.message.answer(
        f"<b>Merch</b>\n\n"
        f"Ссылка:\n<code>{_esc(merch_link)}</code>\n\n"
        f"Перешло: <b>{stats['visits']}</b>\n"
        f"Купило: <b>{stats['buyers']}</b>\n"
        f"Покупок: <b>{stats['purchases']}</b>\n"
        f"Сумма: <b>{stats['total_revenue']:.0f}₽</b>",
        reply_markup=_back("admin_panel", "В админку"),
        parse_mode="HTML",
    )


def _parse_price(text: str):
    parts = text.replace("₽", "").replace(",", " ").split()
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        raise ValueError("Нужны два числа: месяцы и цена. Пример: 3 500")
    months = int(parts[0])
    price = int(parts[1])
    if months < 1 or months > 36:
        raise ValueError("Месяцы: число от 1 до 36")
    if price < 1:
        raise ValueError("Цена должна быть больше нуля")
    return months, price


def _parse_client(text: str):
    parts = text.split()
    if not parts or not parts[0].isdigit():
        raise ValueError("Первым нужен Telegram ID")
    tg_id = int(parts[0])
    months = 1
    end_date = None
    if len(parts) >= 2:
        param = parts[1]
        if "." in param:
            chunks = param.split(".")
            if len(chunks) != 3:
                raise ValueError("Дата в формате ДД.ММ.ГГГГ")
            day, month, year = chunks
            if len(day) == 1:
                day = "0" + day
            if len(month) == 1:
                month = "0" + month
            if len(year) == 2:
                year = "20" + year
            import datetime

            datetime.datetime.strptime(f"{day}.{month}.{year}", "%d.%m.%Y")
            end_date = f"{day}.{month}.{year}"
        else:
            if not param.isdigit():
                raise ValueError("Вторым аргументом укажите месяцы или дату ДД.ММ.ГГГГ")
            months = int(param)
            if months < 1 or months > 36:
                raise ValueError("Месяцы: число от 1 до 36")
    if len(parts) > 2:
        raise ValueError("Лишние слова. Формат: TG_ID, TG_ID 3 или TG_ID 31.12.2026")
    return tg_id, months, end_date


def _server_or_none(data, index):
    if index is None or index < 0 or index >= len(data["servers"]):
        return None
    return data["servers"][index]


async def _finish_servers(message: Message, state: FSMContext, note: str):
    await state.clear()
    text, markup = _servers_view(settings.get())
    await _say(message, f"{note}\n\n{text}", markup)


@router.message(StateFilter(*_INPUT_STATES), PlainText())
async def admin_text(message: Message, state: FSMContext):
    current = await state.get_state()
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пустое сообщение не записываю. Пришлите текст или нажмите «Отмена».")
        return
    import main

    try:
        if current == AdminEdit.info.state:
            clean = _html_of(message)
            await main.create_or_update_info(clean)
            await state.clear()
            await message.answer("Информация сохранена.")
            try:
                await message.answer(clean, parse_mode="HTML")
            except Exception:
                await message.answer("Текст записан. Telegram не показал разметку: проверьте теги и пришлите ещё раз через «Изменить».")
            return

        if current == AdminEdit.contacts.state:
            clean = _html_of(message)
            await main.create_or_update_contact(clean)
            await state.clear()
            await message.answer("Контакты сохранены.")
            try:
                await message.answer(clean, parse_mode="HTML")
            except Exception:
                await message.answer("Текст записан. Telegram не показал разметку: проверьте теги и пришлите ещё раз через «Изменить».")
            return

        if current == AdminEdit.add_price.state:
            months, price = _parse_price(text)
            await main.set_price(months, price)
            await state.clear()
            await _say(message, f"Цена записана: {_months_label(months)} — {price}₽", _back("admin_prices", "К ценам"))
            return

        if current == AdminEdit.edit_price.state:
            months, price = _parse_price(text)
            existing = await main.get_price(months)
            if existing is None:
                await _say(message, f"Цены на {months} мес. ещё нет. Пришлите другую пару или откройте «Добавить».")
                return
            await main.set_price(months, price)
            await state.clear()
            await _say(message, f"Цена обновлена: {_months_label(months)} — {price}₽", _back("admin_prices", "К ценам"))
            return

        if current == AdminEdit.delete_price.state:
            if not text.isdigit():
                raise ValueError("Пришлите только число месяцев, например 3")
            months = int(text)
            removed = await main.delete_price(months)
            if not removed:
                await _say(message, f"Цены на {months} мес. нет. Пришлите другое число или нажмите «Отмена».")
                return
            await state.clear()
            await _say(message, f"Цена на {months} мес. удалена.", _back("admin_prices", "К ценам"))
            return

        if current == AdminEdit.add_client.state:
            tg_id, months, end_date = _parse_client(text)
            await state.clear()
            status = await message.answer(f"Добавляю клиента TG ID: {tg_id}…")
            await main.execute_add_client(status, tg_id, months, end_date)
            return

        if current == AdminEdit.broadcast.state:
            clean = _html_of(message)
            try:
                await message.answer(clean, parse_mode="HTML")
            except Exception:
                await _say(message, "Telegram не принял разметку. Исправьте текст и пришлите ещё раз. Шаг не сброшен.")
                return
            await state.update_data(pending_broadcast=clean)
            await message.answer(
                "Выше сообщение так, как его увидят пользователи. Отправить всем?",
                reply_markup=_kb(
                    [
                        [_btn("Отправить", "broadcast_go")],
                        [_btn("Отмена", "admin_panel", style="danger")],
                    ]
                ),
            )
            return

        if current == AdminEdit.remove_cantfree.state:
            if not text.isdigit():
                raise ValueError("Нужен Telegram ID из цифр")
            tg_id = int(text)
            result = await main.remove_from_cantfree_local(tg_id)
            await state.clear()
            if result.get("success"):
                await _say(message, f"Пользователь <code>{tg_id}</code> удалён из CantFree.", _back("admin_panel", "В админку"))
            else:
                detail = result.get("message") or result.get("error") or "неизвестная ошибка"
                await _say(message, f"Не удалился <code>{tg_id}</code>: {_esc(detail)}", _back("admin_panel", "В админку"))
            return

        if current == AdminEdit.sub_link.state:
            base = settings.normalize_subscription_base(text)

            def mutate(data):
                data["subscription_base"] = base

            saved = settings.update(mutate)
            ok, detail = settings.write_index_subscription_base(saved["web_domain"], base)
            await state.clear()
            file_note = "index.html обновлён." if ok else f"index.html не изменён: {_esc(detail)}"
            await _say(
                message,
                f"Ссылка бота: <code>{_esc(base)}/ID</code>\n{file_note}",
                _back("admin_sub_link", "К ссылке"),
            )
            return

        if current == AdminEdit.index_link.state:
            data = settings.get()
            ok, detail = settings.write_index_subscription_base(data["web_domain"], text)
            if not ok:
                await _say(message, f"{_esc(detail)}\nШаг не сброшен, можно прислать другую ссылку.")
                return
            await state.clear()
            await _say(message, _esc(detail), _back("admin_index_html", "К index.html"))
            return

        if current == AdminEdit.index_domain.state:
            folder = settings.clean_web_folder(text)

            def mutate(data):
                data["web_domain"] = folder

            settings.update(mutate)
            await state.clear()
            await _say(
                message,
                f"Домен: <code>{_esc(folder)}</code>\nФайл: <code>{_esc(settings.active_index_path(folder))}</code>",
                _back("admin_index_html", "К index.html"),
            )
            return

        if current == AdminEdit.provision_domain.state:
            domain = text.lower().rstrip(".")
            if not re.fullmatch(r"[a-z0-9.-]{1,253}", domain) or "." not in domain:
                raise ValueError("Нужен домен, например panel.example.ru")
            await state.update_data(provision={"domain": domain})
            await state.set_state(AdminEdit.provision_host)
            await _say(message, "Шаг 2 из 5. IP сервера, например <code>203.0.113.10</code>", _back("admin_servers"))
            return

        if current == AdminEdit.provision_host.state:
            if not re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", text):
                raise ValueError("Нужен IPv4, четыре числа через точку")
            draft = dict((await state.get_data()).get("provision") or {})
            draft["host"] = text
            await state.update_data(provision=draft)
            await state.set_state(AdminEdit.provision_user)
            await _say(message, "Шаг 3 из 5. Логин SSH, обычно <code>root</code>", _back("admin_servers"))
            return

        if current == AdminEdit.provision_user.state:
            if not re.fullmatch(r"[A-Za-z0-9._-]{1,32}", text):
                raise ValueError("Логин: латиница, цифры, точка, _ и -")
            draft = dict((await state.get_data()).get("provision") or {})
            draft["user"] = text
            await state.update_data(provision=draft)
            await state.set_state(AdminEdit.provision_password)
            await _say(message, "Шаг 4 из 5. Пароль SSH одним сообщением.", _back("admin_servers"))
            return

        if current == AdminEdit.provision_password.state:
            draft = dict((await state.get_data()).get("provision") or {})
            draft["password"] = text
            await state.update_data(provision=draft)
            await state.set_state(AdminEdit.provision_country)
            await _say(
                message,
                "Шаг 5 из 5. Страна для названий подключений.\nПример: <code>Нидерланды</code>",
                _back("admin_servers"),
            )
            return

        if current == AdminEdit.provision_country.state:
            import provision_server

            flag, country_name, slug = provision_server.resolve_country(text)
            draft = dict((await state.get_data()).get("provision") or {})
            draft["country"] = text
            draft["flag"] = flag
            draft["country_name"] = country_name
            draft["slug"] = slug
            await state.update_data(provision=draft)
            await state.set_state(AdminEdit.provision_confirm)
            await _say(
                message,
                "<b>Проверьте и запустите</b>\n\n"
                f"Домен: <code>{_esc(draft.get('domain'))}</code>\n"
                f"Сервер: <code>{_esc(draft.get('user'))}@{_esc(draft.get('host'))}</code>\n"
                f"Страна: {_esc(flag)} {_esc(country_name)}\n\n"
                "3x-ui повторит подключения дополнительного сервера, клиенты возьмутся с основного.",
                _kb(
                    [
                        [_btn("Поднять", "provision_go")],
                        [_btn("Отмена", "admin_servers", style="danger")],
                    ]
                ),
            )
            return

        if current == AdminEdit.provision_confirm.state:
            await _say(message, "Нажмите «Поднять» или «Отмена». Этот шаг текст не записывает.")
            return

        if current == AdminEdit.server_add_name.state:
            if not text or len(text) > 64:
                raise ValueError("Название: от 1 до 64 символов")
            await state.update_data(draft={"label": text})
            await state.set_state(AdminEdit.server_add_url)
            await _say(
                message,
                "Шаг 2 из 4. Ссылка на панель 3x-ui целиком, с секретным путём.\n"
                "Пример: <code>https://panel.example.ru:2053/секретный_путь</code>",
                _back("admin_servers"),
            )
            return

        if current == AdminEdit.server_add_url.state:
            parsed = settings.parse_panel_url(text)
            if any(item.get("panel_url") == parsed["base"] for item in settings.get()["servers"]):
                raise ValueError("Такая панель уже добавлена")
            draft = dict((await state.get_data()).get("draft") or {})
            draft["panel_url"] = parsed["base"]
            await state.update_data(draft=draft)
            await state.set_state(AdminEdit.server_add_user)
            await _say(message, "Шаг 3 из 4. Логин панели.", _back("admin_servers"))
            return

        if current == AdminEdit.server_add_user.state:
            if not text or any(ch.isspace() for ch in text):
                raise ValueError("Логин одной строкой, без пробелов")
            draft = dict((await state.get_data()).get("draft") or {})
            draft["panel_user"] = text
            await state.update_data(draft=draft)
            await state.set_state(AdminEdit.server_add_pass)
            await _say(message, "Шаг 4 из 4. Пароль панели. Сообщение с ним я удалю.", _back("admin_servers"))
            return

        if current == AdminEdit.server_add_pass.state:
            import asyncio

            import api
            import sub_proxy

            draft = dict((await state.get_data()).get("draft") or {})
            try:
                await message.delete()
            except Exception:
                pass
            if not draft.get("panel_url"):
                await state.clear()
                await _say(message, "Шаги сбились. Откройте «Добавить сервер» ещё раз.", _back("admin_servers", "К серверам"))
                return
            server = {
                "name": "",
                "label": draft["label"],
                "panel_url": draft["panel_url"],
                "panel_user": draft["panel_user"],
                "panel_password": text,
                "sub_url": "",
                "enabled": True,
                "is_primary": False,
            }
            ok, err = await asyncio.to_thread(api.server_login_check, server)
            if not ok:
                await _say(
                    message,
                    f"Не удалось войти в панель: {_esc(err)}\nМожно прислать пароль ещё раз или нажать «Отмена».",
                    _back("admin_servers"),
                )
                return
            sub_url, sub_err = await asyncio.to_thread(sub_proxy.detect_sub_url, server)
            server["sub_url"] = sub_url or ""
            taken = {item["name"] for item in settings.get()["servers"]}
            base_name = re.sub(r"[^A-Za-z0-9_-]+", "-", draft["label"]).strip("-")[:24] or "server"
            name, number = base_name, 2
            while name in taken:
                name = f"{base_name}-{number}"
                number += 1
            server["name"] = name

            def mutate(data):
                data["servers"].append(server)

            settings.update(mutate)
            notes = ["Вход в панель выполнен."]
            if sub_url:
                px_ok, px_msg = await asyncio.to_thread(sub_proxy.add_url, sub_url)
                notes.append(f"Прокси подписок: {'добавлена' if px_ok else 'не добавлена'} <code>{_esc(sub_url)}</code>"
                             + ("" if px_ok else f" ({_esc(px_msg)})"))
            else:
                notes.append(f"Ссылку подписки определить не удалось ({_esc(sub_err)}). Задайте её в карточке сервера.")
            renamed = await asyncio.to_thread(api.rename_server_inbounds, server)
            notes.append(f"Подключения переименованы: {len(renamed['changed'])}"
                         + (f" (ошибка: {_esc(renamed['errors'][0])})" if renamed["errors"] else ""))
            await message.answer("Переношу клиентов с главного сервера, это может занять несколько минут…")
            sync = await asyncio.to_thread(api.sync_clients_to_server, server)
            line = f"Клиенты с главного: перенесено {sync['added']} из {sync['total']}"
            if sync.get("skipped"):
                line += f" (уже были: {sync['skipped']})"
            if sync.get("error"):
                line += f"\nОшибка: {_esc(sync['error'])}. Повторить можно кнопкой «Скопировать клиентов с главного» в карточке сервера."
            notes.append(line)
            await _finish_servers(message, state, f"Сервер <b>{_esc(draft['label'])}</b> добавлен.\n" + "\n".join(notes))
            return

        data_state = await state.get_data()
        index = data_state.get("server_index")

        if current == AdminEdit.proxy_add.state:
            import asyncio

            import sub_proxy

            ok, msg = await asyncio.to_thread(sub_proxy.add_url, text)
            await state.clear()
            view, markup = _proxy_view()
            await _say(message, f"{'✅' if ok else '❌'} {_esc(msg)}\n\n{view}", markup)
            return

        if current == AdminEdit.server_sub.state:
            import sub_proxy

            url = sub_proxy.normalize_url(text)

            def mutate(data):
                server = _server_or_none(data, index)
                if server is None:
                    raise ValueError("Сервер уже удалён")
                server["sub_url"] = url

            settings.update(mutate)
            await _finish_servers(message, state, "Ссылка подписки сохранена. В прокси её можно добавить в разделе «Прокси подписок».")
            return

        if current == AdminEdit.server_creds.state:
            lines = [part.strip() for part in text.splitlines() if part.strip()]
            if len(lines) != 2:
                raise ValueError("Нужны две строки: логин и пароль")
            try:
                await message.delete()
            except Exception:
                pass

            def mutate(data):
                server = _server_or_none(data, index)
                if server is None:
                    raise ValueError("Сервер уже удалён")
                server["panel_user"], server["panel_password"] = lines

            settings.update(mutate)
            await _finish_servers(message, state, "Логин и пароль сохранены.")
            return

        if current == AdminEdit.server_label.state:
            if not text or len(text) > 64:
                raise ValueError("Подпись: от 1 до 64 символов")

            def mutate(data):
                server = _server_or_none(data, index)
                if server is None:
                    raise ValueError("Сервер уже удалён")
                server["label"] = text

            settings.update(mutate)
            await _finish_servers(message, state, "Название сохранено.")
            return

        if current == AdminEdit.server_panel.state:
            parsed = settings.parse_panel_url(text)
            promote = bool(data_state.get("promote"))

            def mutate(data):
                server = _server_or_none(data, index)
                if server is None:
                    raise ValueError("Сервер уже удалён")
                server["panel_url"] = parsed["base"]
                if promote:
                    for pos, item in enumerate(data["servers"]):
                        item["is_primary"] = pos == index

            settings.update(mutate)
            note = "URL панели сохранён."
            await _finish_servers(message, state, note)
            return

        if current == AdminEdit.token_value.state:
            key = data_state.get("token_key")
            if key not in settings.TOKEN_LABELS:
                await state.clear()
                await _say(message, "Не понял, какой токен менять. Откройте раздел ещё раз.", _back("admin_tokens", "К токенам"))
                return
            token = settings.clean_token(message.text or "")

            def mutate(data):
                data["tokens"][key] = token

            settings.update(mutate)
            await state.clear()
            extra = ""
            if key == "telegram_bot":
                extra = "\nПерезапустите бота, чтобы он начал ходить в Telegram с этим токеном."
            await _say(
                message,
                f"{_esc(settings.TOKEN_LABELS[key])}: <code>{_esc(settings.mask_token(token))}</code>{extra}",
                _back("admin_tokens", "К токенам"),
            )
            return

        await state.clear()
        await message.answer("Этот шаг уже закрыт. Откройте раздел в админке ещё раз.")
    except ValueError as exc:
        await _say(message, f"{_esc(exc)}\nМожно прислать значение ещё раз или нажать «Отмена».")
    except Exception as exc:
        await _say(message, f"Не сохранилось: {_esc(exc)}\nШаг ещё открыт, можно прислать значение снова.")


@router.message(StateFilter(*_INPUT_STATES), ~F.text)
async def admin_need_text(message: Message):
    await message.answer("Нужен обычный текст одним сообщением. Кнопка «Отмена» закрывает ввод.")


@router.message(Command("check"))
async def admin_check_client(message: Message):
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].lstrip("-").isdigit():
        await message.answer("Использование: /check &lt;telegram_id&gt;", parse_mode="HTML")
        return
    tg_id = int(parts[1])
    status = await message.answer("⏳ Собираю данные…")
    import asyncio
    import check_client

    try:
        blocks = await asyncio.to_thread(check_client.build_report, tg_id)
    except Exception as e:
        await status.edit_text(f"Ошибка: {html.escape(str(e))}", parse_mode="HTML")
        return
    await status.delete()
    for b in blocks:
        for i in range(0, len(b), 4000):
            await message.answer(b[i:i + 4000], parse_mode="HTML")


@router.message(Command("delsub"))
async def admin_delsub(message: Message):
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Использование: /delsub &lt;telegram_id&gt;", parse_mode="HTML")
        return
    tg_id = int(parts[1])
    import asyncio
    import check_client

    rows, err = await asyncio.to_thread(check_client._collect_panel, tg_id)
    if err:
        await message.answer(f"Не удалось получить данные основной панели: {html.escape(err)}")
        return
    emails = sorted({r["client"].get("email") for r in rows if r["client"].get("email")})
    text = (
        f"⚠️ Удалить подписку клиента <code>{tg_id}</code> со <b>всех серверов</b>?\n"
        f"На основной панели найдено клиентов: {len(rows)} ({html.escape(', '.join(emails)) or '—'}).\n"
        "Действие необратимо."
    )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=_kb([[
            _btn("🗑 Да, удалить", f"delsub_yes:{tg_id}"),
            _btn("Отмена", "delsub_no"),
        ]]),
    )


@router.callback_query(_cb(r"^delsub_no$"))
async def admin_delsub_cancel(callback: CallbackQuery):
    await callback.message.edit_text("Удаление отменено.")
    await callback.answer()


@router.callback_query(_cb(r"^delsub_yes:\d+$"))
async def admin_delsub_confirm(callback: CallbackQuery):
    tg_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(f"⏳ Удаляю подписку {tg_id} со всех серверов…")
    await callback.answer()
    import asyncio
    import api

    def _run():
        sub_id = None
        info = api_ext.getSubById(tg_id)
        if info.get("success"):
            sub_id = info.get("subId")
        main_res = api.dell_client_from_all_inbounds(tg_id)
        remote_res = api.send_dell_client_webhook(tg_id, sub_id or "")
        return main_res, remote_res

    import api_extended as api_ext

    try:
        main_res, remote_res = await asyncio.to_thread(_run)
    except Exception as e:
        await callback.message.edit_text(f"Ошибка: {html.escape(str(e))}")
        return

    deleted = [r for r in main_res.get("results", []) if "email" in r]
    lines = [f"🗑 <b>Удаление {tg_id}</b>"]
    lines.append(
        f"Основная панель: {'✅' if main_res.get('success') else '❌ ' + html.escape(str(main_res.get('error')))}, "
        f"удалено записей: {len(deleted)}"
    )
    for r in remote_res.get("results", []):
        mark = "✅" if r.get("success") else f"❌ {html.escape(str(r.get('error') or ''))}"
        lines.append(f"{html.escape(str(r.get('label')))}: {mark}")
    lines.append("\nПроверить результат: /check " + str(tg_id))
    await callback.message.edit_text("\n".join(lines), parse_mode="HTML")
