import asyncio
import datetime
import json
import os
import re
import sys
import time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from sqlalchemy import create_engine, Column, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker, declarative_base

from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardMarkup, InlineKeyboardButton

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api import add_client, getSubById, check_cantfree, add_to_cantfree, dell_client, get_clients, renew_subscription

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
        print(f"Raw prices from DB: {prices}")  # Отладочная информация
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
        # Ищем пользователя с указанным telegram_id
        result = await session.execute(select(User).filter(User.telegram_id == user.id))
        existing_user = result.scalar_one_or_none()
        
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if existing_user:
            # Если пользователь существует, обновляем его данные и время последней активности
            existing_user.username = user.username
            existing_user.first_name = user.first_name
            existing_user.last_name = user.last_name
            existing_user.last_active = current_time
            await session.commit()
            await session.refresh(existing_user)
            print(f"User {user.id} updated: {user.username or user.first_name}")
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
            print(f"New user {user.id} registered: {user.username or user.first_name}")
        
        return existing_user or new_user

# Асинхронная функция для получения всех пользователей
async def get_all_users():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        return users

# Асинхронная функция для рассылки сообщения всем пользователям
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
            print(f"Message sent to user {user.telegram_id}: {user.username or user.first_name}")
            
            # Небольшая задержка чтобы не превысить лимиты Telegram
            await asyncio.sleep(0.1)
            
        except Exception as e:
            error_count += 1
            print(f"Failed to send message to user {user.telegram_id}: {e}")
    
    print(f"Broadcast completed: {success_count} successful, {error_count} errors")
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
        # Проверяем, не получал ли пользователь уже бонус
        if user_id in referral_bonus_given:
            print(f"User {user_id} already received referral bonus")
            return
        
        # Проверяем подписку реферала
        subscription_info, status = await get_subscription_info(referrer_id)
        
        if status == "has_subscription":
            # У реферала есть подписка - добавляем 2 дня к подписке нового пользователя
            await add_referral_days_to_user(user_id, 2)
            
            # Отправляем уведомление новому пользователю
            await bot.send_message(
                user_id,
                f"<tg-emoji emoji-id='5416081784641168838'>🎉</tg-emoji> <b>Поздравляем! Вы получили бонус!</b>\n\n"
                f"Вы перешли по реферальной ссылке пользователя.\n"
                f"<tg-emoji emoji-id='5440621591387980068'>🎁</tg-emoji> Вам начислено: <b>2 дня</b> бесплатной подписки!\n\n"
                "Спасибо, что выбрали наш сервис! 🚀",
                parse_mode=ParseMode.HTML
            )
            
            # Отправляем уведомление рефералу
            await bot.send_message(
                referrer_id,
                f"<tg-emoji emoji-id='5416081784641168838'>🎉</tg-emoji> <b>Поздравляем! Новый реферал!</b>\n\n"
                f"По вашей ссылке зарегистрировался новый пользователь.\n"
                f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Ваш бонус скоро будет начислен!\n\n"
                "Спасибо за привлечение новых пользователей! 🚀",
                parse_mode=ParseMode.HTML
            )
            
        else:
            # У реферала нет подписки - даем подписку на 2 дня новому пользователю
            await add_referral_days_to_user(user_id, 2)
            
            # Отправляем уведомление новому пользователю
            await bot.send_message(
                user_id,
                f"<tg-emoji emoji-id='5416081784641168838'>🎉</tg-emoji> <b>Поздравляем! Вы получили бонус!</b>\n\n"
                f"Вы перешли по реферальной ссылке.\n"
                f"<tg-emoji emoji-id='5440621591387980068'>🎁</tg-emoji> Вам начислена подписка на <b>2 дня</b>!\n\n"
                "Спасибо, что выбрали наш сервис! 🚀",
                parse_mode=ParseMode.HTML
            )
        
        # Помечаем, что бонус выдан
        referral_bonus_given[user_id] = True
        print(f"Referral bonus given to user {user_id} from referrer {referrer_id}")
        
    except Exception as e:
        print(f"Error handling referral bonus for user {user_id}: {e}")

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
                    print(f"Added {days} days to existing subscription for user {user_id}")
                else:
                    print(f"Failed to add days to subscription for user {user_id}: {renew_result.get('error')}")
        else:
            # У пользователя нет подписки - создаем новую на 2 дня
            current_time = datetime.datetime.now()
            end_time = current_time + datetime.timedelta(days=days)
            api_date = end_time.strftime("%d.%m.%Y")
            
            add_result = add_client(21, f"user_{user_id}", user_id, api_date)
            if add_result.get('success'):
                print(f"Created new {days} day subscription for user {user_id}")
            else:
                print(f"Failed to create subscription for user {user_id}: {add_result}")
                
    except Exception as e:
        print(f"Error adding referral days for user {user_id}: {e}")

async def check_subscription_expirations():
    """Проверяет истечение подписок и отправляет напоминания"""
    try:
        # Получаем всех клиентов
        clients_data = get_clients()
        
        if not clients_data.get('success'):
            print("Failed to get clients for expiration check")
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
        print(f"Error checking subscription expirations: {e}")

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
        print(f"Sent {reminder_type} reminder to user {tg_id}")
        
    except Exception as e:
        print(f"Error sending reminder to user {tg_id}: {e}")

# Проверка на админа
def is_admin(user_id: int) -> bool:
    return user_id == OPERATOR_CHAT_ID

# Создаем inline кнопки
subscription_btn = InlineKeyboardButton(text="Подписка", callback_data="subscription", style="primary", icon_custom_emoji_id='5296369303661067030')
contact_btn = InlineKeyboardButton(text="Связь", callback_data="contact", style="primary", icon_custom_emoji_id='5443038326535759644')
info_btn = InlineKeyboardButton(text="Информация", callback_data="info", style="primary", icon_custom_emoji_id='5282843764451195532')
instruction_btn = InlineKeyboardButton(text="Инструкция и приложение", url = 'https://ezh-dev.ru/vpn_bot/index.html', style="success", icon_custom_emoji_id='5282843764451195532')
app_btn = InlineKeyboardButton(text="Приложение", callback_data="app", style="primary")
buy_subscription_btn = InlineKeyboardButton(text="Купить подписку", callback_data="buy_subscription", style="primary", icon_custom_emoji_id='5271604874419647061')
referral_btn = InlineKeyboardButton(text="Реферальная программа", callback_data="referral", style="primary", icon_custom_emoji_id='5416081784641168838')
admin_btn = InlineKeyboardButton(text="⚙️ Админ панель", callback_data="admin_panel", style="secondary")

# Создаем inline клавиатуру (кнопки в разных строках)
keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [subscription_btn],      # Первая строка                
        [contact_btn],          # Вторая строка  
        [info_btn],             # Третья строка
        [instruction_btn],      # Четвертая строка
        [referral_btn],        # Пятая строка - реферальная программа
        [buy_subscription_btn]  # Шестая строка
    ]
)

# Админ клавиатура
admin_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💰 Цены", callback_data="admin_prices", style="primary")],
        [InlineKeyboardButton(text="📝 Информация", callback_data="admin_info", style="primary")],
        [InlineKeyboardButton(text="📞 Контакты", callback_data="admin_contacts", style="primary")],
        [InlineKeyboardButton(text="� Рассылка", callback_data="admin_broadcast", style="primary")],
        [InlineKeyboardButton(text="�� Назад", callback_data="back_to_main", style="primary")]
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
        print(f"User {message.from_user.id} joined with referrer {referrer_id}")
    
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
        f"• Если у вас есть подписка - рефералу добавится <b>2 дня</b> к подписке\n"
        f"• Если у вас нет подписки - рефералу дается подписка на <b>2 дня</b>\n\n"
        "Делитесь ссылкой и получайте бонусы! 🚀",
        parse_mode=ParseMode.HTML
    )

@router.message(Command("notify"))
async def broadcast_command(message: types.Message):
    """Рассылает сообщение всем пользователям (только для админа)"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    
    # Проверяем, есть ли текст после команды
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "📢 <b>Рассылка сообщений</b>\n\n"
            "Использование:\n"
            "<code>/broadcast Ваше сообщение</code>\n\n"
            "Пример:\n"
            "<code>/broadcast 🔔 Внимание! Проводятся технические работы...</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    broadcast_text = args[1]
    
    # Отправляем сообщение о начале рассылки
    status_message = await message.answer("📢 Начинаю рассылку сообщений...")
    
    # Выполняем рассылку
    result = await broadcast_to_all_users(broadcast_text)
    
    # Обновляем статусное сообщение
    await status_message.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Успешно отправлено: <b>{result['success']}</b>\n"
        f"• Ошибок: <b>{result['errors']}</b>\n"
        f"• Всего пользователей: <b>{result['success'] + result['errors']}</b>",
        parse_mode=ParseMode.HTML
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
            # Проверяем время подписки
            expiry_time = result['client_info']['expiryTime']
            current_time = int(time.time() * 1000)  # Текущее время в миллисекундах
            
            # Если время подписки вышло, удаляем клиента
            if expiry_time != 0 and expiry_time < current_time:
                # Получаем inboundId для удаления
                clients_data = get_clients()
                inbound_id = None
                
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
                                    if str(client.get('tgId')) == str(tg_id):
                                        inbound_id = inbound.get('id')
                                        break
                        if inbound_id:
                            break
                
                # Удаляем клиента
                if inbound_id:
                    dell_client(inbound_id, tg_id)
                
                return "<tg-emoji emoji-id='5411225014148014586'>❌</tg-emoji> Время вашей подписки истекло\n\nДля получения доступа к VPN необходимо оформить подписку.", "no_subscription"
            
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
                    [InlineKeyboardButton(text="Использовать", url=f"http://ezh-dev.ru:2096/sub/{sub_id}", callback_data=f"use_sub_{sub_id}", style="primary", icon_custom_emoji_id='5271604874419647061')],
                    [InlineKeyboardButton(text="Продлить подписку", callback_data="renew_subscription", style="primary", icon_custom_emoji_id='5231012545799666522')],
                    [instruction_btn],
                    [InlineKeyboardButton(text="Назад", callback_data="main_menu", style="danger")]
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
    
    print(f"Prices from DB: {prices}")  # Отладочная информация
    
    # Создаем клавиатуру с ценами из БД
    keyboard_buttons = []
    for price in prices:
        months_text = "год" if price.time == 12 else f"{price.time} месяц{'а' if price.time > 1 and price.time < 5 else 'ев'}"
        button_text = f"{months_text} - {price.price}₽"
        keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"select_price_{price.time}_{price.price}", style="primary")])
        print(f"Created button: {button_text} with callback_data: select_price_{price.time}_{price.price}")
    
    buy_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    print(f"Keyboard buttons: {keyboard_buttons}")
    
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
            [InlineKeyboardButton(text="Оплатить картой", callback_data=f"confirm_pay_{time_months}_{price_rubles}", style="primary")],
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

@router.callback_query(lambda callback: callback.data.startswith("pay_stars_"))
async def pay_stars_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "<tg-emoji emoji-id='5416081784641168838'>🚧</tg-emoji> <b>В разработке</b>\n\n"
        "Оплата звездами временно недоступна.\n"
        "Мы работаем над добавлением этой функции.\n\n"
        "Пожалуйста, воспользуйтесь оплатой картой.",
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
        f"• Если у вас есть подписка - рефералу добавится <b>2 дня</b> к подписке\n"
        f"• Если у вас нет подписки - рефералу дается подписка на <b>2 дня</b>\n\n"
        "Делитесь ссылкой и получайте бонусы! 🚀",
        parse_mode=ParseMode.HTML
    )

@router.callback_query(lambda callback: callback.data == "renew_subscription")
async def renew_subscription_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    # Получаем все цены из БД
    prices = await get_all_prices()
    
    print(f"Prices from DB (renew): {prices}")  # Отладочная информация
    
    # Создаем клавиатуру с ценами из БД
    keyboard_buttons = []
    for price in prices:
        months_text = "год" if price.time == 12 else f"{price.time} месяц{'а' if price.time > 1 and price.time < 5 else 'ев'}"
        button_text = f"{months_text} - {price.price}₽"
        keyboard_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"renew_select_price_{price.time}_{price.price}", style="primary")])
        print(f"Created renew button: {button_text} with callback_data: renew_select_price_{price.time}_{price.price}")
    
    renew_keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    print(f"Renew keyboard buttons: {keyboard_buttons}")
    
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
            [InlineKeyboardButton(text="Оплатить картой", callback_data=f"renew_confirm_pay_{time_months}_{price_rubles}", style="primary")],
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
            "<code>/broadcast Ваше сообщение</code>\n\n"
            "Пример:\n"
            "<code>/broadcast 🔔 Внимание! Проводятся технические работы...</code>\n\n"
            "Сообщение будет отправлено всем пользователям бота.",
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
    dp.include_router(router)
    await dp.start_polling(bot)
    






if __name__ == "__main__":
    import asyncio
    asyncio.run(main())


