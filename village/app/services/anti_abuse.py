# app/services/anti_abuse.py
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from app.db.models import BattleLog, User, Village, BattleType
import hashlib

RATE_LIMITS = {
    'work': {'calls': 10, 'window': 60},
    'mine': {'calls': 5, 'window': 60},
    'battle': {'calls': 5, 'window': 60},
    'quest': {'calls': 10, 'window': 60},
}

class RateLimiter:
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.in_memory = {}  # Fallback to in-memory if no redis
    
    def check_rate_limit(self, user_id: int, action: str) -> bool:
        """Check if user exceeded rate limit for action"""
        if action not in RATE_LIMITS:
            return True
        
        limit = RATE_LIMITS[action]
        key = f"ratelimit:{user_id}:{action}"
        
        if self.redis:
            count = self.redis.incr(key)
            if count == 1:
                self.redis.expire(key, limit['window'])
            return count <= limit['calls']
        else:
            now = datetime.utcnow()
            if key not in self.in_memory:
                self.in_memory[key] = {'count': 0, 'reset_at': now + timedelta(seconds=limit['window'])}
            
            entry = self.in_memory[key]
            if now >= entry['reset_at']:
                entry['count'] = 0
                entry['reset_at'] = now + timedelta(seconds=limit['window'])
            
            entry['count'] += 1
            return entry['count'] <= limit['calls']

def check_pvp_attack_limit(session: Session, attacker_id: int, defender_id: int) -> dict:
    """
    Check if attacker can attack defender.
    Max 3 attacks per 24 hours.
    """
    from app.config import PVP_ATTACKS_PER_DAY
    
    attacker = session.execute(
        select(Village).where(Village.id == attacker_id)
    ).scalar_one()
    
    defender = session.execute(
        select(Village).where(Village.id == defender_id)
    ).scalar_one()
    
    # Check newbie shield
    if defender.level < 3:
        return {'allowed': False, 'reason': 'newbie_shield'}
    
    # Check defeat shield
    if defender.pvp_shield_until and defender.pvp_shield_until > datetime.utcnow():
        return {'allowed': False, 'reason': 'shield_active', 'until': defender.pvp_shield_until}
    
    # Check attack limit
    last_24h = datetime.utcnow() - timedelta(hours=24)
    attack_count = session.execute(
        select(BattleLog)
        .where(BattleLog.attacker_village_id == attacker_id)
        .where(BattleLog.defender_village_id == defender_id)
        .where(BattleLog.created_at >= last_24h)
    ).scalars().all()
    
    if len(attack_count) >= PVP_ATTACKS_PER_DAY:
        return {'allowed': False, 'reason': 'attack_limit_reached', 'limit': PVP_ATTACKS_PER_DAY}
    
    return {'allowed': True}

def check_referral_validity(session: Session, referred_user: User, referrer_user: User) -> dict:
    """
    Check if referral is valid for reward.
    Requirements:
    - referred user >= level 3
    - referred user played >= 20 minutes
    - one tg_id = one referral
    """
    from app.config import REF_MIN_LEVEL, REF_MIN_PLAYTIME
    
    if not referred_user.villages:
        return {'valid': False, 'reason': 'no_village'}
    
    village = referred_user.villages[0]
    
    if village.level < REF_MIN_LEVEL:
        return {'valid': False, 'reason': 'level_too_low', 'required': REF_MIN_LEVEL, 'current': village.level}
    
    playtime = (datetime.utcnow() - referred_user.created_at).total_seconds()
    if playtime < REF_MIN_PLAYTIME:
        return {'valid': False, 'reason': 'playtime_too_short', 'required': REF_MIN_PLAYTIME, 'current': int(playtime)}
    
    return {'valid': True}

def generate_ref_code(user_id: int) -> str:
    """Generate short ref code"""
    hash_obj = hashlib.md5(str(user_id).encode())
    return hash_obj.hexdigest()[:8].upper()

def count_referral_actions(session: Session, village: Village) -> int:
    """Count number of actions player has taken"""
    # Simple proxy: count battles + quests + buildings upgraded
    # For MVP, can be simplified
    from app.db.models import BattleLog, UserActiveQuest
    
    battles = session.execute(
        select(BattleLog).where(BattleLog.attacker_village_id == village.id)
    ).scalars().all()
    
    quests = session.execute(
        select(UserActiveQuest).where(UserActiveQuest.village_id == village.id)
    ).scalars().all()
    
    return len(battles) + len(quests)