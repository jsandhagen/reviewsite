#!/usr/bin/env python3
"""
Simple database initialization script
"""
import sys
from pathlib import Path

project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

from database import init_db, create_user

print("Initializing database...")
try:
    init_db()
    print("[OK] Database schema created")
    
    # Try to create default user
    try:
        success, msg = create_user("admin", "password")
        if success:
            print(f"[OK] Default user created (admin/password)")
        else:
            print(f"[OK] User account exists: {msg}")
    except Exception as e:
        print(f"[!] User creation error: {e}")
    
    print("\nDatabase ready!")
    print("\nNext steps:")
    print("1. Start the app: python app.py")
    print("2. Visit http://localhost:5000")
    print("3. Login with admin/password")
    print("4. Upload your CSV or add games manually")
    
except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
