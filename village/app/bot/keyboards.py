# app/bot/keyboards.py
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    buttons = [
        [KeyboardButton(text="🏡 Деревня"), KeyboardButton(text="🧑‍🌾 Work!"), KeyboardButton(text="🌾 Собрать")],
        [KeyboardButton(text="💰 Продать"), KeyboardButton(text="👥 Нанять рабочего"), KeyboardButton(text="⛏ Шахта")],
        [KeyboardButton(text="⚔️ В бой"), KeyboardButton(text="🚀 Квесты"), KeyboardButton(text="🏆 ТОП")],
        [KeyboardButton(text="💎 Магазин"), KeyboardButton(text="🏗 Здания"), KeyboardButton(text="⚙️ Настройки")],
        [KeyboardButton(text="🔄 Обновить"), KeyboardButton(text="📚 Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def choose_language():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
                InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
            ]
        ]
    )