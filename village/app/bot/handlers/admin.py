from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.crud import UserCRUD
from app.db.models import User
from app.bot.keyboards import main_menu, admin_menu
from app.bot.texts_ru import TEXTS
from app.config import ADMIN_IDS
from sqlalchemy import select

router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(TEXTS['access_denied'])
        return
    await message.answer(TEXTS['admin_menu'], reply_markup=admin_menu())

@router.callback_query(F.data == "admin_give_gold")
async def admin_give_gold_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer(TEXTS['access_denied'], show_alert=True)
        return
    await callback.message.edit_text(TEXTS['admin_give_gold'])

@router.message(F.text.startswith("/admin_give_gold"))
async def admin_give_gold_exec(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(TEXTS['access_denied'])
        return
    try:
        parts = message.text.split()
        tg_id = int(parts[1])
        amount = int(parts[2])
    except (IndexError, ValueError):
        await message.answer("❌ Формат: /admin_give_gold <tg_id> <amount>")
        return
    
    session = SessionLocal()
    user = session.execute(select(User).where(User.tg_id == tg_id)).scalar_one_or_none()
    if not user or not user.villages:
        await message.answer("❌ Пользователь не найден")
        session.close()
        return
    
    village = user.villages[0]
    village.gold += amount
    session.commit()
    await message.answer(f"✅ Выдано {amount} 💰 пользователю {user.username}")
    session.close()

@router.message(F.text.startswith("/admin_ban"))
async def admin_ban_user(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(TEXTS['access_denied'])
        return
    try:
        tg_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("❌ Формат: /admin_ban <tg_id>")
        return
    
    session = SessionLocal()
    user = session.execute(select(User).where(User.tg_id == tg_id)).scalar_one_or_none()
    if not user:
        await message.answer("❌ Пользователь не найден")
        session.close()
        return
    
    user.is_banned = True
    session.commit()
    await message.answer(f"✅ Пользователь {user.username} забанен")
    session.close()

@router.message(F.text.startswith("/admin_create_promo"))
async def admin_create_promo(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer(TEXTS['access_denied'])
        return
    try:
        parts = message.text.split()
        code = parts[1]
        gold = int(parts[2]) if len(parts) > 2 else 0
        diamonds = int(parts[3]) if len(parts) > 3 else 0
    except (IndexError, ValueError):
        await message.answer("❌ Формат: /admin_create_promo <code> <gold> <diamonds>")
        return
    
    session = SessionLocal()
    from app.db.models import PromoCode
    promo = PromoCode(code=code, reward_gold=gold, reward_diamonds=diamonds, max_uses_total=1, max_uses_per_user=1)
    session.add(promo)
    session.commit()
    await message.answer(f"✅ Промо-код '{code}' создан")
    session.close()