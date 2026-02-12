from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from app.bot.keyboards import main_menu
from app.bot.texts_ru import TEXTS

router = Router()

@router.message(F.text == "📚 Помощь")
@router.message(Command("help"))
async def show_help(message: Message):
    await message.answer(TEXTS['help_text'], reply_markup=main_menu())