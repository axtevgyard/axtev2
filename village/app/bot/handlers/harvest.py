# app/bot/handlers/harvest.py (extended with workers/troops)
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.crud import UserCRUD, VillageCRUD
from app.bot.keyboards import main_menu
from app.bot.texts_ru import TEXTS
from app.services.economy import harvest_action, buy_worker, buy_troops

router = Router()

@router.message(F.text == "🌾 Собрать")
async def harvest_handler(message: Message):
    """Harvest action (no cost, just update)"""
    session = SessionLocal()
    
    try:
        user = UserCRUD.get_by_tg_id(session, message.from_user.id)
        if not user or not user.villages:
            await message.answer(TEXTS['error'], reply_markup=main_menu())
            return
        
        village = user.villages[0]
        result = harvest_action(session, village)
        session.commit()
        
        if result['success']:
            text = TEXTS['harvest_success'].format(
                farm_storage=village.farm_storage,
                farm_capacity=village.farm_capacity
            )
        else:
            text = TEXTS['error']
        
        await message.answer(text, reply_markup=main_menu())
    
    except Exception as e:
        print(f"Harvest error: {e}")
        await message.answer(TEXTS['error'], reply_markup=main_menu())
    finally:
        session.close()