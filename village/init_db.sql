-- init_db.sql - Database initialization script

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    tg_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(64),
    first_name VARCHAR(64),
    lang VARCHAR(2) DEFAULT 'ru',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_banned BOOLEAN DEFAULT FALSE,
    ref_code VARCHAR(8) UNIQUE,
    referred_by_user_id INTEGER REFERENCES users(id),
    referred_count INTEGER DEFAULT 0
);

-- Villages table
CREATE TABLE IF NOT EXISTS villages (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
    name VARCHAR(40) DEFAULT 'Деревня',
    level INTEGER DEFAULT 1,
    xp BIGINT DEFAULT 0,
    gold BIGINT DEFAULT 50,
    diamonds BIGINT DEFAULT 0,
    medals BIGINT DEFAULT 0,
    workers INTEGER DEFAULT 2,
    troops INTEGER DEFAULT 0,
    energy INTEGER DEFAULT 60,
    energy_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    farm_storage INTEGER DEFAULT 0,
    farm_capacity INTEGER DEFAULT 500,
    farm_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_notify_full_at TIMESTAMP,
    last_daily_bonus_at TIMESTAMP,
    pvp_shield_until TIMESTAMP
);

-- Buildings table
CREATE TABLE IF NOT EXISTS buildings (
    id SERIAL PRIMARY KEY,
    village_id INTEGER NOT NULL REFERENCES villages(id),
    building_type VARCHAR(50) NOT NULL,
    level INTEGER DEFAULT 1
);

-- Mine state table
CREATE TABLE IF NOT EXISTS mine_state (
    id SERIAL PRIMARY KEY,
    village_id INTEGER NOT NULL UNIQUE REFERENCES villages(id),
    pickaxe_level INTEGER DEFAULT 1,
    pickaxe_power INTEGER DEFAULT 13,
    pickaxe_bonus_crit FLOAT DEFAULT 0.05,
    mine_depth INTEGER DEFAULT 1,
    mining_charges INTEGER DEFAULT 3,
    mining_charges_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_mine_at TIMESTAMP
);

-- Inventory resources table
CREATE TABLE IF NOT EXISTS inventory_resources (
    id SERIAL PRIMARY KEY,
    village_id INTEGER NOT NULL REFERENCES villages(id),
    resource_type VARCHAR(50) NOT NULL,
    amount BIGINT DEFAULT 0,
    UNIQUE(village_id, resource_type)
);

-- Quests table
CREATE TABLE IF NOT EXISTS quests (
    id SERIAL PRIMARY KEY,
    quest_type VARCHAR(50) NOT NULL,
    title_ru VARCHAR(256) NOT NULL,
    title_en VARCHAR(256) NOT NULL,
    description_ru TEXT,
    description_en TEXT,
    min_level INTEGER DEFAULT 1,
    troops_required INTEGER DEFAULT 0,
    gold_fee INTEGER DEFAULT 0,
    duration_sec INTEGER DEFAULT 0,
    success_chance FLOAT DEFAULT 1.0,
    reward_gold INTEGER DEFAULT 0,
    reward_xp INTEGER DEFAULT 0,
    reward_medals INTEGER DEFAULT 0,
    reward_resource_type VARCHAR(50),
    reward_resource_amount INTEGER
);

-- User active quests table
CREATE TABLE IF NOT EXISTS user_active_quests (
    id SERIAL PRIMARY KEY,
    village_id INTEGER NOT NULL REFERENCES villages(id),
    quest_id INTEGER NOT NULL REFERENCES quests(id),
    status VARCHAR(50) NOT NULL,
    troops_locked INTEGER DEFAULT 0,
    troops_casualties INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    ends_at TIMESTAMP,
    result_seed INTEGER,
    claimed_at TIMESTAMP
);

-- Battle logs table
CREATE TABLE IF NOT EXISTS battle_logs (
    id SERIAL PRIMARY KEY,
    attacker_village_id INTEGER NOT NULL REFERENCES villages(id),
    defender_village_id INTEGER REFERENCES villages(id),
    battle_type VARCHAR(50) NOT NULL,
    difficulty VARCHAR(32),
    attacker_troops_sent INTEGER NOT NULL,
    attacker_troops_casualties INTEGER DEFAULT 0,
    defender_power_snapshot INTEGER,
    attacker_power_snapshot INTEGER,
    seed INTEGER NOT NULL,
    result VARCHAR(50) NOT NULL,
    gold_delta_attacker INTEGER DEFAULT 0,
    medals_delta_attacker INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Shop orders table
CREATE TABLE IF NOT EXISTS shop_orders (
    id SERIAL PRIMARY KEY,
    village_id INTEGER NOT NULL REFERENCES villages(id),
    provider VARCHAR(40) NOT NULL,
    payload_id VARCHAR(256) UNIQUE NOT NULL,
    item_sku VARCHAR(40) NOT NULL,
    amount_fiat FLOAT DEFAULT 0.0,
    currency VARCHAR(8) DEFAULT 'RUB',
    diamonds_granted INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'CREATED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    paid_at TIMESTAMP
);

-- Promo codes table
CREATE TABLE IF NOT EXISTS promo_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(32) UNIQUE NOT NULL,
    reward_gold INTEGER DEFAULT 0,
    reward_diamonds INTEGER DEFAULT 0,
    reward_workers INTEGER DEFAULT 0,
    reward_energy INTEGER DEFAULT 0,
    max_uses_total INTEGER DEFAULT 1,
    max_uses_per_user INTEGER DEFAULT 1,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Promo uses table
CREATE TABLE IF NOT EXISTS promo_uses (
    id SERIAL PRIMARY KEY,
    promo_code_id INTEGER NOT NULL REFERENCES promo_codes(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Leaderboards table
CREATE TABLE IF NOT EXISTS leaderboards (
    id SERIAL PRIMARY KEY,
    type VARCHAR(50) NOT NULL,
    village_id INTEGER NOT NULL REFERENCES villages(id),
    score BIGINT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_users_tg_id ON users(tg_id);
CREATE INDEX IF NOT EXISTS idx_villages_user_id ON villages(user_id);
CREATE INDEX IF NOT EXISTS idx_buildings_village_id ON buildings(village_id);
CREATE INDEX IF NOT EXISTS idx_mine_state_village_id ON mine_state(village_id);
CREATE INDEX IF NOT EXISTS idx_inventory_village_id ON inventory_resources(village_id);
CREATE INDEX IF NOT EXISTS idx_battle_logs_attacker ON battle_logs(attacker_village_id);
CREATE INDEX IF NOT EXISTS idx_leaderboards_type_score ON leaderboards(type, score);

-- Verify
SELECT 'Database initialized successfully!' as status;