#!/usr/bin/env python3
"""
Import GameData.csv with proper cover image linking
"""
import sys
from pathlib import Path
import csv
import os

project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

from database import init_db, create_user, add_or_get_game, set_user_score, set_user_playtime

def safe_float(val):
    """Convert value to float, handle empty/dash values"""
    if not val or str(val).strip() == '' or str(val).strip() == '-':
        return None
    try:
        return float(val)
    except:
        return None

def find_cover_image(game_name):
    """Find matching PNG file in covers folder"""
    covers_dir = project_dir / "static" / "covers"
    
    if not covers_dir.exists():
        return None
    
    # Exact match
    png_file = covers_dir / f"{game_name}.png"
    if png_file.exists():
        return f"/static/covers/{game_name}.png"
    
    # Case-insensitive search
    for file in covers_dir.glob("*.png"):
        if file.stem.lower() == game_name.lower():
            return f"/static/covers/{file.name}"
    
    return None

def import_gamedata():
    """Import GameData.csv into database"""
    
    print("[1/3] Initializing database...")
    init_db()
    print("✓ Database initialized")
    
    print("\n[2/3] Creating default user account...")
    try:
        success, msg = create_user("admin", "password")
        if success:
            print(f"✓ {msg}")
        else:
            print(f"✓ User already exists")
    except Exception as e:
        print(f"! User creation: {e}")
    
    user_id = 1  # Admin user
    
    print("\n[3/3] Importing games from GameData.csv...")
    
    csv_path = project_dir / "GameData.csv"
    if not csv_path.exists():
        print(f"✗ File not found: {csv_path}")
        return False
    
    imported = 0
    
    # Try multiple encodings
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
    f = None
    for enc in encodings:
        try:
            f = open(csv_path, 'r', encoding=enc)
            reader = csv.DictReader(f)
            # Try to read first row to verify encoding
            first_row = next(reader, None)
            if first_row:
                # Reset reader
                f.close()
                f = open(csv_path, 'r', encoding=enc)
                reader = csv.DictReader(f)
                print(f"✓ Using encoding: {enc}")
                break
        except:
            if f:
                f.close()
            continue
    
    if not reader:
        print("✗ Could not determine CSV encoding")
        return False
    
    try:
        for row in reader:
            # Use 'Name' column from GameData.csv
            game_name = row.get('Name', '').strip()
            if not game_name:
                continue
            
            # Extract metadata from GameData.csv
            app_id = row.get('AppID', '').strip() or None
            release_date = row.get('Release Date', '').strip() or None
            description = row.get('Short Description', '').strip() or None
            genres = row.get('Genres', '').strip() or None
            
            # Parse price
            price_str = row.get('Price (USD)', '').strip()
            price = None
            if price_str and price_str != '-':
                try:
                    # Remove "USD" and other text, keep just the number
                    price_val = price_str.replace('USD', '').replace('$', '').strip()
                    price = float(price_val)
                except:
                    price = None
            
            # Find cover image in covers folder
            cover_path = find_cover_image(game_name)
            
            # Add/get game
            try:
                game_id = add_or_get_game(
                    name=game_name,
                    app_id=app_id,
                    release_date=release_date,
                    description=description,
                    genres=genres,
                    price=price,
                    cover_path=cover_path
                )
                
                # Extract scores from 'Enjoyment Score', etc columns
                enjoyment = safe_float(row.get('Enjoyment Score', ''))
                gameplay = safe_float(row.get('Gameplay Score', ''))
                music = safe_float(row.get('Music Score', ''))
                narrative = safe_float(row.get('Narrative Score', ''))
                metacritic = safe_float(row.get('MetaCritic Score', ''))
                playtime = safe_float(row.get('Playtime (Hours)', ''))
                
                # Save user scores (only if at least one score exists)
                if any([enjoyment, gameplay, music, narrative, metacritic]):
                    set_user_score(user_id, game_id, enjoyment, gameplay, music, narrative, metacritic)
                # Save playtime if present
                if playtime is not None:
                    set_user_playtime(user_id, game_id, playtime)
                
                imported += 1
                status = "✓" if cover_path else "!"
                print(f"  {status} {game_name} (ID: {game_id}, Cover: {'Yes' if cover_path else 'No'})")
                
            except Exception as e:
                print(f"  ✗ {game_name}: {e}")
                continue
    finally:
        if f:
            f.close()
    
    print(f"\n✓ Imported {imported} games")
    print(f"✓ Cover images linked where available")
    
    print("\n" + "="*60)
    print("Setup complete!")
    print("="*60)
    print("\nDefault login:")
    print("  Username: admin")
    print("  Password: password")
    print("\n⚠️  IMPORTANT: Change password after first login!")
    print("\nNext steps:")
    print("1. Start the app: python app.py")
    print("2. Login with admin/password")
    print("3. Change your password")
    print("4. Register additional users if needed")
    print("5. Each user can upload their own CSV with ratings")
    
    return True

if __name__ == "__main__":
    try:
        success = import_gamedata()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
