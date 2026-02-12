# app/bot/handlers/sell.py
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.crud import UserCRUD, VillageCRUD
from app.bot.keyboards import main_menu
from app.bot.texts_ru import TEXTS
from app.services.economy import sell_bread

router = Router()

@router.message(F.text == "💰 Продать")
async def sell_handler(message: Message):
    """Sell bread for gold"""
    session = SessionLocal()
    
    try:
        user = UserCRUD.get_by_tg_id(session, message.from_user.id)
        if not user or not user.villages:
            await message.answer(TEXTS['error'], reply_markup=main_menu())
            return
        
        village = VillageCRUD.get_with_lock(session, user.id)
        if not village:
            await message.answer(TEXTS['error'], reply_markup=main_menu())
            return
        
        result = sell_bread(session, village)
        session.commit()
        
        if result['success']:
            text = TEXTS['sell_success'].format(
                gold=result['gold_gained'],
                farm_storage=result['farm_storage'],
                farm_capacity=village.farm_capacity,
                xp=result['xp_gained']
            )
        else:
            text = TEXTS['sell_not_enough']
        
        await message.answer(text, reply_markup=main_menu())
    
    except Exception as e:
        print(f"Sell error: {e}")
        await message.answer(TEXTS['error'], reply_markup=main_menu())
    finally:
        session.close()