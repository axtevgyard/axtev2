# app/bot/handlers/shop.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.crud import UserCRUD, VillageCRUD
from app.bot.keyboards import main_menu, shop_menu
from app.bot.texts_ru import TEXTS
from app.services.shop_engine import get_shop_catalog, buy_item

router = Router()

@router.message(F.text == "💎 Магазин")
async def shop_menu_handler(message: Message):
    """Show shop menu"""
    await message.answer("💎 МАГАЗИН\n\nВыбери раздел:", reply_markup=shop_menu())

@router.callback_query(F.data == "shop_items")
async def shop_items_list(query: CallbackQuery):
    """Show shop items"""
    session = SessionLocal()
    
    try:
        user = UserCRUD.get_by_tg_id(session, query.from_user.id)
        if not user or not user.villages:
            await query.answer(TEXTS['error'])
            return
        
        village = user.villages[0]
        catalog = get_shop_catalog()
        
        items_text = "🛍️ ТОВАРЫ ЗА АЛМАЗЫ:\n\n"
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = []
        for sku, item in catalog['items'].items():
            item_type = item['type']
            cost = item['diamonds_cost']
            
            if item_type == 'gold':
                display = f"💰 Золото x{item['amount']} - {cost} 💎"
            elif item_type == 'worker':
                display = f"👨‍🌾 Рабочий x{item['amount']} - {cost} 💎"
            elif item_type == 'energy':
                display = f"⚡ Энергия x{item['amount']} - {cost} 💎"
            elif item_type == 'mine_charge':
                display = f"⛏️ Заряд шахты x{item['amount']} - {cost} 💎"
            elif item_type == 'pickaxe_bonus':
                display = f"🔧 Бонус кирки +{item['amount']} - {cost} 💎"
            else:
                display = f"{sku} - {cost} 💎"
            
            buttons.append([InlineKeyboardButton(text=display, callback_data=f"buy_{sku}")])
            items_text += f"• {display}\n"
        
        buttons.append([InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await query.answer()
        await query.message.edit_text(items_text, reply_markup=keyboard)
    
    except Exception as e:
        print(f"Shop items error: {e}")
        await query.answer(TEXTS['error'])
    finally:
        session.close()

@router.callback_query(F.data == "shop_packs")
async def shop_packs_list(query: CallbackQuery):
    """Show donate packs"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from app.config import DONATE_PACKS
    
    packs_text = "📦 ПАКЕТЫ АЛМАЗОВ:\n\n"
    buttons = []
    
    for pack in DONATE_PACKS:
        sku = pack['sku']
        diamonds = pack['diamonds'] + pack['bonus']
        price = pack['price_fiat']
        bonus_text = f" +{pack['bonus']}" if pack['bonus'] > 0 else ""
        
        display = f"💎 x{pack['diamonds']}{bonus_text} - {price} руб"
        packs_text += f"• {display}\n"
        
        buttons.append([InlineKeyboardButton(text=display, callback_data=f"buy_{sku}")])
    
    buttons.append([InlineKeyboardButton(text="❌ Назад", callback_data="back_menu")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await query.answer()
    await query.message.edit_text(packs_text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("buy_"))
async def buy_item_handler(query: CallbackQuery):
    """Buy item from shop"""
    session = SessionLocal()
    
    try:
        item_sku = query.data.replace("buy_", "")
        
        user = UserCRUD.get_by_tg_id(session, query.from_user.id)
        if not user or not user.villages:
            await query.answer(TEXTS['error'])
            return
        
        village = VillageCRUD.get_with_lock(session, user.id)
        
        result = buy_item(session, village, item_sku)
        session.commit()
        
        if result['success']:
            text = TEXTS['shop_buy_success'].format(
                item=item_sku,
                diamonds=result.get('diamonds', village.diamonds)
            )
            await query.answer(text, show_alert=True)
        else:
            await query.answer(TEXTS['shop_no_diamonds'], show_alert=True)
    
    except Exception as e:
        print(f"Buy item error: {e}")
        await query.answer(TEXTS['error'])
    finally:
        session.close()