"""
Migration script to add superlatives system to the database.
Run this script to add the necessary tables for the "Pulse Points" feature.
"""
from database import get_db

def migrate_superlatives():
    """Add superlatives tables and populate with initial data."""
    with get_db() as conn:
        c = conn.cursor()

        # Create superlatives master table
        c.execute('''
            CREATE TABLE IF NOT EXISTS superlatives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK(category IN ('solo', 'friend'))
            )
        ''')

        # Create user_superlatives table to track unlocked superlatives
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_superlatives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                superlative_id INTEGER NOT NULL,
                game_id INTEGER,
                friend_id INTEGER,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (superlative_id) REFERENCES superlatives (id) ON DELETE CASCADE,
                FOREIGN KEY (game_id) REFERENCES games (game_id) ON DELETE SET NULL,
                FOREIGN KEY (friend_id) REFERENCES users (id) ON DELETE SET NULL,
                UNIQUE(user_id, superlative_id, game_id, friend_id)
            )
        ''')

        # Add active_title column to users table
        try:
            c.execute("ALTER TABLE users ADD COLUMN active_title INTEGER")
        except Exception:
            pass  # Column already exists

        # Populate superlatives with initial data
        superlatives_data = [
            # SOLO Superlatives
            ("Toxic Relationship", "Awarded for having a game with an overall score below 7 but over 100 hours played", "solo"),
            ("Die on this Hill", "Awarded for rating a game more than 2 points above the community average", "solo"),
            ("Agree to Disagree", "Awarded for rating a game more than 2 points below the community average", "solo"),
            ("Favorite Child", "Awarded for having a game with more than double the hours of your next most-played game", "solo"),
            ("Nostalgic", "Awarded for giving a game from before 2009 an overall score above 9", "solo"),
            ("Worth Every Nickel", "Awarded for a game with a price-per-hour value at or below $0.05", "solo"),
            ("Here for the Music", "Awarded for a game with a music score 2+ points higher than any other category", "solo"),
            ("Here for the Story", "Awarded for a game with a narrative score 2+ points higher than any other category", "solo"),
            ("Gameplay Guru", "Awarded for a game with a gameplay score 2+ points higher than any other category", "solo"),
            ("Small Business Supporter", "Awarded for having an indie game in your top 5", "solo"),
            ("Don't Make Them Like They Used To", "Awarded for having your top overall game be from earlier than 2010", "solo"),
            ("Get What You Pay For", "Awarded for having a top 10 game with a price-per-hour value above $2", "solo"),
            ("Graphics Not Required", "Awarded for giving a score of 9+ to a game with low graphics quality", "solo"),
            ("Buyer's Remorse", "Awarded for a game with a score below 6 and less than 10 hours played", "solo"),
            ("Early Adopter", "Awarded for being one of the first 10 reviewers of a game", "solo"),

            # FRIEND Superlatives
            ("Polar Opposites", "Awarded when you and a friend have a difference in overall score greater than 2 points for the same game", "friend"),
            ("Cultists", "Awarded when you and a friend both rate a game more than 2 points higher than the community average", "friend"),
            ("In Good Company", "Awarded when you and a friend both have the same game in your top 5", "friend"),
            ("Great Minds", "Awarded when you and a friend share the same #1 game", "friend"),
            ("Addicts", "Awarded when you and a friend both have over 100 hours in the same game", "friend"),
        ]

        for name, description, category in superlatives_data:
            try:
                c.execute('''
                    INSERT INTO superlatives (name, description, category)
                    VALUES (?, ?, ?)
                ''', (name, description, category))
            except Exception:
                # Superlative already exists, skip
                pass

        conn.commit()
        print("Superlatives migration complete!")
        print(f"  - Created superlatives table")
        print(f"  - Created user_superlatives table")
        print(f"  - Added active_title column to users")
        print(f"  - Populated {len(superlatives_data)} superlative definitions")

if __name__ == '__main__':
    migrate_superlatives()
