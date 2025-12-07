"""Script to promote a user to admin status."""
from database import get_db
import sys

def make_admin(username):
    """Promote a user to admin."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET user_type = 'admin' WHERE username = ?", (username,))
        if c.rowcount == 0:
            print(f"User '{username}' not found")
            return False
        conn.commit()
        print(f"User '{username}' promoted to admin")
        return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python make_admin.py <username>")
        sys.exit(1)
    
    username = sys.argv[1]
    make_admin(username)
