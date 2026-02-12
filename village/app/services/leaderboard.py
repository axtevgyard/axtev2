# app/services/leaderboard.py
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.models import Leaderboard, Village, LeaderboardType
from app.db.crud import VillageCRUD

def update_leaderboards(session: Session, village: Village):
    """Update all leaderboard scores for a village"""
    from app.db.crud import LeaderboardCRUD
    
    # Update medals leaderboard
    LeaderboardCRUD.update_score(session, village.id, LeaderboardType.MEDALS, village.medals)
    
    # Update level leaderboard
    LeaderboardCRUD.update_score(session, village.id, LeaderboardType.LEVEL, village.level)
    
    # Update gold leaderboard
    LeaderboardCRUD.update_score(session, village.id, LeaderboardType.GOLD, village.gold)

def get_leaderboard(session: Session, lb_type: LeaderboardType, limit: int = 10) -> list:
    """Get top villages by leaderboard type"""
    return session.execute(
        select(Leaderboard)
        .where(Leaderboard.type == lb_type)
        .order_by(Leaderboard.score.desc())
        .limit(limit)
    ).scalars().all()

def get_player_rank(session: Session, village: Village, lb_type: LeaderboardType) -> int:
    """Get player's rank on specific leaderboard"""
    leaderboard = session.execute(
        select(Leaderboard)
        .where(Leaderboard.village_id == village.id)
        .where(Leaderboard.type == lb_type)
    ).scalar_one_or_none()
    
    if not leaderboard:
        return 0
    
    rank = session.execute(
        select(Leaderboard)
        .where(Leaderboard.type == lb_type)
        .where(Leaderboard.score > leaderboard.score)
    ).scalars().all()
    
    return len(rank) + 1

def get_leaderboard_with_player(session: Session, village: Village, lb_type: LeaderboardType, limit: int = 10) -> dict:
    """Get top leaderboard entries + player's position"""
    top = get_leaderboard(session, lb_type, limit)
    player_rank = get_player_rank(session, village, lb_type)
    
    return {
        'top': top,
        'player_rank': player_rank,
        'player_village': village,
    }