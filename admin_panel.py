"""Админка бота. Текст принимается только после нажатия кнопки и не пишется в базу сам по себе."""

import html
import re

from aiogram import F, Router
from aiogram.filters import Filter, StateFilter
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
    server_add_label = State()
    server_add_url = State()
    server_webhook = State()
    server_label = State()
    server_panel = State()
    token_value = State()


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
    AdminEdit.server_add_label,
    AdminEdit.server_add_url,
    AdminEdit.server_webhook,
    AdminEdit.server_label,
    AdminEdit.server_panel,
    AdminEdit.token_value,
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
        [_btn("Серверы", "admin_servers")],
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
        role = "основной" if server.get("is_primary") else "дополнительный"
        panel = server.get("panel_url") or "—"
        hook = server.get("webhook_url") or "—"
        lines.append(f"{mark}<b>{_esc(server.get('label') or server['name'])}</b> ({role})")
        lines.append(f"имя: <code>{_esc(server['name'])}</code>")
        lines.append(f"панель: <code>{_esc(panel)}</code>")
        lines.append(f"webhook: <code>{_esc(hook)}</code>")
        lines.append("")
        rows.append([_btn(f"{mark}{server.get('label') or server['name']}"[:40], f"srv:{index}")])
    if not data["servers"]:
        lines.append("Список пуст.")
    lines.append("Основной — панель 3x-ui, на ней клиент создаётся первым. Остальные получают webhook.")
    rows.append([_btn("Добавить сервер", "srv_add")])
    rows.append([_btn("Назад", "admin_panel")])
    return "\n".join(lines), _kb(rows)


def _server_card(data, index: int):
    server = data["servers"][index]
    role = "основной" if server.get("is_primary") else "дополнительный"
    text = (
        f"<b>{_esc(server.get('label') or server['name'])}</b>\n\n"
        f"Роль: {role}\n"
        f"Имя: <code>{_esc(server['name'])}</code>\n"
        f"Панель: <code>{_esc(server.get('panel_url') or '—')}</code>\n"
        f"Webhook: <code>{_esc(server.get('webhook_url') or '—')}</code>"
    )
    rows = [
        [_btn("Webhook", f"srv_wh:{index}"), _btn("Название", f"srv_lb:{index}")],
        [_btn("URL панели", f"srv_pn:{index}")],
    ]
    if not server.get("is_primary"):
        rows.append([_btn("Сделать основным", f"srv_pr:{index}")])
        rows.append([_btn("Удалить", f"srv_rm:{index}", style="danger")])
    rows.append([_btn("К списку", "admin_servers")])
    return text, _kb(rows)


def _tokens_view():
    lines = ["<b>Токены</b>", "", "Показаны только края. Новое значение пришлите следующим сообщением.", ""]
    rows = []
    for key, label in settings.TOKEN_LABELS.items():
        lines.append(f"{_esc(label)}: <code>{_esc(settings.mask_token(settings.effective_token(key)))}</code>")
        rows.append([_btn(label, f"tok:{key}"), _btn("Сброс", f"tok_reset:{key}")])
    lines.append("")
    lines.append("Пустое сохранённое значение возвращает токен из кода. Смена токена бота применяется к текущему процессу.")
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
        "<b>Новый сервер</b>\n\nШаг 1 из 3. Короткое имя латиницей, например <code>ezh-dev</code>",
        _back("admin_servers"),
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


@router.callback_query(_cb(r"^srv_wh:\d+$"))
async def srv_webhook(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.split(":")[1])
    await state.set_state(AdminEdit.server_webhook)
    await state.update_data(server_index=index)
    await _show(
        callback,
        "<b>Webhook сервера</b>\n\nПришлите адрес, например <code>https://panel.example.ru:2500</code>",
        _back(f"srv:{index}"),
    )


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


@router.callback_query(_cb(r"^srv_pr:\d+$"))
async def srv_primary(callback: CallbackQuery, state: FSMContext):
    index = int(callback.data.split(":")[1])
    data = settings.get()
    if index < 0 or index >= len(data["servers"]):
        await _show(callback, "Сервер уже не в списке.", _back("admin_servers", "К серверам"))
        return
    server = data["servers"][index]
    if not server.get("panel_url"):
        await state.set_state(AdminEdit.server_panel)
        await state.update_data(server_index=index, promote=True)
        await _show(
            callback,
            "<b>Этот сервер станет основным</b>\n\nСначала пришлите URL его панели 3x-ui:\n<code>https://домен:порт/путь</code>",
            _back("admin_servers"),
        )
        return
    _mark_primary(data, index)
    settings.save(data)
    warning = ""
    old_without_hook = [
        item["label"]
        for item in data["servers"]
        if not item.get("is_primary") and not item.get("webhook_url") and item.get("panel_url")
    ]
    if old_without_hook:
        warning = (
            "\n\nУ сервера без webhook клиенты больше не создаются: "
            + ", ".join(_esc(name) for name in old_without_hook)
            + ". Укажите ему webhook, если он должен остаться в списке."
        )
    text, markup = _servers_view(settings.get())
    await _show(callback, f"Основной сервер: <b>{_esc(server.get('label') or server['name'])}</b>{warning}\n\n{text}", markup)


def _mark_primary(data, index: int):
    for pos, item in enumerate(data["servers"]):
        item["is_primary"] = pos == index


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

    def mutate(data):
        if 0 <= index < len(data["servers"]) and not data["servers"][index].get("is_primary"):
            del data["servers"][index]

    settings.update(mutate)
    text, markup = _servers_view(settings.get())
    await _show(callback, text, markup)


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

        if current == AdminEdit.server_add_name.state:
            name = settings.clean_server_name(text)
            data = settings.get()
            if any(item["name"] == name for item in data["servers"]):
                raise ValueError("Такое имя уже есть. Пришлите другое.")
            await state.update_data(draft={"name": name})
            await state.set_state(AdminEdit.server_add_label)
            await _say(message, "Шаг 2 из 3. Подпись сервера, например <code>www.ezh-dev.ru</code>", _back("admin_servers"))
            return

        if current == AdminEdit.server_add_label.state:
            if not text or len(text) > 64:
                raise ValueError("Подпись: от 1 до 64 символов")
            draft = dict((await state.get_data()).get("draft") or {})
            draft["label"] = text
            await state.update_data(draft=draft)
            await state.set_state(AdminEdit.server_add_url)
            await _say(
                message,
                "Шаг 3 из 3. Webhook, например <code>https://www.ezh-dev.ru:2500</code>",
                _back("admin_servers"),
            )
            return

        if current == AdminEdit.server_add_url.state:
            url = settings.clean_webhook_url(text)
            draft = dict((await state.get_data()).get("draft") or {})
            if not draft.get("name"):
                await state.clear()
                await _say(message, "Шаги сбились. Откройте «Добавить сервер» ещё раз.", _back("admin_servers", "К серверам"))
                return

            def mutate(data):
                data["servers"].append(
                    {
                        "name": draft["name"],
                        "label": draft.get("label") or draft["name"],
                        "panel_url": "",
                        "webhook_url": url,
                        "is_primary": False,
                    }
                )

            settings.update(mutate)
            await _finish_servers(message, state, f"Сервер <b>{_esc(draft['name'])}</b> добавлен.")
            return

        data_state = await state.get_data()
        index = data_state.get("server_index")

        if current == AdminEdit.server_webhook.state:
            url = settings.clean_webhook_url(text)

            def mutate(data):
                server = _server_or_none(data, index)
                if server is None:
                    raise ValueError("Сервер уже удалён")
                server["webhook_url"] = url

            settings.update(mutate)
            await _finish_servers(message, state, "Webhook сохранён.")
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
            if promote:
                note = "Сервер назначен основным."
                leftover = [
                    item.get("label") or item["name"]
                    for item in settings.get()["servers"]
                    if not item.get("is_primary") and item.get("panel_url") and not item.get("webhook_url")
                ]
                if leftover:
                    note += " Без webhook клиенты не создаются на: " + ", ".join(_esc(name) for name in leftover)
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
                extra = "\nТекущий процесс уже берёт этот токен. Если бот замолчал, в bot_settings.json верните прежний и перезапустите."
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
