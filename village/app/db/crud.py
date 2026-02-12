# app/db/crud.py (ВЕСЬ КОД БЕЗ ИЗМЕНЕНИЙ)
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.db.models import (
    User, Village, Building, MineState, InventoryResource,
    Quest, UserActiveQuest, BattleLog, Leaderboard,
    BuildingType, ResourceType, LeaderboardType
)

class UserCRUD:
    @staticmethod
    def get_or_create(session: Session, tg_id: int, username: str = None, first_name: str = None):
        user = session.execute(select(User).where(User.tg_id == tg_id)).scalar_one_or_none()
        if not user:
            user = User(tg_id=tg_id, username=username, first_name=first_name)
            session.add(user)
            session.flush()
        return user
    
    @staticmethod
    def get_by_tg_id(session: Session, tg_id: int):
        return session.execute(select(User).where(User.tg_id == tg_id)).scalar_one_or_none()

class VillageCRUD:
    @staticmethod
    def get_with_lock(session: Session, user_id: int):
        """Get village with row-level lock for update"""
        return session.execute(
            select(Village)
            .where(Village.user_id == user_id)
            .with_for_update()
        ).scalar_one_or_none()
    
    @staticmethod
    def create(session: Session, user_id: int, name: str = "Деревня"):
        village = Village(user_id=user_id, name=name)
        session.add(village)
        session.flush()
        # Create default buildings
        for btype in [BuildingType.TOWNHALL, BuildingType.FARM, BuildingType.BARN, 
                      BuildingType.BARRACKS, BuildingType.WALL, BuildingType.MINE, BuildingType.WORKSHOP]:
            building = Building(village_id=village.id, building_type=btype, level=1)
            session.add(building)
        # Create mine state
        mine = MineState(village_id=village.id)
        session.add(mine)
        session.flush()
        return village
    
    @staticmethod
    def update_energy(session: Session, village: Village):
        """Lazy update energy regeneration"""
        now = datetime.utcnow()
        energy_max = VillageCRUD.calc_energy_max(village)
        delta_sec = int((now - village.energy_updated_at).total_seconds())
        regen = delta_sec // 300  # 1 energy per 5 minutes
        if regen > 0:
            village.energy = min(energy_max, village.energy + regen)
            village.energy_updated_at = now
    
    @staticmethod
    def update_farm(session: Session, village: Village):
        """Lazy update farm production"""
        now = datetime.utcnow()
        farm_level = VillageCRUD.get_building_level(village, BuildingType.FARM)
        barn_level = VillageCRUD.get_building_level(village, BuildingType.BARN)
        village_level = village.level
        workers = village.workers
        
        farm_capacity = 500 + 250 * barn_level + 50 * village_level
        base_rate = 20  # bread per hour
        rate = base_rate * (1 + 0.12 * farm_level) * (1 + 0.06 * workers) * (1 + 0.02 * village_level)
        
        delta_sec = (now - village.farm_updated_at).total_seconds()
        produced = int(rate / 3600 * delta_sec)
        
        village.farm_storage = min(farm_capacity, village.farm_storage + produced)
        village.farm_capacity = farm_capacity
        village.farm_updated_at = now
    
    @staticmethod
    def calc_energy_max(village: Village) -> int:
        townhall_level = VillageCRUD.get_building_level(village, BuildingType.TOWNHALL)
        return 60 + 4 * townhall_level + 2 * village.level
    
    @staticmethod
    def calc_workers_max(village: Village) -> int:
        townhall_level = VillageCRUD.get_building_level(village, BuildingType.TOWNHALL)
        return 10 + 5 * townhall_level
    
    @staticmethod
    def calc_troops_max(village: Village) -> int:
        barracks_level = VillageCRUD.get_building_level(village, BuildingType.BARRACKS)
        return 50 + 25 * barracks_level + 5 * village.level
    
    @staticmethod
    def get_building_level(village: Village, building_type: BuildingType) -> int:
        b = next((b for b in village.buildings if b.building_type == building_type), None)
        return b.level if b else 1
    
    @staticmethod
    def add_xp(session: Session, village: Village, amount: int):
        """Add XP and handle level up"""
        from app.config import XP_FORMULA
        village.xp += amount
        while village.xp >= XP_FORMULA(village.level):
            village.xp -= XP_FORMULA(village.level)
            village.level += 1

class MineCRUD:
    @staticmethod
    def update_charges(session: Session, mine_state: MineState):
        """Lazy update mining charges"""
        now = datetime.utcnow()
        mine_level = VillageCRUD.get_building_level(mine_state.village, BuildingType.MINE)
        cap_charges = 3 + mine_level // 3
        
        from app.config import MINING_CHARGE_SECONDS
        delta_sec = int((now - mine_state.mining_charges_updated_at).total_seconds())
        add = delta_sec // MINING_CHARGE_SECONDS
        
        if add > 0:
            mine_state.mining_charges = min(cap_charges, mine_state.mining_charges + add)
            mine_state.mining_charges_updated_at += timedelta(seconds=add * MINING_CHARGE_SECONDS)

class ResourceCRUD:
    @staticmethod
    def add_resource(session: Session, village_id: int, resource_type: ResourceType, amount: int):
        """Add resource to inventory"""
        inv = session.execute(
            select(InventoryResource)
            .where(InventoryResource.village_id == village_id)
            .where(InventoryResource.resource_type == resource_type)
        ).scalar_one_or_none()
        
        if inv:
            inv.amount += amount
        else:
            inv = InventoryResource(village_id=village_id, resource_type=resource_type, amount=amount)
            session.add(inv)
    
    @staticmethod
    def get_resource(session: Session, village_id: int, resource_type: ResourceType) -> int:
        inv = session.execute(
            select(InventoryResource)
            .where(InventoryResource.village_id == village_id)
            .where(InventoryResource.resource_type == resource_type)
        ).scalar_one_or_none()
        return inv.amount if inv else 0

class LeaderboardCRUD:
    @staticmethod
    def update_score(session: Session, village_id: int, lb_type: LeaderboardType, score: int):
        """Update or create leaderboard entry"""
        lb = session.execute(
            select(Leaderboard)
            .where(Leaderboard.village_id == village_id)
            .where(Leaderboard.type == lb_type)
        ).scalar_one_or_none()
        
        if lb:
            lb.score = score
            lb.updated_at = datetime.utcnow()
        else:
            lb = Leaderboard(village_id=village_id, type=lb_type, score=score)
            session.add(lb)
    
    @staticmethod
    def get_top(session: Session, lb_type: LeaderboardType, limit: int = 10):
        return session.execute(
            select(Leaderboard)
            .where(Leaderboard.type == lb_type)
            .order_by(Leaderboard.score.desc())
            .limit(limit)
        ).scalars().all()