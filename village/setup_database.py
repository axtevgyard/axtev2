# setup_database.py
"""
Automatic database setup script.
Run this ONCE to create all tables.
Usage: python setup_database.py
"""

import os
import sys
from sqlalchemy import create_engine, text
from app.db.models import Base

def setup_database():
    """Create all database tables automatically"""
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ ERROR: DATABASE_URL not set in environment variables!")
        print("Set it in deploy-f.com panel or .env file")
        return False
    
    print("=" * 60)
    print("🔧 DATABASE SETUP SCRIPT")
    print("=" * 60)
    print(f"\n📊 Database URL: {database_url[:80]}...")
    
    try:
        # Create engine
        print("\n⏳ Connecting to database...")
        engine = create_engine(database_url)
        
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Connection successful!")
        
        # Create all tables from models
        print("\n⏳ Creating tables from models...")
        Base.metadata.create_all(engine)
        print("✅ Tables created successfully!")
        
        # List created tables
        print("\n📋 Created tables:")
        inspector = __import__('sqlalchemy').inspect(engine)
        tables = inspector.get_table_names()
        
        if tables:
            for table in sorted(tables):
                print(f"   ✓ {table}")
            print(f"\n✅ Total tables: {len(tables)}")
        else:
            print("   ⚠️  No tables created (check database permissions)")
        
        print("\n" + "=" * 60)
        print("✅ DATABASE SETUP COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\nNow you can start the bot:")
        print("  python -m app.main")
        print()
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = setup_database()
    sys.exit(0 if success else 1)