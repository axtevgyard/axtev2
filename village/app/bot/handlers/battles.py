# app/bot/handlers/battles.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.crud import UserCRUD, VillageCRUD
from app.bot.keyboards import main_menu, pve_difficulty, troop_selection
from app.bot.texts_ru import TEXTS
from app.services.battle_engine import resolve_pve_battle, resolve_pvp_battle, find_pvp_opponent, check_pvp_shield

router = Router()

@router.message(F.text == "⚔️ В бой")
async def battles_menu(message: Message):
    """Show battles menu"""
    battles_keyboard = __get_battles_menu()
    await message.answer("⚔️ БОЕВОЕ МЕНЮ\n\nВыбери тип боя:", reply_markup=battles_keyboard)

def __get_battles_menu():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🐉 PvE (vs NPC)", callback_data="battle_pve")],
            [InlineKeyboardButton(text="⚔️ PvP (vs Players)", callback_data="battle_pvp")],
            [InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")]
        ]
    )

@router.callback_query(F.data == "battle_pve")
async def pve_difficulty_select(query: CallbackQuery):
    """Select PvE difficulty"""
    await query.answer()
    await query.message.edit_text("⚔️ Выбери сложность:", reply_markup=pve_difficulty())

@router.callback_query(F.data.startswith("pve_"))
async def pve_battle_start(query: CallbackQuery):
    """Start PvE battle"""
    session = SessionLocal()
    
    try:
        difficulty = query.data.replace("pve_", "")
        
        user = UserCRUD.get_by_tg_id(session, query.from_user.id)
        if not user or not user.villages:
            await query.answer(TEXTS['error'])
            return
        
        village = VillageCRUD.get_with_lock(session, user.id)
        if not village:
            await query.answer(TEXTS['error'])
            return
        
        result = resolve_pve_battle(session, village, difficulty)
        session.commit()
        
        if result['success']:
            if result['is_win']:
                text = TEXTS['pve_win'].format(
                    gold=result['gold_delta'],
                    xp=result['xp_gained'],
                    casualty=result['casualty']
                )
            else:
                text = TEXTS['pve_lose'].format(
                    casualty=result['casualty']
                )
        else:
            text = TEXTS['error']
        
        await query.answer()
        await query.message.edit_text(text)
    
    except Exception as e:
        print(f"PvE battle error: {e}")
        await query.answer(TEXTS['error'])
    finally:
        session.close()

@router.callback_query(F.data == "battle_pvp")
async def pvp_search_opponent(query: CallbackQuery):
    """Search for PvP opponent"""
    session = SessionLocal()
    
    try:
        user = UserCRUD.get_by_tg_id(session, query.from_user.id)
        if not user or not user.villages:
            await query.answer(TEXTS['error'])
            return
        
        village = user.villages[0]
        opponent = find_pvp_opponent(session, village)
        
        if not opponent:
            await query.answer("Не найдено противников. Попробуй позже!", show_alert=True)
            return
        
        # Store opponent in context (simplified, normally use FSM)
        min_troops = max(5, opponent.troops // 2)
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        pvp_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⚔️ Атаковать", callback_data=f"pvp_attack_{opponent.id}")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="back_menu")]
            ]
        )
        
        text = TEXTS['pvp_found_opponent'].format(
            name=opponent.name,
            level=opponent.level,
            min_troops=min_troops,
            gold=50 + 10 * village.level,
            medals=random.randint(1, 3)
        )
        
        await query.answer()
        await query.message.edit_text(text, reply_markup=pvp_keyboard)
    
    except Exception as e:
        print(f"PvP search error: {e}")
        await query.answer(TEXTS['error'])
    finally:
        session.close()

@router.callback_query(F.data.startswith("pvp_attack_"))
async def pvp_select_troops(query: CallbackQuery):
    """Select troops for PvP attack"""
    defender_id = int(query.data.replace("pvp_attack_", ""))
    
    await query.answer()
    await query.message.edit_text(
        "⚔️ Сколько войск отправить?",
        reply_markup=troop_selection()
    )
    
    # Store defender_id in callback_data chain
    # This is simplified; use FSM for production

@router.callback_query(F.data.startswith("troops_"))
async def pvp_battle_confirm(query: CallbackQuery):
    """Confirm and execute PvP battle"""
    session = SessionLocal()
    
    try:
        troops_count = query.data.replace("troops_", "")
        
        user = UserCRUD.get_by_tg_id(session, query.from_user.id)
        if not user or not user.villages:
            await query.answer(TEXTS['error'])
            return
        
        village = VillageCRUD.get_with_lock(session, user.id)
        if not village:
            await query.answer(TEXTS['error'])
            return
        
        # Simplified: should use FSM to pass defender_id
        await query.answer("Функция в разработке (используй FSM для полной реализации)")
    
    except Exception as e:
        print(f"PvP battle error: {e}")
        await query.answer(TEXTS['error'])
    finally:
        session.close()