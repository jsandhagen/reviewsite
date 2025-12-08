"""
Setup script to create admin account and remove test users.
Run this before deploying.
"""
import sqlite3
import hashlib

DB_PATH = 'ratings.db'

def hash_password(password):
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def setup_admin():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Find the existing admin user
    c.execute('SELECT id, username FROM users WHERE user_type = ?', ('admin',))
    admin_user = c.fetchone()

    if admin_user:
        admin_id = admin_user[0]
        old_username = admin_user[1]
        print(f"Found existing admin user: {old_username} (ID: {admin_id})")
        print(f"Updating to new credentials: Jsaber")

        # Update admin account credentials
        username = 'Jsaber'
        password = 'Vstjd6943'
        password_hash = hash_password(password)

        c.execute('''
            UPDATE users
            SET username = ?, password = ?
            WHERE id = ?
        ''', (username, password_hash, admin_id))

        print(f"Admin account updated (all reviews and data preserved)")
    else:
        # No admin exists, create new one
        print("No existing admin found, creating new admin account")
        username = 'Jsaber'
        password = 'Vstjd6943'
        password_hash = hash_password(password)

        c.execute('''
            INSERT INTO users (username, password, user_type, review_points)
            VALUES (?, ?, 'admin', 0)
        ''', (username, password_hash))

        print("New admin account created: Jsaber")

    # Remove testuser if it exists
    c.execute('SELECT id FROM users WHERE username = ?', ('testuser',))
    testuser = c.fetchone()

    if testuser:
        testuser_id = testuser[0]
        print(f"\nRemoving testuser account (ID: {testuser_id})...")

        # Delete testuser's data
        c.execute('DELETE FROM user_scores WHERE user_id = ?', (testuser_id,))
        c.execute('DELETE FROM user_superlatives WHERE user_id = ?', (testuser_id,))
        c.execute('DELETE FROM friends WHERE user_id = ? OR friend_id = ?', (testuser_id, testuser_id))
        c.execute('DELETE FROM users WHERE id = ?', (testuser_id,))

        print("Testuser account removed")
    else:
        print("\nNo testuser account found (skipping)")

    conn.commit()

    # Verify
    c.execute('SELECT username, user_type FROM users')
    users = c.fetchall()

    print("\n=== Current Users ===")
    for user in users:
        user_type = user[1] if user[1] else 'regular'
        print(f"Username: {user[0]}, Type: {user_type}")

    conn.close()
    print("\nAdmin setup complete!")

if __name__ == '__main__':
    setup_admin()
