from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import User
from app.db.crud import UserCRUD, VillageCRUD
from app.bot.keyboards import main_menu, choose_language
from app.bot.texts_ru import TEXTS
from app.services.economy import update_energy, update_farm

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    session = SessionLocal()
    user = UserCRUD.get_or_create(session, tg_id=message.from_user.id, username=message.from_user.username, first_name=message.from_user.first_name)
    session.commit()
    
    if not user.villages:
        village = VillageCRUD.create(session, user.id)
        session.commit()
    else:
        village = user.villages[0]
    
    update_energy(session, village)
    update_farm(session, village)
    session.commit()
    
    welcome_text = TEXTS['welcome'].format(energy=village.energy, energy_max=60 + 4 * 1 + 2 * village.level)
    await message.answer(welcome_text, reply_markup=main_menu())
    session.close()

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(TEXTS['help_text'], reply_markup=main_menu())

@router.message(F.text == "🏡 Деревня")
async def show_village_status(message: Message):
    session = SessionLocal()
    user = UserCRUD.get_by_tg_id(session, message.from_user.id)
    if not user or not user.villages:
        await message.answer(TEXTS['error'])
        session.close()
        return
    
    village = user.villages[0]
    update_energy(session, village)
    update_farm(session, village)
    session.commit()
    
    from app.services.economy import calculate_energy_max, calculate_workers_max, calculate_troops_max, calculate_progress_percent
    energy_max = calculate_energy_max(village)
    workers_max = calculate_workers_max(village)
    troops_max = calculate_troops_max(village)
    progress = calculate_progress_percent(village)
    mine_level = next((b.level for b in village.buildings if b.building_type.value == 'MINE'), 1)
    
    status_text = TEXTS['village_status'].format(
        name=village.name, level=village.level, progress=progress, workers=village.workers, workers_max=workers_max,
        troops=village.troops, troops_max=troops_max, farm_storage=village.farm_storage, farm_capacity=village.farm_capacity,
        gold=village.gold, diamonds=village.diamonds, medals=village.medals, energy=village.energy, energy_max=energy_max,
        mine_depth=village.mine_state.mine_depth, pickaxe_level=village.mine_state.pickaxe_level,
        pickaxe_power=village.mine_state.pickaxe_power, mine_charges=village.mine_state.mining_charges, mine_charges_max=3 + mine_level // 3
    )
    await message.answer(status_text, reply_markup=main_menu())
    session.close()

@router.message(F.text == "🔄 Обновить")
async def refresh_data(message: Message):
    session = SessionLocal()
    user = UserCRUD.get_by_tg_id(session, message.from_user.id)
    if not user or not user.villages:
        await message.answer(TEXTS['error'])
        session.close()
        return
    
    village = user.villages[0]
    update_energy(session, village)
    update_farm(session, village)
    session.commit()
    await message.answer("🔄 Данные обновлены!", reply_markup=main_menu())
    session.close()

@router.message(Command("chooselanguage"))
async def choose_language_cmd(message: Message):
    await message.answer(TEXTS['choose_language'], reply_markup=choose_language())