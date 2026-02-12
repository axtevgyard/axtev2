# app/services/quest_engine.py
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.models import (
    Quest, UserActiveQuest, QuestStatus, QuestType, 
    Village, BuildingType, ResourceType
)
from app.db.crud import VillageCRUD, ResourceCRUD

def generate_quest_offers(session: Session, village: Village, count: int = 3) -> list:
    """
    Generate random quest offers suitable for player level.
    """
    quests = session.execute(
        select(Quest)
        .where(Quest.min_level <= village.level)
        .order_by(random.random())
        .limit(count)
    ).scalars().all()
    
    return quests

def start_quest(session: Session, village: Village, quest: Quest) -> dict:
    """
    Start a quest for the village.
    """
    from app.services.economy import update_energy
    update_energy(session, village)
    
    # Check requirements
    if village.level < quest.min_level:
        return {'success': False, 'error': 'level_too_low', 'required': quest.min_level}
    
    if quest.troops_required > 0:
        if village.troops < quest.troops_required:
            return {'success': False, 'error': 'not_enough_troops', 'needed': quest.troops_required}
        troops_locked = quest.troops_required
    else:
        troops_locked = 0
    
    if quest.gold_fee > 0:
        if village.gold < quest.gold_fee:
            return {'success': False, 'error': 'not_enough_gold', 'needed': quest.gold_fee}
        village.gold -= quest.gold_fee
    
    # Lock troops
    if troops_locked > 0:
        village.troops -= troops_locked
    
    # Create active quest
    now = datetime.utcnow()
    duration = timedelta(seconds=quest.duration_sec) if quest.duration_sec > 0 else timedelta(seconds=1)
    ends_at = now + duration if quest.duration_sec > 0 else now
    
    active_quest = UserActiveQuest(
        village_id=village.id,
        quest_id=quest.id,
        status=QuestStatus.RUNNING if quest.duration_sec > 0 else QuestStatus.FINISHED,
        troops_locked=troops_locked,
        started_at=now,
        ends_at=ends_at,
        result_seed=random.randint(0, 2147483647),
    )
    session.add(active_quest)
    session.flush()
    
    return {
        'success': True,
        'active_quest_id': active_quest.id,
        'duration': quest.duration_sec,
        'troops_locked': troops_locked,
        'gold_spent': quest.gold_fee,
        'gold': village.gold,
        'troops': village.troops,
    }

def finish_quest(session: Session, active_quest: UserActiveQuest, village: Village) -> dict:
    """
    Finish a quest and award rewards.
    """
    quest = session.execute(
        select(Quest).where(Quest.id == active_quest.quest_id)
    ).scalar_one()
    
    # Determine result based on seed
    random.seed(active_quest.result_seed)
    is_success = random.random() < quest.success_chance
    
    # Return troops (with possible casualties)
    troops_returned = active_quest.troops_locked
    if is_success:
        casualty = int(troops_returned * random.uniform(0.0, 0.2))
    else:
        casualty = int(troops_returned * random.uniform(0.2, 0.6))
    
    troops_returned -= casualty
    active_quest.troops_casualties = casualty
    village.troops += troops_returned
    
    # Award rewards if success
    if is_success:
        active_quest.status = QuestStatus.FINISHED
        
        village.gold += quest.reward_gold
        VillageCRUD.add_xp(session, village, quest.reward_xp)
        village.medals += quest.reward_medals
        
        if quest.reward_resource_type and quest.reward_resource_amount:
            ResourceCRUD.add_resource(session, village.id, quest.reward_resource_type, quest.reward_resource_amount)
        
        return {
            'success': True,
            'result': 'win',
            'gold_gained': quest.reward_gold,
            'xp_gained': quest.reward_xp,
            'medals_gained': quest.reward_medals,
            'casualty': casualty,
            'gold': village.gold,
            'troops': village.troops,
            'medals': village.medals,
        }
    else:
        active_quest.status = QuestStatus.FAILED
        
        return {
            'success': True,
            'result': 'fail',
            'casualty': casualty,
            'gold': village.gold,
            'troops': village.troops,
        }

def claim_quest_reward(session: Session, active_quest: UserActiveQuest, village: Village) -> dict:
    """
    Claim rewards from finished quest.
    """
    if active_quest.status != QuestStatus.FINISHED:
        return {'success': False, 'error': 'quest_not_finished'}
    
    quest = session.execute(
        select(Quest).where(Quest.id == active_quest.quest_id)
    ).scalar_one()
    
    active_quest.status = QuestStatus.CLAIMED
    active_quest.claimed_at = datetime.utcnow()
    
    return {'success': True, 'claimed': True}

def get_active_quests(session: Session, village: Village) -> list:
    """
    Get all active quests for village.
    """
    return session.execute(
        select(UserActiveQuest)
        .where(UserActiveQuest.village_id == village.id)
        .where(UserActiveQuest.status.in_([QuestStatus.RUNNING, QuestStatus.FINISHED]))
    ).scalars().all()

def check_quest_completion(session: Session, active_quest: UserActiveQuest) -> bool:
    """
    Check if quest should be completed (timer expired).
    """
    if active_quest.status != QuestStatus.RUNNING:
        return False
    
    return datetime.utcnow() >= active_quest.ends_at