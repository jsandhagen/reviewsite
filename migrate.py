#!/usr/bin/env python3
"""
Script to migrate existing CSV data into the new database schema.
This script will:
1. Create the database with the new schema
2. Create a default user account
3. Import all games from data.csv
4. Copy cover images if they exist
"""

import sys
import os
from pathlib import Path

# Add the project directory to path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

from database import init_db, create_user, import_csv_data
import shutil

def migrate_data():
    """Migrate CSV data to the new database."""
    
    # Initialize database
    print("[1/4] Initializing database with new schema...")
    init_db()
    print("✓ Database initialized")
    
    # Create default user
    print("\n[2/4] Creating default user account...")
    success, msg = create_user("admin", "password")
    if not success:
        print(f"! User already exists or error: {msg}")
        # Try to get admin user ID for import
        user_id = 1  # Assume first user has ID 1
    else:
        print(f"✓ {msg}")
        user_id = 1
    
    # Import CSV data
    csv_path = project_dir / "data.csv"
    if csv_path.exists():
        print(f"\n[3/4] Importing games from {csv_path}...")
        with open(csv_path, 'r', encoding='utf-8') as f:
            csv_content = f.read()
        
        try:
            imported = import_csv_data(user_id, csv_content)
            print(f"✓ Imported {imported} games")
        except Exception as e:
            print(f"✗ Error importing CSV: {e}")
            return False
    else:
        print(f"\n[3/4] No CSV file found at {csv_path}")
    
    # Note about cover images
    print("\n[4/4] Cover image migration...")
    covers_dir = project_dir / "static" / "covers"
    if covers_dir.exists() and list(covers_dir.glob("*.png")):
        print(f"✓ Found {len(list(covers_dir.glob('*.png')))} cover images in {covers_dir}")
        print("  These will be automatically linked when the app runs")
    else:
        print("! No cover images found in static/covers/")
        print("  You can:")
        print("  1. Add PNG files to static/covers/")
        print("  2. Use /autofill_covers in the web app to auto-download covers")
        print("  3. Manually set cover paths in the database")
    
    print("\n" + "="*60)
    print("Migration complete!")
    print("="*60)
    print("\nDefault login credentials:")
    print("  Username: admin")
    print("  Password: password")
    print("\n⚠️  IMPORTANT: Change this password after first login!")
    print("\nNext steps:")
    print("1. Start the app: python app.py")
    print("2. Login with admin/password")
    print("3. Change your password")
    print("4. Add more users as needed")
    print("5. Games will show average enjoyment scores from all users")
    
    return True

if __name__ == "__main__":
    try:
        success = migrate_data()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
