#!/usr/bin/env python3
"""
Reset all superlatives for all accounts.
This will clear all unlocked superlatives so users can recalculate them.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "ratings.db")

def reset_superlatives():
    """Clear all user superlatives and reset active titles."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Count current superlatives before clearing
        cursor.execute("SELECT COUNT(*) FROM user_superlatives")
        count = cursor.fetchone()[0]
        print(f"Found {count} superlatives to reset")

        # Clear all user superlatives
        cursor.execute("DELETE FROM user_superlatives")

        # Clear all active titles
        cursor.execute("UPDATE users SET active_title = NULL")

        conn.commit()
        print(f"[OK] Successfully reset all superlatives")
        print(f"[OK] Cleared {count} unlocked superlatives")
        print(f"[OK] Cleared all active titles")
        print("\nUsers can now recalculate their superlatives on the Superlatives page")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Error resetting superlatives: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("RESET ALL SUPERLATIVES")
    print("=" * 60)
    print()

    # Confirmation
    response = input("This will reset ALL superlatives for ALL users. Continue? (yes/no): ")
    if response.lower() == 'yes':
        reset_superlatives()
    else:
        print("Cancelled.")
