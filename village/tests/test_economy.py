# tests/test_economy.py
import pytest
from app.db.models import Village, User, Building, BuildingType, MineState
from app.services.economy import (
    work_action, harvest_action, sell_bread, buy_worker,
    calculate_energy_max, calculate_workers_max, calculate_farm_capacity
)
from datetime import datetime

@pytest.fixture
def user(db_session):
    user = User(tg_id=123, username="testuser")
    db_session.add(user)
    db_session.flush()
    return user

@pytest.fixture
def village(db_session, user):
    village = Village(user_id=user.id, gold=100, workers=2)
    db_session.add(village)
    db_session.flush()
    
    # Add buildings
    for btype in [BuildingType.TOWNHALL, BuildingType.FARM, BuildingType.BARN]:
        b = Building(village_id=village.id, building_type=btype, level=1)
        db_session.add(b)
    
    # Add mine state
    mine = MineState(village_id=village.id)
    db_session.add(mine)
    db_session.flush()
    
    return village

def test_work_action_success(db_session, village):
    """Test successful work action"""
    village.energy = 10
    result = work_action(db_session, village)
    
    assert result['success'] is True
    assert result['gain'] > 0
    assert village.energy < 10

def test_work_action_no_energy(db_session, village):
    """Test work with no energy"""
    village.energy = 0
    result = work_action(db_session, village)
    
    assert result['success'] is False
    assert result['error'] == 'not_enough_energy'

def test_harvest_action(db_session, village):
    """Test harvest action"""
    village.farm_storage = 50
    result = harvest_action(db_session, village)
    
    assert result['success'] is True
    assert result['farm_storage'] == village.farm_storage

def test_sell_bread_success(db_session, village):
    """Test selling bread"""
    village.farm_storage = 50
    result = sell_bread(db_session, village)
    
    assert result['success'] is True
    assert village.farm_storage < 50
    assert village.gold > 100

def test_sell_bread_not_enough(db_session, village):
    """Test selling with not enough bread"""
    village.farm_storage = 5
    result = sell_bread(db_session, village)
    
    assert result['success'] is False
    assert result['error'] == 'not_enough_bread'

def test_buy_worker_success(db_session, village):
    """Test buying worker"""
    village.gold = 100
    result = buy_worker(db_session, village)
    
    assert result['success'] is True
    assert village.workers == 3

def test_buy_worker_no_gold(db_session, village):
    """Test buying worker with no gold"""
    village.gold = 1
    result = buy_worker(db_session, village)
    
    assert result['success'] is False
    assert result['error'] == 'not_enough_gold'

def test_calculate_energy_max(village):
    """Test energy max calculation"""
    energy_max = calculate_energy_max(village)
    assert energy_max >= 60

def test_calculate_workers_max(village):
    """Test workers max calculation"""
    workers_max = calculate_workers_max(village)
    assert workers_max >= 10

def test_calculate_farm_capacity(village):
    """Test farm capacity calculation"""
    capacity = calculate_farm_capacity(village)
    assert capacity >= 500