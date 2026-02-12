# app/services/notifications.py
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.models import Village

async def check_full_storage_notification(session: Session, village: Village, bot) -> bool:
    """
    Check if farm storage is full and send notification.
    Max once per 3 hours.
    """
    if village.farm_storage >= village.farm_capacity * 0.95:
        now = datetime.utcnow()
        
        if village.last_notify_full_at:
            if (now - village.last_notify_full_at).total_seconds() < 10800:  # 3 hours
                return False
        
        village.last_notify_full_at = now
        
        from app.db.session import SessionLocal
        SessionLocal.commit()
        
        # Send notification
        from app.bot.texts_ru import TEXTS
        user = session.query(User).filter(User.id == village.user_id).first()
        
        try:
            await bot.send_message(
                chat_id=user.tg_id,
                text=TEXTS.get('storage_full', 'Ваш склад почти полон! 🌾')
            )
            return True
        except Exception as e:
            print(f"Notification error: {e}")
            return False
    
    return False

def schedule_daily_bonuses(scheduler, bot):
    """Schedule daily bonus distribution"""
    def award_daily_bonuses():
        from app.db.session import SessionLocal
        from app.db.models import User
        from app.services.economy import add_daily_bonus
        
        session = SessionLocal()
        users = session.query(User).all()
        
        for user in users:
            if user.villages:
                village = user.villages[0]
                result = add_daily_bonus(session, village)
                if result.get('success'):
                    # Notify user
                    pass
        
        session.commit()
        session.close()
    
    scheduler.add_job(award_daily_bonuses, 'cron', hour=0, minute=0)