"""
Restore admin account with all reviews and update to new schema.
"""
import sqlite3
import hashlib

DB_PATH = 'ratings.db'

def hash_password(password):
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def restore_and_update():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Check if user_type column exists
    c.execute('PRAGMA table_info(users)')
    columns = [col[1] for col in c.fetchall()]

    # Add missing columns if they don't exist
    if 'user_type' not in columns:
        print("Adding user_type column...")
        c.execute("ALTER TABLE users ADD COLUMN user_type TEXT DEFAULT 'user'")

    if 'review_points' not in columns:
        print("Adding review_points column...")
        c.execute("ALTER TABLE users ADD COLUMN review_points INTEGER DEFAULT 0")

    if 'active_title' not in columns:
        print("Adding active_title column...")
        c.execute("ALTER TABLE users ADD COLUMN active_title INTEGER")

    if 'favorite_game_id' not in columns:
        print("Adding favorite_game_id column...")
        c.execute("ALTER TABLE users ADD COLUMN favorite_game_id INTEGER")

    # Check games table schema
    c.execute('PRAGMA table_info(games)')
    game_columns = [col[1] for col in c.fetchall()]

    if 'original_price' not in game_columns:
        print("Adding original_price column to games table...")
        c.execute("ALTER TABLE games ADD COLUMN original_price REAL")

    # Update admin user credentials
    print("\nUpdating admin credentials...")
    username = 'Jsaber'
    password = 'Vstjd6943'
    password_hash = hash_password(password)

    c.execute('''
        UPDATE users
        SET username = ?, password = ?, user_type = 'admin'
        WHERE id = 1
    ''', (username, password_hash))

    conn.commit()

    # Verify
    c.execute('SELECT id, username, user_type FROM users')
    users = c.fetchall()

    print("\n=== Users ===")
    for user in users:
        print(f"ID: {user[0]}, Username: {user[1]}, Type: {user[2]}")

    c.execute('SELECT user_id, COUNT(*) as count FROM user_scores GROUP BY user_id')
    scores = c.fetchall()

    print("\n=== Reviews ===")
    for score in scores:
        print(f"User ID {score[0]}: {score[1]} reviews")

    conn.close()
    print("\nRestore complete! All reviews preserved.")

if __name__ == '__main__':
    restore_and_update()
