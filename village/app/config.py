# app/config.py
import os
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg2://postgres:postgres@localhost:5432/farmgame')
if DB_URL and not '+psycopg2' in DB_URL and 'postgresql' in DB_URL:
    DB_URL = DB_URL.replace('postgresql://', 'postgresql+psycopg2://')

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not set!")

ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '123456').split(',') if x.strip()]

MINING_CHARGE_SECONDS = int(os.getenv('MINING_CHARGE_SECONDS', 600))
ENERGY_REGEN_SECONDS = 300
DAILY_BONUS_GOLD = 15
DAILY_BONUS_ENERGY = 12
DAILY_BONUS_DIAMOND_CHANCE = 0.03

PVP_SHIELD_MINUTES = 30
PVP_ATTACKS_PER_DAY = 3
REF_MIN_LEVEL = 3
REF_MIN_PLAYTIME = 1200

DONATE_PACKS = [
    {'sku': 'pack_s', 'diamonds': 25, 'price_fiat': 49, 'bonus': 0},
    {'sku': 'pack_m', 'diamonds': 60, 'price_fiat': 109, 'bonus': 5},
    {'sku': 'pack_l', 'diamonds': 140, 'price_fiat': 249, 'bonus': 20},
    {'sku': 'pack_xl', 'diamonds': 320, 'price_fiat': 499, 'bonus': 60},
]

BUILDING_COSTS = {
    'TOWNHALL': 120, 'FARM': 60, 'BARN': 55, 'BARRACKS': 80,
    'WALL': 70, 'MINE': 65, 'WORKSHOP': 90,
}

XP_FORMULA = lambda level: round(80 * level**2 + 220 * level + 200)