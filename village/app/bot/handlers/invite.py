from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.crud import UserCRUD
from app.bot.keyboards import main_menu
from app.bot.texts_ru import TEXTS
from app.services.anti_abuse import generate_ref_code

router = Router()

@router.message(Command("invite_friends"))
async def show_referral(message: Message):
    session = SessionLocal()
    user = UserCRUD.get_by_tg_id(session, message.from_user.id)
    if not user:
        await message.answer(TEXTS['error'])
        session.close()
        return
    
    if not user.ref_code:
        user.ref_code = generate_ref_code(user.id)
        session.commit()
    
    from app.config import BOT_TOKEN
    bot_username = BOT_TOKEN.split(':')[0]
    link = f"https://t.me/{bot_username}?start={user.ref_code}"
    text = TEXTS['referral_link'].format(link=f"<code>{link}</code>", count=user.referred_count)
    await message.answer(text, reply_markup=main_menu())
    session.close()