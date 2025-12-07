"""
Migration script to add Review Points (RP) system.
Run this script to add RP tracking to users.
"""
from database import get_db

def migrate_review_points():
    """Add review_points column to users table and calculate initial RP."""
    with get_db() as conn:
        c = conn.cursor()

        # Add review_points column to users table
        try:
            c.execute("ALTER TABLE users ADD COLUMN review_points INTEGER DEFAULT 0")
            print("Added review_points column to users table")
        except Exception:
            print("review_points column already exists")

        # Calculate initial RP for existing users based on their reviewed games
        # 1 RP per game with at least one score
        c.execute('''
            UPDATE users
            SET review_points = (
                SELECT COUNT(DISTINCT game_id)
                FROM user_scores
                WHERE user_scores.user_id = users.id
                AND (
                    enjoyment_score IS NOT NULL
                    OR gameplay_score IS NOT NULL
                    OR music_score IS NOT NULL
                    OR narrative_score IS NOT NULL
                )
            )
        ''')

        conn.commit()

        # Show RP summary for all users
        c.execute('SELECT username, review_points FROM users ORDER BY review_points DESC')
        users = c.fetchall()

        print("\nReview Points Summary:")
        print("-" * 40)
        for user in users:
            print(f"  {user['username']}: {user['review_points']} RP")

        print("\nReview Points migration complete!")

if __name__ == '__main__':
    migrate_review_points()
