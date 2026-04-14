import asyncio
import datetime
import json
import os
import re
import sys
import time
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery
from botlogic import payment_keyboard 
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton
from sqlalchemy import create_engine, Column, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker, declarative_base
from sqlalchemy.exc import IntegrityError

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardMarkup, InlineKeyboardButton

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api import add_client, getSubById, check_cantfree, add_to_cantfree, dell_client, get_clients, renew_subscription, convert_timestamp_to_human_readable
from api_sheets import add_vpn_sale
from payment_api import create_paycore_payment, get_payment_status, set_bot_instance, update_payment_message_id
from config import subscription_api_base_url, PANEL_DOMAIN

OPERATOR_CHAT_ID = 1240656726

API_BASE_URL = subscription_api_base_url()

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
    __tablename__ = 'prices'
    id = Column(Integer, primary_key=True, index=True)
    time = Column(Integer, nullable=False)
    price = Column(Integer, nullable=False)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    registered_at = Column(String, nullable=False)
    last_active = Column(String, nullable=True)

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
        
        # Если в БД нет цен, добавляем тестовые
        if not prices:
            default_prices = [
                {"time": 1, "price": 150},
                {"time": 3, "price": 425},
                {"time": 6, "price": 720},
                {"time": 12, "price": 1260}
            ]
            
            for price_data in default_prices:
                new_price = Price(
                    time=price_data["time"],
                    price=price_data["price"]
                )
                session.add(new_price)
            
            await session.commit()
            
            # Повторно получаем цены
            result = await session.execute(select(Price).order_by(Price.time))
            prices = result.scalars().all()
        
        return prices

# Асинхронная функция для получения цены по времени
async def get_price(time_months: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Price).filter(Price.time == time_months))
        price_record = result.scalar_one_or_none()
        return price_record.price if price_record else None

# Асинхронная функция для добавления/обновления пользователя
async def add_or_update_user(user: types.User):
    async with AsyncSessionLocal() as session:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            # Ищем пользователя с указанным telegram_id
            result = await session.execute(select(User).filter(User.telegram_id == user.id))
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                # Если пользователь существует, обновляем его данные и время последней активности
                existing_user.username = user.username
                existing_user.first_name = user.first_name
                existing_user.last_name = user.last_name
                existing_user.last_active = current_time
                await session.commit()
                await session.refresh(existing_user)
                return existing_user
            else:
                # Если пользователя нет, создаем нового
                new_user = User(
                    telegram_id=user.id,
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    registered_at=current_time,
                    last_active=current_time
                )
                session.add(new_user)
                await session.commit()
                await session.refresh(new_user)
                return new_user
                
        except IntegrityError:
            # Пользователь уже был создан (race condition) - обновляем его
            await session.rollback()
            result = await session.execute(select(User).filter(User.telegram_id == user.id))
            existing_user = result.scalar_one_or_none()
            if existing_user:
                existing_user.username = user.username
                existing_user.first_name = user.first_name
                existing_user.last_name = user.last_name
                existing_user.last_active = current_time
                await session.commit()
                await session.refresh(existing_user)
            return existing_user

# Асинхронная функция для получения всех пользователей
async def get_all_users():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        return users

# Асинхронная функция для рассылки сообщения всем пользователям
async def get_subscription_info(user_tg_id: int):
    """Получает информацию о подписке пользователя"""
    try:
        result = getSubById(user_tg_id)
        
        if result.get('success'):
            client_info = result.get('client_info', {})
            expiry_time = client_info.get('expiryTime', 0)
            
            # Конвертируем timestamp в читаемый формат
            expiry_date = convert_timestamp_to_human_readable(expiry_time)
            
            # Проверяем активна ли подписка
            current_time = datetime.datetime.now()
            if expiry_time > 0:
                expiry_datetime = datetime.datetime.fromtimestamp(expiry_time / 1000)
                is_active = expiry_datetime > current_time
            else:
                is_active = False
            
            if is_active:
                return (
                    f"<tg-emoji emoji-id='5416081784641168838'>✅</tg-emoji> <b>Подписка активна</b>\n\n"
                    f"<tg-emoji emoji-id='5440621591387980068'>📅</tg-emoji> Дата окончания: <b>{expiry_date}</b>\n"
                    f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Трафик: безлимитный",
                    "has_subscription"
                )
            else:
                return (
                    f"<tg-emoji emoji-id='5411225014148014586'>❌</tg-emoji> <b>Подписка истекла</b>\n\n"
                    f"<tg-emoji emoji-id='5440621591387980068'>📅</tg-emoji> Дата окончания: <b>{expiry_date}</b>\n"
                    f"<tg-emoji emoji-id='5416081784641168838'>🔄</tg-emoji> Продлите подписку для продолжения использования.",
                    "no_subscription"
                )
        else:
            return (
                f"<tg-emoji emoji-id='5411225014148014586'>❌</tg-emoji> <b>Подписка не найдена</b>\n\n"
                f"<tg-emoji emoji-id='5416081784641168838'>🛒</tg-emoji> Оформите подписку для использования VPN.",
                "no_subscription"
            )
    except Exception as e:
        return (
            f"<tg-emoji emoji-id='5411225014148014586'>⚠️</tg-emoji> <b>Ошибка проверки подписки</b>\n\n"
            f"Попробуйте позже или обратитесь в поддержку.",
            "error"
        )

async def broadcast_to_all_users(message_text: str):
    users = await get_all_users()
    success_count = 0
    error_count = 0
    
    for user in users:
        try:
            await bot.send_message(
                user.telegram_id,
                message_text,
                parse_mode=ParseMode.HTML
            )
            success_count += 1
            
            # Небольшая задержка чтобы не превысить лимиты Telegram
            await asyncio.sleep(0.1)
            
        except Exception as e:
            error_count += 1
    
    return {"success": success_count, "errors": error_count}

# Код бота
TOKEN = "8358697144:AAGppsqXjG9S08nGLUpghL-jUfTz9H4gj58"

bot = Bot(token=TOKEN)
router = Router()

# Инициализация планировщика
scheduler = AsyncIOScheduler()

# Словарь для отслеживания отправленных напоминаний
sent_reminders = {}  # {tg_id: {"day": timestamp, "hour": timestamp}

# Словарь для отслеживания рефералов
referral_bonus_given = {}  # {tg_id: True}

async def handle_referral_bonus(user_id: int, referrer_id: int):
    """Обрабатывает реферальный бонус"""
    try:
        # Проверяем, не получал ли реферер уже бонус за этого пользователя
        if referrer_id in referral_bonus_given:
            return
        
        # Проверяем подписку реферала
        subscription_info, status = await get_subscription_info(referrer_id)
        
        if status == "has_subscription":
            # У реферала есть подписка - добавляем 2 дня к подписке реферала
            await add_referral_days_to_user(referrer_id, 2)
            
            # Отправляем уведомление рефералу
            await bot.send_message(
                referrer_id,
                f"<tg-emoji emoji-id='5416081784641168838'>🎉</tg-emoji> <b>Поздравляем! Вы получили бонус!</b>\n\n"
                f"По вашей ссылке зарегистрировался новый пользователь.\n"
                f"<tg-emoji emoji-id='5440621591387980068'>🎁</tg-emoji> Вам начислено: <b>2 дня</b> к подписке!\n\n"
                "Спасибо за привлечение новых пользователей! 🚀",
                parse_mode=ParseMode.HTML
            )
            
            # Отправляем уведомление новому пользователю
            await bot.send_message(
                user_id,
                f"<tg-emoji emoji-id='5416081784641168838'>🎉</tg-emoji> <b>Добро пожаловать!</b>\n\n"
                f"Вы перешли по реферальной ссылке.\n"
                f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Ваш реферер получил бонус за вашу регистрацию!\n\n"
                "Спасибо, что выбрали наш сервис! 🚀",
                parse_mode=ParseMode.HTML
            )
            
        else:
            # У реферала нет подписки - даем подписку на 2 дня рефералу
            await add_referral_days_to_user(referrer_id, 2)
            
            # Отправляем уведомление рефералу
            await bot.send_message(
                referrer_id,
                f"<tg-emoji emoji-id='5416081784641168838'>🎉</tg-emoji> <b>Поздравляем! Вы получили бонус!</b>\n\n"
                f"По вашей ссылке зарегистрировался новый пользователь.\n"
                f"<tg-emoji emoji-id='5440621591387980068'>🎁</tg-emoji> Вам начислена подписка на <b>2 дня</b>!\n\n"
                "Спасибо за привлечение новых пользователей! 🚀",
                parse_mode=ParseMode.HTML
            )
            
            # Отправляем уведомление новому пользователю
            await bot.send_message(
                user_id,
                f"<tg-emoji emoji-id='5416081784641168838'>🎉</tg-emoji> <b>Добро пожаловать!</b>\n\n"
                f"Вы перешли по реферальной ссылке.\n"
                f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Ваш реферер получил бонус за вашу регистрацию!\n\n"
                "Спасибо, что выбрали наш сервис! 🚀",
                parse_mode=ParseMode.HTML
            )
        
        # Помечаем, что бонус выдан рефереру
        referral_bonus_given[referrer_id] = True
        
    except Exception as e:
        pass

async def add_referral_days_to_user(user_id: int, days: int):
    """Добавляет дни к подписке пользователя или создает новую подписку"""
    try:
        # Проверяем, есть ли у пользователя уже подписка
        result = getSubById(user_id)
        
        if result.get('success'):
            # У пользователя есть подписка - продлеваем
            current_expiry = result.get('client_info', {}).get('expiryTime', 0)
            if current_expiry:
                # Добавляем 2 дня (48 часов в миллисекундах)
                new_expiry = current_expiry + (days * 24 * 60 * 60 * 1000)
                
                # Обновляем клиента с новым временем
                email = result.get('client_info', {}).get('email', f'user_{user_id}')
                renew_result = renew_subscription(user_id, days)
                
                if renew_result.get('success'):
                    pass
                else:
                    pass
        else:
            # У пользователя нет подписки - создаем новую на 2 дня
            current_time = datetime.datetime.now()
            end_time = current_time + datetime.timedelta(days=days)
            api_date = end_time.strftime("%d.%m.%Y")
            
            add_result = add_client(21, f"user_{user_id}", user_id, api_date)
            pass
    except Exception as e:
        pass

async def check_subscription_expirations():
    """Проверяет истечение подписок и отправляет напоминания"""
    try:
        # Получаем всех клиентов
        clients_data = get_clients()
        
        if not clients_data.get('success'):
            return
        
        inbounds = clients_data.get('obj', [])
        current_time = datetime.datetime.now()
        
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
                        tg_id = client.get('tgId')
                        expiry_time = client.get('expiryTime')
                        
                        if not tg_id or not expiry_time:
                            continue
                        
                        # Конвертируем время из миллисекунд в datetime
                        expiry_date = datetime.datetime.fromtimestamp(expiry_time / 1000)
                        time_left = expiry_date - current_time
                        
                        # Получаем информацию о ранее отправленных напоминаниях
                        user_reminders = sent_reminders.get(tg_id, {})
                        
                        # Проверяем разные интервалы времени
                        if datetime.timedelta(hours=22) <= time_left <= datetime.timedelta(hours=25):
                            # Осталось 1 день (22-25 часов)
                            last_day_reminder = user_reminders.get("day", 0)
                            
                            # Проверяем, не отправляли ли когда-либо напоминание за день
                            if last_day_reminder == 0:
                                await send_expiration_reminder(tg_id, "day", expiry_date)
                                # Обновляем время отправки напоминания
                                if tg_id not in sent_reminders:
                                    sent_reminders[tg_id] = {}
                                sent_reminders[tg_id]["day"] = current_time.timestamp()
                                
                        elif datetime.timedelta(minutes=30) <= time_left <= datetime.timedelta(hours=2):
                            # Осталось 1 час (30 минут - 2 часа)
                            last_hour_reminder = user_reminders.get("hour", 0)
                            
                            # Проверяем, не отправляли ли когда-либо напоминание за час
                            if last_hour_reminder == 0:
                                await send_expiration_reminder(tg_id, "hour", expiry_date)
                                # Обновляем время отправки напоминания
                                if tg_id not in sent_reminders:
                                    sent_reminders[tg_id] = {}
                                sent_reminders[tg_id]["hour"] = current_time.timestamp()
    except Exception as e:
        pass

async def send_expiration_reminder(tg_id: int, reminder_type: str, expiry_date: datetime.datetime):
    """Отправляет напоминание об окончании подписки"""
    try:
        if reminder_type == "day":
            message_text = (
                f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> <b>Напоминание об окончании подписки</b>\n\n"
                f"Ваша подписка заканчивается завтра!\n"
                f"<tg-emoji emoji-id='5440621591387980068'>📅</tg-emoji> Дата окончания: {expiry_date.strftime('%d.%m.%Y')}\n\n"
                "Не забудьте продлить подписку, чтобы избежать перерывов в работе VPN.\n\n"
                "Для продления нажмите кнопку ниже:"
            )
            reply_markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Продлить подписку", callback_data="renew_subscription", style="primary")]
                ]
            )
            
        elif reminder_type == "hour":
            message_text = (
                f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> <b>СРОЧНО! Подписка заканчивается!</b>\n\n"
                f"Ваша подписка заканчивается в течение часа!\n"
                f"<tg-emoji emoji-id='5440621591387980068'>📅</tg-emoji> Дата окончания: {expiry_date.strftime('%d.%m.%Y %H:%M')}\n\n"
                "Продлите подписку прямо сейчас, чтобы VPN продолжил работать!"
            )
            reply_markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Продлить подписку", callback_data="renew_subscription", style="primary")]
                ]
            )
        
        await bot.send_message(
            tg_id, 
            text=message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        pass

# Проверка на админа
def is_admin(user_id: int) -> bool:
    return user_id == OPERATOR_CHAT_ID

# Создаем inline кнопки
subscription_btn = InlineKeyboardButton(text="Подписка", callback_data="subscription", style="primary", icon_custom_emoji_id='5296369303661067030')
contact_btn = InlineKeyboardButton(text="Связь", callback_data="contact", style="primary", icon_custom_emoji_id='5443038326535759644')
info_btn = InlineKeyboardButton(text="Информация", callback_data="info", style="primary", icon_custom_emoji_id='5282843764451195532')
instruction_btn = InlineKeyboardButton(
    text="Инструкция и приложение",
    url=f"https://{PANEL_DOMAIN}/vpn_bot/index.html",
    style="success",
    icon_custom_emoji_id='5282843764451195532',
)
app_btn = InlineKeyboardButton(text="Приложение", callback_data="app", style="primary")
buy_subscription_btn = InlineKeyboardButton(text="Купить подписку", callback_data="buy_subscription", style="primary", icon_custom_emoji_id='5271604874419647061')
referral_btn = InlineKeyboardButton(text="Реферальная программа", callback_data="referral", style="primary", icon_custom_emoji_id='5416081784641168838')
admin_btn = InlineKeyboardButton(text="⚙️ Админ панель", callback_data="admin_panel", style="secondary")

# Создаем inline клавиатуру (кнопки в разных строках)
keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        # [instruction_btn],      # Четвертая строка
        [subscription_btn],      # Первая строка                
        [contact_btn],          # Вторая строка  
        [info_btn],             # Третья строка

        [referral_btn]        # Пятая строка - реферальная программа
    ]
)

# Админ клавиатура
admin_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💰 Цены", callback_data="admin_prices", style="primary")],
        [InlineKeyboardButton(text="📝 Информация", callback_data="admin_info", style="primary")],
        [InlineKeyboardButton(text="📞 Контакты", callback_data="admin_contacts", style="primary")],
        [InlineKeyboardButton(text="👤 Добавить клиента", callback_data="admin_add_client", style="primary")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast", style="primary")],
        [InlineKeyboardButton(text="�️ Удалить из CantFree", callback_data="admin_remove_cantfree", style="primary")],
        [InlineKeyboardButton(text="� Назад", callback_data="back_to_main", style="primary")]
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
    # Добавляем/обновляем пользователя в базе данных
    await add_or_update_user(message.from_user)
    
    # Проверяем, есть ли реферальный параметр
    args = message.text.split()
    referrer_id = None
    
    if len(args) > 1 and args[1].isdigit():
        referrer_id = int(args[1])
    
    if is_admin(message.from_user.id):
        await message.answer(
            "⚙️ <b>Админ панель</b>\n\n"
            "Выберите действие:",
            reply_markup=admin_keyboard,
            parse_mode=ParseMode.HTML
        )
    else:
        # Если есть реферал, даем бонус
        if referrer_id and referrer_id != message.from_user.id:
            await handle_referral_bonus(message.from_user.id, referrer_id)
        
        await message.answer(
            "Привет! Я бот для управления VPN.\n\n"
            "Выберите одну из опций ниже:",
            reply_markup=keyboard
        )

@router.message(Command("referral"))
async def referral_command(message: types.Message):
    """Отправляет реферальную ссылку пользователю"""
    if is_admin(message.from_user.id):
        return
    
    # Создаем реферальную ссылку
    bot_username = (await bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={message.from_user.id}"
    
    await message.answer(
        f"<tg-emoji emoji-id='5416081784641168838'>🔗</tg-emoji> <b>Ваша реферальная ссылка</b>\n\n"
        f"<code>{referral_link}</code>\n\n"
        f"<tg-emoji emoji-id='5440621591387980068'>🎁</tg-emoji> <b>Условия бонуса:</b>\n"
        f"• Если у вас есть подписка - вам добавится <b>2 дня</b> к подписке\n"
        f"• Если у вас нет подписки - вам дается подписка на <b>2 дня</b>\n\n"
        "Бонус начисляется ВАМ за каждого нового пользователя, перешедшего по вашей ссылке!\n"
        "Делитесь ссылкой и получайте бонусы! 🚀",
        parse_mode=ParseMode.HTML
    )

async def remove_from_cantfree_local(user_id: int):
    """Удаляет пользователя из списка CantFree"""
    async with AsyncSessionLocal() as session:
        try:
            # Ищем пользователя в таблице CantFree
            result = await session.execute(
                select(CantFree).where(CantFree.user_id == user_id)
            )
            cantfree_user = result.scalar_one_or_none()
            
            if cantfree_user:
                # Удаляем пользователя
                await session.delete(cantfree_user)
                await session.commit()
                return {"success": True, "message": f"Пользователь {user_id} удален из CantFree"}
            else:
                return {"success": False, "message": f"Пользователь {user_id} не найден в CantFree"}
        except Exception as e:
            await session.rollback()
            return {"success": False, "error": str(e)}

async def add_to_cantfree_local(user_id: int, username: str):
    """Добавляет пользователя в список CantFree"""
    async with AsyncSessionLocal() as session:
        try:
            # Создаем новую запись в CantFree
            new_cantfree = CantFree(
                user_id=user_id,
                username=username,
                registered_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                last_active=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            session.add(new_cantfree)
            await session.commit()
            return {"success": True, "message": f"Пользователь {user_id} добавлен в CantFree"}
        except Exception as e:
            await session.rollback()
            return {"success": False, "error": str(e)}

@router.message(Command("add_client"))
async def add_client_command(message: types.Message):
    """Добавляет клиента по TG ID (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    
    # Получаем аргументы команды
    args = message.text.split()
    
    if len(args) < 2:
        await message.answer(
            "👤 <b>Добавление клиента</b>\n\n"
            "Использование:\n"
            "<code>/add_client TG_ID [месяцы]</code>\n"
            "<code>/add_client TG_ID [дата]</code>\n\n"
            "Примеры:\n"
            "<code>/add_client 8489038592</code> - на 1 месяц\n"
            "<code>/add_client 8489038592 3</code> - на 3 месяца\n"
            "<code>/add_client 8489038592 31.12.2024</code> - до 31.12.2024\n\n"
            "Или просто отправьте TG ID пользователя сообщением.",
            parse_mode=ParseMode.HTML
        )
        return
    
    tg_id = args[1]
    months = 1  # по умолчанию
    end_date = None
    
    if len(args) >= 3:
        param = args[2]
        # Проверяем, это дата или количество месяцев
        if '.' in param and len(param.split('.')) == 3:
            # Это дата в формате ДД.ММ.ГГГГ
            try:
                day, month, year = param.split('.')
                if len(day) == 1:
                    day = '0' + day
                if len(month) == 1:
                    month = '0' + month
                if len(year) == 2:
                    year = '20' + year
                
                # Валидация даты
                import datetime
                datetime.datetime.strptime(f'{day}.{month}.{year}', '%d.%m.%Y')
                end_date = f'{day}.{month}.{year}'
            except ValueError:
                await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ (например: 31.12.2024)")
                return
        else:
            # Это количество месяцев
            try:
                months = int(param)
            except ValueError:
                months = 1
    
    try:
        tg_id = int(tg_id)
    except ValueError:
        await message.answer("❌ Неверный формат Telegram ID. Используйте только цифры.")
        return
    
    # Показываем статус добавления
    status_message = await message.answer(f"🔄 Добавляю клиента TG ID: {tg_id}...")
    
    try:
        import requests
        
        # Готовим данные для API
        api_data = {
            "tg_id": tg_id
        }
        
        if end_date:
            api_data["end_date"] = end_date
            status_text = f"до {end_date}"
        else:
            api_data["months"] = months
            status_text = f"на {months} месяц{'ев' if months > 1 and months < 5 else 'ев' if months > 4 else ''}"
        
        # Вызываем API endpoint
        response = requests.post(
            f"{API_BASE_URL}/admin/add_client",
            json=api_data,
            verify=False,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('success'):
                await status_message.edit_text(
                    f"✅ <b>Клиент успешно добавлен!</b>\n\n"
                    f"👤 Telegram ID: <code>{tg_id}</code>\n"
                    f"📅 Период: <b>{status_text}</b>\n"
                    f"📝 Username: <code>{result.get('username', 'N/A')}</code>\n"
                    f"🔑 SubID: <code>{result.get('subId', 'N/A')}</code>\n"
                    f"📅 Дата окончания: <b>{result.get('end_date', 'N/A')}</b>",
                    parse_mode=ParseMode.HTML
                )
            else:
                await status_message.edit_text(
                    f"❌ <b>Ошибка при добавлении клиента</b>\n\n"
                    f"👤 Telegram ID: <code>{tg_id}</code>\n"
                    f"🔍 Ошибка: <code>{result.get('error', 'Unknown error')}</code>",
                    parse_mode=ParseMode.HTML
                )
        else:
            await status_message.edit_text(
                f"❌ <b>Ошибка API</b>\n\n"
                f"👤 Telegram ID: <code>{tg_id}</code>\n"
                f"🔍 Status: <code>{response.status_code}</code>\n"
                f"📝 Response: <code>{response.text[:200]}</code>",
                parse_mode=ParseMode.HTML
            )
            
    except Exception as e:
        await status_message.edit_text(
            f"❌ <b>Критическая ошибка</b>\n\n"
            f"👤 Telegram ID: <code>{tg_id}</code>\n"
            f"🔍 Ошибка: <code>{str(e)}</code>",
            parse_mode=ParseMode.HTML
        )

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
                    [InlineKeyboardButton(text="Использовать", url=f"https://www.ezhqpy.ru/0QmoakBn0d/index.html?name={sub_id}", style="primary", icon_custom_emoji_id='5271604874419647061')],
                    [InlineKeyboardButton(text="Продлить подписку", callback_data="renew_subscription", style="primary", icon_custom_emoji_id='5231012545799666522')],
                    # [instruction_btn],
                    [InlineKeyboardButton(text="Назад", callback_data="main_menu", style="danger")]
                ]
            )
        else:
            subscription_keyboard = None
    elif status == "no_subscription":
        # Проверяем есть ли пользователь в CantFree (локально)
        cantfree_result = check_cantfree(user_tg_id)
        
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
    cantfree_result = check_cantfree(user_tg_id)
    
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
            [InlineKeyboardButton(text="Оплата по СБП", callback_data=f"pay_sbp_{time_months}_{price_rubles}", style="primary")],
            [InlineKeyboardButton(text="Оплатить звездами", callback_data=f"pay_stars_{time_months}_{price_rubles}", style="primary")]
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



@router.callback_query(lambda callback: callback.data == "admin_remove_cantfree")
async def admin_remove_cantfree_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    
    # Запрашиваем TG ID пользователя для удаления
    await callback.message.answer(
        "<tg-emoji emoji-id='5406756500108501710'>🗑️</tg-emoji> <b>Удаление из CantFree</b>\n\n"
        "📝 <b>Отправьте TG ID пользователя для удаления из списка CantFree:</b>\n\n"
        "<code>/remove_cantfree TG_ID</code>\n\n"
        "Или просто отправьте TG ID пользователя сообщением.",
        parse_mode=ParseMode.HTML
    )

@router.message(lambda message: message.text and message.text.startswith('/remove_cantfree'))
async def remove_cantfree_command(message: Message):
    # Проверяем права администратора
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора.")
        return
    
    # Получаем TG ID из команды
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Неверный формат. Используйте: /remove_cantfree TG_ID")
        return
    
    try:
        tg_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный формат TG ID. Используйте только цифры.")
        return
    
    # Показываем статус удаления
    status_message = await message.answer(f"🔄 Удаляю пользователя {tg_id} из CantFree...")
    
    # Удаляем из CantFree
    remove_result = await remove_from_cantfree_local(tg_id)
    
    if remove_result.get("success"):
        await status_message.edit_text(
            f"✅ <b>Пользователь удален из CantFree!</b>\n\n"
            f"👤 TG ID: <code>{tg_id}</code>\n"
            f"📝 Статус: {remove_result.get('message')}",
            parse_mode=ParseMode.HTML
        )
    else:
        await status_message.edit_text(
            f"❌ <b>Ошибка при удалении</b>\n\n"
            f"👤 TG ID: <code>{tg_id}</code>\n"
            f"🔍 Ошибка: <code>{remove_result.get('error', 'Unknown error')}</code>",
            parse_mode=ParseMode.HTML
        )

async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):  
    await pre_checkout_query.answer(ok=True)

async def success_payment_handler(message: Message):
    """Обработчик успешной оплаты звездами"""
    try:
        # Получаем информацию о платеже
        payment_info = message.successful_payment
        payload = payment_info.invoice_payload
        
        # Парсим payload
        parts = payload.split("_")
        if parts[0] == "sub":
            time_months = int(parts[1])
            price_rubles = int(parts[2])
            
            # Отправляем уведомление администратору
            await bot.send_message(
                OPERATOR_CHAT_ID,
                f"<tg-emoji emoji-id='5416081784641168838'>💰</tg-emoji> <b>Новая покупка!</b>\n\n"
                f"👤 Пользователь: @{message.from_user.username} (ID: {message.from_user.id})\n"
                f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Период: {time_months} мес.\n"
                f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Цена: {price_rubles}₽\n"
                f"<tg-emoji emoji-id='5424972470023104089'>⭐</tg-emoji> Оплата: {payment_info.total_amount} {payment_info.currency}\n\n"
                f"<tg-emoji emoji-id='5416081784641168838'>✅</tg-emoji> Покупка успешно завершена!",
                parse_mode=ParseMode.HTML
            )
            
            # Проверяем, есть ли у пользователя уже подписка
            subscription_info, status = await get_subscription_info(message.from_user.id)
            
            if status == "has_subscription":
                # У пользователя есть подписка - продлеваем
                renew_result = renew_subscription(message.from_user.id, time_months)
                
                if renew_result.get('success'):
                    new_expiry = renew_result.get('new_expiry')
                    end_time = datetime.datetime.fromtimestamp(new_expiry / 1000)
                    end_date_str = end_time.strftime("%d.%m.%Y")
                    
                    # Обновляем уведомление администратору о продлении
                    await bot.send_message(
                        OPERATOR_CHAT_ID,
                        f"<tg-emoji emoji-id='5406756500108501710'>🔄</tg-emoji> <b>Подписка продлена!</b>\n\n"
                        f"👤 Пользователь: @{message.from_user.username} (ID: {message.from_user.id})\n"
                        f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Продление на: {time_months} мес.\n"
                        f"<tg-emoji emoji-id='5440621591387980068'>📅</tg-emoji> Новая дата: {end_date_str}\n"
                        f"<tg-emoji emoji-id='5424972470023104089'>⭐</tg-emoji> Оплата: {payment_info.total_amount} {payment_info.currency}",
                        parse_mode=ParseMode.HTML
                    )
                    
                    await message.answer(
                        f"<tg-emoji emoji-id='5416081784641168838'>✅</tg-emoji> <b>Подписка продлена!</b>\n\n"
                        f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Продление на: {time_months} мес.\n"
                        f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Оплачено: {payment_info.total_amount} {payment_info.currency}\n"
                        f"<tg-emoji emoji-id='5440621591387980068'>📅</tg-emoji> Действует до: {end_date_str}\n\n"
                        "Подписка успешно продлена! 🎉",
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[
                                [InlineKeyboardButton(text="Моя подписка", callback_data="subscription", style="primary")]
                            ]
                        ),
                        parse_mode=ParseMode.HTML
                    )
                else:
                    await message.answer(
                        "❌ Ошибка при продлении подписки. Пожалуйста, свяжитесь с поддержкой.",
                        parse_mode=ParseMode.HTML
                    )
            else:
                # У пользователя нет подписки - создаем новую
                current_time = datetime.datetime.now()
                end_time = current_time + datetime.timedelta(days=time_months * 31)
                end_timestamp = int(end_time.timestamp() * 1000)
                
                # Формируем дату в читаемом формате
                end_date_str = end_time.strftime("%d.%m.%Y")
                
                # Добавляем клиента в систему
                try:
                    api_date = end_time.strftime("%d.%m.%Y")
                    result = add_client(21, f"user_{message.from_user.id}", message.from_user.id, api_date)
                    print(f"Client added via stars payment: {result}")
                    
                    # Записываем продажу в Google Sheets
                    add_vpn_sale(message.from_user.id, message.from_user.username, time_months, price_rubles)
                    
                    # Обновляем уведомление администратору о новой подписке
                    await bot.send_message(
                        OPERATOR_CHAT_ID,
                        f"<tg-emoji emoji-id='5416081784641168838'>🆕</tg-emoji> <b>Новая подписка создана!</b>\n\n"
                        f"👤 Пользователь: @{message.from_user.username} (ID: {message.from_user.id})\n"
                        f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Период: {time_months} мес.\n"
                        f"<tg-emoji emoji-id='5440621591387980068'>📅</tg-emoji> Действует до: {end_date_str}\n"
                        f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Цена: {price_rubles}₽\n"
                        f"<tg-emoji emoji-id='5424972470023104089'>⭐</tg-emoji> Оплата: {payment_info.total_amount} {payment_info.currency}",
                        parse_mode=ParseMode.HTML
                    )
                    
                    # Отправляем подтверждение пользователю
                    await message.answer(
                        f"<tg-emoji emoji-id='5416081784641168838'>✅</tg-emoji> <b>Оплата успешно завершена!</b>\n\n"
                        f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Период: {time_months} мес.\n"
                        f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Оплачено: {payment_info.total_amount} {payment_info.currency}\n"
                        f"<tg-emoji emoji-id='5440621591387980068'>📅</tg-emoji> Действует до: {end_date_str}\n\n"
                        "Подписка активирована! 🎉",
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[
                                [InlineKeyboardButton(text="Моя подписка", callback_data="subscription", style="primary")]
                            ]
                        ),
                        parse_mode=ParseMode.HTML
                    )
                    
                except Exception as e:
                    print(f"Error adding client via stars payment: {e}")
                    await message.answer(
                        "❌ Ошибка при активации подписки. Пожалуйста, свяжитесь с поддержкой.",
                        parse_mode=ParseMode.HTML
                    )
        
    except Exception as e:
        print(f"Error processing stars payment: {e}")
        await message.answer(
            "❌ Ошибка при обработке платежа. Пожалуйста, свяжитесь с поддержкой.",
            parse_mode=ParseMode.HTML
        )
    
@router.callback_query(lambda callback: callback.data.startswith("pay_stars_"))
async def pay_stars_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    # Извлекаем данные из callback_data
    parts = callback.data.split("_")
    time_months = int(parts[2])  # "pay_stars_1_200" -> parts[2] = "1"
    price_rubles = int(parts[3])  # "pay_stars_1_200" -> parts[3] = "200"
    

     
    # Формируем цену в звездах (пример: 1 XTR = 1 звезда)
    stars_amount = price_rubles  # Фиксированная цена в звездах
    
    prices = [LabeledPrice(label="XTR", amount=stars_amount)]  
    await callback.message.answer_invoice(  
            title="Покупка подписки",  
            description=f"Покупка подписки на {time_months} месяцев за {stars_amount} звёзд!",  
            prices=prices,  
            provider_token="",  
            payload=f"sub_{time_months}_{price_rubles}",  
            currency="XTR",  
            reply_markup=payment_keyboard(stars_amount),  
        )


@router.callback_query(lambda callback: callback.data.startswith("pay_sbp_"))
async def pay_sbp_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    # Извлекаем данные из callback_data
    parts = callback.data.split("_")
    time_months = int(parts[2])  # "pay_sbp_1_200" -> parts[2] = "1"
    price_rubles = int(parts[3])  # "pay_sbp_1_200" -> parts[3] = "200"
    
    user_id = callback.from_user.id
    username = callback.from_user.username
    
    # Перенаправляем в функцию обработки СБП (доступно всем)
    await process_sbp_payment(callback.message, user_id, username, time_months, price_rubles, is_renewal=False)


async def process_sbp_payment(message, user_id, username, time_months, price_rubles, is_renewal=False):
    """Функция обработки оплаты через СБП через PayCore API
    
    Принимает все необходимые данные для оплаты:
    - user_id: ID пользователя Telegram
    - username: имя пользователя
    - time_months: количество месяцев подписки
    - price_rubles: цена в рублях
    - is_renewal: флаг продления (True/False)
    """
    # Список ID операторов (для специальной цены 1 рубль)
    OPERATOR_IDS = [8489038592, 1401086794]
    
    # Если пользователь - оператор, меняем цену на 1 рубль для тестирования
    if user_id in OPERATOR_IDS:
        price_rubles = 1
        print(f"[BOT] Operator detected, setting test price: 1 ruble")
    
    # Формируем текст времени
    months_text = "год" if time_months == 12 else f"{time_months} месяц{'а' if time_months > 1 and time_months < 5 else 'ев'}"
    
    operation_type = "Продление" if is_renewal else "Покупка"
    
    print(f"[BOT] Starting SBP payment: user={user_id}, amount={price_rubles}, type={operation_type}")
    
    # Создаём платёж через PayCore API
    result = create_paycore_payment(
        amount=float(price_rubles),
        description=f"{operation_type} VPN на {months_text}",
        user_id=user_id,
        username=username,
        time_months=time_months,
        is_renewal=is_renewal
    )
    
    print(f"[BOT] PayCore result: {result}")
    
    if result.get("success"):
        order_id = result.get("order_id")
        payment_url = result.get("payment_url")
        
        # Отправляем пользователю информацию об оплате и сохраняем message_id
        sent_message = await message.answer(
            f"<tg-emoji emoji-id='5345956698253180145'>👤</tg-emoji> <b>Оплата через СБП</b>\n\n"
            f"<tg-emoji emoji-id='5231012545799666522'>👤</tg-emoji> Пользователь: @{username} (ID: {user_id})\n"
            f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Период: {months_text}\n"
            f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Сумма: {price_rubles}₽\n\n"

            "<tg-emoji emoji-id='5440621591387980068'>⏳</tg-emoji> После оплаты подписка будет активирована автоматически.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=f"Перейти к оплате ({price_rubles}₽)", url=payment_url, style="success")]
                ]
            ),
            parse_mode=ParseMode.HTML
        )
        
        # Сохраняем message_id для последующего редактирования
        if sent_message and sent_message.message_id:
            update_payment_message_id(order_id, sent_message.message_id)
            print(f"[BOT] Message ID {sent_message.message_id} saved for order {order_id}")
    else:
        # Ошибка создания платежа
        error_msg = result.get('error', 'Неизвестная ошибка')
        status_code = result.get('status_code', 'N/A')
        full_response = result.get('full_response', {})
        print(f"[BOT] Payment creation FAILED: error='{error_msg}', status={status_code}, full_response={full_response}")
        
        await message.answer(
            f"<tg-emoji emoji-id='5411225014148014586'>❌</tg-emoji> <b>Ошибка создания платежа</b>\n\n"
            f"Не удалось создать платёж: {error_msg}\n\n"
            "Пожалуйста, попробуйте позже или выберите другой способ оплаты.",
            parse_mode=ParseMode.HTML
        )


@router.callback_query(lambda callback: callback.data.startswith("sbp_paid_"))
async def sbp_paid_callback(callback: types.CallbackQuery):
    """Обработчик нажатия кнопки 'Я оплатил' - проверяет статус платежа"""
    
    # Извлекаем order_id из callback_data
    order_id = callback.data.replace("sbp_paid_", "")
    
    # Проверяем статус платежа
    payment_info = get_payment_status(order_id)
    
    if payment_info.get("exists"):
        status = payment_info.get("status")
        
        if status == "completed":
            # Платёж подтверждён - активируем подписку
            try:
                # Получаем информацию о платеже для извлечения данных
                payment_details = get_payment_status(order_id)
                if payment_details.get("exists"):
                    time_months = payment_details.get("time_months", 1)
                    price_rubles = payment_details.get("amount", 0)
                    
                    # Проверяем, есть ли у пользователя уже подписка
                    subscription_info, status = await get_subscription_info(callback.from_user.id)
                    
                    if status == "has_subscription":
                        # У пользователя есть подписка - продлеваем
                        renew_result = renew_subscription(callback.from_user.id, time_months)
                        
                        if renew_result.get('success'):
                            new_expiry = renew_result.get('new_expiry')
                            end_time = datetime.datetime.fromtimestamp(new_expiry / 1000)
                            end_date_str = end_time.strftime("%d.%m.%Y")
                            
                            # Отправляем уведомление администратору о продлении
                            await bot.send_message(
                                OPERATOR_CHAT_ID,
                                f"<tg-emoji emoji-id='5406756500108501710'>🔄</tg-emoji> <b>Подписка продлена (СБП)!</b>\n\n"
                                f"👤 Пользователь: @{callback.from_user.username} (ID: {callback.from_user.id})\n"
                                f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Продление на: {time_months} мес.\n"
                                f"<tg-emoji emoji-id='5440621591387980068'>📅</tg-emoji> Новая дата: {end_date_str}\n"
                                f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Оплата: {price_rubles}₽\n"
                                f"Order ID: <code>{order_id}</code>",
                                parse_mode=ParseMode.HTML
                            )
                            
                            await callback.message.edit_text(
                                f"<tg-emoji emoji-id='5416081784641168838'>✅</tg-emoji> <b>Подписка продлена!</b>\n\n"
                                f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Продление на: {time_months} мес.\n"
                                f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Оплачено: {price_rubles}₽\n"
                                f"<tg-emoji emoji-id='5440621591387980068'>📅</tg-emoji> Действует до: {end_date_str}\n\n"
                                "Подписка успешно продлена! 🎉",
                                reply_markup=InlineKeyboardMarkup(
                                    inline_keyboard=[
                                        [InlineKeyboardButton(text="Моя подписка", callback_data="subscription", style="primary")]
                                    ]
                                ),
                                parse_mode=ParseMode.HTML
                            )
                        else:
                            await callback.message.edit_text(
                                "❌ Ошибка при продлении подписки. Пожалуйста, свяжитесь с поддержкой.",
                                parse_mode=ParseMode.HTML
                            )
                    else:
                        # У пользователя нет подписки - создаем новую
                        current_time = datetime.datetime.now()
                        end_time = current_time + datetime.timedelta(days=time_months * 31)
                        end_timestamp = int(end_time.timestamp() * 1000)
                        
                        # Формируем дату в читаемом формате
                        end_date_str = end_time.strftime("%d.%m.%Y")
                        
                        # Добавляем клиента в систему
                        try:
                            api_date = end_time.strftime("%d.%m.%Y")
                            result = add_client(21, f"user_{callback.from_user.id}", callback.from_user.id, api_date)
                            print(f"Client added via SBP payment: {result}")
                            
                            # Записываем продажу в Google Sheets
                            add_vpn_sale(callback.from_user.id, callback.from_user.username, time_months, price_rubles)
                            
                            # Отправляем уведомление администратору о новой подписке
                            await bot.send_message(
                                OPERATOR_CHAT_ID,
                                f"<tg-emoji emoji-id='5416081784641168838'>🆕</tg-emoji> <b>Новая подписка создана (СБП)!</b>\n\n"
                                f"👤 Пользователь: @{callback.from_user.username} (ID: {callback.from_user.id})\n"
                                f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Период: {time_months} мес.\n"
                                f"<tg-emoji emoji-id='5440621591387980068'>📅</tg-emoji> Действует до: {end_date_str}\n"
                                f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Цена: {price_rubles}₽\n"
                                f"Order ID: <code>{order_id}</code>",
                                parse_mode=ParseMode.HTML
                            )
                            
                            # Отправляем подтверждение пользователю
                            await callback.message.edit_text(
                                f"<tg-emoji emoji-id='5416081784641168838'>✅</tg-emoji> <b>Оплата успешно завершена!</b>\n\n"
                                f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Период: {time_months} мес.\n"
                                f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Оплачено: {price_rubles}₽\n"
                                f"<tg-emoji emoji-id='5440621591387980068'>📅</tg-emoji> Действует до: {end_date_str}\n\n"
                                "Подписка активирована! 🎉",
                                reply_markup=InlineKeyboardMarkup(
                                    inline_keyboard=[
                                        [InlineKeyboardButton(text="Моя подписка", callback_data="subscription", style="primary")]
                                    ]
                                ),
                                parse_mode=ParseMode.HTML
                            )
                            
                        except Exception as e:
                            print(f"Error adding client via SBP payment: {e}")
                            await callback.message.edit_text(
                                "❌ Ошибка при активации подписки. Пожалуйста, обратитесь в поддержку.",
                                parse_mode=ParseMode.HTML
                            )
                
            except Exception as e:
                print(f"Error processing SBP payment completion: {e}")
                await callback.message.edit_text(
                    f"<tg-emoji emoji-id='5416081784641168838'>✅</tg-emoji> <b>Оплата подтверждена!</b>\n\n"
                    f"Спасибо за оплату. Оператор скоро активирует вашу подписку.",
                    parse_mode=ParseMode.HTML
                )
            
            # Уведомляем оператора о подтверждении от пользователя
            await bot.send_message(
                OPERATOR_CHAT_ID,
                f"<tg-emoji emoji-id='5416081784641168838'>💰</tg-emoji> <b>Пользователь подтвердил оплату СБП</b>\n\n"
                f"Order ID: <code>{order_id}</code>\n"
                f"Статус: {status}\n\n"
                f"Проверьте поступление средств и активируйте подписку.",
                parse_mode=ParseMode.HTML
            )
            await callback.answer("✅ Оплата подтверждена!")
            
        elif status == "pending":
            # Платёж ещё в обработке - показываем popup
            await callback.answer(
                "⏳ Платёж ещё обрабатывается. Подождите несколько минут и проверьте снова.",
                show_alert=True
            )
            
        else:
            # Другой статус
            await callback.answer(
                f"❌ Статус платежа: {status}. Свяжитесь с поддержкой.",
                show_alert=True
            )
    else:
        # Платёж не найден в БД
        await callback.answer(
            "❌ Платёж не найден. Если вы уже оплатили, подождите несколько минут.",
            show_alert=True
        )


@router.callback_query(lambda callback: callback.data.startswith("renew_pay_stars_"))
async def renew_pay_stars_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    # Извлекаем данные из callback_data
    parts = callback.data.split("_")
    time_months = int(parts[3])  # "renew_pay_stars_1_200" -> parts[3] = "1"
    price_rubles = int(parts[4])  # "renew_pay_stars_1_200" -> parts[4] = "200"
    

    
    # Формируем цену в звездах
    stars_amount = price_rubles # Фиксированная цена в звездах
    
    prices = [LabeledPrice(label="XTR", amount=stars_amount)]  
    await callback.message.answer_invoice(  
            title="Продление подписки",  
            description=f"Продление подписки на {time_months} месяцев за {stars_amount} звёзд!",  
            prices=prices,  
            provider_token="",  
            payload=f"sub_{time_months}_{price_rubles}",  
            currency="XTR",  
            reply_markup=payment_keyboard(stars_amount),  
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
        
        # Записываем продажу в Google Sheets
        add_vpn_sale(user_id, callback.from_user.username, time_months, price_rubles)
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
    
    # Отправляем уведомление оператору
    await callback.message.answer(
        f"<tg-emoji emoji-id='5411225014148014586'>❌</tg-emoji> <b>Оплата отклонена</b>\n\n"
        f"👤 Пользователь ID: {user_id}\n"
        f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Период: {time_months} мес.\n"
        f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Сумма: {price_rubles}₽\n\n"
        "Оплата не подтверждена. Свяжитесь с поддержкой.", 
        parse_mode=ParseMode.HTML
    )
    
    # Отправляем уведомление пользователю
    try:
        await bot.send_message(
            user_id,
            f"<tg-emoji emoji-id='5411225014148014586'>❌</tg-emoji> <b>Оплата отклонена</b>\n\n"
            f"К сожалению, ваша оплата на сумму {price_rubles}₽ за {time_months} мес. не была подтверждена.\n\n"
            "Пожалуйста, свяжитесь с поддержкой для уточнения деталей.\n"
            "Возможно, требуется дополнительная проверка оплаты.",
            parse_mode=ParseMode.HTML
        )
        print(f"Rejection notification sent to user {user_id}")
    except Exception as e:
        print(f"Failed to send rejection notification to user {user_id}: {e}")

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

@router.callback_query(lambda callback: callback.data == "instruction")
async def instruction_callback(callback: types.CallbackQuery):
    await callback.answer()
    # Пока ничего не делаем по нажатию

@router.callback_query(lambda callback: callback.data == "referral")
async def referral_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    # Создаем реферальную ссылку
    bot_username = (await bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={callback.from_user.id}"
    
    await callback.message.answer(
        f"<tg-emoji emoji-id='5416081784641168838'>🔗</tg-emoji> <b>Ваша реферальная ссылка</b>\n\n"
        f"<code>{referral_link}</code>\n\n"
        f"<tg-emoji emoji-id='5440621591387980068'>🎁</tg-emoji> <b>Условия бонуса:</b>\n"
        f"• Если у вас есть подписка - вам добавится <b>2 дня</b> к подписке\n"
        f"• Если у вас нет подписки - вам дается подписка на <b>2 дня</b>\n\n"
        "Бонус начисляется ВАМ за каждого нового пользователя, перешедшего по вашей ссылке!\n"
        "Делитесь ссылкой и получайте бонусы! 🚀",
        parse_mode=ParseMode.HTML
    )

@router.callback_query(lambda callback: callback.data == "renew_subscription")
async def renew_subscription_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    # Получаем все цены из БД
    prices = await get_all_prices()
    
    # Создаем клавиатуру с ценами из БД
    keyboard_buttons = []
    for price in prices:
        months_text = "год" if price.time == 12 else f"{price.time} месяц{'а' if price.time > 1 and price.time < 5 else 'ев'}"
        button_text = f"{months_text} - {price.price}₽"
        keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"renew_select_price_{price.time}_{price.price}", style="primary")])
    
    renew_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.answer(
        "<tg-emoji emoji-id='5406756500108501710'>⏰</tg-emoji> <b>Продление подписки</b>\n\n"
        "Выберите на какой период продлить подписку:\n\n"
        "<tg-emoji emoji-id='5416081784641168838'>✅</tg-emoji> Все тарифы включают:\n"
        "• Безлимитный трафик\n"
        "• Высокая скорость\n"
        "• Поддержка 24/7\n"
        "• Все устройства",
        reply_markup=renew_keyboard,
        parse_mode=ParseMode.HTML
    )

@router.callback_query(lambda callback: callback.data.startswith("renew_select_price_"))
async def renew_select_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    
    # Извлекаем время и цену из callback_data
    parts = callback.data.split("_")
    time_months = int(parts[3])  # "renew_select_price_1_200" -> parts[3] = "1"
    price_rubles = int(parts[4])  # "renew_select_price_1_200" -> parts[4] = "200"
    
    # Формируем текст времени
    months_text = "год" if time_months == 12 else f"{time_months} месяц{'а' if time_months > 1 and time_months < 5 else 'ев'}"
    
    # Создаем кнопку оплаты
    pay_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплата по СБП", callback_data=f"renew_pay_sbp_{time_months}_{price_rubles}", style="primary")],
            [InlineKeyboardButton(text="Оплатить звездами", callback_data=f"renew_pay_stars_{time_months}_{price_rubles}", style="primary")]
        ]
    )
    
    await callback.message.answer(
        f"<tg-emoji emoji-id='5251203410396458957'>💳</tg-emoji> <b>Продление подписки</b>\n\n"
        f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Период продления: {months_text}\n"
        f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Цена: {price_rubles}₽\n\n"
        "Нажмите 'Оплатить' для продолжения:",
        reply_markup=pay_keyboard,
        parse_mode=ParseMode.HTML
    )

@router.callback_query(lambda callback: callback.data.startswith("renew_pay_stars_"))
async def renew_pay_stars_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "<tg-emoji emoji-id='5416081784641168838'>🚧</tg-emoji> <b>В разработке</b>\n\n"
        "Оплата звездами временно недоступна.\n"
        "Мы работаем над добавлением этой функции.\n\n"
        "Пожалуйста, воспользуйтесь оплатой картой.",
        parse_mode=ParseMode.HTML
    )

@router.callback_query(lambda callback: callback.data.startswith("renew_pay_sbp_"))
async def renew_pay_sbp_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    # Извлекаем данные из callback_data
    parts = callback.data.split("_")
    time_months = int(parts[3])  # "renew_pay_sbp_1_200" -> parts[3] = "1"
    price_rubles = int(parts[4])  # "renew_pay_sbp_1_200" -> parts[4] = "200"
    
    user_id = callback.from_user.id
    username = callback.from_user.username
    
    # Перенаправляем в функцию обработки СБП (доступно всем)
    await process_sbp_payment(callback.message, user_id, username, time_months, price_rubles, is_renewal=True)

@router.callback_query(lambda callback: callback.data.startswith("renew_confirm_pay_"))
async def renew_confirm_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    
    # Извлекаем время и цену из callback_data
    parts = callback.data.split("_")
    time_months = int(parts[3])
    price_rubles = int(parts[4])
    
    # Формируем текст времени
    months_text = "год" if time_months == 12 else f"{time_months} месяц{'а' if time_months > 1 and time_months < 5 else 'ев'}"
    
    await callback.message.answer(
        f"<tg-emoji emoji-id='5251203410396458957'>💳</tg-emoji> <b>Информация об оплате продления</b>\n\n"
        f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Период продления: {months_text}\n"
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
                [InlineKeyboardButton(text="Я оплатил", callback_data=f"renew_paid_notify_{time_months}_{price_rubles}", style="primary")]
            ]
        ),
        parse_mode=ParseMode.HTML
    )

@router.callback_query(lambda callback: callback.data.startswith("renew_paid_notify_"))
async def renew_paid_notify_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    # Извлекаем время и цену из callback_data
    parts = callback.data.split("_")
    time_months = int(parts[3])
    price_rubles = int(parts[4])
    
    user_tg_id = callback.from_user.id
    
    # Формируем текст времени
    months_text = "год" if time_months == 12 else f"{time_months} месяц{'а' if time_months > 1 and time_months < 5 else 'ев'}"
    
    # Отправляем уведомление администратору
    await bot.send_message(
        OPERATOR_CHAT_ID,
        f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> <b>Запрос на продление подписки</b>\n\n"
        f"👤 Пользователь ID: {user_tg_id}\n"
        f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Продление на: {months_text}\n"
        f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Сумма: {price_rubles}₽\n\n"
        "Для подтверждения продления:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"renew_approve_{user_tg_id}_{time_months}_{price_rubles}", style="primary")],
                [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"renew_reject_{user_tg_id}", style="primary")]
            ]
        ),
        parse_mode=ParseMode.HTML
    )
    
    await callback.message.edit_text(f'<tg-emoji emoji-id="5386367538735104399">✅</tg-emoji> Ожидайте подтверждения оплаты от оператора', parse_mode=ParseMode.HTML)

@router.callback_query(lambda callback: callback.data.startswith("renew_approve_"))
async def renew_approve_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    
    # Извлекаем информацию
    parts = callback.data.split("_")
    user_id = int(parts[2])
    time_months = int(parts[3])
    price_rubles = int(parts[4])
    
    # Продлеваем подписку
    renew_result = renew_subscription(user_id, time_months)
    
    if renew_result.get('success'):
        # Получаем новую дату окончания
        new_expiry = renew_result.get('new_expiry')
        end_time = datetime.datetime.fromtimestamp(new_expiry / 1000)
        end_date_str = end_time.strftime("%d.%m.%Y")
        
        # Записываем продажу в Google Sheets
        add_vpn_sale(user_id, callback.from_user.username, time_months, price_rubles)
        
        await bot.send_message(
            chat_id=user_id,
            text=(
                f"<tg-emoji emoji-id='5416081784641168838'>✅</tg-emoji> <b>Подписка продлена</b>\n\n"
                f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Период продления: {time_months} мес.\n"
                f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Сумма: {price_rubles}₽\n"
                f"<tg-emoji emoji-id='5440621591387980068'>📅</tg-emoji> Действует до: {end_date_str}\n\n"
                "Подписка успешно продлена! 🎉"
            ),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Моя подписка", callback_data="subscription", style="primary", icon_custom_emoji_id='5296369303661067030')]
                ]
            ),
            parse_mode=ParseMode.HTML
        )
        
        await callback.message.answer(
            f"✅ Подписка пользователя {user_id} продлена на {time_months} месяцев",
            parse_mode=ParseMode.HTML
        )
    else:
        await bot.send_message(
            chat_id=user_id,
            text="❌ Ошибка при продлении подписки. Свяжитесь с поддержкой.",
            parse_mode=ParseMode.HTML
        )
        
        await callback.message.answer(
            f"❌ Ошибка при продлении подписки пользователя {user_id}: {renew_result.get('error')}",
            parse_mode=ParseMode.HTML
        )

@router.callback_query(lambda callback: callback.data.startswith("renew_reject_"))
async def renew_reject_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    
    user_id = int(callback.data.split("_")[2])
    
    # Отправляем уведомление пользователю
    await bot.send_message(
        chat_id=user_id,
        text=f"<tg-emoji emoji-id='5411225014148014586'>❌</tg-emoji> <b>Запрос на продление отклонен</b>\n\n"
            "К сожалению, ваш запрос на продление подписки не был подтвержден.\n\n"
            "Пожалуйста, свяжитесь с поддержкой для уточнения деталей.\n"
            "Возможно, требуется дополнительная проверка оплаты.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Моя подписка", callback_data="subscription", style="primary")]
            ]
        ),
        parse_mode=ParseMode.HTML
    )
    
    # Отправляем уведомление оператору
    await callback.message.answer(
        f"<tg-emoji emoji-id='5411225014148014586'>❌</tg-emoji> <b>Продление отклонено</b>\n\n"
        f"👤 Пользователь ID: {user_id}\n\n"
        "Запрос на продление подписки отклонен.",
        parse_mode=ParseMode.HTML
    )

@router.callback_query(lambda callback: callback.data == "main_menu")
async def main_menu_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    
    await callback.message.answer(
        "Привет! Я бот для управления VPN.\n\n"
        "Выберите одну из опций ниже:",
        reply_markup=keyboard
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

@router.callback_query(lambda callback: callback.data == "admin_add_client")
async def admin_add_client_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    if is_admin(callback.from_user.id):
        try:
            await callback.message.delete()
        except:
            pass
        
        await callback.message.answer(
            "👤 <b>Добавление клиента</b>\n\n"
            "Отправьте Telegram ID пользователя:\n\n"
            "Пример: <code>8489038592</code>\n\n"
            "Или используйте команду:\n"
            "<code>/add_client 8489038592 1</code>\n"
            "где 1 - количество месяцев",
            parse_mode=ParseMode.HTML
        )

@router.callback_query(lambda callback: callback.data == "admin_broadcast")
async def admin_broadcast_callback(callback: types.CallbackQuery):
    await callback.answer()
    
    if is_admin(callback.from_user.id):
        try:
            await callback.message.delete()
        except:
            pass
            
        await callback.message.answer(
            "📢 <b>Рассылка сообщений</b>\n\n"
            "Используйте команду:\n"
            "<code>/notify Ваше сообщение</code>\n\n"
            "Пример:\n"
            "<code>/notify 🔔 Внимание! Проводятся технические работы...</code>\n\n"
            "Поддерживаются Telegram эмодзи и HTML-теги.",
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

    # Запуск планировщика для проверки подписок
    scheduler.add_job(
        check_subscription_expirations,
        trigger=IntervalTrigger(minutes=10),  # Проверка каждые 10 минут
        id='subscription_expiration_check',
        name='Check subscription expirations',
        replace_existing=True
    )
    
    # Запускаем планировщик
    scheduler.start()
    print("Scheduler started - checking subscription expirations every 10 minutes")
    
    # Запуск бота
    dp = Dispatcher()
    dp.pre_checkout_query.register(pre_checkout_handler)
    dp.message.register(success_payment_handler, F.successful_payment)
    dp.include_router(router)
    
    # Передаём бота в payment_api для отправки уведомлений
    set_bot_instance(bot)
    print("[BOT] Bot instance set for payment_api")
    
    await dp.start_polling(bot)
    






if __name__ == "__main__":
    import asyncio
    asyncio.run(main())


