# tests/test_mine.py
import pytest
from app.db.models import Village, User, Building, BuildingType, MineState, ResourceType
from app.services.mine_engine import (
    mine_dig_action, upgrade_pickaxe, roll_mine_drop,
    get_resources_for_depth
)

@pytest.fixture
def user(db_session):
    user = User(tg_id=124, username="minetest")
    db_session.add(user)
    db_session.flush()
    return user

@pytest.fixture
def village_with_mine(db_session, user):
    village = Village(user_id=user.id, gold=1000, energy=100)
    db_session.add(village)
    db_session.flush()
    
    for btype in [BuildingType.TOWNHALL, BuildingType.FARM, BuildingType.BARN, BuildingType.MINE]:
        b = Building(village_id=village.id, building_type=btype, level=1)
        db_session.add(b)
    
    mine = MineState(village_id=village.id, mining_charges=3, pickaxe_level=1)
    db_session.add(mine)
    db_session.flush()
    
    return village

def test_mine_dig_success(db_session, village_with_mine):
    """Test mining action"""
    mine = village_with_mine.mine_state
    result = mine_dig_action(db_session, mine, village_with_mine)
    
    assert result['success'] is True
    assert result['drops']
    assert mine.mining_charges == 2

def test_mine_dig_no_charges(db_session, village_with_mine):
    """Test mining with no charges"""
    mine = village_with_mine.mine_state
    mine.mining_charges = 0
    result = mine_dig_action(db_session, mine, village_with_mine)
    
    assert result['success'] is False
    assert result['error'] == 'no_charges'

def test_get_resources_for_depth():
    """Test resource probability table"""
    resources_1 = get_resources_for_depth(1)
    resources_10 = get_resources_for_depth(10)
    
    assert len(resources_1) > 0
    assert len(resources_10) > 0
    assert resources_10 != resources_1  # Different depth = different drops

def test_roll_mine_drop():
    """Test drop calculation"""
    drops = roll_mine_drop(5, 1, 0.05)
    
    assert drops
    assert drops[0][1] > 0  # Amount > 0