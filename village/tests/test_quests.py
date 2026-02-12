 # tests/test_quests.py
import pytest
from app.services.quest_engine import (
    generate_quest_offers, start_quest, get_active_quests
)

def test_generate_quest_offers(test_db, test_village):
    """Test quest offer generation"""
    # Create some quests first
    from app.db.models import Quest, QuestType
    
    quest = Quest(
        quest_type=QuestType.COMBAT,
        title_ru="Test Quest",
        title_en="Test Quest",
        min_level=1,
        troops_required=5,
        gold_fee=10,
        reward_gold=20,
        reward_xp=10
    )
    test_db.add(quest)
    test_db.commit()
    
    offers = generate_quest_offers(test_db, test_village, 1)
    assert len(offers) > 0

def test_start_quest(test_db, test_village):
    """Test quest start"""
    from app.db.models import Quest, QuestType
    
    quest = Quest(
        quest_type=QuestType.COMBAT,
        title_ru="Test",
        title_en="Test",
        min_level=1,
        troops_required=0,
        gold_fee=5,
        reward_gold=10,
        reward_xp=10
    )
    test_db.ad