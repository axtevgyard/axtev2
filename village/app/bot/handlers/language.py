from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.crud import UserCRUD
from app.bot.keyboards import main_menu, choose_language
from app.bot.texts_ru import TEXTS

router = Router()

@router.message(Command("chooselanguage"))
async def choose_lang(message: Message):
    await message.answer(TEXTS['choose_language'], reply_markup=choose_language())

@router.callback_query(F.data == "lang_ru")
async def set_lang_ru(callback: CallbackQuery):
    session = SessionLocal()
    user = UserCRUD.get_by_tg_id(session, callback.from_user.id)
    if user:
        user.lang = "ru"
        session.commit()
    await callback.message.edit_text(TEXTS['language_changed'], reply_markup=main_menu())
    session.close()

@router.callback_query(F.data == "lang_en")
async def set_lang_en(callback: CallbackQuery):
    session = SessionLocal()
    user = UserCRUD.get_by_tg_id(session, callback.from_user.id)
    if user:
        user.lang = "en"
        session.commit()
    await callback.message.edit_text("✅ Language changed to English 🇬🇧", reply_markup=main_menu())
    session.close()