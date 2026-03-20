from aiogram.utils.keyboard import InlineKeyboardBuilder  
  
  
def payment_keyboard(stars_amount):  
    builder = InlineKeyboardBuilder()  
    builder.button(text=f"Оплатить {stars_amount} звёзд", pay=True, style='success', icon_custom_emoji_id=5422367241645611298)  
  
    return builder.as_markup()