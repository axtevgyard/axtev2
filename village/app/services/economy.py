# app/services/economy.py
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.models import Village, Building, BuildingType, ResourceType
from app.db.crud import VillageCRUD, MineCRUD, ResourceCRUD
from app.config import XP_FORMULA

def calculate_xp_to_next_level(level: int) -> int:
    """Calculate XP needed to reach next level"""
    return XP_FORMULA(level)

def calculate_progress_percent(village: Village) -> float:
    """Calculate current level progress as percentage"""
    xp_needed = calculate_xp_to_next_level(village.level)
    return (village.xp / xp_needed * 100) if xp_needed > 0 else 0.0

def calculate_worker_cost(current_workers: int) -> int:
    """Calculate cost to hire next worker"""
    return round(5 + 2.2 * (current_workers ** 1.15))

def calculate_building_upgrade_cost(building_type: BuildingType, level: int) -> int:
    """Calculate cost to upgrade building"""
    from app.config import BUILDING_COSTS
    base = BUILDING_COSTS.get(building_type.value, 100)
    return round(base * (level ** 1.7) + 40 * level)

def calculate_pickaxe_upgrade_cost(pickaxe_level: int) -> dict:
    """Calculate full cost to upgrade pickaxe to next level"""
    next_level = pickaxe_level + 1
    gold_cost = round(30 * (next_level ** 1.6))
    stone = round(60 * (next_level ** 1.3))
    coal = round(20 * (next_level ** 1.25))
    
    if next_level <= 4:
        ore_type = ResourceType.COPPER_ORE
        ore_amount = 10 * next_level
    elif next_level <= 9:
        ore_type = ResourceType.IRON_ORE
        ore_amount = 8 * next_level
    elif next_level <= 14:
        ore_type = ResourceType.SILVER_ORE
        ore_amount = 6 * next_level
    else:
        ore_type = ResourceType.GOLD_ORE
        ore_amount = 5 * next_level
    
    gems = max(0, next_level // 3)
    
    return {
        'gold': gold_cost,
        'stone': stone,
        'coal': coal,
        'ore_type': ore_type,
        'ore_amount': ore_amount,
        'gems': gems,
    }

def calculate_troop_cost(troops_to_buy: int) -> int:
    """Calculate cost to buy troops"""
    base_cost = troops_to_buy * 1
    tax = round(0.02 * (troops_to_buy // 50))
    return base_cost + tax

def get_building_level(village: Village, building_type: BuildingType) -> int:
    """Get level of specific building"""
    b = next((b for b in village.buildings if b.building_type == building_type), None)
    return b.level if b else 1

def calculate_energy_max(village: Village) -> int:
    """Calculate maximum energy"""
    townhall_level = get_building_level(village, BuildingType.TOWNHALL)
    return 60 + 4 * townhall_level + 2 * village.level

def calculate_workers_max(village: Village) -> int:
    """Calculate maximum workers"""
    townhall_level = get_building_level(village, BuildingType.TOWNHALL)
    return 10 + 5 * townhall_level

def calculate_troops_max(village: Village) -> int:
    """Calculate maximum troops"""
    barracks_level = get_building_level(village, BuildingType.BARRACKS)
    return 50 + 25 * barracks_level + 5 * village.level

def calculate_farm_capacity(village: Village) -> int:
    """Calculate farm storage capacity"""
    barn_level = get_building_level(village, BuildingType.BARN)
    return 500 + 250 * barn_level + 50 * village.level

def calculate_farm_production_rate(village: Village) -> float:
    """Calculate farm production rate (bread per hour)"""
    farm_level = get_building_level(village, BuildingType.FARM)
    workers = village.workers
    village_level = village.level
    
    base_rate = 20
    rate = base_rate * (1 + 0.12 * farm_level) * (1 + 0.06 * workers) * (1 + 0.02 * village_level)
    return rate

def update_energy(session: Session, village: Village) -> int:
    """
    Lazy update energy regeneration.
    Returns updated energy amount.
    """
    now = datetime.utcnow()
    energy_max = calculate_energy_max(village)
    delta_sec = int((now - village.energy_updated_at).total_seconds())
    regen = delta_sec // 300  # 1 energy per 5 minutes
    
    if regen > 0:
        village.energy = min(energy_max, village.energy + regen)
        village.energy_updated_at = now
    
    return village.energy

def update_farm(session: Session, village: Village) -> int:
    """
    Lazy update farm production.
    Returns updated farm storage amount.
    """
    now = datetime.utcnow()
    farm_capacity = calculate_farm_capacity(village)
    rate = calculate_farm_production_rate(village)
    
    delta_sec = (now - village.farm_updated_at).total_seconds()
    produced = int(rate / 3600 * delta_sec)
    
    village.farm_storage = min(farm_capacity, village.farm_storage + produced)
    village.farm_capacity = farm_capacity
    village.farm_updated_at = now
    
    return village.farm_storage

def work_action(session: Session, village: Village) -> dict:
    """
    Execute /work action (active farming).
    Returns result dict with gain and updated values.
    """
    energy_cost = 6
    energy_max = calculate_energy_max(village)
    
    # Update lazy values first
    update_energy(session, village)
    update_farm(session, village)
    
    if village.energy < energy_cost:
        return {'success': False, 'error': 'not_enough_energy', 'needed': energy_cost, 'current': village.energy}
    
    # Spend energy
    village.energy -= energy_cost
    
    # Calculate work gain
    farm_level = get_building_level(village, BuildingType.FARM)
    workers = village.workers
    work_gain = round(30 * (1 + 0.05 * workers) * (1 + 0.08 * farm_level))
    
    # Add to storage
    farm_capacity = village.farm_capacity
    village.farm_storage = min(farm_capacity, village.farm_storage + work_gain)
    
    # Award XP
    VillageCRUD.add_xp(session, village, 5)
    
    return {
        'success': True,
        'gain': work_gain,
        'energy': village.energy,
        'energy_max': energy_max,
        'farm_storage': village.farm_storage,
        'farm_capacity': farm_capacity,
        'xp_gained': 5,
    }

def harvest_action(session: Session, village: Village) -> dict:
    """
    Execute harvest action (just update farm, no cost).
    Returns updated state.
    """
    update_energy(session, village)
    update_farm(session, village)
    
    energy_max = calculate_energy_max(village)
    
    return {
        'success': True,
        'energy': village.energy,
        'energy_max': energy_max,
        'farm_storage': village.farm_storage,
        'farm_capacity': village.farm_capacity,
    }

def sell_bread(session: Session, village: Village) -> dict:
    """
    Sell bread for gold.
    Sells in batches of 10 bread.
    """
    update_farm(session, village)
    
    if village.farm_storage < 10:
        return {'success': False, 'error': 'not_enough_bread', 'have': village.farm_storage}
    
    market_level = get_building_level(village, BuildingType.FARM)  # proxy for market
    batches = village.farm_storage // 10
    
    gold_per_batch = 1 + (market_level // 5)
    gold_gain = batches * gold_per_batch
    
    village.gold += gold_gain
    village.farm_storage = village.farm_storage % 10
    
    # Award XP: 1 per 10 bread
    VillageCRUD.add_xp(session, village, batches)
    
    return {
        'success': True,
        'gold_gained': gold_gain,
        'batches': batches,
        'gold': village.gold,
        'farm_storage': village.farm_storage,
        'xp_gained': batches,
    }

def buy_worker(session: Session, village: Village) -> dict:
    """
    Buy a worker for gold.
    """
    workers_max = calculate_workers_max(village)
    if village.workers >= workers_max:
        return {'success': False, 'error': 'workers_max_reached', 'max': workers_max}
    
    cost = calculate_worker_cost(village.workers)
    if village.gold < cost:
        return {'success': False, 'error': 'not_enough_gold', 'needed': cost, 'have': village.gold}
    
    village.gold -= cost
    village.workers += 1
    
    return {
        'success': True,
        'cost': cost,
        'workers': village.workers,
        'workers_max': workers_max,
        'gold': village.gold,
    }

def buy_troops(session: Session, village: Village, amount: int) -> dict:
    """
    Buy troops for gold.
    """
    troops_max = calculate_troops_max(village)
    if village.troops + amount > troops_max:
        amount = troops_max - village.troops
    
    cost = calculate_troop_cost(amount)
    if village.gold < cost:
        return {'success': False, 'error': 'not_enough_gold', 'needed': cost, 'have': village.gold, 'max_buyable': 0}
    
    village.gold -= cost
    village.troops += amount
    
    return {
        'success': True,
        'cost': cost,
        'troops_bought': amount,
        'troops': village.troops,
        'troops_max': troops_max,
        'gold': village.gold,
    }

def upgrade_building(session: Session, village: Village, building_type: BuildingType) -> dict:
    """
    Upgrade a building.
    """
    building = next((b for b in village.buildings if b.building_type == building_type), None)
    if not building:
        return {'success': False, 'error': 'building_not_found'}
    
    cost = calculate_building_upgrade_cost(building_type, building.level)
    if village.gold < cost:
        return {'success': False, 'error': 'not_enough_gold', 'needed': cost, 'have': village.gold}
    
    village.gold -= cost
    building.level += 1
    
    # Award XP
    VillageCRUD.add_xp(session, village, cost // 10)
    
    return {
        'success': True,
        'cost': cost,
        'building': building_type.value,
        'new_level': building.level,
        'gold': village.gold,
    }

def buy_energy_potion(session: Session, village: Village) -> dict:
    """
    Buy energy potion for diamonds.
    Grants +30 energy.
    """
    energy_max = calculate_energy_max(village)
    energy_cost = 3
    energy_gain = 30
    
    if village.diamonds < energy_cost:
        return {'success': False, 'error': 'not_enough_diamonds', 'needed': energy_cost, 'have': village.diamonds}
    
    village.diamonds -= energy_cost
    village.energy = min(energy_max + 20, village.energy + energy_gain)
    
    return {
        'success': True,
        'cost': energy_cost,
        'energy_gained': energy_gain,
        'energy': village.energy,
        'energy_max': energy_max,
        'diamonds': village.diamonds,
    }

def add_daily_bonus(session: Session, village: Village) -> dict:
    """
    Award daily bonus (gold, energy, rare diamond).
    Only once per 24 hours.
    """
    from app.config import DAILY_BONUS_GOLD, DAILY_BONUS_ENERGY, DAILY_BONUS_DIAMOND_CHANCE
    import random
    
    now = datetime.utcnow()
    last_bonus = village.last_daily_bonus_at
    
    if last_bonus and (now - last_bonus).total_seconds() < 86400:
        return {'success': False, 'error': 'cooldown', 'seconds_until': 86400 - int((now - last_bonus).total_seconds())}
    
    village.gold += DAILY_BONUS_GOLD
    energy_max = calculate_energy_max(village)
    village.energy = min(energy_max, village.energy + DAILY_BONUS_ENERGY)
    
    diamond_bonus = 0
    if random.random() < DAILY_BONUS_DIAMOND_CHANCE:
        village.diamonds += 1
        diamond_bonus = 1
    
    village.last_daily_bonus_at = now
    
    return {
        'success': True,
        'gold': DAILY_BONUS_GOLD,
        'energy': DAILY_BONUS_ENERGY,
        'diamonds': diamond_bonus,
    }

# app/services/economy.py - добавить эту функцию в конец
def get_building_description(building_type, level):
    """Get description for building"""
    descriptions = {
        BuildingType.TOWNHALL: f"Увеличивает лимит рабочих и энергию (+{4*level} энергии)",
        BuildingType.FARM: f"Производит хлеб (+12% за уровень)",
        BuildingType.BARN: f"Склад для хранения (+250 мест за уровень)",
        BuildingType.BARRACKS: f"Казарма для войск (+25 войск за уровень)",
        BuildingType.WALL: f"Защита от атак (+{10*level}% защиты)",
        BuildingType.MINE: f"Добыча ресурсов (+{level} зарядов)",
        BuildingType.WORKSHOP: f"Улучшение оборудования (+{10*level}% эффективности)",
    }
    return descriptions.get(building_type, "Неизвестное здание")