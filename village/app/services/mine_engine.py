# app/services/mine_engine.py
import random
from typing import List, Tuple
from sqlalchemy.orm import Session
from app.db.models import MineState, ResourceType
from app.db.crud import VillageCRUD, ResourceCRUD, MineCRUD
from app.config import XP_FORMULA

def get_mine_depth_table() -> dict:
    """Returns probability table for mine resources by depth"""
    return {
        (1, 2): [
            (ResourceType.STONE, 0.70),
            (ResourceType.COAL, 0.20),
            (ResourceType.COPPER_ORE, 0.10),
        ],
        (3, 5): [
            (ResourceType.STONE, 0.45),
            (ResourceType.COAL, 0.20),
            (ResourceType.COPPER_ORE, 0.20),
            (ResourceType.IRON_ORE, 0.15),
        ],
        (6, 9): [
            (ResourceType.STONE, 0.30),
            (ResourceType.COAL, 0.20),
            (ResourceType.COPPER_ORE, 0.15),
            (ResourceType.IRON_ORE, 0.25),
            (ResourceType.SILVER_ORE, 0.10),
        ],
        (10, 14): [
            (ResourceType.STONE, 0.20),
            (ResourceType.COAL, 0.20),
            (ResourceType.IRON_ORE, 0.25),
            (ResourceType.SILVER_ORE, 0.20),
            (ResourceType.GOLD_ORE, 0.12),
            (ResourceType.GEMS, 0.03),
        ],
        (15, 100): [
            (ResourceType.STONE, 0.15),
            (ResourceType.COAL, 0.15),
            (ResourceType.SILVER_ORE, 0.20),
            (ResourceType.GOLD_ORE, 0.20),
            (ResourceType.GEMS, 0.08),
        ],
    }

def get_resources_for_depth(depth: int) -> List[Tuple[ResourceType, float]]:
    """Get probability distribution for given depth"""
    table = get_mine_depth_table()
    for (min_d, max_d), resources in table.items():
        if min_d <= depth <= max_d:
            return resources
    return table[(15, 100)]

def roll_mine_drop(depth: int, pickaxe_level: int, pickaxe_bonus_crit: float) -> List[Tuple[ResourceType, int]]:
    """
    Roll for mine drop.
    Returns list of (resource_type, amount) tuples.
    """
    resources = get_resources_for_depth(depth)
    res_types = [r[0] for r in resources]
    weights = [r[1] for r in resources]
    
    res_type = random.choices(res_types, weights=weights, k=1)[0]
    
    # Base amount calculation
    base_amount = 8 + 2 * depth
    variance = random.uniform(0.8, 1.2)
    pickaxe_multiplier = 1 + 0.08 * pickaxe_level
    amount = int(base_amount * pickaxe_multiplier * variance)
    
    # Crit chance
    crit_chance = 0.05 + 0.01 * pickaxe_level + pickaxe_bonus_crit
    if random.random() < crit_chance:
        amount *= 2
    
    return [(res_type, amount)]

def calculate_pickaxe_upgrade_cost(pickaxe_level: int) -> dict:
    """Calculate cost to upgrade pickaxe"""
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

def mine_dig_action(session: Session, mine_state: MineState, village) -> dict:
    """
    Execute mining action.
    Requires energy and mining charges.
    """
    from app.services.economy import update_energy, calculate_energy_max
    
    energy_cost = 8
    
    # Update lazy values
    update_energy(session, village)
    MineCRUD.update_charges(session, mine_state)
    
    energy_max = calculate_energy_max(village)
    
    if mine_state.mining_charges <= 0:
        from datetime import timedelta
        next_charge_in = 600 - int((datetime.utcnow() - mine_state.mining_charges_updated_at).total_seconds() % 600)
        return {
            'success': False,
            'error': 'no_charges',
            'charges': mine_state.mining_charges,
            'next_charge_in': next_charge_in,
        }
    
    if village.energy < energy_cost:
        return {
            'success': False,
            'error': 'not_enough_energy',
            'needed': energy_cost,
            'current': village.energy,
        }
    
    # Spend resources
    village.energy -= energy_cost
    mine_state.mining_charges -= 1
    
    # Roll drops
    drops = roll_mine_drop(mine_state.mine_depth, mine_state.pickaxe_level, mine_state.pickaxe_bonus_crit)
    
    # Add to inventory
    for res_type, amount in drops:
        ResourceCRUD.add_resource(session, village.id, res_type, amount)
    
    # Award XP
    xp_gain = int(10 + mine_state.mine_depth * 0.5)
    from app.db.crud import VillageCRUD
    VillageCRUD.add_xp(session, village, xp_gain)
    
    return {
        'success': True,
        'drops': drops,
        'energy': village.energy,
        'energy_max': energy_max,
        'charges': mine_state.mining_charges,
        'xp_gained': xp_gain,
    }

def upgrade_pickaxe(session: Session, mine_state: MineState, village) -> dict:
    """
    Upgrade pickaxe to next level.
    Requires gold and ores.
    """
    cost = calculate_pickaxe_upgrade_cost(mine_state.pickaxe_level)
    
    # Check gold
    if village.gold < cost['gold']:
        return {
            'success': False,
            'error': 'not_enough_gold',
            'needed': cost['gold'],
            'have': village.gold,
        }
    
    # Check stone
    stone_have = ResourceCRUD.get_resource(session, village.id, ResourceType.STONE)
    if stone_have < cost['stone']:
        return {
            'success': False,
            'error': 'not_enough_stone',
            'needed': cost['stone'],
            'have': stone_have,
        }
    
    # Check coal
    coal_have = ResourceCRUD.get_resource(session, village.id, ResourceType.COAL)
    if coal_have < cost['coal']:
        return {
            'success': False,
            'error': 'not_enough_coal',
            'needed': cost['coal'],
            'have': coal_have,
        }
    
    # Check ore
    ore_have = ResourceCRUD.get_resource(session, village.id, cost['ore_type'])
    if ore_have < cost['ore_amount']:
        return {
            'success': False,
            'error': 'not_enough_ore',
            'ore_type': cost['ore_type'].value,
            'needed': cost['ore_amount'],
            'have': ore_have,
        }
    
    # Check gems
    gems_have = ResourceCRUD.get_resource(session, village.id, ResourceType.GEMS)
    if cost['gems'] > 0 and gems_have < cost['gems']:
        return {
            'success': False,
            'error': 'not_enough_gems',
            'needed': cost['gems'],
            'have': gems_have,
        }
    
    # Spend resources
    village.gold -= cost['gold']
    ResourceCRUD.add_resource(session, village.id, ResourceType.STONE, -cost['stone'])
    ResourceCRUD.add_resource(session, village.id, ResourceType.COAL, -cost['coal'])
    ResourceCRUD.add_resource(session, village.id, cost['ore_type'], -cost['ore_amount'])
    if cost['gems'] > 0:
        ResourceCRUD.add_resource(session, village.id, ResourceType.GEMS, -cost['gems'])
    
    # Upgrade pickaxe
    old_level = mine_state.pickaxe_level
    mine_state.pickaxe_level += 1
    mine_state.pickaxe_power = 10 + 3 * mine_state.pickaxe_level
    mine_state.pickaxe_bonus_crit = 0.05 + 0.01 * mine_state.pickaxe_level
    
    # Award XP
    VillageCRUD.add_xp(session, village, cost['gold'] // 5)
    
    return {
        'success': True,
        'old_level': old_level,
        'new_level': mine_state.pickaxe_level,
        'pickaxe_power': mine_state.pickaxe_power,
        'gold': village.gold,
    }

def upgrade_mine_depth(session: Session, mine_state: MineState, village, building_level: int) -> dict:
    """
    Upgrade mine depth (tied to MINE building level).
    """
    mine_state.mine_depth = building_level
    return {'success': True, 'new_depth': mine_state.mine_depth}