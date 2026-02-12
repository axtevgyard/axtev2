# app/bot/handlers/quests.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.crud import UserCRUD
from app.db.models import Quest, UserActiveQuest, QuestStatus
from app.bot.keyboards import main_menu, quest_menu
from app.bot.texts_ru import TEXTS
from app.services.quest_engine import (
    generate_quest_offers, start_quest, finish_quest,
    get_active_quests, check_quest_completion
)
from datetime import datetime

router = Router()

current_quest_index = {}  # Simplified quest tracking

@router.message(F.text == "🚀 Квесты")
async def quests_menu(message: Message):
    """Show available quests"""
    session = SessionLocal()
    
    try:
        user = UserCRUD.get_by_tg_id(session, message.from_user.id)
        if not user or not user.villages:
            await message.answer(TEXTS['error'], reply_markup=main_menu())
            return
        
        village = user.villages[0]
        
        # Get active quests
        active_quests = get_active_quests(session, village)
        
        # Check completions
        for aq in active_quests:
            if check_quest_completion(session, aq):
                aq.status = QuestStatus.FINISHED
        
        session.commit()
        
        # Display active quests
        if active_quests:
            quests_text = "🚀 АКТИВНЫЕ КВЕСТЫ:\n\n"
            for i, aq in enumerate(active_quests, 1):
                quest = next((q for q in session.query(Quest).all() if q.id == aq.quest_id), None)
                if quest:
                    status_emoji = "⏳" if aq.status == QuestStatus.RUNNING else "✅"
                    quests_text += f"{i}. {status_emoji} {quest.title_ru}\n"
            
            await message.answer(quests_text, reply_markup=main_menu())
        else:
            # Generate new offers
            offers = generate_quest_offers(session, village, 3)
            if not offers:
                await message.answer(TEXTS['quests_no_offers'], reply_markup=main_menu())
                return
            
            current_quest_index[message.from_user.id] = 0
            display_quest_offer(message, offers[0])
    
    except Exception as e:
        print(f"Quests error: {e}")
        await message.answer(TEXTS['error'], reply_markup=main_menu())
    finally:
        session.close()

def display_quest_offer(message: Message, quest: Quest):
    """Display a single quest offer"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    medals_text = f", {quest.reward_medals} 🏅" if quest.reward_medals > 0 else ""
    resource_text = f", {quest.reward_resource_amount} {quest.reward_resource_type.value}" if quest.reward_resource_type else ""
    
    text = TEXTS['quest_offer'].format(
        title=quest.title_ru,
        type=quest.quest_type.value,
        troops=quest.troops_required,
        fee=quest.gold_fee,
        reward_gold=quest.reward_gold,
        reward_xp=quest.reward_xp,
        medals=medals_text,
        resource=resource_text
    )
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_quest_{quest.id}")],
            [InlineKeyboardButton(text="➡️ Следующий", callback_data="next_quest")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="back_menu")]
        ]
    )
    
    # This should use message.edit_text or send_message depending on context

@router.callback_query(F.data.startswith("accept_quest_"))
async def accept_quest(query: CallbackQuery):
    """Accept and start a quest"""
    session = SessionLocal()
    
    try:
        quest_id = int(query.data.replace("accept_quest_", ""))
        
        user = UserCRUD.get_by_tg_id(session, query.from_user.id)
        if not user or not user.villages:
            await query.answer(TEXTS['error'])
            return
        
        village = user.villages[0]
        quest = session.query(Quest).filter(Quest.id == quest_id).first()
        
        if not quest:
            await query.answer(TEXTS['error'])
            return
        
        result = start_quest(session, village, quest)
        session.commit()
        
        if result['success']:
            text = TEXTS['quest_started'].format(
                duration=result['duration'],
                troops=result['troops_locked']
            )
        else:
            text = TEXTS['error']
        
        await query.answer()
        await query.message.edit_text(text)
    
    except Exception as e:
        print(f"Accept quest error: {e}")
        await query.answer(TEXTS['error'])
    finally:
        session.close()