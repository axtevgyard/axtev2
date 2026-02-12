# app/main.py
import asyncio
import logging
import sys
from sqlalchemy import text, inspect
from aiogram import Bot, Dispatcher, Router, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from app.config import BOT_TOKEN, DB_URL
from app.db.session import engine, SessionLocal
from app.db.models import Base
from app.db.crud import UserCRUD, VillageCRUD, LeaderboardCRUD
from app.bot.keyboards import main_menu, choose_language
from app.bot.texts_ru import TEXTS
from app.services.economy import *

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def reset_database():
    """Drop ALL tables and indexes, then create fresh ones"""
    logger.info("\n📊 DATABASE RESET")
    
    try:
        with engine.connect() as conn:
            logger.info("🧹 Dropping all indexes...")
            inspector = inspect(conn)
            
            for table_name in reversed(inspector.get_table_names()):
                for index in inspector.get_indexes(table_name):
                    try:
                        conn.execute(text(f"DROP INDEX IF EXISTS {index['name']}"))
                    except:
                        pass
            
            logger.info("🧹 Dropping all tables...")
            Base.metadata.drop_all(conn)
            conn.commit()
            
            logger.info("✅ All tables and indexes dropped")
    except Exception as e:
        logger.warning(f"⚠️  Could not drop: {e}")
    
    logger.info("⏳ Creating new tables...")
    try:
        Base.metadata.create_all(engine)
        logger.info("✅ New tables created")
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        raise
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logger.info(f"📋 Total tables: {len(tables)}")
    for table in sorted(tables):
        logger.info(f"   ✓ {table}")

async def main():
    logger.info("=" * 70)
    logger.info("🚀 BOT STARTUP")
    logger.info("=" * 70)
    
    try:
        reset_database()
        
        logger.info("\n🤖 Initializing bot...")
        bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
        dp = Dispatcher(storage=MemoryStorage())
        
        router = Router()
        
        # ===== START =====
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
            
            VillageCRUD.update_energy(session, village)
            VillageCRUD.update_farm(session, village)
            session.commit()
            
            welcome_text = TEXTS['welcome'].format(energy=village.energy, energy_max=VillageCRUD.calc_energy_max(village))
            await message.answer(welcome_text, reply_markup=main_menu())
            session.close()
        
        # ===== VILLAGE STATUS =====
        @router.message(F.text == "🏡 Деревня")
        async def show_village_status(message: Message):
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, message.from_user.id)
            if not user or not user.villages:
                await message.answer(TEXTS['error'])
                session.close()
                return
            
            village = user.villages[0]
            VillageCRUD.update_energy(session, village)
            VillageCRUD.update_farm(session, village)
            session.commit()
            
            energy_max = VillageCRUD.calc_energy_max(village)
            workers_max = VillageCRUD.calc_workers_max(village)
            troops_max = VillageCRUD.calc_troops_max(village)
            progress = calculate_progress_percent(village)
            mine_level = VillageCRUD.get_building_level(village, BuildingType.MINE)
            
            status_text = TEXTS['village_status'].format(
                name=village.name, level=village.level, progress=progress, workers=village.workers, workers_max=workers_max,
                troops=village.troops, troops_max=troops_max, farm_storage=village.farm_storage, farm_capacity=village.farm_capacity,
                gold=village.gold, diamonds=village.diamonds, medals=village.medals, energy=village.energy, energy_max=energy_max,
                mine_depth=village.mine_state.mine_depth, pickaxe_level=village.mine_state.pickaxe_level,
                pickaxe_power=village.mine_state.pickaxe_power, mine_charges=village.mine_state.mining_charges, mine_charges_max=3 + mine_level // 3
            )
            await message.answer(status_text, reply_markup=main_menu())
            session.close()
        
        # ===== WORK =====
        @router.message(F.text == "🧑‍🌾 Work!")
        async def cmd_work(message: Message):
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, message.from_user.id)
            if not user or not user.villages:
                await message.answer(TEXTS['error'])
                session.close()
                return
            
            village = user.villages[0]
            result = work_action(session, village)
            session.commit()
            
            if result['success']:
                response = f"✅ <b>Ты поработал!</b>\n\n+{result['gain']} 🍞 собрано\nЭнергия: {result['energy']}/{result['energy_max']} ⚡"
            else:
                response = f"❌ <b>Не хватает энергии!</b>\nНужно {result['needed']} ⚡, а у тебя {result['current']} ⚡\nЭнергия восполняется 1 за 5 минут ⏰"
            
            await message.answer(response, reply_markup=main_menu())
            session.close()
        
        # ===== HARVEST =====
        @router.message(F.text == "🌾 Собрать")
        async def cmd_harvest(message: Message):
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, message.from_user.id)
            if not user or not user.villages:
                await message.answer(TEXTS['error'])
                session.close()
                return
            
            village = user.villages[0]
            result = harvest_action(session, village)
            session.commit()
            
            response = f"✅ <b>Урожай собран!</b>\n\n📦 Склад: {result['farm_storage']}/{result['farm_capacity']} 🍞\n\n<i>Урожай растёт автоматически каждый час. Скорость зависит от уровня фермы, количества рабочих и уровня деревни.</i>"
            await message.answer(response, reply_markup=main_menu())
            session.close()
        
        # ===== SELL =====
        @router.message(F.text == "💰 Продать")
        async def cmd_sell(message: Message):
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, message.from_user.id)
            if not user or not user.villages:
                await message.answer(TEXTS['error'])
                session.close()
                return
            
            village = user.villages[0]
            result = sell_bread(session, village)
            session.commit()
            
            if result['success']:
                response = f"✅ <b>Хлеб продан!</b>\n\n+{result['gold_gained']} 💰 получено\n+{result['xp_gained']} 📈 опыта\n\n📦 Склад: {result['farm_storage']}/{village.farm_capacity} 🍞"
            else:
                response = f"❌ <b>Мало хлеба!</b>\nНужно минимум 10 шт. 🍞, а у тебя {result['have']}\n\nПроизводи хлеб через кнопку '🌾 Собрать' или работай через '🧑‍🌾 Work!'"
            
            await message.answer(response, reply_markup=main_menu())
            session.close()
        
        # ===== HIRE WORKER =====
        @router.message(F.text == "👥 Нанять рабочего")
        async def cmd_hire_worker(message: Message):
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, message.from_user.id)
            if not user or not user.villages:
                await message.answer(TEXTS['error'])
                session.close()
                return
            
            village = user.villages[0]
            workers_max = VillageCRUD.calc_workers_max(village)
            
            if village.workers >= workers_max:
                response = f"❌ <b>Максимум рабочих достигнут!</b>\n\nТекущий лимит: {workers_max}\n\nУвеличить лимит можно улучшив 🏰 Ратушу"
                await message.answer(response, reply_markup=main_menu())
                session.close()
                return
            
            cost = calculate_worker_cost(village.workers)
            
            text = f"👥 <b>НАНЯТЬ РАБОЧЕГО</b>\n\n"
            text += f"Текущие рабочие: {village.workers}/{workers_max}\n"
            text += f"Стоимость: {cost} 💰\n"
            text += f"Ваше золото: {village.gold} 💰\n\n"
            text += f"<i>Рабочие повышают производительность фермы на 6% за каждого\nПервые 15 рабочих дешевле, чем остальные</i>"
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=f"✅ Нанять за {cost} 💰", callback_data="hire_worker")],
                    [InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")]
                ]
            )
            
            await message.answer(text, reply_markup=keyboard)
            session.close()
        
        @router.callback_query(F.data == "hire_worker")
        async def hire_worker_callback(callback: CallbackQuery):
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, callback.from_user.id)
            if not user or not user.villages:
                await callback.answer("❌ Ошибка", show_alert=True)
                session.close()
                return
            
            village = user.villages[0]
            result = buy_worker(session, village)
            session.commit()
            
            if result['success']:
                text = f"✅ <b>Рабочий нанят!</b>\n\n"
                text += f"Затрачено: {result['cost']} 💰\n"
                text += f"Рабочих: {result['workers']}/{result['workers_max']}\n"
                text += f"Золото: {result['gold']} 💰\n\n"
                text += f"<i>Каждый рабочий повышает производительность фермы на 6%</i>"
            else:
                text = f"❌ <b>Не хватает золота!</b>\n\nНужно {result['needed']} 💰\nУ вас {result['have']} 💰\n\nНужно ещё {result['needed'] - result['have']} 💰"
            
            await callback.message.edit_text(text, reply_markup=main_menu())
            session.close()
        
        # ===== BUILDINGS =====
        @router.message(F.text == "🏗 Здания")
        async def show_buildings(message: Message):
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, message.from_user.id)
            if not user or not user.villages:
                await message.answer(TEXTS['error'])
                session.close()
                return
            
            village = user.villages[0]
            
            text = "<b>🏗️ ЗДАНИЯ ДЕРЕВНИ</b>\n\n"
            text += f"Уровень деревни: {village.level}\n"
            text += f"Золото: {village.gold} 💰\n\n"
            
            buttons = []
            for building in village.buildings:
                cost = calculate_building_upgrade_cost(building.building_type, building.level)
                text += f"🏢 <b>{building.building_type.value}</b> (ур. {building.level})\n"
                text += f"   Апгрейд стоит: {cost} 💰\n"
                text += f"   Описание: {get_building_description(building.building_type, building.level)}\n\n"
                
                buttons.append([InlineKeyboardButton(text=f"⬆️ {building.building_type.value} (ур. {building.level})", callback_data=f"upgrade_{building.building_type.value}")])
            
            buttons.append([InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")])
            
            await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
            session.close()
        
        @router.callback_query(F.data.startswith("upgrade_"))
        async def upgrade_building_callback(callback: CallbackQuery):
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            building_name = callback.data.replace("upgrade_", "")
            building_type = BuildingType[building_name]
            
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, callback.from_user.id)
            if not user or not user.villages:
                await callback.answer("❌ Ошибка", show_alert=True)
                session.close()
                return
            
            village = user.villages[0]
            result = upgrade_building(session, village)
            session.commit()
            
            if result['success']:
                text = f"✅ <b>Здание улучшено!</b>\n\n"
                text += f"🏢 {result['building']}: {result['new_level']-1} → {result['new_level']}\n"
                text += f"Затрачено: {result['cost']} 💰\n"
                text += f"Золото осталось: {result['gold']} 💰"
            else:
                cost = calculate_building_upgrade_cost(building_type, VillageCRUD.get_building_level(village, building_type))
                text = f"❌ <b>Не хватает золота!</b>\n\n"
                text += f"Нужно: {cost} 💰\n"
                text += f"У вас: {village.gold} 💰"
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"upgrade_{building_name}")],
                    [InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")]
                ]
            )
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            session.close()
        
        # ===== MINE =====
        @router.message(F.text == "⛏ Шахта")
        async def show_mine_menu(message: Message):
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, message.from_user.id)
            if not user or not user.villages:
                await message.answer(TEXTS['error'])
                session.close()
                return
            
            village = user.villages[0]
            mine = village.mine_state
            mine_level = VillageCRUD.get_building_level(village, BuildingType.MINE)
            max_charges = 3 + mine_level // 3
            
            text = f"⛏️ <b>ШАХТА</b>\n\n"
            text += f"📍 Глубина: {mine.mine_depth} м\n"
            text += f"🔨 Кирка: уровень {mine.pickaxe_level} (сила {mine.pickaxe_power})\n"
            text += f"🔋 Заряды: {mine.mining_charges}/{max_charges}\n\n"
            text += f"<i>Каждый заряд восполняется за 10 минут\nКирка улучшается ресурсами из шахты</i>"
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⛏️ Копать", callback_data="mine_dig")],
                    [InlineKeyboardButton(text="🔨 Улучшить кирку", callback_data="mine_upgrade")],
                    [InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")]
                ]
            )
            
            await message.answer(text, reply_markup=keyboard)
            session.close()
        
        @router.callback_query(F.data == "mine_dig")
        async def mine_dig_callback(callback: CallbackQuery):
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, callback.from_user.id)
            if not user or not user.villages:
                await callback.answer("❌ Ошибка", show_alert=True)
                session.close()
                return
            
            village = user.villages[0]
            mine = village.mine_state
            
            if mine.mining_charges <= 0:
                await callback.answer("❌ Нет зарядов! Приходи через 10 минут", show_alert=True)
                session.close()
                return
            
            mine.mining_charges -= 1
            ore_gain = mine.pickaxe_power + (mine.mine_depth // 10)
            mine.mine_depth += 1
            
            session.commit()
            
            text = f"✅ <b>Ты выкопал руду!</b>\n\n"
            text += f"+{ore_gain} 💎 ресурсов\n"
            text += f"Глубина: {mine.mine_depth} м\n"
            text += f"Зарядов осталось: {mine.mining_charges}"
            
            await callback.answer(text, show_alert=True)
            session.close()
        
        @router.callback_query(F.data == "mine_upgrade")
        async def mine_upgrade_callback(callback: CallbackQuery):
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, callback.from_user.id)
            if not user or not user.villages:
                await callback.answer("❌ Ошибка", show_alert=True)
                session.close()
                return
            
            village = user.villages[0]
            mine = village.mine_state
            
            text = f"🔨 <b>УЛУЧШИТЬ КИРКУ</b>\n\n"
            text += f"Текущий уровень: {mine.pickaxe_level}\n"
            text += f"Сила: {mine.pickaxe_power}\n"
            text += f"Критический урон: {mine.pickaxe_bonus_crit*100:.1f}%\n\n"
            text += f"<i>Для улучшения нужны ресурсы из шахты\nСейчас функция в разработке</i>"
            
            await callback.message.edit_text(text)
            session.close()
        
        # ===== BATTLES =====
        @router.message(F.text == "⚔️ В бой")
        async def show_battle_menu(message: Message):
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, message.from_user.id)
            if not user or not user.villages:
                await message.answer(TEXTS['error'])
                session.close()
                return
            
            village = user.villages[0]
            troops_max = VillageCRUD.calc_troops_max(village)
            
            text = f"⚔️ <b>БОЕВАЯ СИСТЕМА</b>\n\n"
            text += f"Ваши войска: {village.troops}/{troops_max}\n\n"
            text += f"<b>Выберите тип боя:</b>"
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🤖 PvE (против NPC)", callback_data="battle_pve")],
                    [InlineKeyboardButton(text="⚔️ PvP (против игроков)", callback_data="battle_pvp")],
                    [InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")]
                ]
            )
            
            await message.answer(text, reply_markup=keyboard)
            session.close()
        
        @router.callback_query(F.data == "battle_pve")
        async def battle_pve_callback(callback: CallbackQuery):
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, callback.from_user.id)
            if not user or not user.villages:
                await callback.answer("❌ Ошибка", show_alert=True)
                session.close()
                return
            
            village = user.villages[0]
            
            text = f"🤖 <b>БОЙ ПРОТИВ NPC</b>\n\n"
            text += f"Ваши войска: {village.troops}\n"
            text += f"Ваши медали: {village.medals}\n\n"
            text += f"<b>Выберите сложность:</b>\n"
            text += f"🟢 Легко - мало наград, гарантия побед\n"
            text += f"🟡 Средне - хорошие награды, 50% побед\n"
            text += f"🔴 Сложно - много наград, высокий риск"
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🟢 Легко", callback_data="pve_easy")],
                    [InlineKeyboardButton(text="🟡 Средне", callback_data="pve_medium")],
                    [InlineKeyboardButton(text="🔴 Сложно", callback_data="pve_hard")],
                    [InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")]
                ]
            )
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            session.close()
        
        @router.callback_query(F.data.startswith("pve_"))
        async def pve_fight_callback(callback: CallbackQuery):
            import random
            
            difficulty = callback.data.replace("pve_", "")
            
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, callback.from_user.id)
            if not user or not user.villages:
                await callback.answer("❌ Ошибка", show_alert=True)
                session.close()
                return
            
            village = user.villages[0]
            
            if village.troops == 0:
                await callback.answer("❌ У вас нет войск! Купите войска сначала", show_alert=True)
                session.close()
                return
            
            # Боевая механика
            difficulty_mod = {'easy': 0.5, 'medium': 1.0, 'hard': 1.5}[difficulty]
            
            player_power = village.troops * 10
            npc_power = 50 + (village.level * 10) * difficulty_mod
            
            win_chance = min(0.95, max(0.05, player_power / (player_power + npc_power)))
            is_win = random.random() < win_chance
            
            if is_win:
                gold_reward = int(100 * difficulty_mod)
                medals_reward = int(5 * difficulty_mod)
                xp_reward = int(20 * difficulty_mod)
                
                village.gold += gold_reward
                village.medals += medals_reward
                VillageCRUD.add_xp(session, village, xp_reward)
                
                text = f"✅ <b>ПОБЕДА!</b>\n\n"
                text += f"+{gold_reward} 💰\n"
                text += f"+{medals_reward} 🏅\n"
                text += f"+{xp_reward} 📈"
            else:
                casualties = random.randint(1, min(5, village.troops // 2))
                village.troops -= casualties
                
                text = f"❌ <b>ПОРАЖЕНИЕ!</b>\n\n"
                text += f"Потеряно войск: {casualties}\n"
                text += f"Войск осталось: {village.troops}"
            
            session.commit()
            
            await callback.message.edit_text(text, reply_markup=main_menu())
            session.close()
        
        @router.callback_query(F.data == "battle_pvp")
        async def battle_pvp_callback(callback: CallbackQuery):
            text = f"⚔️ <b>PvP БОИ</b>\n\n"
            text += f"<i>Функция в разработке 🔄\n\nСкоро вы сможете сражаться с реальными игроками!</i>"
            
            await callback.message.edit_text(text)
        
        # ===== QUESTS =====
        @router.message(F.text == "🚀 Квесты")
        async def show_quests(message: Message):
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, message.from_user.id)
            if not user or not user.villages:
                await message.answer(TEXTS['error'])
                session.close()
                return
            
            village = user.villages[0]
            
            text = f"🚀 <b>КВЕСТЫ</b>\n\n"
            text += f"Уровень деревни: {village.level}\n"
            text += f"Опыт: {village.xp}/{calculate_xp_to_next_level(village.level)}\n\n"
            text += f"<b>Доступные задания:</b>\n"
            text += f"1️⃣ Нарубить дрова (0 войск)\n"
            text += f"2️⃣ Собрать урожай (0 войск)\n"
            text += f"3️⃣ Добыть камней (0 войск)\n"
            text += f"4️⃣ Обойти патруль (5 войск)\n"
            text += f"5️⃣ Разбить лагерь гоблинов (10 войск)\n"
            text += f"6️⃣ Найти сокровище (15 войск)\n"
            text += f"7️⃣ Спасти крестьян (20 войск)\n"
            text += f"8️⃣ Разгромить бандитов (25 войск)\n"
            text += f"9️⃣ Завоевать форт (30 войск)\n"
            text += f"🔟 Оборонять деревню (35 войск)\n\n"
            text += f"<i>Квесты дают опыт, ресурсы и награды</i>"
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="ℹ️ О квестах", callback_data="quests_info")],
                    [InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")]
                ]
            )
            
            await message.answer(text, reply_markup=keyboard)
            session.close()
        
        @router.callback_query(F.data == "quests_info")
        async def quests_info_callback(callback: CallbackQuery):
            text = f"📚 <b>ИНФОРМАЦИЯ О КВЕСТАХ</b>\n\n"
            text += f"<b>Как это работает:</b>\n"
            text += f"✅ Выбери квест из списка\n"
            text += f"✅ Трать войска и время\n"
            text += f"✅ Получай награды\n\n"
            text += f"<b>Награды могут быть:</b>\n"
            text += f"💰 Золото\n"
            text += f"📈 Опыт\n"
            text += f"🏅 Медали\n"
            text += f"💎 Ресурсы\n\n"
            text += f"<b>Сложность квестов:</b>\n"
            text += f"🟢 Легкие: 0-10 войск\n"
            text += f"🟡 Средние: 10-25 войск\n"
            text += f"🔴 Тяжёлые: 25+ войск"
            
            await callback.message.edit_text(text)
        
        # ===== TOP =====
        @router.message(F.text == "🏆 ТОП")
        async def show_top_menu(message: Message):
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            text = f"🏆 <b>ТАБЛИЦА ЛИДЕРОВ</b>\n\n"
            text += f"<b>Выберите категорию:</b>"
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🏅 По медалям", callback_data="top_medals")],
                    [InlineKeyboardButton(text="🏰 По уровню", callback_data="top_level")],
                    [InlineKeyboardButton(text="💰 По золоту", callback_data="top_gold")],
                    [InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")]
                ]
            )
            
            await message.answer(text, reply_markup=keyboard)
        
        @router.callback_query(F.data.startswith("top_"))
        async def top_callback(callback: CallbackQuery):
            from app.db.models import LeaderboardType
            
            top_type = callback.data.replace("top_", "").upper()
            
            session = SessionLocal()
            
            if top_type == "MEDALS":
                lb_type = LeaderboardType.MEDALS
                title = "🏅 ТОП ПО МЕДАЛЯМ"
                emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
            elif top_type == "LEVEL":
                lb_type = LeaderboardType.LEVEL
                title = "🏰 ТОП ПО УРОВНЮ"
                emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
            else:
                lb_type = LeaderboardType.GOLD
                title = "💰 ТОП ПО ЗОЛОТУ"
                emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
            
            top_list = LeaderboardCRUD.get_top(session, lb_type, 5)
            
            text = f"<b>{title}</b>\n\n"
            
            if not top_list:
                text += "<i>Таблица пуста</i>"
            else:
                for i, entry in enumerate(top_list):
                    emoji = emojis[i] if i < len(emojis) else "•"
                    text += f"{emoji} {entry.village.name}: {entry.score}\n"
            
            await callback.message.edit_text(text)
            session.close()
        
        # ===== SHOP =====
        @router.message(F.text == "💎 Магазин")
        async def show_shop(message: Message):
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            text = f"💎 <b>МАГАЗИН</b>\n\n"
            text += f"<b>Что вы хотите купить?</b>"
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⚔️ Войска", callback_data="shop_troops")],
                    [InlineKeyboardButton(text="💎 Алмазы", callback_data="shop_diamonds")],
                    [InlineKeyboardButton(text="🍖 Ресурсы", callback_data="shop_resources")],
                    [InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")]
                ]
            )
            
            await message.answer(text, reply_markup=keyboard)
        
        @router.callback_query(F.data == "shop_troops")
        async def shop_troops_callback(callback: CallbackQuery):
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, callback.from_user.id)
            if not user or not user.villages:
                await callback.answer("❌ Ошибка", show_alert=True)
                session.close()
                return
            
            village = user.villages[0]
            troops_max = VillageCRUD.calc_troops_max(village)
            
            text = f"⚔️ <b>КУПИТЬ ВОЙСКА</b>\n\n"
            text += f"Текущие войска: {village.troops}/{troops_max}\n"
            text += f"Ваше золото: {village.gold} 💰\n\n"
            text += f"<b>Цены:</b>\n"
            text += f"1 войск = 1 💰\n\n"
            text += f"<i>Войска используются для боёв и квестов</i>"
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Купить 10", callback_data="buy_troops_10")],
                    [InlineKeyboardButton(text="Купить 50", callback_data="buy_troops_50")],
                    [InlineKeyboardButton(text="Купить 100", callback_data="buy_troops_100")],
                    [InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")]
                ]
            )
            
            await callback.message.edit_text(text, reply_markup=keyboard)
            session.close()
        
        @router.callback_query(F.data.startswith("buy_troops_"))
        async def buy_troops_callback(callback: CallbackQuery):
            amount = int(callback.data.replace("buy_troops_", ""))
            
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, callback.from_user.id)
            if not user or not user.villages:
                await callback.answer("❌ Ошибка", show_alert=True)
                session.close()
                return
            
            village = user.villages[0]
            result = buy_troops(session, village, amount)
            session.commit()
            
            if result['success']:
                text = f"✅ <b>Войска куплены!</b>\n\n"
                text += f"Куплено: {result['troops_bought']} ⚔️\n"
                text += f"Затрачено: {result['cost']} 💰\n"
                text += f"Войск теперь: {result['troops']}/{result['troops_max']}"
            else:
                text = f"❌ <b>Не хватает золота!</b>\n\n"
                text += f"Нужно: {result['needed']} 💰\n"
                text += f"У вас: {result['have']} 💰"
            
            await callback.answer(text, show_alert=True)
            session.close()
        
        @router.callback_query(F.data == "shop_diamonds")
        async def shop_diamonds_callback(callback: CallbackQuery):
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            text = f"💎 <b>КУПИТЬ АЛМАЗЫ</b>\n\n"
            text += f"<b>Доступные пакеты:</b>\n\n"
            text += f"🟢 Маленький: 25 💎 = 49 ₽\n"
            text += f"🟡 Средний: 60 💎 = 109 ₽\n"
            text += f"🔴 Большой: 140 💎 = 249 ₽\n"
            text += f"⭐ Огромный: 320 💎 = 499 ₽\n\n"
            text += f"<i>💎 Алмазы используются для премиум функций и ускорения</i>"
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🟢 25 💎 (49₽)", url="https://t.me/farmingvillage_bot?start=shop_25")],
                    [InlineKeyboardButton(text="🟡 60 💎 (109₽)", url="https://t.me/farmingvillage_bot?start=shop_60")],
                    [InlineKeyboardButton(text="🔴 140 💎 (249₽)", url="https://t.me/farmingvillage_bot?start=shop_140")],
                    [InlineKeyboardButton(text="⭐ 320 💎 (499₽)", url="https://t.me/farmingvillage_bot?start=shop_320")],
                    [InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")]
                ]
            )
            
            await callback.message.edit_text(text, reply_markup=keyboard)
        
        @router.callback_query(F.data == "shop_resources")
        async def shop_resources_callback(callback: CallbackQuery):
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            text = f"🍖 <b>КУПИТЬ РЕСУРСЫ</b>\n\n"
            text += f"<b>Доступны:</b>\n\n"
            text += f"🪨 Камень: 10 шт = 50 💰\n"
            text += f"🌳 Дерево: 10 шт = 50 💰\n"
            text += f"💨 Уголь: 5 шт = 50 💰\n"
            text += f"💎 Драгоценные камни: 1 шт = 100 💰\n\n"
            text += f"<i>Ресурсы нужны для улучшений</i>"
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🪨 Камень (50 💰)", callback_data="buy_stone")],
                    [InlineKeyboardButton(text="🌳 Дерево (50 💰)", callback_data="buy_wood")],
                    [InlineKeyboardButton(text="💨 Уголь (50 💰)", callback_data="buy_coal")],
                    [InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")]
                ]
            )
            
            await callback.message.edit_text(text, reply_markup=keyboard)
        
        # ===== SETTINGS =====
        @router.message(F.text == "⚙️ Настройки")
        async def show_settings(message: Message):
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, message.from_user.id)
            if not user:
                await message.answer(TEXTS['error'])
                session.close()
                return
            
            text = f"⚙️ <b>НАСТРОЙКИ</b>\n\n"
            text += f"Язык: {'🇷🇺 Русский' if user.lang == 'ru' else '🇬🇧 English'}\n"
            text += f"ID Telegram: {user.tg_id}\n"
            text += f"Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}\n\n"
            text += f"<b>Опции:</b>"
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🌍 Язык", callback_data="settings_lang")],
                    [InlineKeyboardButton(text="📊 Статистика", callback_data="settings_stats")],
                    [InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")]
                ]
            )
            
            await message.answer(text, reply_markup=keyboard)
            session.close()
        
        @router.callback_query(F.data == "settings_lang")
        async def settings_lang_callback(callback: CallbackQuery):
            text = TEXTS['choose_language']
            await callback.message.edit_text(text, reply_markup=choose_language())
        
        @router.callback_query(F.data == "settings_stats")
        async def settings_stats_callback(callback: CallbackQuery):
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, callback.from_user.id)
            if not user or not user.villages:
                await callback.answer("❌ Ошибка", show_alert=True)
                session.close()
                return
            
            village = user.villages[0]
            
            text = f"📊 <b>СТАТИСТИКА</b>\n\n"
            text += f"🏰 Уровень де��евни: {village.level}\n"
            text += f"👥 Всего рабочих: {village.workers}\n"
            text += f"⚔️ Всего войск: {village.troops}\n"
            text += f"💰 Всего золота получено: {village.gold}\n"
            text += f"🏅 Медали: {village.medals}\n"
            text += f"📅 Игрок с: {village.user.created_at.strftime('%d.%m.%Y')}"
            
            await callback.message.edit_text(text)
            session.close()
        
        # ===== REFRESH =====
        @router.message(F.text == "🔄 Обновить")
        async def refresh_data(message: Message):
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, message.from_user.id)
            if not user or not user.villages:
                await message.answer(TEXTS['error'])
                session.close()
                return
            
            village = user.villages[0]
            VillageCRUD.update_energy(session, village)
            VillageCRUD.update_farm(session, village)
            session.commit()
            
            energy_max = VillageCRUD.calc_energy_max(village)
            
            await message.answer(f"🔄 <b>Данные обновлены!</b>\n\n⚡ Энергия: {village.energy}/{energy_max}\n🍞 Урожай: {village.farm_storage}/{village.farm_capacity}", reply_markup=main_menu())
            session.close()
        
        # ===== LANGUAGE =====
        @router.message(Command("chooselanguage"))
        async def choose_lang(message: Message):
            await message.answer(TEXTS['choose_language'], reply_markup=choose_language())
        
        @router.callback_query(F.data == "lang_ru")
        async def set_lang_ru(callback: CallbackQuery):
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, callback.from_user.id)
            if user:
                user.lang = "ru"
                session.commit()
            await callback.message.edit_text(TEXTS['language_changed'], reply_markup=main_menu())
            session.close()
        
        @router.callback_query(F.data == "lang_en")
        async def set_lang_en(callback: CallbackQuery):
            session = SessionLocal()
            user = UserCRUD.get_by_tg_id(session, callback.from_user.id)
            if user:
                user.lang = "en"
                session.commit()
            await callback.message.edit_text("✅ Language changed to English 🇬🇧", reply_markup=main_menu())
            session.close()
        
        # ===== BACK BUTTON =====
        @router.callback_query(F.data == "back_menu")
        async def back_to_menu(callback: CallbackQuery):
            await callback.message.edit_text("Главное меню:", reply_markup=main_menu())
        
        @router.message(F.text == "📚 Помощь")
        @router.message(Command("help"))
        async def cmd_help(message: Message):
            await message.answer(TEXTS['help_text'], reply_markup=main_menu())
        
        dp.include_router(router)
        
        logger.info("✅ Bot ready! Starting polling...")
        logger.info("=" * 70)
        
        await dp.start_polling(bot)
    
    except Exception as e:
        logger.error(f"❌ ERROR: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main())