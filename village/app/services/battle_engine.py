# app/services/battle_engine.py
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.models import Village, BattleLog, BattleType, BattleResult, BuildingType
from app.db.crud import VillageCRUD

def calculate_village_power(village: Village) -> int:
    """Calculate village combat power"""
    barracks_level = VillageCRUD.get_building_level(village, BuildingType.BARRACKS)
    wall_level = VillageCRUD.get_building_level(village, BuildingType.WALL)
    
    troop_power = village.troops * (1 + 0.06 * barracks_level) * (1 + 0.01 * village.level)
    wall_bonus = 10 * wall_level
    
    return int(troop_power + wall_bonus)

def check_pvp_shield(village: Village) -> bool:
    """Check if village has PvP shield (after defeat or newbie)"""
    if village.level < 3:
        return True  # Newbie shield
    
    if village.pvp_shield_until and village.pvp_shield_until > datetime.utcnow():
        return True
    
    return False

def apply_pvp_shield(village: Village, minutes: int = 30):
    """Apply PvP shield after defeat"""
    from app.config import PVP_SHIELD_MINUTES
    village.pvp_shield_until = datetime.utcnow() + timedelta(minutes=minutes)

def resolve_pve_battle(session: Session, attacker: Village, difficulty: str) -> dict:
    """
    Resolve PvE (vs NPC) battle.
    difficulty: 'easy', 'medium', 'hard'
    """
    from app.services.economy import update_energy, calculate_energy_max
    
    update_energy(session, attacker)
    energy_max = calculate_energy_max(attacker)
    
    # Config for each difficulty
    config = {
        'easy': {
            'energy_cost': 8,
            'required_troops_min': 5,
            'enemy_power': 30,
            'base_win_chance': 0.70,
            'rewards_gold': 20,
            'rewards_xp': 20,
            'medal_chance': 0.05,
            'casualty_percent': 0.10,
        },
        'medium': {
            'energy_cost': 10,
            'required_troops_min': 12,
            'enemy_power': 80,
            'base_win_chance': 0.50,
            'rewards_gold': 50,
            'rewards_xp': 50,
            'medal_chance': 0.10,
            'casualty_percent': 0.20,
        },
        'hard': {
            'energy_cost': 12,
            'required_troops_min': 20,
            'enemy_power': 180,
            'base_win_chance': 0.30,
            'rewards_gold': 100,
            'rewards_xp': 100,
            'medal_chance': 0.15,
            'casualty_percent': 0.30,
        },
    }
    
    cfg = config.get(difficulty, config['easy'])
    
    if attacker.energy < cfg['energy_cost']:
        return {'success': False, 'error': 'not_enough_energy', 'needed': cfg['energy_cost']}
    
    if attacker.troops < cfg['required_troops_min']:
        return {'success': False, 'error': 'not_enough_troops', 'needed': cfg['required_troops_min']}
    
    # Spend energy
    attacker.energy -= cfg['energy_cost']
    
    # Calculate win chance
    attacker_power = int(attacker.troops * (1 + 0.06 * VillageCRUD.get_building_level(attacker, BuildingType.BARRACKS)))
    enemy_power = cfg['enemy_power']
    
    win_chance = min(0.95, max(0.05, 0.15 + attacker_power / (attacker_power + enemy_power)))
    
    # Roll result with seed
    seed = random.randint(0, 2147483647)
    random.seed(seed)
    is_win = random.random() < win_chance
    
    # Calculate casualties and rewards
    if is_win:
        casualty = int(attacker.troops * cfg['casualty_percent'] * random.uniform(0.5, 1.0))
        attacker.troops -= casualty
        attacker.gold += cfg['rewards_gold']
        VillageCRUD.add_xp(session, attacker, cfg['rewards_xp'])
        
        medal_gain = 0
        if random.random() < cfg['medal_chance']:
            medal_gain = 1
            attacker.medals += 1
        
        result = BattleResult.WIN
        gold_delta = cfg['rewards_gold']
        medals_delta = medal_gain
    else:
        casualty = int(attacker.troops * cfg['casualty_percent'] * random.uniform(1.0, 2.0))
        attacker.troops -= casualty
        attacker.gold = max(0, attacker.gold - random.randint(2, 10))
        VillageCRUD.add_xp(session, attacker, max(4, cfg['rewards_xp'] // 2))
        
        # Apply PvP shield
        apply_pvp_shield(attacker)
        
        result = BattleResult.LOSE
        gold_delta = -random.randint(2, 10)
        medals_delta = 0
    
    # Create battle log
    battle_log = BattleLog(
        attacker_village_id=attacker.id,
        defender_village_id=None,
        battle_type=BattleType.PVE,
        difficulty=difficulty,
        attacker_troops_sent=attacker.troops + casualty,
        attacker_troops_casualties=casualty,
        defender_power_snapshot=enemy_power,
        attacker_power_snapshot=attacker_power,
        seed=seed,
        result=result,
        gold_delta_attacker=gold_delta,
        medals_delta_attacker=medals_delta,
    )
    session.add(battle_log)
    
    return {
        'success': True,
        'result': result.value,
        'is_win': is_win,
        'casualty': casualty,
        'troops': attacker.troops,
        'gold_delta': gold_delta,
        'xp_gained': cfg['rewards_xp'] if is_win else max(4, cfg['rewards_xp'] // 2),
        'medals_gained': medals_delta,
        'gold': attacker.gold,
        'medals': attacker.medals,
        'energy': attacker.energy,
    }

def find_pvp_opponent(session: Session, attacker: Village) -> Village:
    """Find a suitable PvP opponent"""
    from sqlalchemy import select
    from app.db.models import User
    
    # Find villages within level range and not recently attacked
    min_level = max(1, attacker.level - 2)
    max_level = attacker.level + 2
    
    defender = session.execute(
        select(Village)
        .where(Village.id != attacker.id)
        .where(Village.level >= min_level)
        .where(Village.level <= max_level)
        .order_by(random.random())
        .limit(1)
    ).scalar_one_or_none()
    
    return defender

def resolve_pvp_battle(session: Session, attacker: Village, defender: Village, troops_sent: int) -> dict:
    """
    Resolve PvP battle between two villages.
    """
    from app.services.economy import update_energy, calculate_energy_max
    
    update_energy(session, attacker)
    energy_max = calculate_energy_max(attacker)
    
    energy_cost = 12
    
    if attacker.energy < energy_cost:
        return {'success': False, 'error': 'not_enough_energy', 'needed': energy_cost}
    
    if attacker.troops < troops_sent:
        return {'success': False, 'error': 'not_enough_troops', 'needed': troops_sent}
    
    if check_pvp_shield(defender):
        return {'success': False, 'error': 'defender_shield'}
    
    # Spend energy
    attacker.energy -= energy_cost
    
    # Calculate power
    attacker_power = int(troops_sent * (1 + 0.06 * VillageCRUD.get_building_level(attacker, BuildingType.BARRACKS)) * (1 + 0.01 * attacker.level))
    defender_power = int(defender.troops * (1 + 0.06 * VillageCRUD.get_building_level(defender, BuildingType.BARRACKS)) * (1 + 0.01 * defender.level))
    wall_bonus = 10 * VillageCRUD.get_building_level(defender, BuildingType.WALL)
    defender_power += wall_bonus
    
    # Roll result
    win_chance = min(0.95, max(0.05, 0.15 + attacker_power / (attacker_power + defender_power)))
    
    seed = random.randint(0, 2147483647)
    random.seed(seed)
    is_win = random.random() < win_chance
    
    if is_win:
        # Attacker wins
        casualty = int(troops_sent * 0.05 * random.uniform(0.5, 1.0))
        attacker.troops -= casualty
        
        steal_gold = min(int(defender.gold * 0.03), 50 + 10 * attacker.level)
        attacker.gold += steal_gold
        defender.gold -= steal_gold
        
        medal_gain = random.randint(1, 3)
        attacker.medals += medal_gain
        
        VillageCRUD.add_xp(session, attacker, 30)
        
        # Apply shield to defender
        apply_pvp_shield(defender)
        
        result = BattleResult.WIN
        gold_delta = steal_gold
        medals_delta = medal_gain
    else:
        # Attacker loses
        casualty = int(troops_sent * 0.20 * random.uniform(1.0, 2.0))
        attacker.troops -= casualty
        
        penalty_gold = random.randint(2, 10)
        attacker.gold = max(0, attacker.gold - penalty_gold)
        
        VillageCRUD.add_xp(session, attacker, 10)
        
        # Apply shield to attacker
        apply_pvp_shield(attacker)
        
        result = BattleResult.LOSE
        gold_delta = -penalty_gold
        medals_delta = 0
    
    # Create battle log
    battle_log = BattleLog(
        attacker_village_id=attacker.id,
        defender_village_id=defender.id,
        battle_type=BattleType.PVP,
        attacker_troops_sent=troops_sent,
        attacker_troops_casualties=casualty,
        defender_power_snapshot=defender_power,
        attacker_power_snapshot=attacker_power,
        seed=seed,
        result=result,
        gold_delta_attacker=gold_delta,
        medals_delta_attacker=medals_delta,
    )
    session.add(battle_log)
    
    return {
        'success': True,
        'result': result.value,
        'is_win': is_win,
        'casualty': casualty,
        'troops': attacker.troops,
        'gold_delta': gold_delta,
        'gold': attacker.gold,
        'medals_gained': medals_delta,
        'medals': attacker.medals,
        'energy': attacker.energy,
        'defender_name': defender.name,
    }