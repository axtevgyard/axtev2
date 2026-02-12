# app/services/shop_engine.py
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import ShopOrder, ShopOrderStatus, Village, MineState, BuildingType
from app.db.crud import VillageCRUD
from app.config import DONATE_PACKS

SHOP_ITEMS = {
    'gold_50': {'type': 'gold', 'amount': 50, 'diamonds_cost': 2},
    'gold_150': {'type': 'gold', 'amount': 150, 'diamonds_cost': 5},
    'worker_1': {'type': 'worker', 'amount': 1, 'diamonds_cost': 5},
    'worker_3': {'type': 'worker', 'amount': 3, 'diamonds_cost': 14},
    'energy_30': {'type': 'energy', 'amount': 30, 'diamonds_cost': 3},
    'energy_100': {'type': 'energy', 'amount': 100, 'diamonds_cost': 8},
    'mine_charge': {'type': 'mine_charge', 'amount': 1, 'diamonds_cost': 2},
    'pickaxe_steel': {'type': 'pickaxe_bonus', 'amount': 3, 'diamonds_cost': 25},
    'pickaxe_silver': {'type': 'pickaxe_bonus', 'amount': 6, 'diamonds_cost': 55},
    'pickaxe_gold': {'type': 'pickaxe_bonus', 'amount': 9, 'diamonds_cost': 90},
    'vip_month': {'type': 'vip_subscription', 'amount': 30, 'diamonds_cost': 120},
}

def get_shop_catalog() -> dict:
    """Get all shop items and donate packs"""
    return {
        'items': SHOP_ITEMS,
        'packs': DONATE_PACKS,
    }

def buy_item(session: Session, village: Village, item_sku: str) -> dict:
    """
    Buy item from shop with diamonds.
    """
    from app.services.economy import calculate_energy_max, calculate_workers_max
    
    if item_sku not in SHOP_ITEMS:
        return {'success': False, 'error': 'item_not_found'}
    
    item = SHOP_ITEMS[item_sku]
    cost = item['diamonds_cost']
    
    if village.diamonds < cost:
        return {'success': False, 'error': 'not_enough_diamonds', 'needed': cost, 'have': village.diamonds}
    
    # Spend diamonds
    village.diamonds -= cost
    
    item_type = item['type']
    amount = item['amount']
    
    # Process item
    if item_type == 'gold':
        village.gold += amount
        return {
            'success': True,
            'item_sku': item_sku,
            'gold_gained': amount,
            'gold': village.gold,
            'diamonds': village.diamonds,
        }
    
    elif item_type == 'worker':
        workers_max = calculate_workers_max(village)
        if village.workers + amount > workers_max:
            village.workers = workers_max
            actual_gain = workers_max - village.workers
        else:
            village.workers += amount
            actual_gain = amount
        
        return {
            'success': True,
            'item_sku': item_sku,
            'workers_gained': actual_gain,
            'workers': village.workers,
            'diamonds': village.diamonds,
        }
    
    elif item_type == 'energy':
        energy_max = calculate_energy_max(village)
        village.energy = min(energy_max + 20, village.energy + amount)
        
        return {
            'success': True,
            'item_sku': item_sku,
            'energy_gained': amount,
            'energy': village.energy,
            'diamonds': village.diamonds,
        }
    
    elif item_type == 'mine_charge':
        mine_state = village.mine_state
        mine_level = VillageCRUD.get_building_level(village, BuildingType.MINE)
        cap_charges = 3 + mine_level // 3
        mine_state.mining_charges = min(cap_charges, mine_state.mining_charges + amount)
        
        return {
            'success': True,
            'item_sku': item_sku,
            'charges_gained': amount,
            'charges': mine_state.mining_charges,
            'diamonds': village.diamonds,
        }
    
    elif item_type == 'pickaxe_bonus':
        mine_state = village.mine_state
        old_level = mine_state.pickaxe_level
        max_pickaxe = village.level * 2  # Cap at 2x village level
        mine_state.pickaxe_level = min(max_pickaxe, mine_state.pickaxe_level + amount)
        mine_state.pickaxe_power = 10 + 3 * mine_state.pickaxe_level
        
        return {
            'success': True,
            'item_sku': item_sku,
            'pickaxe_bonus': mine_state.pickaxe_level - old_level,
            'pickaxe_level': mine_state.pickaxe_level,
            'diamonds': village.diamonds,
        }
    
    elif item_type == 'vip_subscription':
        # TODO: Implement VIP system
        village.diamonds += cost  # Refund for now
        return {'success': False, 'error': 'vip_not_implemented'}
    
    return {'success': False, 'error': 'unknown_item_type'}

def create_payment_order(session: Session, village_id: int, item_sku: str, provider: str, payload_id: str) -> dict:
    """
    Create payment order for donate pack.
    """
    if not any(p['sku'] == item_sku for p in DONATE_PACKS):
        return {'success': False, 'error': 'pack_not_found'}
    
    pack = next((p for p in DONATE_PACKS if p['sku'] == item_sku), None)
    
    order = ShopOrder(
        village_id=village_id,
        provider=provider,
        payload_id=payload_id,
        item_sku=item_sku,
        amount_fiat=pack['price_fiat'],
        currency='RUB',
        diamonds_granted=pack['diamonds'] + pack['bonus'],
        status=ShopOrderStatus.CREATED,
    )
    session.add(order)
    session.flush()
    
    return {
        'success': True,
        'order_id': order.id,
        'diamonds': pack['diamonds'] + pack['bonus'],
        'price': pack['price_fiat'],
    }

def complete_payment(session: Session, payload_id: str, village: Village) -> dict:
    """
    Complete payment and grant diamonds.
    """
    from sqlalchemy import select
    
    order = session.execute(
        select(ShopOrder).where(ShopOrder.payload_id == payload_id)
    ).scalar_one_or_none()
    
    if not order:
        return {'success': False, 'error': 'order_not_found'}
    
    if order.status == ShopOrderStatus.PAID:
        # Idempotency: already paid
        return {'success': True, 'already_paid': True, 'diamonds_granted': order.diamonds_granted}
    
    if order.status != ShopOrderStatus.CREATED:
        return {'success': False, 'error': 'order_invalid_status'}
    
    # Grant diamonds
    village.diamonds += order.diamonds_granted
    order.status = ShopOrderStatus.PAID
    order.paid_at = datetime.utcnow()
    
    return {
        'success': True,
        'diamonds_granted': order.diamonds_granted,
        'diamonds': village.diamonds,
    }