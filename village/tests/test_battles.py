# tests/test_battles.py
import pytest
from app.db.models import Village, User, Building, BuildingType, MineState, BattleType
from app.services.battle_engine import (
    resolve_pve_battle, calculate_village_power, check_pvp_shield
)

@pytest.fixture
def user(db_session):
    user = User(tg_id=125, username="battletest")
    db_session.add(user)
    db_session.flush()
    return user

@pytest.fixture
def battle_village(db_session, user):
    village = Village(user_id=user.id, gold=500, troops=50, energy=100, level=2)
    db_session.add(village)
    db_session.flush()
    
    for btype in [BuildingType.TOWNHALL, BuildingType.FARM, BuildingType.BARN, 
                  BuildingType.BARRACKS, BuildingType.WALL]:
        b = Building(village_id=village.id, building_type=btype, level=2)
        db_session.add(b)
    
    mine = MineState(village_id=village.id)
    db_session.add(mine)
    db_session.flush()
    
    return village

def test_pve_battle_easy_success(db_session, battle_village):
    """Test PvE easy battle"""
    result = resolve_pve_battle(db_session, battle_village, 'easy')
    
    assert result['success'] is True
    assert 'result' in result
    assert 'casualty' in result

def test_pve_battle_no_energy(db_session, battle_village):
    """Test PvE with no energy"""
    battle_village.energy = 0
    result = resolve_pve_battle(db_session, battle_village, 'easy')
    
    assert result['success'] is False
    assert result['error'] == '