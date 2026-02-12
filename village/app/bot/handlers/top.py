# app/bot/handlers/top.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.crud import UserCRUD
from app.db.models import LeaderboardType
from app.bot.keyboards import main_menu, top_menu
from app.bot.texts_ru import TEXTS
from app.services.leaderboard import get_leaderboard_with_player

router = Router()

@router.message(F.text == "🏆 ТОП")
async def top_menu_handler(message: Message):
    """Show top menu"""
    await message.answer("🏆 ТАБЛИЦА ЛИДЕРОВ\n\nВыбери категорию:", reply_markup=top_menu())

@router.callback_query(F.data == "top_medals")
async def show_top_medals(query: CallbackQuery):
    """Show medals leaderboard"""
    session = SessionLocal()
    
    try:
        user = UserCRUD.get_by_tg_id(session, query.from_user.id)
        if not user or not user.villages:
            await query.answer(TEXTS['error'])
            return
        
        village = user.villages[0]
        lb_data = get_leaderboard_with_player(session, village, LeaderboardType.MEDALS, 10)
        
        top_text = "🏅 ТОП ПО МЕДАЛЯМ:\n\n"
        for i, entry in enumerate(lb_data['top'], 1):
            v = entry.village
            top_text += f"{i}. {v.name} (ур. {v.level}) - {entry.score} 🏅\n"
        
        top_text += f"\n\nТвоя позиция: #{lb_data['player_rank']}"
        
        await query.answer()
        await query.message.edit_text(top_text)
    
    except Exception as e:
        print(f"Top medals error: {e}")
        await query.answer(TEXTS['error'])
    finally:
        session.close()

@router.callback_query(F.data == "top_level")
async def show_top_level(query: CallbackQuery):
    """Show level leaderboard"""
    session = SessionLocal()
    
    try:
        user = UserCRUD.get_by_tg_id(session, query.from_user.id)
        if not user or not user.villages:
            await query.answer(TEXTS['error'])
            return
        
        village = user.villages[0]
        lb_data = get_leaderboard_with_player(session, village, LeaderboardType.LEVEL, 10)
        
        top_text = "🏰 ТОП ПО УРОВНЮ:\n\n"
        for i, entry in enumerate(lb_data['top'], 1):
            v = entry.village
            top_text += f"{i}. {v.name} - уровень {entry.score}\n"
        
        top_text += f"\n\nТвоя позиция: #{lb_data['player_rank']}"
        
        await query.answer()
        await query.message.edit_text(top_text)
    
    except Exception as e:
        print(f"Top level error: {e}")
        await query.answer(TEXTS['error'])
    finally:
        session.close()

@router.callback_query(F.data == "top_gold")
async def show_top_gold(query: CallbackQuery):
    """Show gold leaderboard"""
    session = SessionLocal()
    
    try:
        user = UserCRUD.get_by_tg_id(session, query.from_user.id)
        if not user or not user.villages:
            await query.answer(TEXTS['error'])
            return
        
        village = user.villages[0]
        lb_data = get_leaderboard_with_player(session, village, LeaderboardType.GOLD, 10)
        
        top_text = "💰 ТОП ПО ЗОЛОТУ:\n\n"
        for i, entry in enumerate(lb_data['top'], 1):
            v = entry.village
            top_text += f"{i}. {v.name} (ур. {v.level}) - {entry.score} 💰\n"
        
        top_text += f"\n\nТвоя позиция: #{lb_data['player_rank']}"
        
        await query.answer()
        await query.message.edit_text(top_text)
    
    except Exception as e:
        print(f"Top gold error: {e}")
        await query.answer(TEXTS['error'])
    finally:
        session.close()