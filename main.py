import asyncio
import datetime
import os
import re
import sys

from sqlalchemy import create_engine, Column, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker, declarative_base

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardMarkup, InlineKeyboardButton

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api import add_client, getSubById, check_cantfree, add_to_cantfree

OPERATOR_CHAT_ID = 1240656726

# Асинхронный SQLite
async_engine = create_async_engine("sqlite+aiosqlite:///vpn_bot.db", echo=False)

Base = declarative_base()

class Info(Base):
    __tablename__ = "info"
    id = Column(Integer, primary_key=True)
    value = Column(String)

class Contacts(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True)
    value = Column(String)

class Price(Base):
    __tablename__ = "price"
    id = Column(Integer, primary_key=True)
    time = Column(Integer)
    price = Column(Integer)

class CantFree(Base):
    __tablename__ = "cant_free"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)

# Создание таблиц (асинхронно)
async def create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Создание фабрики асинхронных сессий
AsyncSessionLocal = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

# Асинхронная функция для создания/обновления info
async def create_or_update_info(value: str, info_id: int = 1):
    async with AsyncSessionLocal() as session:
        # Ищем запись с указанным id
        result = await session.execute(select(Info).filter(Info.id == info_id))
        info = result.scalar_one_or_none()
        
        if info:
            # Если запись существует, обновляем ее
            info.value = value
            await session.commit()
            await session.refresh(info)
            print(f"Запись с id={info_id} обновлена: {value}")
        else:
            # Если записи нет, создаем новую
            info = Info(id=info_id, value=value)
            session.add(info)
            await session.commit()
            await session.refresh(info)
            print(f"Создана новая запись с id={info_id}: {value}")
        
        return info

# Асинхронная функция для создания/обновления контактов
async def create_or_update_contact(value: str, contact_id: int = 1):
    async with AsyncSessionLocal() as session:
        # Ищем контакт с указанным id
        result = await session.execute(select(Contacts).filter(Contacts.id == contact_id))
        contact = result.scalar_one_or_none()
        
        if contact:
            # Если контакт существует, обновляем его
            contact.value = value
            await session.commit()
            await session.refresh(contact)
            print(f"Контакт с id={contact_id} обновлен: {value}")
        else:
            # Если контакта нет, создаем новый
            contact = Contacts(id=contact_id, value=value)
            session.add(contact)
            await session.commit()
            await session.refresh(contact)
            print(f"Создан новый контакт с id={contact_id}: {value}")
        
        return contact

# Асинхронная функция для установки/обновления цены
async def set_price(time_months: int, price_rubles: int):
    async with AsyncSessionLocal() as session:
        # Ищем запись с указанным временем
        result = await session.execute(select(Price).filter(Price.time == time_months))
        price_record = result.scalar_one_or_none()
        
        if price_record:
            # Если запись существует, обновляем цену
            price_record.price = price_rubles
            await session.commit()
            await session.refresh(price_record)
            print(f"Цена для {time_months} месяцев обновлена: {price_rubles}₽")
        else:
            # Если записи нет, создаем новую
            price_record = Price(time=time_months, price=price_rubles)
            session.add(price_record)
            await session.commit()
            await session.refresh(price_record)
            print(f"Создана новая цена для {time_months} месяцев: {price_rubles}₽")
        
        return price_record

# Асинхронная функция для получения всех цен
async def get_all_prices():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Price).order_by(Price.time))
        prices = result.scalars().all()
        return prices

# Асинхронная функция для получения цены по времени
async def get_price(time_months: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Price).filter(Price.time == time_months))
        price_record = result.scalar_one_or_none()
        return price_record.price if price_record else None

# Код бота
TOKEN = "8358697144:AAGppsqXjG9S08nGLUpghL-jUfTz9H4gj58"

bot = Bot(token=TOKEN)
router = Router()

# Проверка на админа
def is_admin(user_id: int) -> bool:
    return user_id == OPERATOR_CHAT_ID

# Создаем inline кнопки
subscription_btn = InlineKeyboardButton(text="Подписка", callback_data="subscription", style="primary", icon_custom_emoji_id='5296369303661067030')
contact_btn = InlineKeyboardButton(text="Связь", callback_data="contact", style="primary", icon_custom_emoji_id='5443038326535759644')
info_btn = InlineKeyboardButton(text="Информация", callback_data="info", style="primary", icon_custom_emoji_id='5282843764451195532')
buy_subscription_btn = InlineKeyboardButton(text="Купить подписку", callback_data="buy_subscription", style="primary", icon_custom_emoji_id='5271604874419647061')
admin_btn = InlineKeyboardButton(text="⚙️ Админ панель", callback_data="admin_panel", style="secondary")

# Создаем inline клавиатуру (кнопки в разных строках)
keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [subscription_btn],      # Первая строка
        # [buy_subscription_btn], # Вторая строка
        [contact_btn],          # Третья строка  
        [info_btn]              # Четвертая строка
    ]
)

# Админ клавиатура
admin_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💰 Цены", callback_data="admin_prices", style="primary")],
        [InlineKeyboardButton(text="📝 Информация", callback_data="admin_info", style="primary")],
        [InlineKeyboardButton(text="📞 Контакты", callback_data="admin_contacts", style="primary")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main", style="primary")]
    ]
)

# Клавиатура управления ценами
prices_management_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить цену", callback_data="add_price", style="primary")],
        [InlineKeyboardButton(text="✏️ Изменить цену", callback_data="edit_price", style="primary")],
        [InlineKeyboardButton(text="🗑️ Удалить цену", callback_data="delete_price")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel", style="primary")]
    ]
)

# Клавиатура управления информацией
info_management_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить информацию", callback_data="edit_info", style="primary")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel", style="primary")]
    ]
)

# Клавиатура управления контактами
contacts_management_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить контакты", callback_data="edit_contacts", style="primary")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel", style="primary")]
    ]
)

@router.message(Command("start"))
async def start(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer(
            "⚙️ <b>Админ панель</b>\n\n"
            "Выберите действие:",
            reply_markup=admin_keyboard,
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(
            "Привет! Я бот для управления VPN.\n\n"
            "Выберите одну из опций ниже:",
            reply_markup=keyboard
        )

# Асинхронная функция для получения info из БД
async def get_info(info_id: int = 1):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Info).filter(Info.id == info_id))
        info = result.scalar_one_or_none()
        return info.value if info else "Информация не найдена"

# Асинхронная функция для получения контактов из БД
async def get_contact(contact_id: int = 1):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Contacts).filter(Contacts.id == contact_id))
        contact = result.scalar_one_or_none()
        return contact.value if contact else "Контакты не найдены"

# Импортируем функции из api.py
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def convert_timestamp_to_human_readable(timestamp_ms):
    """Конвертирует timestamp в миллисекундах в читаемый формат ДД.ММ.ГГГГ ЧЧ:ММ:СС"""
    if timestamp_ms == 0:
        return "Не ограничено"
    
    try:
        # Конвертируем миллисекунды в секунды
        timestamp_s = timestamp_ms / 1000
        # Создаем datetime объект
        dt = datetime.datetime.fromtimestamp(timestamp_s)
        # Форматируем в ДД.ММ.ГГГГ ЧЧ:ММ:СС
        return dt.strftime("%d.%m.%Y %H:%M:%S")
    except (ValueError, OSError) as e:
        return f"Ошибка конвертации: {e}"

# Асинхронная функция для проверки пользователя в CantFree (локальная)
async def check_cantfree_local(tg_id):
    """Проверяет есть ли пользователь в локальной CantFree таблице"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CantFree).filter(CantFree.user_id == tg_id))
        user = result.scalar_one_or_none()
        return {"exists": user is not None}

# Асинхронная функция для добавления пользователя в CantFree (локальная)
async def add_to_cantfree_local(tg_id, username):
    """Добавляет пользователя в локальную CantFree таблицу"""
    async with AsyncSessionLocal() as session:
        # Проверяем есть ли уже такой пользователь
        result = await session.execute(select(CantFree).filter(CantFree.user_id == tg_id))
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            return {"success": False, "message": "User already exists"}
        
        # Добавляем нового пользователя
        new_user = CantFree(user_id=tg_id)
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        return {"success": True, "message": "User added to CantFree"}

# Асинхронная функция для получения информации о подписке по TG ID
async def get_subscription_info(tg_id: int):
    # Проверяем основную подписку через API
    try:
        result = getSubById(tg_id)

        print(result)
        if result.get('success'):
            # Проверяем статус подписки
            is_enabled = result['client_info']['enable']
            status_emoji = "<tg-emoji emoji-id='5416081784641168838'>✅</tg-emoji>" if is_enabled else "<tg-emoji emoji-id='5411225014148014586'>❌</tg-emoji>"
            status_text = "Подписка активна" if is_enabled else "Подписка неактивна"
            
            # Проверяем лимит
            total_gb = result['client_info']['totalGB']
            limit_text = "Безлимитный" if total_gb == 0 else f"{total_gb} GB"
            
            return f"{status_emoji} {status_text}\n\n" \
                   f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Истекает: {convert_timestamp_to_human_readable(result['client_info']['expiryTime'])}\n" \
                   f"<tg-emoji emoji-id='5375338737028841420'>💾</tg-emoji> Лимит: {limit_text}", "has_subscription"
        else:
            error_msg = result.get('error', '')
            if "No client found with tgId" in error_msg:
                return "<tg-emoji emoji-id='5411225014148014586'>❌</tg-emoji> У вас нет подписки\n\nДля получения доступа к VPN необходимо оформить подписку.", "no_subscription"
            else:
                return f"<tg-emoji emoji-id='5411225014148014586'>❌</tg-emoji> {result.get('error', 'Подписка не найдена')}", "error"
    except Exception as e:
        return f"<tg-emoji emoji-id='5411225014148014586'>❌</tg-emoji> Ошибка при проверке подписки: {str(e)}", "error"

@router.callback_query(lambda callback: callback.data == "subscription")
async def subscription_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    # Получаем TG ID пользователя
    user_tg_id = callback.from_user.id
    
    # Получаем информацию о подписке и статус
    subscription_info, status = await get_subscription_info(user_tg_id)
    
    # Получаем данные из API для проверки статуса (только если есть подписка)
    if status == "has_subscription":
        try:
            result = getSubById(user_tg_id)
            is_enabled = result.get('client_info', {}).get('enable', False) if result.get('success') else False
            sub_id = result.get('subId', '') if result.get('success') else ''
        except:
            is_enabled = False
            sub_id = ''
        
        # Создаем клавиатуру только если подписка активна
        if is_enabled:
            subscription_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Использовать", url=f"http://ezh-dev.ru:2096/sub/{sub_id}", callback_data=f"use_sub_{sub_id}", style="primary", icon_custom_emoji_id='5271604874419647061')]
                ]
            )
        else:
            subscription_keyboard = None
    elif status == "no_subscription":
        # Проверяем есть ли пользователь в CantFree (локально)
        cantfree_result = await check_cantfree_local(user_tg_id)
        
        if cantfree_result.get("exists") == False:
            # Пользователя нет в CantFree - предлагаем пробный период
            subscription_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Пробный период", callback_data="trial_period", style="primary", icon_custom_emoji_id='5406756500108501710')],
                    [InlineKeyboardButton(text="Купить подписку", callback_data="buy_subscription", style="primary", icon_custom_emoji_id='5271604874419647061')]
                ]
            )
        else:
            # Пользователь уже использовал пробный период
            subscription_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Купить подписку", callback_data="buy_subscription", style="primary", icon_custom_emoji_id='5271604874419647061')]
                ]
            )
    else:
        # Для ошибок - без клавиатуры
        subscription_keyboard = None
    
    await callback.message.answer(
        f"<tg-emoji emoji-id='5251203410396458957'>📱</tg-emoji> <b>Ваша подписка</b>\n\n{subscription_info}",
        reply_markup=subscription_keyboard,
        parse_mode=ParseMode.HTML
    )

@router.callback_query(lambda callback: callback.data == "buy_subscription")
async def buy_subscription_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    # Получаем все цены из БД
    prices = await get_all_prices()
    
    # Создаем клавиатуру с ценами из БД
    keyboard_buttons = []
    for price in prices:
        months_text = "год" if price.time == 12 else f"{price.time} месяц{'а' if price.time > 1 and price.time < 5 else 'ев'}"
        button_text = f"{months_text} - {price.price}₽"
        keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"select_price_{price.time}_{price.price}", style="primary")])
    
    buy_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.answer(
        "<tg-emoji emoji-id='5251203410396458957'>🛒</tg-emoji> <b>Покупка подписки</b>\n\n"
        "Выберите подходящий вам тариф:\n\n"
        "<tg-emoji emoji-id='5416081784641168838'>✅</tg-emoji> Все тарифы включают:\n"
        "• Безлимитный трафик\n"
        "• Высокая скорость\n"
        "• Поддержка 24/7\n"
        "• Все устройства",
        reply_markup=buy_keyboard,
        parse_mode=ParseMode.HTML
    )

@router.callback_query(lambda callback: callback.data == "trial_period")
async def trial_period_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    
    user_tg_id = callback.from_user.id
    user_username = callback.from_user.username
    
    # Проверяем еще раз что пользователя нет в CantFree (локально)
    cantfree_result = await check_cantfree_local(user_tg_id)
    
    if cantfree_result.get("exists") == True:
        # Пользователь уже использовал пробный период
        await callback.message.answer(
            "<tg-emoji emoji-id='5411225014148014586'>❌</tg-emoji> <b>Пробный период уже использован</b>\n\n"
            "Вы уже активировали пробный период ранее.\n"
            "Для продолжения использования VPN необходимо оформить подписку.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Купить подписку", callback_data="buy_subscription", style="primary", icon_custom_emoji_id='5271604874419647061')]
                ]
            ),
            parse_mode=ParseMode.HTML
        )
        return
    
    # Добавляем пользователя в CantFree (локально)
    add_result = await add_to_cantfree_local(user_tg_id, user_username)
    
    if add_result.get("success"):
        # Создаем пробную подписку на 3 дня через API
        current_time = datetime.datetime.now()
        end_time = current_time + datetime.timedelta(days=3)
        end_date_str = end_time.strftime("%d.%m.%Y")
        
        # Добавляем клиента в систему с пробной подпиской через API
        try:
            api_date = end_time.strftime("%d.%m.%Y")
            client_result = add_client(21, f"trial_user_{user_tg_id}", user_tg_id, api_date)
            
            await callback.message.answer(
                "<tg-emoji emoji-id='5416081784641168838'>✅</tg-emoji> <b>Пробный период активирован!</b>\n\n"
                f"🎁 <b>Пробный период на 3 дня</b>\n"
                f"📅 Действует до: {end_date_str}\n"
                f"⏰ Осталось: 3 дня\n\n"
                "Доступ ко всем функциям VPN:\n"
                "• Безлимитный трафик\n"
                "• Высокая скорость\n"
                "• Все устройства\n\n"
                "Для продления подпишитесь на платный тариф!",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="Моя подписка", callback_data="subscription", style="primary", icon_custom_emoji_id='5296369303661067030')],
                        [InlineKeyboardButton(text="Купить подписку", callback_data="buy_subscription", style="primary", icon_custom_emoji_id='5271604874419647061')]
                    ]
                ),
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            await callback.message.answer(
                "<tg-emoji emoji-id='5411225014148014586'>❌</tg-emoji> <b>Ошибка активации</b>\n\n"
                "Не удалось создать пробную подписку. Пожалуйста, обратитесь в поддержку.",
                parse_mode=ParseMode.HTML
            )
            print(f"Error adding trial client: {e}")
    else:
        await callback.message.answer(
            "<tg-emoji emoji-id='5411225014148014586'>❌</tg-emoji> <b>Ошибка активации</b>\n\n"
            "Не удалось активировать пробный период. Пожалуйста, попробуйте позже.",
            parse_mode=ParseMode.HTML
        )

@router.callback_query(lambda callback: callback.data.startswith("select_price_"))
async def select_price_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    # Извлекаем время и цену из callback_data
    parts = callback.data.split("_")
    time_months = int(parts[2])  # "select_price_1_200" -> parts[2] = "1"
    price_rubles = int(parts[3])  # "select_price_1_200" -> parts[3] = "200"
    
    # Формируем текст времени
    months_text = "год" if time_months == 12 else f"{time_months} месяц{'а' if time_months > 1 and time_months < 5 else 'ев'}"
    
    # Создаем кнопку оплаты
    pay_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить", callback_data=f"confirm_pay_{time_months}_{price_rubles}", style="primary")]
        ]
    )
    
    await callback.message.answer(
        f"<tg-emoji emoji-id='5251203410396458957'>💳</tg-emoji> <b>Выбранный тариф</b>\n\n"
        f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Период: {months_text}\n"
        f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Цена: {price_rubles}₽\n\n"
        "Нажмите 'Оплатить' для продолжения:",
        reply_markup=pay_keyboard,
        parse_mode=ParseMode.HTML
    )

@router.callback_query(lambda callback: callback.data.startswith("confirm_pay_"))
async def confirm_pay_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    # Извлекаем время и цену из callback_data
    parts = callback.data.split("_")
    time_months = int(parts[2])
    price_rubles = int(parts[3])
    
    # Формируем текст времени
    months_text = "год" if time_months == 12 else f"{time_months} месяц{'а' if time_months > 1 and time_months < 5 else 'ев'}"
    
    await callback.message.answer(
        f"<tg-emoji emoji-id='5251203410396458957'>💳</tg-emoji> <b>Информация об оплате</b>\n\n"
        f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Период: {months_text}\n"
        f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Цена: {price_rubles}₽\n\n"
        f"<tg-emoji emoji-id='5424972470023104089'>💳</tg-emoji> РЕКВИЗИТЫ <tg-emoji emoji-id='5424972470023104089'>💳</tg-emoji>\n"
        f"<tg-emoji emoji-id='5195396392058641159'>💳</tg-emoji> ТИНЬКОФФ:\n"
        f"<tg-emoji emoji-id='5440660757194744323'>💳</tg-emoji> <code>2200701411111369</code> (тык)\n\n"
        f"<tg-emoji emoji-id='5345956698253180145'>💳</tg-emoji> СБП:\n"
        f"<tg-emoji emoji-id='5440660757194744323'>💳</tg-emoji> <code>+7 962 992 91-38</code> (тык)\n"
        f"<tg-emoji emoji-id='5440660757194744323'>💳</tg-emoji> СТРОГО Т-БАНК <tg-emoji emoji-id='5195396392058641159'>💳</tg-emoji>\n\n"
        "После оплаты нажмите 'Я оплатил'",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Я оплатил", callback_data=f"paid_notify_{time_months}_{price_rubles}", style="primary")]
            ]
        ),
        parse_mode=ParseMode.HTML
    )

@router.callback_query(lambda callback: callback.data.startswith("paid_notify_"))
async def paid_notify_callback(callback: types.CallbackQuery):
    await callback.answer()

    # Извлекаем информацию об оплате
    parts = callback.data.split("_")
    time_months = int(parts[2])
    price_rubles = int(parts[3])
    
    # Формируем текст времени
    months_text = "год" if time_months == 12 else f"{time_months} месяц{'а' if time_months > 1 and time_months < 5 else 'ев'}"
    await callback.message.edit_text(f'<tg-emoji emoji-id="5386367538735104399">✅</tg-emoji> Ожидайте подтверждения оплаты от оператора', parse_mode=ParseMode.HTML)
    # Создаем клавиатуру для оператора
    operator_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
                [InlineKeyboardButton(text="Подтвердить", callback_data=f"approve_payment_{callback.from_user.id}_{time_months}_{price_rubles}", style="primary")],
                [InlineKeyboardButton(text="Отклонить", callback_data=f"reject_payment_{callback.from_user.id}_{time_months}_{price_rubles}", style="danger")]
            ]
        )
    
    await bot.send_message(
        chat_id=OPERATOR_CHAT_ID,
        text=(
            f"<tg-emoji emoji-id='5416081784641168838'>✅</tg-emoji> <b>Уведомление об оплате</b>\n\n"
            f"👤 Пользователь: @{callback.from_user.username}\n"
            f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Период: {months_text}\n"
            f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Сумма: {price_rubles}₽\n\n"
            "Проверьте оплату и подтвердите:"
        ),
        reply_markup=operator_keyboard,
        parse_mode=ParseMode.HTML
    )

@router.callback_query(lambda callback: callback.data.startswith("approve_payment_"))
async def approve_payment_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    # Извлекаем информацию
    parts = callback.data.split("_")
    user_id = int(parts[2])
    time_months = int(parts[3])
    price_rubles = int(parts[4])
    
    # Рассчитываем дату окончания подписки
    current_time = datetime.datetime.now()
    end_time = current_time + datetime.timedelta(days=time_months * 31)
    end_timestamp = int(end_time.timestamp() * 1000)  # Конвертируем в миллисекунды
    
    # Формируем дату в читаемом формате
    end_date_str = end_time.strftime("%d.%m.%Y")
    
    await bot.send_message(
        chat_id=user_id,
        text=(
            f"<tg-emoji emoji-id='5416081784641168838'>✅</tg-emoji> <b>Оплата подтверждена</b>\n\n"
            f"👤 Пользователь ID: {user_id}\n"
            f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Период: {time_months} мес.\n"
            f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Сумма: {price_rubles}₽\n"
            f"<tg-emoji emoji-id='5440621591387980068'>📅</tg-emoji> Действует до: {end_date_str}\n\n"
            "Подписка активирована! 🎉"
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Моя подписка", callback_data="subscription", style="primary", icon_custom_emoji_id='5296369303661067030')]
            ]
        ),
        parse_mode=ParseMode.HTML
    )
    
    # Добавляем клиента в систему
    try:
        # Конвертируем дату в формат ДД.ММ.ГГГГ для API
        api_date = end_time.strftime("%d.%m.%Y")
        result = add_client(21, f"user_{user_id}", user_id, api_date)
        print(f"Client added: {result}")
    except Exception as e:
        print(f"Error adding client: {e}")

@router.callback_query(lambda callback: callback.data.startswith("reject_payment_"))
async def reject_payment_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    # Извлекаем информацию
    parts = callback.data.split("_")
    user_id = int(parts[2])
    time_months = int(parts[3])
    price_rubles = int(parts[4])
    
    await callback.message.answer(
        f"<tg-emoji emoji-id='5411225014148014586'>❌</tg-emoji> <b>Оплата отклонена</b>\n\n"
        f"👤 Пользователь ID: {user_id}\n"
        f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Период: {time_months} мес.\n"
        f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Сумма: {price_rubles}₽\n\n"
        "Оплата не подтверждена. Свяжитесь с поддержкой.", parse_mode=ParseMode.HTML
    )

@router.callback_query(lambda callback: callback.data == "contact")
async def contact_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    # Получаем контакты из БД
    contact_info = await get_contact()
    
    await callback.message.answer(
        f"{contact_info}",
        parse_mode=ParseMode.HTML
    )

@router.callback_query(lambda callback: callback.data == "info")
async def info_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    # Получаем информацию из БД
    info_text = await get_info()
    
    await callback.message.answer(
        f"{info_text}",
        parse_mode=ParseMode.HTML
    )

@router.callback_query(lambda callback: callback.data == "admin_panel")
async def admin_panel_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    if is_admin(callback.from_user.id):
        try:
            await callback.message.delete()
        except:
            pass
        
        await callback.message.answer(
            "⚙️ <b>Админ панель</b>\n\n"
            "Выберите действие:",
            reply_markup=admin_keyboard,
            parse_mode=ParseMode.HTML
        )

@router.callback_query(lambda callback: callback.data == "admin_prices")
async def admin_prices_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    if is_admin(callback.from_user.id):
        try:
            await callback.message.delete()
        except:
            pass
            
        prices = await get_all_prices()
        
        # Формируем список цен
        prices_text = "💰 <b>Текущие цены:</b>\n\n"
        for price in prices:
            months_text = "год" if price.time == 12 else f"{price.time} месяц{'а' if price.time > 1 and price.time < 5 else 'ев'}"
            prices_text += f"• {months_text}: {price.price}₽\n"
        
        await callback.message.answer(
            prices_text + "\n\nВыберите действие:",
            reply_markup=prices_management_keyboard,
            parse_mode=ParseMode.HTML
        )

@router.callback_query(lambda callback: callback.data == "admin_info")
async def admin_info_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    if is_admin(callback.from_user.id):
        try:
            await callback.message.delete()
        except:
            pass
            
        info_text = await get_info()
        print(info_text)
        await callback.message.answer(
            f'📝 <b>Текущая информация:</b>\n\n{info_text}\n\nВыберите действие:',
            reply_markup=info_management_keyboard,
            parse_mode=ParseMode.HTML
        )

@router.callback_query(lambda callback: callback.data == "admin_contacts")
async def admin_contacts_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    if is_admin(callback.from_user.id):
        try:
            await callback.message.delete()
        except:
            pass
            
        contact_text = await get_contact()
        await callback.message.answer(
            f"📞 <b>Текущие контакты:</b>\n\n{contact_text}\n\nВыберите действие:",
            reply_markup=contacts_management_keyboard,
            parse_mode=ParseMode.HTML
        )

@router.callback_query(lambda callback: callback.data == "edit_info")
async def edit_info_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    if is_admin(callback.from_user.id):
        # Устанавливаем состояние редактирования информации
        admin_states[callback.from_user.id] = "editing_info"
        
        await callback.message.answer(
            "📝 <b>Редактирование информации</b>\n\n"
            "Отправьте новое сообщение для информации.\n"
            "Можно использовать эмодзи и форматирование.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_info", style="primary")]
                ]
            ),
            parse_mode=ParseMode.HTML
        )

@router.callback_query(lambda callback: callback.data == "edit_contacts")
async def edit_contacts_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    if is_admin(callback.from_user.id):
        # Устанавливаем состояние редактирования контактов
        admin_states[callback.from_user.id] = "editing_contacts"
        
        try:
            await callback.message.delete()
        except:
            pass
            
        await callback.message.answer(
            "📞 <b>Редактирование контактов</b>\n\n"
            "Отправьте новое сообщение для контактов.\n"
            "Можно использовать эмодзи и форматирование.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_contacts", style="primary")]
                ]
            ),
            parse_mode=ParseMode.HTML
        )

@router.callback_query(lambda callback: callback.data == "add_price")
async def add_price_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    if is_admin(callback.from_user.id):
        try:
            await callback.message.delete()
        except:
            pass
            
        await callback.message.answer(
            "➕ <b>Добавление цены</b>\n\n"
            "Отправьте в формате:\n"
            "<code>месяцы цена</code>\n\n"
            "Например: <code>3 500</code>",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_prices", style="primary"),
                     InlineKeyboardButton(text="➕ Добавить", callback_data="add_price_confirm", style="primary")]
                ]
            ),
            parse_mode=ParseMode.HTML
        )

@router.callback_query(lambda callback: callback.data == "edit_price")
async def edit_price_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    if is_admin(callback.from_user.id):
        try:
            await callback.message.delete()
        except:
            pass
            
        await callback.message.answer(
            "✏️ <b>Изменение цены</b>\n\n"
            "Отправьте в формате:\n"
            "<code>месяцы новая_цена</code>\n\n"
            "Например: <code>3 600</code>",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_prices", style="primary"),
                     InlineKeyboardButton(text="✏️ Изменить", callback_data="edit_price_confirm", style="primary")]
                ]
            ),
            parse_mode=ParseMode.HTML
        )

@router.callback_query(lambda callback: callback.data == "delete_price")
async def delete_price_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    if is_admin(callback.from_user.id):
        try:
            await callback.message.delete()
        except:
            pass
            
        await callback.message.answer(
            "🗑️ <b>Удаление цены</b>\n\n"
            "Отправьте количество месяцев для удаления:\n\n"
            "Например: <code>3</code>",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_prices", style="primary"),
                     InlineKeyboardButton(text="🗑️ Удалить", callback_data="delete_price_confirm", style="primary")]
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_prices", style="primary")]
                ]
            ),
            parse_mode=ParseMode.HTML
        )

# Глобальное хранилище состояний админа
admin_states = {}

@router.message()
async def handle_admin_messages(message: types.Message):
    """Обработка сообщений от админа для редактирования"""
    if is_admin(message.from_user.id):
        # Если это текстовое сообщение и не команда
        if message.text and not message.text.startswith('/'):
            text_parts = message.text.strip().split()
            
            # Сначала проверяем состояние админа
            user_id = message.from_user.id
            state = admin_states.get(user_id)
            
            if state == "editing_info":
                # Очищаем и исправляем текст от неправильных эмодзи перед сохранением
                clean_text = message.html_text  # Получаем текст с HTML-тегами
                
                # Исправляем неправильные теги <tg-emoji> на правильные
                # Заменяем emoji_id на emoji-id
                clean_text = clean_text.replace('emoji_id=', 'emoji-id=')
                
                # Обновляем только информацию
                await create_or_update_info(clean_text)
                await message.answer(
                    "✅ <b>Информация обновлена!</b>\n\n"
                    f"<b>Новый текст:</b>\n{clean_text}",
                    parse_mode=ParseMode.HTML
                )
                # Сбрасываем состояние
                admin_states[user_id] = None
                
                # Удаляем исходное сообщение через небольшую задержку
                await asyncio.sleep(1)
                try:
                    await message.delete()
                except:
                    pass
                    
            elif state == "editing_contacts":
                # Очищаем и исправляем текст от неправильных эмодзи перед сохранением
                clean_text = message.html_text  # Получаем текст с HTML-тегами
                
                # Исправляем неправильные теги <tg-emoji> на правильные
                # Заменяем emoji_id на emoji-id
                clean_text = clean_text.replace('emoji_id=', 'emoji-id=')
                
                # Обновляем только контакты
                await create_or_update_contact(clean_text)
                await message.answer(
                    "✅ <b>Контакты обновлены!</b>\n\n"
                    f"<b>Новый текст:</b>\n{clean_text}",
                    parse_mode=ParseMode.HTML
                )
                # Сбрасываем состояние
                admin_states[user_id] = None
                
                # Удаляем исходное сообщение через небольшую задержку
                await asyncio.sleep(1)
                try:
                    await message.delete()
                except:
                    pass
            
            # Если нет состояния, обрабатываем цены и прочее
            else:
                # Обработка добавления цены
                if len(text_parts) == 2 and text_parts[0].isdigit() and text_parts[1].isdigit():
                    months = int(text_parts[0])
                    price = int(text_parts[1])
                    await set_price(months, price)
                    await message.answer(
                        f"✅ <b>Цена добавлена!</b>\n\n"
                        f"📅 Период: {months} мес.\n"
                        f"💰 Цена: {price}₽",
                        parse_mode=ParseMode.HTML
                    )
                
                # Обработка изменения цены
                elif len(text_parts) == 2 and text_parts[0].isdigit() and text_parts[1].isdigit():
                    months = int(text_parts[0])
                    price = int(text_parts[1])
                    await set_price(months, price)
                    await message.answer(
                        f"✅ <b>Цена обновлена!</b>\n\n"
                        f"📅 Период: {months} мес.\n"
                        f"💰 Новая цена: {price}₽",
                        parse_mode=ParseMode.HTML
                    )
                
                # Обработка удаления цены
                elif len(text_parts) == 1 and text_parts[0].isdigit():
                    months = int(text_parts[0])
                    # Здесь нужно добавить функцию удаления цены
                    await message.answer(
                        f"🗑️ <b>Удаление цены для {months} месяцев</b>\n\n"
                        "Функция удаления будет добавлена позже.",
                        parse_mode=ParseMode.HTML
                    )
                
                # Иначе считаем что это текст для информации по умолчанию
                else:
                    # Очищаем и исправляем текст от неправильных эмодзи перед сохранением
                    clean_text = message.html_text  # Получаем текст с HTML-тегами
                    
                    # Исправляем неправильные теги <tg-emoji> на правильные
                    # Заменяем emoji_id на emoji-id
                    clean_text = clean_text.replace('emoji_id=', 'emoji-id=')
                    
                    # По умолчанию обновляем информацию
                    await create_or_update_info(clean_text)
                    await message.answer(
                        "✅ <b>Информация обновлена!</b>\n\n"
                        f"<b>Новый текст:</b>\n{clean_text}",
                        parse_mode=ParseMode.HTML
                    )
                    
                    # Удаляем исходное сообщение через небольшую задержку
                    await asyncio.sleep(1)
                    try:
                        await message.delete()
                    except:
                        pass

async def main():
    await create_tables()

    
    # Запуск бота
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)
    






if __name__ == "__main__":
    import asyncio
    asyncio.run(main())


