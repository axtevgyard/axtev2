# app/bot/handlers/mine.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.crud import UserCRUD, VillageCRUD
from app.bot.keyboards import main_menu
from app.bot.texts_ru import TEXTS
from app.services.mine_engine import mine_dig_action, upgrade_pickaxe

router = Router()

@router.message(F.text == "⛏ Шахта")
async def mine_menu(message: Message):
    """Show mine menu"""
    session = SessionLocal()
    
    try:
        user = UserCRUD.get_by_tg_id(session, message.from_user.id)
        if not user or not user.villages:
            await message.answer(TEXTS['error'], reply_markup=main_menu())
            return
        
        village = user.villages[0]
        mine_state = village.mine_state
        
        from app.services.economy import calculate_energy_max
        energy_max = calculate_energy_max(village)
        
        mine_text = (
            f"⛏️ ШАХТА\n\n"
            f"Глубина: {mine_state.mine_depth}\n"
            f"Кирка уровень: {mine_state.pickaxe_level}\n"
            f"Сила кирки: {mine_state.pickaxe_power}\n"
            f"Заряды: {mine_state.mining_charges}\n"
            f"Энергия: {village.energy}/{energy_max} ⚡\n\n"
        )
        
        mine_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⛏️ Копать", callback_data="mine_dig")],
                [InlineKeyboardButton(text="🔧 Апгрейд кирки", callback_data="mine_upgrade")],
                [InlineKeyboardButton(text="📦 Инвентарь", callback_data="mine_inventory")],
                [InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")]
            ]
        )
        
        await message.answer(mine_text, reply_markup=mine_keyboard)
    
    except Exception as e:
        print(f"Mine menu error: {e}")
        await message.answer(TEXTS['error'], reply_markup=main_menu())
    finally:
        session.close()

@router.callback_query(F.data == "mine_dig")
async def mine_dig(query: CallbackQuery):
    """Execute mining action"""
    session = SessionLocal()
    
    try:
        user = UserCRUD.get_by_tg_id(session, query.from_user.id)
        if not user or not user.villages:
            await query.answer(TEXTS['error'])
            return
        
        village = VillageCRUD.get_with_lock(session, user.id)
        mine_state = village.mine_state
        
        result = mine_dig_action(session, mine_state, village)
        session.commit()
        
        if result['success']:
            drops_str = ", ".join([f"{res_type.value}x{amount}" for res_type, amount in result['drops']])
            text = TEXTS['mine_dig_success'].format(
                list=drops_str,
                charges=result['charges'],
                cap=3,
                xp=result['xp_gained']
            )
        else:
            if result['error'] == 'no_charges':
                text = TEXTS['mine_no_charges'].format(
                    next_charge_in=result['next_charge_in']
                )
            elif result['error'] == 'not_enough_energy':
                text = TEXTS['mine_no_energy'].format(needed=8)
            else:
                text = TEXTS['error']
        
        await query.answer()
        await query.message.edit_text(text)
    
    except Exception as e:
        print(f"Mine dig error: {e}")
        await query.answer(TEXTS['error'])
    finally:
        session.close()

@router.callback_query(F.data == "mine_upgrade")
async def mine_upgrade_menu(query: CallbackQuery):
    """Show pickaxe upgrade menu with costs"""
    session = SessionLocal()
    
    try:
        user = UserCRUD.get_by_tg_id(session, query.from_user.id)
        if not user or not user.villages:
            await query.answer(TEXTS['error'])
            return
        
        village = user.villages[0]
        mine_state = village.mine_state
        
        from app.services.mine_engine import calculate_pickaxe_upgrade_cost
        cost = calculate_pickaxe_upgrade_cost(mine_state.pickaxe_level)
        
        cost_text = (
            f"🔧 АПГРЕЙД КИРКИ\n\n"
            f"Текущий уровень: {mine_state.pickaxe_level}\n"
            f"Следующий уровень: {mine_state.pickaxe_level + 1}\n\n"
            f"<b>Требуется:</b>\n"
            f"💰 Золото: {cost['gold']}\n"
            f"🪨 Камень: {cost['stone']}\n"
            f"⚫ Уголь: {cost['coal']}\n"
            f"🟠 {cost['ore_type'].value}: {cost['ore_amount']}\n"
        )
        
        if cost['gems'] > 0:
            cost_text += f"💎 Самоцветы: {cost['gems']}\n"
        
        upgrade_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Апгрейдить", callback_data="mine_do_upgrade")],
                [InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")]
            ]
        )
        
        await query.answer()
        await query.message.edit_text(cost_text, reply_markup=upgrade_keyboard)
    
    except Exception as e:
        print(f"Mine upgrade menu error: {e}")
        await query.answer(TEXTS['error'])
    finally:
        session.close()

@router.callback_query(F.data == "mine_do_upgrade")
async def mine_do_upgrade(query: CallbackQuery):
    """Execute pickaxe upgrade"""
    session = SessionLocal()
    
    try:
        user = UserCRUD.get_by_tg_id(session, query.from_user.id)
        if not user or not user.villages:
            await query.answer(TEXTS['error'])
            return
        
        village = VillageCRUD.get_with_lock(session, user.id)
        mine_state = village.mine_state
        
        result = upgrade_pickaxe(session, mine_state, village)
        session.commit()
        
        if result['success']:
            text = TEXTS['mine_pickaxe_upgraded'].format(
                new_level=result['new_level'],
                pickaxe_power=result['pickaxe_power'],
                cost=result['cost']
            )
        else:
            text = TEXTS['error']
        
        await query.answer()
        await query.message.edit_text(text)
    
    except Exception as e:
        print(f"Mine upgrade error: {e}")
        await query.answer(TEXTS['error'])
    finally:
        session.close()

@router.callback_query(F.data == "mine_inventory")
async def mine_inventory(query: CallbackQuery):
    """Show inventory resources"""
    session = SessionLocal()
    
    try:
        user = UserCRUD.get_by_tg_id(session, query.from_user.id)
        if not user or not user.villages:
            await query.answer(TEXTS['error'])
            return
        
        village = user.villages[0]
        
        inv_text = "📦 ИНВЕНТАРЬ (Ресурсы):\n\n"
        for inv in village.inventory_resources:
            inv_text += f"{inv.resource_type.value}: {inv.amount}\n"
        
        await query.answer()
        await query.message.edit_text(inv_text)
    
    except Exception as e:
        print(f"Mine inventory error: {e}")
        await query.answer(TEXTS['error'])
    finally:
        session.close()