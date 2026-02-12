# app/bot/handlers/buildings.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.crud import UserCRUD, VillageCRUD
from app.db.models import BuildingType
from app.bot.keyboards import building_menu, main_menu
from app.bot.texts_ru import TEXTS
from app.services.economy import upgrade_building, calculate_building_upgrade_cost

router = Router()

@router.message(F.text == "🏗 Здания")
async def buildings_handler(message: Message):
    """Show buildings menu"""
    session = SessionLocal()
    
    try:
        user = UserCRUD.get_by_tg_id(session, message.from_user.id)
        if not user or not user.villages:
            await message.answer(TEXTS['error'], reply_markup=main_menu())
            return
        
        village = user.villages[0]
        
        # Show building levels and costs
        buildings_info = []
        for btype in [BuildingType.TOWNHALL, BuildingType.FARM, BuildingType.BARN, 
                      BuildingType.BARRACKS, BuildingType.WALL, BuildingType.MINE, BuildingType.WORKSHOP]:
            b = next((b for b in village.buildings if b.building_type == btype), None)
            level = b.level if b else 1
            cost = calculate_building_upgrade_cost(btype, level)
            buildings_info.append(f"🏢 {btype.value}: уровень {level} (апгрейд: {cost} 💰)")
        
        buildings_text = "🏗 ЗДАНИЯ\n\n" + "\n".join(buildings_info) + "\n\nВыбери здание для апгрейда:"
        await message.answer(buildings_text, reply_markup=building_menu())
    
    except Exception as e:
        print(f"Buildings error: {e}")
        await message.answer(TEXTS['error'], reply_markup=main_menu())
    finally:
        session.close()

@router.callback_query(F.data.startswith("upgrade_"))
async def upgrade_building_callback(query: CallbackQuery):
    """Handle building upgrade"""
    session = SessionLocal()
    
    try:
        building_name = query.data.replace("upgrade_", "").upper()
        building_type = BuildingType[building_name]
        
        user = UserCRUD.get_by_tg_id(session, query.from_user.id)
        if not user or not user.villages:
            await query.answer(TEXTS['error'])
            return
        
        village = VillageCRUD.get_with_lock(session, user.id)
        if not village:
            await query.answer(TEXTS['error'])
            return
        
        result = upgrade_building(session, village, building_type)
        session.commit()
        
        if result['success']:
            text = TEXTS['building_upgraded'].format(
                building=building_name,
                new_level=result['new_level'],
                cost=result['cost']
            )
            await query.answer(text)
        else:
            await query.answer(TEXTS['building_not_enough_gold'])
    
    except Exception as e:
        print(f"Upgrade building error: {e}")
        await query.answer(TEXTS['error'])
    finally:
        session.close()

@router.callback_query(F.data == "back_menu")
async def back_to_menu(query: CallbackQuery):
    """Go back to main menu"""
    await query.answer()
    await query.message.delete()