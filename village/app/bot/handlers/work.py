# app/bot/handlers/work.py
from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.crud import UserCRUD, VillageCRUD
from app.bot.keyboards import main_menu
from app.bot.texts_ru import TEXTS
from app.services.economy import work_action, update_energy, calculate_energy_max

router = Router()

@router.message(F.text == "🧑‍🌾 Work!")
@router.message(F.text == "/work")
async def work_handler(message: Message):
    """Execute work action"""
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
        
        result = work_action(session, village)
        session.commit()
        
        if result['success']:
            text = TEXTS['work_success'].format(
                gain=result['gain'],
                energy=result['energy'],
                energy_max=result['energy_max']
            )
        else:
            text = TEXTS['work_no_energy'].format(
                needed=6,
                current=result['current']
            )
        
        await message.answer(text, reply_markup=main_menu())
    
    except Exception as e:
        print(f"Work error: {e}")
        await message.answer(TEXTS['error'], reply_markup=main_menu())
    finally:
        session.close()