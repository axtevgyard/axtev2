# app/bot/router.py
from aiogram import Router
from app.bot.handlers import (
    start, work, harvest, sell, buildings,
    battles, quests, mine, shop, top, help, language,
    invite, admin
)

router = Router()

# Include all handler routers
router.include_router(start.router)
router.include_router(work.router)
router.include_router(harvest.router)
router.include_router(sell.router)
router.include_router(buildings.router)
router.include_router(battles.router)
router.include_router(quests.router)
router.include_router(mine.router)
router.include_router(shop.router)
router.include_router(top.router)
router.include_router(help.router)
router.include_router(language.router)
router.include_router(invite.router)
router.include_router(admin.router)