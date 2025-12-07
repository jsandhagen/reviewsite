"""
Fix superlatives that don't have an associated game_id by finding appropriate games.
"""
import sqlite3

DB_PATH = 'ratings.db'

def fix_superlative_games():
    """Update user_superlatives to add game_id where missing."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Find all solo superlatives without a game_id
    c.execute('''
        SELECT us.id, us.user_id, s.name, s.category
        FROM user_superlatives us
        JOIN superlatives s ON us.superlative_id = s.id
        WHERE s.category = 'solo' AND us.game_id IS NULL
    ''')

    missing_games = c.fetchall()
    updated_count = 0

    for row in missing_games:
        us_id = row['id']
        user_id = row['user_id']
        superlative_name = row['name']

        game_id = None

        # Find appropriate game based on superlative type
        if superlative_name == 'Nostalgic':
            # Find a pre-2009 game with score >9
            # Date format is "Month Day, Year" so we check the last 4 characters
            c.execute('''
                SELECT us.game_id
                FROM user_scores us
                JOIN games g ON us.game_id = g.game_id
                WHERE us.user_id = ?
                AND us.enjoyment_score > 9
                AND g.release_date IS NOT NULL
                AND CAST(substr(g.release_date, -4) AS INTEGER) < 2009
                ORDER BY us.enjoyment_score DESC
                LIMIT 1
            ''', (user_id,))
        elif superlative_name == "Don't Make Them Like They Used To":
            # Find #1 game from before 2010
            # Date format is "Month Day, Year" so we check the last 4 characters
            c.execute('''
                SELECT us.game_id
                FROM user_scores us
                JOIN games g ON us.game_id = g.game_id
                WHERE us.user_id = ?
                AND us.enjoyment_score IS NOT NULL
                AND g.release_date IS NOT NULL
                AND CAST(substr(g.release_date, -4) AS INTEGER) < 2010
                ORDER BY us.enjoyment_score DESC, us.enjoyment_order ASC
                LIMIT 1
            ''', (user_id,))
        elif superlative_name == 'Favorite Child':
            # Most played game
            c.execute('''
                SELECT game_id
                FROM user_scores
                WHERE user_id = ? AND hours_played IS NOT NULL
                ORDER BY hours_played DESC
                LIMIT 1
            ''', (user_id,))
        elif superlative_name == 'Toxic Relationship':
            # Game scored <7 but played >100 hours
            c.execute('''
                SELECT game_id
                FROM user_scores
                WHERE user_id = ?
                AND enjoyment_score < 7
                AND hours_played > 100
                ORDER BY hours_played DESC
                LIMIT 1
            ''', (user_id,))
        elif superlative_name == 'Worth Every Nickel':
            # Playtime value ratio ≤0.05
            c.execute('''
                SELECT us.game_id
                FROM user_scores us
                JOIN games g ON us.game_id = g.game_id
                WHERE us.user_id = ?
                AND us.hours_played IS NOT NULL
                AND us.hours_played > 0
                AND (g.original_price IS NOT NULL OR g.price IS NOT NULL)
                AND ((COALESCE(g.original_price, g.price) / us.hours_played) <= 0.05)
                ORDER BY (COALESCE(g.original_price, g.price) / us.hours_played) ASC
                LIMIT 1
            ''', (user_id,))
        else:
            # For other solo superlatives, use the top-rated game
            c.execute('''
                SELECT game_id
                FROM user_scores
                WHERE user_id = ? AND enjoyment_score IS NOT NULL
                ORDER BY enjoyment_score DESC, enjoyment_order ASC
                LIMIT 1
            ''', (user_id,))

        game_row = c.fetchone()
        if game_row:
            game_id = game_row['game_id']

            # Update the user_superlative with the found game_id
            c.execute('''
                UPDATE user_superlatives
                SET game_id = ?
                WHERE id = ?
            ''', (game_id, us_id))

            # Get game name for logging
            c.execute('SELECT name FROM games WHERE game_id = ?', (game_id,))
            game = c.fetchone()
            game_name = game['name'] if game else 'Unknown'

            print(f"[OK] Updated '{superlative_name}' for user {user_id} with game: {game_name}")
            updated_count += 1
        else:
            print(f"[SKIP] Could not find appropriate game for '{superlative_name}' for user {user_id}")

    conn.commit()
    conn.close()

    print(f"\nFixed {updated_count} superlatives")

if __name__ == '__main__':
    fix_superlative_games()
