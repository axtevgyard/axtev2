# app/db/models.py
import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, BigInteger, String, Boolean, Float, ForeignKey, 
    DateTime, Enum as SQLEnum, UniqueConstraint, Text
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()

# ========== ENUMS ==========

class BuildingType(enum.Enum):
    TOWNHALL = "TOWNHALL"
    FARM = "FARM"
    BARN = "BARN"
    BARRACKS = "BARRACKS"
    WALL = "WALL"
    MINE = "MINE"
    WORKSHOP = "WORKSHOP"

class ResourceType(enum.Enum):
    STONE = "STONE"
    COAL = "COAL"
    COPPER_ORE = "COPPER_ORE"
    IRON_ORE = "IRON_ORE"
    SILVER_ORE = "SILVER_ORE"
    GOLD_ORE = "GOLD_ORE"
    GEMS = "GEMS"
    WOOD = "WOOD"
    CLAY = "CLAY"

class QuestStatus(enum.Enum):
    OFFERED = "OFFERED"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    CLAIMED = "CLAIMED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"

class QuestType(enum.Enum):
    COMBAT = "COMBAT"
    ECONOMIC = "ECONOMIC"
    MINING = "MINING"

class BattleType(enum.Enum):
    PVE = "PVE"
    PVP = "PVP"

class BattleResult(enum.Enum):
    WIN = "WIN"
    LOSE = "LOSE"
    DRAW = "DRAW"

class ShopOrderStatus(enum.Enum):
    CREATED = "CREATED"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"

class LeaderboardType(enum.Enum):
    MEDALS = "MEDALS"
    LEVEL = "LEVEL"
    GOLD = "GOLD"

# ========== MODELS (NO INDEXES) ==========

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(64))
    first_name = Column(String(64))
    lang = Column(String(2), default="ru")
    created_at = Column(DateTime, server_default=func.now())
    last_seen_at = Column(DateTime, server_default=func.now())
    is_banned = Column(Boolean, default=False)
    ref_code = Column(String(8), unique=True)
    referred_by_user_id = Column(Integer, ForeignKey("users.id"))
    referred_count = Column(Integer, default=0)

    villages = relationship("Village", back_populates="user", cascade="all, delete-orphan")


class Village(Base):
    __tablename__ = "villages"
    __table_args__ = (
        UniqueConstraint('user_id', name='uq_user_village'),
    )
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(40), default="Деревня")
    level = Column(Integer, default=1)
    xp = Column(BigInteger, default=0)
    gold = Column(BigInteger, default=50)
    diamonds = Column(BigInteger, default=0)
    medals = Column(BigInteger, default=0)
    workers = Column(Integer, default=2)
    troops = Column(Integer, default=0)
    energy = Column(Integer, default=60)
    energy_updated_at = Column(DateTime, server_default=func.now())
    farm_storage = Column(Integer, default=0)
    farm_capacity = Column(Integer, default=500)
    farm_updated_at = Column(DateTime, server_default=func.now())
    last_notify_full_at = Column(DateTime, nullable=True)
    last_daily_bonus_at = Column(DateTime, nullable=True)
    pvp_shield_until = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="villages")
    buildings = relationship("Building", back_populates="village", cascade="all, delete-orphan")
    mine_state = relationship("MineState", uselist=False, back_populates="village", cascade="all, delete-orphan")
    inventory_resources = relationship("InventoryResource", back_populates="village", cascade="all, delete-orphan")


class Building(Base):
    __tablename__ = "buildings"
    
    id = Column(Integer, primary_key=True)
    village_id = Column(Integer, ForeignKey("villages.id"), nullable=False)
    building_type = Column(SQLEnum(BuildingType), nullable=False)
    level = Column(Integer, default=1)

    village = relationship("Village", back_populates="buildings")


class MineState(Base):
    __tablename__ = "mine_state"
    
    id = Column(Integer, primary_key=True)
    village_id = Column(Integer, ForeignKey("villages.id"), nullable=False, unique=True)
    pickaxe_level = Column(Integer, default=1)
    pickaxe_power = Column(Integer, default=13)
    pickaxe_bonus_crit = Column(Float, default=0.05)
    mine_depth = Column(Integer, default=1)
    mining_charges = Column(Integer, default=3)
    mining_charges_updated_at = Column(DateTime, server_default=func.now())
    last_mine_at = Column(DateTime, nullable=True)

    village = relationship("Village", back_populates="mine_state")


class InventoryResource(Base):
    __tablename__ = "inventory_resources"
    __table_args__ = (
        UniqueConstraint('village_id', 'resource_type', name='uq_village_resource'),
    )
    
    id = Column(Integer, primary_key=True)
    village_id = Column(Integer, ForeignKey("villages.id"), nullable=False)
    resource_type = Column(SQLEnum(ResourceType), nullable=False)
    amount = Column(BigInteger, default=0)

    village = relationship("Village", back_populates="inventory_resources")


class Quest(Base):
    __tablename__ = "quests"
    
    id = Column(Integer, primary_key=True)
    quest_type = Column(SQLEnum(QuestType), nullable=False)
    title_ru = Column(String(256), nullable=False)
    title_en = Column(String(256), nullable=False)
    description_ru = Column(Text)
    description_en = Column(Text)
    min_level = Column(Integer, default=1)
    troops_required = Column(Integer, default=0)
    gold_fee = Column(Integer, default=0)
    duration_sec = Column(Integer, default=0)
    success_chance = Column(Float, default=1.0)
    reward_gold = Column(Integer, default=0)
    reward_xp = Column(Integer, default=0)
    reward_medals = Column(Integer, default=0)
    reward_resource_type = Column(SQLEnum(ResourceType), nullable=True)
    reward_resource_amount = Column(Integer, nullable=True)


class UserActiveQuest(Base):
    __tablename__ = "user_active_quests"
    
    id = Column(Integer, primary_key=True)
    village_id = Column(Integer, ForeignKey("villages.id"), nullable=False)
    quest_id = Column(Integer, ForeignKey("quests.id"), nullable=False)
    status = Column(SQLEnum(QuestStatus), nullable=False)
    troops_locked = Column(Integer, default=0)
    troops_casualties = Column(Integer, default=0)
    started_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    result_seed = Column(Integer, nullable=True)
    claimed_at = Column(DateTime, nullable=True)


class BattleLog(Base):
    __tablename__ = "battle_logs"
    
    id = Column(Integer, primary_key=True)
    attacker_village_id = Column(Integer, ForeignKey("villages.id"), nullable=False)
    defender_village_id = Column(Integer, ForeignKey("villages.id"), nullable=True)
    battle_type = Column(SQLEnum(BattleType), nullable=False)
    difficulty = Column(String(32))
    attacker_troops_sent = Column(Integer, nullable=False)
    attacker_troops_casualties = Column(Integer, default=0)
    defender_power_snapshot = Column(Integer, nullable=True)
    attacker_power_snapshot = Column(Integer, nullable=True)
    seed = Column(Integer, nullable=False)
    result = Column(SQLEnum(BattleResult), nullable=False)
    gold_delta_attacker = Column(Integer, default=0)
    medals_delta_attacker = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class ShopOrder(Base):
    __tablename__ = "shop_orders"
    
    id = Column(Integer, primary_key=True)
    village_id = Column(Integer, ForeignKey("villages.id"), nullable=False)
    provider = Column(String(40), nullable=False)
    payload_id = Column(String(256), unique=True, nullable=False)
    item_sku = Column(String(40), nullable=False)
    amount_fiat = Column(Float, default=0.0)
    currency = Column(String(8), default="RUB")
    diamonds_granted = Column(Integer, default=0)
    status = Column(SQLEnum(ShopOrderStatus), default=ShopOrderStatus.CREATED)
    created_at = Column(DateTime, server_default=func.now())
    paid_at = Column(DateTime, nullable=True)


class PromoCode(Base):
    __tablename__ = "promo_codes"
    
    id = Column(Integer, primary_key=True)
    code = Column(String(32), unique=True, nullable=False)
    reward_gold = Column(Integer, default=0)
    reward_diamonds = Column(Integer, default=0)
    reward_workers = Column(Integer, default=0)
    reward_energy = Column(Integer, default=0)
    max_uses_total = Column(Integer, default=1)
    max_uses_per_user = Column(Integer, default=1)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class PromoUse(Base):
    __tablename__ = "promo_uses"
    
    id = Column(Integer, primary_key=True)
    promo_code_id = Column(Integer, ForeignKey("promo_codes.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    used_at = Column(DateTime, server_default=func.now())


class Leaderboard(Base):
    __tablename__ = "leaderboards"
    
    id = Column(Integer, primary_key=True)
    type = Column(SQLEnum(LeaderboardType), nullable=False)
    village_id = Column(Integer, ForeignKey("villages.id"), nullable=False)
    score = Column(BigInteger, default=0)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())