import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "ratings.db")


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA encoding = 'UTF-8'")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize the database with required tables."""
    with get_db() as conn:
        c = conn.cursor()
        
        # Users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Add optional profile fields if missing
        try:
            c.execute("ALTER TABLE users ADD COLUMN profile_picture TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE users ADD COLUMN steam_profile_url TEXT")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE users ADD COLUMN user_type TEXT DEFAULT 'user'")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE users ADD COLUMN favorite_game_id INTEGER")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE users ADD COLUMN review_points INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            c.execute("ALTER TABLE users ADD COLUMN active_title INTEGER")
        except Exception:
            pass

        # Games table (master list of all games with enhanced metadata)
        c.execute('''
            CREATE TABLE IF NOT EXISTS games (
                game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_id TEXT,
                name TEXT NOT NULL,
                release_date TEXT,
                description TEXT,
                genres TEXT,
                price REAL,
                cover_path TEXT,
                average_enjoyment_score REAL DEFAULT 0,
                num_ratings INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add new fields to games table if missing
        new_game_columns = [
            ("developer", "TEXT"),
            ("publisher", "TEXT"),
            ("original_price", "REAL"),
            ("sale_price", "REAL"),
            ("cover_etag", "TEXT"),
            ("average_gameplay_score", "REAL"),
            ("average_music_score", "REAL"),
            ("average_narrative_score", "REAL"),
            ("pv_ratio", "REAL")
        ]
        for col_name, col_type in new_game_columns:
            try:
                c.execute(f"ALTER TABLE games ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass
        # User game scores (individual ratings per user per game)
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                game_id INTEGER NOT NULL,
                enjoyment_score REAL,
                gameplay_score REAL,
                music_score REAL,
                narrative_score REAL,
                metacritic_score REAL,
                hours_played REAL,
                enjoyment_order INTEGER,
                gameplay_order INTEGER,
                music_order INTEGER,
                narrative_order INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (game_id) REFERENCES games (game_id) ON DELETE CASCADE,
                UNIQUE(user_id, game_id)
            )
        ''')

        # In case the table exists from an older schema, ensure the hours_played column is present
        try:
            c.execute("ALTER TABLE user_scores ADD COLUMN hours_played REAL")
        except Exception:
            pass
        # Add tie-breaker order columns if missing
        for col in ("enjoyment_order","gameplay_order","music_order","narrative_order","backlog_order"):
            try:
                c.execute(f"ALTER TABLE user_scores ADD COLUMN {col} INTEGER")
            except Exception:
                pass
        # Add review_text column if missing
        try:
            c.execute("ALTER TABLE user_scores ADD COLUMN review_text TEXT")
        except Exception:
            pass
        # Add game attribute columns if missing
        for col in ["difficulty TEXT", "graphics_quality TEXT", "completion_time REAL", "replayability TEXT", "style TEXT"]:
            try:
                c.execute(f"ALTER TABLE user_scores ADD COLUMN {col}")
            except Exception:
                pass
        
        # Steam update log table for tracking automatic syncs
        c.execute('''
            CREATE TABLE IF NOT EXISTS steam_update_log (
                user_id INTEGER PRIMARY KEY,
                last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')

        # Friends table for friend relationships
        c.execute('''
            CREATE TABLE IF NOT EXISTS friends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                friend_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                FOREIGN KEY (friend_id) REFERENCES users (id) ON DELETE CASCADE,
                UNIQUE(user_id, friend_id),
                CHECK(user_id != friend_id),
                CHECK(status IN ('pending', 'accepted', 'rejected'))
            )
        ''')

        # Superlatives/Pulse Points table
        c.execute('''
            CREATE TABLE IF NOT EXISTS superlatives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK(category IN ('solo', 'friend'))
            )
        ''')

        # User superlatives (unlocked achievements)
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
                FOREIGN KEY (game_id) REFERENCES games (game_id) ON DELETE CASCADE,
                FOREIGN KEY (friend_id) REFERENCES users (id) ON DELETE CASCADE,
                UNIQUE(user_id, superlative_id)
            )
        ''')

        # Populate superlatives if table is empty
        c.execute('SELECT COUNT(*) as count FROM superlatives')
        if c.fetchone()['count'] == 0:
            superlatives_data = [
                # Solo superlatives
                ('Toxic Relationship', 'Scored a game <7 but played >100 hours', 'solo'),
                ('Die on this Hill', 'Scored a game >2 points above community average', 'solo'),
                ('Agree to Disagree', 'Scored a game >2 points below community average', 'solo'),
                ('Favorite Child', 'Played a game >2x more than your second most played', 'solo'),
                ('Nostalgic', 'Gave a pre-2009 game a score >9', 'solo'),
                ('Worth Every Nickel', 'Achieved a playtime value ratio ≤0.05', 'solo'),
                ('Here for the Music', 'Music score 2+ points higher than other categories', 'solo'),
                ('Here for the Story', 'Narrative score 2+ points higher than other categories', 'solo'),
                ('Gameplay Guru', 'Gameplay score 2+ points higher than other categories', 'solo'),
                ('Small Business Supporter', 'Indie game in your top 5', 'solo'),
                ("Don't Make Them Like They Used To", 'Your #1 game is from before 2010', 'solo'),
                ('Get What You Pay For', 'Top 10 game with PV ratio >2', 'solo'),
                ('Graphics Not Required', 'Score ≥9 with low graphics quality', 'solo'),
                ("Buyer's Remorse", 'Score <6 and <10 hours played', 'solo'),
                ('Early Adopter', 'Among the first 10 reviewers of a game', 'solo'),
                # Friend superlatives
                ('Polar Opposites', 'You and a friend differ by >2 points on a game', 'friend'),
                ('Cultists', 'Both you and a friend scored >2 above community average', 'friend'),
                ('In Good Company', 'Share a game in both your top 5s', 'friend'),
                ('Great Minds', 'Your #1 game matches a friend\'s #1', 'friend'),
                ('Addicts', 'Both played the same game >100 hours', 'friend')
            ]
            c.executemany('INSERT INTO superlatives (name, description, category) VALUES (?, ?, ?)', superlatives_data)

        conn.commit()


def create_user(username, password, user_type='user'):
    """Create a new user. Returns (success, message)."""
    with get_db() as conn:
        c = conn.cursor()
        try:
            c.execute('INSERT INTO users (username, password, user_type) VALUES (?, ?, ?)',
                     (username, password, user_type))
            conn.commit()
            return True, "User created successfully"
        except sqlite3.IntegrityError:
            return False, "Username already exists"
        except Exception as e:
            return False, str(e)


def verify_user(username, password):
    """Verify user credentials. Returns (success, user_id)."""
    import hashlib
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT id, password FROM users WHERE username = ?', (username,))
        row = c.fetchone()
        if row:
            # Hash the provided password and compare with stored hash
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if row['password'] == password_hash:
                return True, row['id']
        return False, None


def get_user(user_id):
    """Get user info by ID."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT id, username, user_type FROM users WHERE id = ?', (user_id,))
        row = c.fetchone()
        return dict(row) if row else None


def get_user_profile(user_id):
    """Return basic profile info for a user."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT id, username, created_at, profile_picture, steam_profile_url, user_type, favorite_game_id, review_points, active_title FROM users WHERE id = ?', (user_id,))
        row = c.fetchone()
        if not row:
            return None

        profile = dict(row)

        # Add last Steam sync time if available
        c.execute('SELECT last_update FROM steam_update_log WHERE user_id = ?', (user_id,))
        sync_row = c.fetchone()
        if sync_row:
            profile['steam_last_sync'] = sync_row['last_update']
        else:
            profile['steam_last_sync'] = None

        # Get favorite game details if set
        if profile.get('favorite_game_id'):
            c.execute('''
                SELECT g.*, us.enjoyment_score, us.gameplay_score, us.music_score,
                       us.narrative_score, us.review_text, us.hours_played,
                       us.difficulty, us.graphics_quality, us.completion_time,
                       us.replayability, us.style
                FROM games g
                LEFT JOIN user_scores us ON g.game_id = us.game_id AND us.user_id = ?
                WHERE g.game_id = ?
            ''', (user_id, profile['favorite_game_id']))
            fav_row = c.fetchone()
            if fav_row:
                profile['favorite_game'] = dict(fav_row)

        return profile


def set_user_profile_picture(user_id, path):
    """Update a user's profile picture path."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('UPDATE users SET profile_picture = ?, created_at = created_at WHERE id = ?', (path, user_id))
        conn.commit()


def set_user_steam_profile(user_id, steam_url):
    """Update a user's Steam profile URL."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('UPDATE users SET steam_profile_url = ? WHERE id = ?', (steam_url, user_id))
        conn.commit()


def set_favorite_game(user_id, game_id):
    """Set the user's favorite game."""
    with get_db() as conn:
        c = conn.cursor()
        # Verify the user has reviewed this game
        c.execute('''
            SELECT 1 FROM user_scores
            WHERE user_id = ? AND game_id = ?
            AND enjoyment_score IS NOT NULL
        ''', (user_id, game_id))
        if not c.fetchone():
            return False, "You must review a game before setting it as your favorite"

        c.execute('UPDATE users SET favorite_game_id = ? WHERE id = ?', (game_id, user_id))
        conn.commit()
        return True, "Favorite game updated!"


def get_user_profile_by_username(username):
    """Get user profile by username."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE username = ?', (username,))
        row = c.fetchone()
        if row:
            return get_user_profile(row['id'])
        return None


def check_superlative_eligibility(user_id, superlative_name):
    """Check if a user is eligible for a specific superlative. Returns (eligible, game_id)."""
    with get_db() as conn:
        c = conn.cursor()
        user_games = get_user_games(user_id)

        if not user_games:
            return False, None

        # Check each superlative type
        if superlative_name == 'Toxic Relationship':
            for game in user_games:
                if game.get('enjoyment_score') and game.get('hours_played'):
                    if game['enjoyment_score'] < 7 and game['hours_played'] > 100:
                        return True, game['game_id']

        elif superlative_name == 'Die on this Hill':
            for game in user_games:
                if game.get('enjoyment_score'):
                    c.execute('SELECT average_enjoyment_score FROM games WHERE game_id = ?', (game['game_id'],))
                    avg_row = c.fetchone()
                    if avg_row and avg_row['average_enjoyment_score']:
                        if game['enjoyment_score'] - avg_row['average_enjoyment_score'] > 2:
                            return True, game['game_id']

        elif superlative_name == 'Agree to Disagree':
            for game in user_games:
                if game.get('enjoyment_score'):
                    c.execute('SELECT average_enjoyment_score FROM games WHERE game_id = ?', (game['game_id'],))
                    avg_row = c.fetchone()
                    if avg_row and avg_row['average_enjoyment_score']:
                        if avg_row['average_enjoyment_score'] - game['enjoyment_score'] > 2:
                            return True, game['game_id']

        elif superlative_name == 'Favorite Child':
            games_with_hours = [g for g in user_games if g.get('hours_played')]
            if len(games_with_hours) >= 2:
                games_with_hours.sort(key=lambda x: x['hours_played'], reverse=True)
                if games_with_hours[0]['hours_played'] > (games_with_hours[1]['hours_played'] * 2):
                    return True, games_with_hours[0]['game_id']

        elif superlative_name == 'Nostalgic':
            for game in user_games:
                if game.get('enjoyment_score') and game['enjoyment_score'] >= 9 and game.get('release_date'):
                    import re
                    year_match = re.search(r'\b(19|20)\d{2}\b', str(game['release_date']))
                    if year_match and int(year_match.group()) < 2009:
                        return True, game['game_id']

        elif superlative_name == 'Worth Every Nickel':
            for game in user_games:
                if game.get('hours_played') and game.get('hours_played') > 0:
                    c.execute('SELECT price, original_price FROM games WHERE game_id = ?', (game['game_id'],))
                    price_row = c.fetchone()
                    price = price_row['original_price'] or price_row['price'] if price_row else None
                    if price and (price / game['hours_played']) <= 0.05:
                        return True, game['game_id']

        elif superlative_name == 'Here for the Music':
            for game in user_games:
                music = game.get('music_score')
                if music:
                    other = [s for s in [game.get('gameplay_score'), game.get('narrative_score'), game.get('enjoyment_score')] if s]
                    if other and all(music - s >= 2 for s in other):
                        return True, game['game_id']

        elif superlative_name == 'Here for the Story':
            for game in user_games:
                narrative = game.get('narrative_score')
                if narrative:
                    other = [s for s in [game.get('gameplay_score'), game.get('music_score'), game.get('enjoyment_score')] if s]
                    if other and all(narrative - s >= 2 for s in other):
                        return True, game['game_id']

        elif superlative_name == 'Gameplay Guru':
            for game in user_games:
                gameplay = game.get('gameplay_score')
                if gameplay:
                    other = [s for s in [game.get('narrative_score'), game.get('music_score'), game.get('enjoyment_score')] if s]
                    if other and all(gameplay - s >= 2 for s in other):
                        return True, game['game_id']

        elif superlative_name == 'Small Business Supporter':
            top_5 = sorted([g for g in user_games if g.get('enjoyment_score')],
                          key=lambda x: (-x['enjoyment_score'], x.get('enjoyment_order') or 999999))[:5]
            for game in top_5:
                if game.get('genres') and 'indie' in game['genres'].lower():
                    return True, game['game_id']

        elif superlative_name == "Don't Make Them Like They Used To":
            top_games = sorted([g for g in user_games if g.get('enjoyment_score')],
                              key=lambda x: (-x['enjoyment_score'], x.get('enjoyment_order') or 999999))
            if top_games and top_games[0].get('release_date'):
                import re
                year_match = re.search(r'\b(19|20)\d{2}\b', str(top_games[0]['release_date']))
                if year_match and int(year_match.group()) < 2010:
                    return True, top_games[0]['game_id']

        elif superlative_name == 'Get What You Pay For':
            top_10 = sorted([g for g in user_games if g.get('enjoyment_score')],
                           key=lambda x: (-x['enjoyment_score'], x.get('enjoyment_order') or 999999))[:10]
            for game in top_10:
                if game.get('hours_played') and game.get('hours_played') > 0:
                    c.execute('SELECT price, original_price FROM games WHERE game_id = ?', (game['game_id'],))
                    price_row = c.fetchone()
                    price = price_row['original_price'] or price_row['price'] if price_row else None
                    if price and (price / game['hours_played']) > 2:
                        return True, game['game_id']

        elif superlative_name == 'Graphics Not Required':
            for game in user_games:
                if game.get('enjoyment_score', 0) >= 9 and game.get('graphics_quality', '').lower() in ['low', 'poor', 'bad']:
                    return True, game['game_id']

        elif superlative_name == "Buyer's Remorse":
            for game in user_games:
                if game.get('enjoyment_score') and game.get('hours_played'):
                    if game['enjoyment_score'] < 6 and game['hours_played'] < 10:
                        return True, game['game_id']

        elif superlative_name == 'Early Adopter':
            for game in user_games:
                c.execute('SELECT COUNT(*) as count FROM user_scores WHERE game_id = ?', (game['game_id'],))
                count = c.fetchone()['count']
                if count <= 10:
                    return True, game['game_id']

        return False, None


def purchase_random_superlative(user_id, cost=10):
    """Purchase a random superlative by spending RP. Only allows purchasing titles user is eligible for."""
    import random

    with get_db() as conn:
        c = conn.cursor()

        # Check if user has enough RP
        c.execute('SELECT review_points FROM users WHERE id = ?', (user_id,))
        row = c.fetchone()
        if not row:
            return False, "User not found", None

        review_points = row['review_points'] or 0
        if review_points < cost:
            return False, f"Not enough RP. You need {cost} RP but only have {review_points} RP", None

        # Check if user has available slots
        unlocked_slots = get_unlocked_superlative_slots(user_id)
        c.execute('''
            SELECT COUNT(*) as count FROM user_superlatives
            WHERE user_id = ?
        ''', (user_id,))
        total_unlocked = c.fetchone()['count']

        if total_unlocked >= unlocked_slots:
            return False, f"No available slots. You have {total_unlocked}/{unlocked_slots} slots filled. Earn more RP to unlock additional slots (1 slot per 5 RP)", None

        # Get all superlatives the user hasn't unlocked yet
        c.execute('''
            SELECT s.id, s.name, s.category
            FROM superlatives s
            WHERE s.id NOT IN (
                SELECT superlative_id FROM user_superlatives WHERE user_id = ?
            )
        ''', (user_id,))
        all_available = c.fetchall()

        if not all_available:
            return False, "You have unlocked all available titles!", None

        # Filter to only eligible superlatives (for solo) or all friend superlatives
        eligible = []
        for sup in all_available:
            if sup['category'] == 'friend':
                # Friend superlatives are always eligible (they depend on friend data)
                eligible.append(sup)
            else:
                # Check eligibility for solo superlatives
                is_eligible, game_id = check_superlative_eligibility(user_id, sup['name'])
                if is_eligible:
                    eligible.append(dict(sup, game_id=game_id))

        if not eligible:
            return False, "You don't qualify for any remaining titles. Keep playing and reviewing games!", None

        # Pick a random eligible one
        chosen = random.choice(eligible)
        superlative_id = chosen['id']
        superlative_name = chosen['name']
        game_id = chosen.get('game_id')  # Already found by check_superlative_eligibility

        # Deduct RP and unlock superlative
        c.execute('''
            UPDATE users
            SET review_points = review_points - ?
            WHERE id = ?
        ''', (cost, user_id))

        c.execute('''
            INSERT INTO user_superlatives (user_id, superlative_id, game_id)
            VALUES (?, ?, ?)
        ''', (user_id, superlative_id, game_id))

        conn.commit()
        return True, f'Successfully unlocked "{superlative_name}"!', superlative_name


def add_or_get_game(name, app_id=None, release_date=None, description=None, genres=None, price=None, cover_path=None, 
                    developer=None, publisher=None, original_price=None, sale_price=None, cover_etag=None):
    """Add a game or update existing game with new information, return game_id."""
    with get_db() as conn:
        c = conn.cursor()
        
        # First, try to find by app_id if provided (more reliable than name)
        if app_id:
            c.execute('SELECT game_id FROM games WHERE app_id = ?', (app_id,))
            row = c.fetchone()
            if row:
                game_id = row['game_id']
                # Update the game with any new information
                update_game_info(game_id, name=name, app_id=app_id, release_date=release_date, 
                               description=description, genres=genres, price=price, cover_path=cover_path,
                               developer=developer, publisher=publisher, original_price=original_price, 
                               sale_price=sale_price, cover_etag=cover_etag)
                return game_id
        
        # If not found by app_id, try by name
        c.execute('SELECT game_id FROM games WHERE name = ?', (name,))
        row = c.fetchone()
        if row:
            game_id = row['game_id']
            # Update with new information
            update_game_info(game_id, name=name, app_id=app_id, release_date=release_date, 
                           description=description, genres=genres, price=price, cover_path=cover_path,
                           developer=developer, publisher=publisher, original_price=original_price, 
                           sale_price=sale_price, cover_etag=cover_etag)
            return game_id
        
        # Game doesn't exist, create it
        c.execute('''
            INSERT INTO games (app_id, name, release_date, description, genres, price, cover_path, 
                             developer, publisher, original_price, sale_price, cover_etag, average_enjoyment_score, num_ratings)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
        ''', (app_id, name, release_date, description, genres, price, cover_path, 
              developer, publisher, original_price, sale_price, cover_etag))
        conn.commit()
        return c.lastrowid


def get_all_games():
    """Get list of all games in database."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT game_id, app_id, name, release_date, description, genres, price, cover_path, 
                   average_enjoyment_score, num_ratings, created_at, updated_at 
            FROM games 
            ORDER BY name
        ''')
        return [dict(row) for row in c.fetchall()]


def get_user_games(user_id):
    """Get all games with scores for a specific user."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT g.game_id, g.app_id, g.name, g.release_date, g.description, g.genres, g.price, 
                   g.cover_path, g.average_enjoyment_score,
                   us.enjoyment_score, us.gameplay_score, us.music_score,
                   us.narrative_score, us.metacritic_score, us.hours_played,
                   us.enjoyment_order, us.gameplay_order, us.music_order, us.narrative_order,
                   us.backlog_order, us.review_text, us.difficulty, us.graphics_quality,
                   us.completion_time, us.replayability, us.style
            FROM games g
            INNER JOIN user_scores us ON g.game_id = us.game_id AND us.user_id = ?
            ORDER BY g.name
        ''', (user_id,))
        return [dict(row) for row in c.fetchall()]


def set_tie_order(user_id, score_key, ordered_game_ids):
    """Persist a user-specific tie-breaker order for a given score key among a list of game_ids.
    ordered_game_ids: list[int] representing desired order top->bottom within tied group.
    score_key: one of enjoyment_score, gameplay_score, music_score, narrative_score
    """
    key_map = {
        'enjoyment_score': 'enjoyment_order',
        'gameplay_score': 'gameplay_order',
        'music_score': 'music_order',
        'narrative_score': 'narrative_order',
    }
    order_col = key_map.get(score_key)
    if not order_col:
        return False
    with get_db() as conn:
        c = conn.cursor()
        pos = 1
        for gid in ordered_game_ids:
            try:
                gid_int = int(gid)
            except Exception:
                continue
            c.execute(
                f'''UPDATE user_scores SET {order_col} = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND game_id = ?''',
                (pos, user_id, gid_int)
            )
            pos += 1
        conn.commit()
    return True


def set_backlog_order(user_id, ordered_game_ids):
    """Set the backlog order for games with no scores."""
    with get_db() as conn:
        c = conn.cursor()
        pos = 1
        for gid in ordered_game_ids:
            try:
                gid_int = int(gid)
            except Exception:
                continue
            c.execute(
                '''UPDATE user_scores SET backlog_order = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND game_id = ?''',
                (pos, user_id, gid_int)
            )
            pos += 1
        conn.commit()
    return True


def add_game_to_user_backlog(user_id, game_id):
    """Add a game to user's backlog by creating a user_scores entry with no scores."""
    with get_db() as conn:
        c = conn.cursor()
        # Check if entry already exists
        c.execute('SELECT 1 FROM user_scores WHERE user_id = ? AND game_id = ?', (user_id, game_id))
        if c.fetchone():
            return True  # Already exists
        
        # Create entry with no scores
        c.execute(
            '''INSERT INTO user_scores (user_id, game_id, backlog_order)
               VALUES (?, ?, 0)''',
            (user_id, game_id)
        )
        conn.commit()
    return True


def set_user_score(user_id, game_id, enjoyment=None, gameplay=None, music=None, narrative=None, metacritic=None, review_text=None, difficulty=None, graphics_quality=None, completion_time=None, replayability=None, style=None):
    """Set or update user scores for a game. Metacritic is kept for backwards compatibility but not used."""
    with get_db() as conn:
        c = conn.cursor()

        # Check if this is a new review (user hasn't scored this game before)
        c.execute('''
            SELECT enjoyment_score, gameplay_score, music_score, narrative_score
            FROM user_scores
            WHERE user_id = ? AND game_id = ?
        ''', (user_id, game_id))
        existing = c.fetchone()

        # Determine if this is a new review (user is adding scores where none existed)
        is_new_review = False
        if existing:
            had_any_score = any(existing[k] is not None for k in ['enjoyment_score', 'gameplay_score', 'music_score', 'narrative_score'])
            has_new_score = any(s is not None for s in [enjoyment, gameplay, music, narrative])
            is_new_review = not had_any_score and has_new_score
        else:
            # No existing entry, and they're adding at least one score
            is_new_review = any(s is not None for s in [enjoyment, gameplay, music, narrative])

        c.execute('''
            INSERT INTO user_scores
            (user_id, game_id, enjoyment_score, gameplay_score, music_score, narrative_score, review_text, difficulty, graphics_quality, completion_time, replayability, style)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, game_id) DO UPDATE SET
            enjoyment_score = COALESCE(?, enjoyment_score),
            gameplay_score = COALESCE(?, gameplay_score),
            music_score = COALESCE(?, music_score),
            narrative_score = COALESCE(?, narrative_score),
            review_text = ?,
            difficulty = ?,
            graphics_quality = ?,
            completion_time = ?,
            replayability = ?,
            style = ?,
            updated_at = CURRENT_TIMESTAMP
        ''', (user_id, game_id, enjoyment, gameplay, music, narrative, review_text, difficulty, graphics_quality, completion_time, replayability, style,
              enjoyment, gameplay, music, narrative, review_text, difficulty, graphics_quality, completion_time, replayability, style))

        # Award 1 RP if this is a new review
        if is_new_review:
            c.execute('UPDATE users SET review_points = review_points + 1 WHERE id = ?', (user_id,))

        conn.commit()
        
        # Update average scores and PV ratio for the game
        c.execute('''
            SELECT 
                AVG(enjoyment_score) as avg_enjoyment,
                AVG(gameplay_score) as avg_gameplay,
                AVG(music_score) as avg_music,
                AVG(narrative_score) as avg_narrative,
                AVG(hours_played) as avg_hours,
                COUNT(*) as num_ratings
            FROM user_scores 
            WHERE game_id = ? AND enjoyment_score IS NOT NULL
        ''', (game_id,))
        result = c.fetchone()
        avg_enjoyment = result['avg_enjoyment'] if result and result['avg_enjoyment'] else 0
        avg_gameplay = result['avg_gameplay'] if result and result['avg_gameplay'] else None
        avg_music = result['avg_music'] if result and result['avg_music'] else None
        avg_narrative = result['avg_narrative'] if result and result['avg_narrative'] else None
        avg_hours = result['avg_hours'] if result and result['avg_hours'] else None
        num_ratings = result['num_ratings'] if result else 0
        
        # Calculate PV ratio (price per hour)
        c.execute('SELECT price FROM games WHERE game_id = ?', (game_id,))
        price_row = c.fetchone()
        pv_ratio = None
        if price_row and price_row['price'] and avg_hours and avg_hours > 0:
            pv_ratio = price_row['price'] / avg_hours
        
        c.execute('''
            UPDATE games 
            SET average_enjoyment_score = ?, 
                average_gameplay_score = ?,
                average_music_score = ?,
                average_narrative_score = ?,
                pv_ratio = ?,
                num_ratings = ?, 
                updated_at = CURRENT_TIMESTAMP
            WHERE game_id = ?
        ''', (avg_enjoyment, avg_gameplay, avg_music, avg_narrative, pv_ratio, num_ratings, game_id))
        conn.commit()


def set_user_playtime(user_id, game_id, hours_played=None):
    """Set or update a user's playtime for a game (in hours)."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO user_scores (user_id, game_id, hours_played)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, game_id) DO UPDATE SET
            hours_played = COALESCE(?, hours_played),
            updated_at = CURRENT_TIMESTAMP
        ''', (user_id, game_id, hours_played, hours_played))
        conn.commit()


def delete_game(game_id):
    """Delete a game and all its associated scores."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('DELETE FROM user_scores WHERE game_id = ?', (game_id,))
        c.execute('DELETE FROM games WHERE id = ?', (game_id,))
        conn.commit()


def delete_user_score(user_id, game_id):
    """Delete a specific user's score for a game."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('DELETE FROM user_scores WHERE user_id = ? AND game_id = ?',
                 (user_id, game_id))
        conn.commit()


def update_game_info(game_id, name=None, app_id=None, release_date=None, description=None, genres=None, price=None, cover_path=None,
                    developer=None, publisher=None, original_price=None, sale_price=None, cover_etag=None):
    """Update game metadata. Only updates fields that are provided (not None)."""
    with get_db() as conn:
        c = conn.cursor()
        updates = []
        values = []
        
        if name is not None:
            updates.append("name = ?")
            values.append(name)
        if app_id is not None:
            updates.append("app_id = ?")
            values.append(app_id)
        if release_date is not None:
            updates.append("release_date = ?")
            values.append(release_date)
        if description is not None:
            updates.append("description = ?")
            values.append(description)
        if genres is not None:
            updates.append("genres = ?")
            values.append(genres)
        if price is not None:
            updates.append("price = ?")
            values.append(price)
        if cover_path is not None:
            updates.append("cover_path = ?")
            values.append(cover_path)
        if developer is not None:
            updates.append("developer = ?")
            values.append(developer)
        if publisher is not None:
            updates.append("publisher = ?")
            values.append(publisher)
        if original_price is not None:
            updates.append("original_price = ?")
            values.append(original_price)
        if sale_price is not None:
            updates.append("sale_price = ?")
            values.append(sale_price)
        if cover_etag is not None:
            updates.append("cover_etag = ?")
            values.append(cover_etag)
        
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            values.append(game_id)
            query = f"UPDATE games SET {', '.join(updates)} WHERE game_id = ?"
            c.execute(query, values)
            conn.commit()


def import_csv_data(user_id, csv_content):
    """Import games and scores from CSV content."""
    import csv
    from io import StringIO
    
    reader = csv.DictReader(StringIO(csv_content))
    imported_count = 0
    
    for row in reader:
        game_name = row.get('Game', '').strip()
        if not game_name:
            continue
        
        # Extract game metadata from CSV
        app_id = row.get('AppID', '').strip() or None
        release_date = row.get('Release Year', '').strip() or None
        description = row.get('Description', '').strip() or None
        genres = row.get('Genres', '').strip() or None
        price_str = row.get('Price', '').strip()
        price = float(price_str) if price_str and price_str != '-' else None
        cover_path = row.get('Cover Path', '').strip() or None
        
        # Add/get game
        game_id = add_or_get_game(
            name=game_name,
            app_id=app_id,
            release_date=release_date,
            description=description,
            genres=genres,
            price=price,
            cover_path=cover_path
        )
        
        # Extract scores - handle empty strings and dashes
        def safe_float(val):
            if not val or val.strip() == '' or val.strip() == '-':
                return None
            try:
                return float(val.strip())
            except:
                return None
        
        enjoyment = safe_float(row.get('Enjoyment Score', ''))
        gameplay = safe_float(row.get('Gameplay Score', ''))
        music = safe_float(row.get('Music Score', ''))
        narrative = safe_float(row.get('Narrative Score', ''))
        metacritic = safe_float(row.get('MetaCritic Score', ''))
        # Optional playtime in hours
        playtime = safe_float(row.get('Playtime (Hours)', '') or row.get('Playtime', ''))
        
        # Save user scores (only if at least one score exists)
        if any([enjoyment, gameplay, music, narrative, metacritic]):
            set_user_score(user_id, game_id, enjoyment, gameplay, music, narrative, metacritic)
            imported_count += 1
        # Save playtime when present (independent of scores)
        if playtime is not None:
            set_user_playtime(user_id, game_id, playtime)
    
    return imported_count


def search_games(query):
    """Search for games in the database by name with fuzzy matching."""
    with get_db() as conn:
        c = conn.cursor()
        # Split query into words for fuzzy matching
        words = query.strip().split()
        if not words:
            return []
        
        # Build fuzzy search pattern - each word should appear somewhere
        conditions = ' AND '.join(['name LIKE ?' for _ in words])
        patterns = [f"%{word}%" for word in words]
        
        c.execute(f'''
            SELECT game_id, name, release_date, cover_path, developer
            FROM games
            WHERE {conditions}
            ORDER BY 
                CASE 
                    WHEN LOWER(name) = LOWER(?) THEN 0
                    WHEN LOWER(name) LIKE LOWER(?) THEN 1
                    ELSE 2
                END,
                name
            LIMIT 50
        ''', patterns + [query, f"{query}%"])
        
        results = []
        for row in c.fetchall():
            game = {
                'game_id': row['game_id'],
                'name': row['name'],
                'cover_path': row['cover_path'],
                'release_date': row['release_date'],
                'developer': row['developer']
            }
            # Format release_date to show just the year (e.g., "2024")
            if row['release_date']:
                try:
                    release_date = str(row['release_date'])
                    # First try to find a 4-digit year (most common case)
                    import re
                    four_digit_year = re.search(r'\b(19|20)\d{2}\b', release_date)
                    if four_digit_year:
                        game['formatted_date'] = four_digit_year.group()
                    elif release_date[0:2].isdigit() and len(release_date) >= 4 and release_date[0:4].isdigit():
                        # Standard YYYY-MM-DD format at start
                        game['formatted_date'] = release_date[:4]
                    else:
                        # Last resort: find any 2 digits and assume 20XX
                        two_digit_match = re.search(r'\d{2}', release_date)
                        if two_digit_match:
                            year_digits = two_digit_match.group()
                            # If it's between 00-25, assume 2000s, otherwise 1900s
                            if int(year_digits) <= 25:
                                game['formatted_date'] = f"20{year_digits}"
                            else:
                                game['formatted_date'] = f"19{year_digits}"
                        else:
                            game['formatted_date'] = 'Unknown'
                except:
                    game['formatted_date'] = 'Unknown'
            else:
                game['formatted_date'] = 'Unknown'
            results.append(game)
        return results


def add_game_to_user_list(user_id, game_id):
    """Add a game to user's list with default null scores."""
    with get_db() as conn:
        c = conn.cursor()
        # Check if already exists
        c.execute('''
            SELECT 1 FROM user_scores 
            WHERE user_id = ? AND game_id = ?
        ''', (user_id, game_id))
        if c.fetchone():
            return False  # Already in list
        
        # Add with null scores
        c.execute('''
            INSERT INTO user_scores (user_id, game_id)
            VALUES (?, ?)
        ''', (user_id, game_id))
        return True


def get_all_games_with_avg_scores(user_id=None):
    """Get all games with their average community scores, sorted by enjoyment score descending."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT 
                g.game_id,
                g.app_id,
                g.name,
                g.release_date,
                g.genres,
                g.cover_path,
                g.price,
                g.original_price,
                AVG(us.enjoyment_score) as avg_enjoyment,
                AVG(us.gameplay_score) as avg_gameplay,
                AVG(us.music_score) as avg_music,
                AVG(us.narrative_score) as avg_narrative,
                COUNT(DISTINCT us.user_id) as num_ratings,
                AVG(us.hours_played) as avg_hours
            FROM games g
            LEFT JOIN user_scores us ON g.game_id = us.game_id
            GROUP BY g.game_id
            ORDER BY avg_enjoyment DESC NULLS LAST, g.name ASC
        ''')
        
        games = []
        for row in c.fetchall():
            game = dict(row)
            # Format release_date as "Jun-2023"
            if game.get('release_date'):
                try:
                    from datetime import datetime
                    # Try parsing "DD-Mon-YY" format (e.g., "25-Jul-24")
                    date_obj = datetime.strptime(game['release_date'], '%d-%b-%y')
                    game['release_date'] = date_obj.strftime('%b-%Y')
                except:
                    # Try standard YYYY-MM-DD format
                    try:
                        date_obj = datetime.strptime(game['release_date'], '%Y-%m-%d')
                        game['release_date'] = date_obj.strftime('%b-%Y')
                    except:
                        # Keep as is if parsing fails
                        pass
            # Format the scores for display
            game['enjoyment_score'] = game.pop('avg_enjoyment')
            game['gameplay_score'] = game.pop('avg_gameplay')
            game['music_score'] = game.pop('avg_music')
            game['narrative_score'] = game.pop('avg_narrative')
            # Keep game_id as 'id' for compatibility with template
            game['id'] = game['game_id']
            
            # Calculate playtime value (price per hour)
            avg_hours = game.pop('avg_hours')

            # Check if game is new (released within last 2 months)
            game['is_new_game'] = False
            if game.get('release_date'):
                try:
                    from datetime import datetime, timedelta
                    import re
                    # Parse release date (format: "Month Day, Year")
                    year_match = re.search(r'\b(19|20)\d{2}\b', str(game['release_date']))
                    if year_match:
                        release_year = int(year_match.group())
                        current_year = datetime.now().year
                        # Simple check: if released this year or last year, do more detailed check
                        if current_year - release_year <= 1:
                            try:
                                release = datetime.strptime(game['release_date'], '%b %d, %Y')
                                two_months_ago = datetime.now() - timedelta(days=60)
                                if release > two_months_ago:
                                    game['is_new_game'] = True
                            except:
                                pass
                except:
                    pass

            if game['is_new_game']:
                game['playtime_value'] = None
            elif game.get('price') and avg_hours and avg_hours > 0:
                game['playtime_value'] = game['price'] / avg_hours
            else:
                game['playtime_value'] = None
            
            # Check if user has reviewed this game
            if user_id:
                c.execute('SELECT 1 FROM user_scores WHERE user_id = ? AND game_id = ?', (user_id, game['game_id']))
                game['user_reviewed'] = c.fetchone() is not None
            else:
                game['user_reviewed'] = False
            
            games.append(game)
        
        return games


def get_game_detail(game_id, user_id=None):
    """Get detailed information about a specific game including description and community scores."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT 
                g.game_id,
                g.name,
                g.release_date,
                g.description,
                g.genres,
                g.cover_path,
                g.price,
                g.app_id,
                g.developer,
                g.publisher,
                g.original_price,
                g.sale_price,
                g.cover_etag,
                AVG(us.enjoyment_score) as avg_enjoyment,
                AVG(us.gameplay_score) as avg_gameplay,
                AVG(us.music_score) as avg_music,
                AVG(us.narrative_score) as avg_narrative,
                COUNT(DISTINCT us.user_id) as num_ratings
            FROM games g
            LEFT JOIN user_scores us ON g.game_id = us.game_id
            WHERE g.game_id = ?
            GROUP BY g.game_id
        ''', (game_id,))
        
        row = c.fetchone()
        if not row:
            return None
        
        game = dict(row)
        # Format release_date as "Jun-2023"
        if game.get('release_date'):
            try:
                from datetime import datetime
                date_obj = datetime.strptime(game['release_date'], '%d-%b-%y')
                game['release_date'] = date_obj.strftime('%b-%Y')
            except:
                try:
                    date_obj = datetime.strptime(game['release_date'], '%Y-%m-%d')
                    game['release_date'] = date_obj.strftime('%b-%Y')
                except:
                    pass
        
        # Format the scores for display
        game['enjoyment_score'] = game.pop('avg_enjoyment')
        game['gameplay_score'] = game.pop('avg_gameplay')
        game['music_score'] = game.pop('avg_music')
        game['narrative_score'] = game.pop('avg_narrative')
        
        # Check if user has reviewed this game
        if user_id:
            c.execute('''
                SELECT enjoyment_score, gameplay_score, music_score, narrative_score 
                FROM user_scores 
                WHERE user_id = ? AND game_id = ?
            ''', (user_id, game['game_id']))
            user_score = c.fetchone()
            if user_score:
                # Check if it's in backlog (no scores) or reviewed (has at least one score)
                has_scores = any(user_score[k] is not None for k in ['enjoyment_score', 'gameplay_score', 'music_score', 'narrative_score'])
                game['user_reviewed'] = has_scores
                game['in_backlog'] = not has_scores
            else:
                game['user_reviewed'] = False
                game['in_backlog'] = False
        else:
            game['user_reviewed'] = False
            game['in_backlog'] = False
        
        return game


def is_admin(user_id):
    """Check if a user is an admin."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT user_type FROM users WHERE id = ?', (user_id,))
        row = c.fetchone()
        return row and row['user_type'] == 'admin'


def admin_update_game_info(game_id, **kwargs):
    """Admin function to update game information."""
    allowed_fields = ['name', 'release_date', 'description', 'genres', 'price',
                      'cover_path', 'developer', 'publisher', 'original_price',
                      'sale_price', 'app_id']

    updates = []
    values = []

    for field, value in kwargs.items():
        if field in allowed_fields and value is not None:
            updates.append(f"{field} = ?")
            values.append(value)

    if not updates:
        return False

    values.append(game_id)

    with get_db() as conn:
        c = conn.cursor()
        query = f"UPDATE games SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE game_id = ?"
        c.execute(query, values)
        conn.commit()
        return True


# Friend Management Functions

def send_friend_request(user_id, friend_username):
    """Send a friend request to another user. Returns (success, message)."""
    with get_db() as conn:
        c = conn.cursor()

        # Get friend's user ID
        c.execute('SELECT id FROM users WHERE username = ?', (friend_username,))
        friend = c.fetchone()

        if not friend:
            return False, "User not found"

        friend_id = friend['id']

        if user_id == friend_id:
            return False, "Cannot add yourself as a friend"

        # Check if friendship already exists
        c.execute('''
            SELECT status FROM friends
            WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)
        ''', (user_id, friend_id, friend_id, user_id))
        existing = c.fetchone()

        if existing:
            if existing['status'] == 'accepted':
                return False, "Already friends"
            elif existing['status'] == 'pending':
                return False, "Friend request already pending"
            elif existing['status'] == 'rejected':
                return False, "Friend request was rejected"

        # Create friend request
        try:
            c.execute('''
                INSERT INTO friends (user_id, friend_id, status)
                VALUES (?, ?, 'pending')
            ''', (user_id, friend_id))
            conn.commit()
            return True, "Friend request sent"
        except Exception as e:
            return False, str(e)


def get_friend_requests(user_id):
    """Get pending friend requests for a user."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT f.id, f.user_id, u.username, u.profile_picture, f.created_at
            FROM friends f
            JOIN users u ON f.user_id = u.id
            WHERE f.friend_id = ? AND f.status = 'pending'
            ORDER BY f.created_at DESC
        ''', (user_id,))
        return [dict(row) for row in c.fetchall()]


def get_sent_requests(user_id):
    """Get friend requests sent by the user."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT f.id, f.friend_id, u.username, u.profile_picture, f.created_at, f.status
            FROM friends f
            JOIN users u ON f.friend_id = u.id
            WHERE f.user_id = ? AND f.status = 'pending'
            ORDER BY f.created_at DESC
        ''', (user_id,))
        return [dict(row) for row in c.fetchall()]


def accept_friend_request(request_id, user_id):
    """Accept a friend request. Returns (success, message)."""
    with get_db() as conn:
        c = conn.cursor()

        # Verify this request is for the current user
        c.execute('SELECT user_id, friend_id FROM friends WHERE id = ? AND friend_id = ?',
                 (request_id, user_id))
        request = c.fetchone()

        if not request:
            return False, "Friend request not found"

        # Update status to accepted
        c.execute('UPDATE friends SET status = ? WHERE id = ?', ('accepted', request_id))
        conn.commit()
        return True, "Friend request accepted"


def reject_friend_request(request_id, user_id):
    """Reject a friend request. Returns (success, message)."""
    with get_db() as conn:
        c = conn.cursor()

        # Verify this request is for the current user
        c.execute('SELECT user_id, friend_id FROM friends WHERE id = ? AND friend_id = ?',
                 (request_id, user_id))
        request = c.fetchone()

        if not request:
            return False, "Friend request not found"

        # Delete the request
        c.execute('DELETE FROM friends WHERE id = ?', (request_id,))
        conn.commit()
        return True, "Friend request rejected"


def remove_friend(user_id, friend_id):
    """Remove a friend. Returns (success, message)."""
    with get_db() as conn:
        c = conn.cursor()

        # Delete friendship (works both ways)
        c.execute('''
            DELETE FROM friends
            WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)
        ''', (user_id, friend_id, friend_id, user_id))

        if c.rowcount == 0:
            return False, "Friendship not found"

        conn.commit()
        return True, "Friend removed"


def get_friends(user_id):
    """Get all accepted friends for a user."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT
                CASE
                    WHEN f.user_id = ? THEN f.friend_id
                    ELSE f.user_id
                END as friend_user_id,
                u.username,
                u.profile_picture
            FROM friends f
            JOIN users u ON (
                CASE
                    WHEN f.user_id = ? THEN f.friend_id = u.id
                    ELSE f.user_id = u.id
                END
            )
            WHERE (f.user_id = ? OR f.friend_id = ?) AND f.status = 'accepted'
            ORDER BY u.username
        ''', (user_id, user_id, user_id, user_id))
        return [dict(row) for row in c.fetchall()]


def search_users(query, exclude_user_id=None):
    """Search for users by username."""
    with get_db() as conn:
        c = conn.cursor()
        if exclude_user_id:
            c.execute('''
                SELECT id, username, profile_picture
                FROM users
                WHERE username LIKE ? AND id != ?
                LIMIT 20
            ''', (f'%{query}%', exclude_user_id))
        else:
            c.execute('''
                SELECT id, username, profile_picture
                FROM users
                WHERE username LIKE ?
                LIMIT 20
            ''', (f'%{query}%',))
        return [dict(row) for row in c.fetchall()]


# Review Points Functions

def get_review_points(user_id):
    """Get the user's current review points."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT review_points FROM users WHERE id = ?', (user_id,))
        row = c.fetchone()
        return row['review_points'] if row else 0


def get_unlocked_superlative_slots(user_id):
    """Calculate how many superlative slots are unlocked based on RP (1 slot per 5 RP)."""
    rp = get_review_points(user_id)
    return rp // 5


# Superlatives Functions

def get_all_superlatives():
    """Get all superlative definitions."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM superlatives ORDER BY category, name')
        return [dict(row) for row in c.fetchall()]


def get_user_superlatives(user_id):
    """Get all unlocked superlatives for a user."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT
                s.id, s.name, s.description, s.category,
                us.game_id, us.friend_id, us.unlocked_at,
                g.name as game_name, g.cover_path as game_cover,
                u.username as friend_username
            FROM user_superlatives us
            JOIN superlatives s ON us.superlative_id = s.id
            LEFT JOIN games g ON us.game_id = g.game_id
            LEFT JOIN users u ON us.friend_id = u.id
            WHERE us.user_id = ?
            ORDER BY us.unlocked_at DESC
        ''', (user_id,))
        return [dict(row) for row in c.fetchall()]


def unlock_superlative(user_id, superlative_name, game_id=None, friend_id=None):
    """Unlock a superlative for a user. Returns (success, message)."""
    with get_db() as conn:
        c = conn.cursor()

        # Get superlative ID
        c.execute('SELECT id FROM superlatives WHERE name = ?', (superlative_name,))
        superlative = c.fetchone()
        if not superlative:
            return False, "Superlative not found"

        superlative_id = superlative['id']

        # Check if already unlocked (any instance of this superlative)
        c.execute('''
            SELECT 1 FROM user_superlatives
            WHERE user_id = ? AND superlative_id = ?
        ''', (user_id, superlative_id))

        if c.fetchone():
            return False, "Already unlocked"

        # Check if user has enough unlocked slots (1 slot per 5 RP)
        unlocked_slots = get_unlocked_superlative_slots(user_id)
        c.execute('SELECT COUNT(*) as count FROM user_superlatives WHERE user_id = ?', (user_id,))
        current_unlocked = c.fetchone()['count']

        if current_unlocked >= unlocked_slots:
            return False, f"Need more Review Points (have {unlocked_slots} slots, need {current_unlocked + 1})"

        # Unlock it
        try:
            c.execute('''
                INSERT INTO user_superlatives (user_id, superlative_id, game_id, friend_id)
                VALUES (?, ?, ?, ?)
            ''', (user_id, superlative_id, game_id, friend_id))
            conn.commit()
            return True, "Superlative unlocked!"
        except Exception as e:
            return False, str(e)


def set_active_title(user_id, superlative_id):
    """Set the user's active title/superlative."""
    with get_db() as conn:
        c = conn.cursor()

        # Verify user has unlocked this superlative
        c.execute('''
            SELECT 1 FROM user_superlatives
            WHERE user_id = ? AND superlative_id = ?
        ''', (user_id, superlative_id))

        if not c.fetchone():
            return False, "You haven't unlocked this title"

        # Set as active
        c.execute('UPDATE users SET active_title = ? WHERE id = ?', (superlative_id, user_id))
        conn.commit()
        return True, "Title activated!"


def clear_active_title(user_id):
    """Clear the user's active title."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('UPDATE users SET active_title = NULL WHERE id = ?', (user_id,))
        conn.commit()


def get_active_title(user_id):
    """Get the user's active title name."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT s.name
            FROM users u
            LEFT JOIN superlatives s ON u.active_title = s.id
            WHERE u.id = ?
        ''', (user_id,))
        row = c.fetchone()
        return row['name'] if row and row['name'] else None


def calculate_solo_superlatives(user_id):
    """Calculate which solo superlatives a user qualifies for and unlock them."""
    unlocked = []

    with get_db() as conn:
        c = conn.cursor()

        # Get user's games with scores and playtime
        user_games = get_user_games(user_id)

        if not user_games:
            return unlocked

        # 1. Toxic Relationship - overall score <7 but hours >100
        for game in user_games:
            if game.get('enjoyment_score') and game.get('hours_played'):
                if game['enjoyment_score'] < 7 and game['hours_played'] > 100:
                    success, msg = unlock_superlative(user_id, "Toxic Relationship", game['game_id'])
                    if success:
                        unlocked.append(("Toxic Relationship", game['name']))

        # 2. Die on this Hill - score >2 points above community average
        for game in user_games:
            if game.get('enjoyment_score'):
                c.execute('SELECT average_enjoyment_score FROM games WHERE game_id = ?', (game['game_id'],))
                avg_row = c.fetchone()
                if avg_row and avg_row['average_enjoyment_score']:
                    diff = game['enjoyment_score'] - avg_row['average_enjoyment_score']
                    if diff > 2:
                        success, msg = unlock_superlative(user_id, "Die on this Hill", game['game_id'])
                        if success:
                            unlocked.append(("Die on this Hill", game['name']))

        # 3. Agree to Disagree - score >2 points below community average
        for game in user_games:
            if game.get('enjoyment_score'):
                c.execute('SELECT average_enjoyment_score FROM games WHERE game_id = ?', (game['game_id'],))
                avg_row = c.fetchone()
                if avg_row and avg_row['average_enjoyment_score']:
                    diff = avg_row['average_enjoyment_score'] - game['enjoyment_score']
                    if diff > 2:
                        success, msg = unlock_superlative(user_id, "Agree to Disagree", game['game_id'])
                        if success:
                            unlocked.append(("Agree to Disagree", game['name']))

        # 4. Favorite Child - game with >2x hours of next most played
        games_with_hours = [g for g in user_games if g.get('hours_played')]
        if len(games_with_hours) >= 2:
            games_with_hours.sort(key=lambda x: x['hours_played'], reverse=True)
            top_game = games_with_hours[0]
            second_game = games_with_hours[1]
            if top_game['hours_played'] > (second_game['hours_played'] * 2):
                success, msg = unlock_superlative(user_id, "Favorite Child", top_game['game_id'])
                if success:
                    unlocked.append(("Favorite Child", top_game['name']))

        # 5. Nostalgic - game from before 2009 with score >=9
        for game in user_games:
            if game.get('enjoyment_score') and game['enjoyment_score'] >= 9:
                if game.get('release_date'):
                    try:
                        # Extract year from release_date
                        import re
                        year_match = re.search(r'\b(19|20)\d{2}\b', str(game['release_date']))
                        if year_match:
                            year = int(year_match.group())
                            if year < 2009:
                                success, msg = unlock_superlative(user_id, "Nostalgic", game['game_id'])
                                if success:
                                    unlocked.append(("Nostalgic", game['name']))
                    except:
                        pass

        # 6. Worth Every Nickel - PV ratio <=0.05
        for game in user_games:
            if game.get('hours_played') and game.get('hours_played') > 0:
                c.execute('SELECT price FROM games WHERE game_id = ?', (game['game_id'],))
                price_row = c.fetchone()
                if price_row and price_row['price']:
                    pv_ratio = price_row['price'] / game['hours_played']
                    if pv_ratio <= 0.05:
                        success, msg = unlock_superlative(user_id, "Worth Every Nickel", game['game_id'])
                        if success:
                            unlocked.append(("Worth Every Nickel", game['name']))

        # 7. Here for the Music - music score 2+ higher than other categories
        for game in user_games:
            music = game.get('music_score')
            if music:
                other_scores = [s for s in [game.get('gameplay_score'), game.get('narrative_score'), game.get('enjoyment_score')] if s is not None]
                if other_scores and all(music - s >= 2 for s in other_scores):
                    success, msg = unlock_superlative(user_id, "Here for the Music", game['game_id'])
                    if success:
                        unlocked.append(("Here for the Music", game['name']))

        # 8. Here for the Story - narrative score 2+ higher than other categories
        for game in user_games:
            narrative = game.get('narrative_score')
            if narrative:
                other_scores = [s for s in [game.get('gameplay_score'), game.get('music_score'), game.get('enjoyment_score')] if s is not None]
                if other_scores and all(narrative - s >= 2 for s in other_scores):
                    success, msg = unlock_superlative(user_id, "Here for the Story", game['game_id'])
                    if success:
                        unlocked.append(("Here for the Story", game['name']))

        # 9. Gameplay Guru - gameplay score 2+ higher than other categories
        for game in user_games:
            gameplay = game.get('gameplay_score')
            if gameplay:
                other_scores = [s for s in [game.get('narrative_score'), game.get('music_score'), game.get('enjoyment_score')] if s is not None]
                if other_scores and all(gameplay - s >= 2 for s in other_scores):
                    success, msg = unlock_superlative(user_id, "Gameplay Guru", game['game_id'])
                    if success:
                        unlocked.append(("Gameplay Guru", game['name']))

        # 10. Small Business Supporter - indie game in top 5
        top_5 = sorted([g for g in user_games if g.get('enjoyment_score')],
                       key=lambda x: (-x['enjoyment_score'], x.get('enjoyment_order') or 999999))[:5]
        for game in top_5:
            if game.get('genres') and 'indie' in game['genres'].lower():
                success, msg = unlock_superlative(user_id, "Small Business Supporter", game['game_id'])
                if success:
                    unlocked.append(("Small Business Supporter", game['name']))
                break

        # 11. Don't Make Them Like They Used To - top game from before 2010
        if top_5:
            top_game = top_5[0]
            if top_game.get('release_date'):
                try:
                    import re
                    year_match = re.search(r'\b(19|20)\d{2}\b', str(top_game['release_date']))
                    if year_match:
                        year = int(year_match.group())
                        if year < 2010:
                            success, msg = unlock_superlative(user_id, "Don't Make Them Like They Used To", top_game['game_id'])
                            if success:
                                unlocked.append(("Don't Make Them Like They Used To", top_game['name']))
                except:
                    pass

        # 12. Get What You Pay For - top 10 game with PV ratio >2
        top_10 = sorted([g for g in user_games if g.get('enjoyment_score')],
                       key=lambda x: (-x['enjoyment_score'], x.get('enjoyment_order') or 999999))[:10]
        for game in top_10:
            if game.get('hours_played') and game.get('hours_played') > 0:
                c.execute('SELECT price FROM games WHERE game_id = ?', (game['game_id'],))
                price_row = c.fetchone()
                if price_row and price_row['price']:
                    pv_ratio = price_row['price'] / game['hours_played']
                    if pv_ratio > 2:
                        success, msg = unlock_superlative(user_id, "Get What You Pay For", game['game_id'])
                        if success:
                            unlocked.append(("Get What You Pay For", game['name']))

        # 13. Graphics Not Required - score >=9 with low graphics
        for game in user_games:
            if game.get('enjoyment_score') and game['enjoyment_score'] >= 9:
                if game.get('graphics_quality') in ['Low', 'Very Low']:
                    success, msg = unlock_superlative(user_id, "Graphics Not Required", game['game_id'])
                    if success:
                        unlocked.append(("Graphics Not Required", game['name']))

        # 14. Buyer's Remorse - score <6 and <10 hours
        for game in user_games:
            if game.get('enjoyment_score') and game.get('hours_played'):
                if game['enjoyment_score'] < 6 and game['hours_played'] < 10:
                    success, msg = unlock_superlative(user_id, "Buyer's Remorse", game['game_id'])
                    if success:
                        unlocked.append(("Buyer's Remorse", game['name']))

        # 15. Early Adopter - reviewed within 6 months of release
        for game in user_games:
            if game.get('enjoyment_score') and game.get('updated_at'):
                # Get game release date
                c.execute('SELECT release_date FROM games WHERE game_id = ?', (game['game_id'],))
                game_row = c.fetchone()
                if game_row and game_row['release_date']:
                    try:
                        import re
                        from datetime import datetime, timedelta

                        # Parse release date (could be various formats)
                        release_date_str = str(game_row['release_date'])
                        release_date = None

                        # Try different date formats
                        for fmt in ['%d-%b-%y', '%Y-%m-%d', '%b-%Y']:
                            try:
                                release_date = datetime.strptime(release_date_str, fmt)
                                break
                            except:
                                continue

                        # If we couldn't parse with standard formats, try to extract year
                        if not release_date:
                            year_match = re.search(r'\b(19|20)\d{2}\b', release_date_str)
                            if year_match:
                                year = int(year_match.group())
                                release_date = datetime(year, 1, 1)  # Use Jan 1 as approximation

                        if release_date:
                            # Parse review date
                            review_date_str = str(game['updated_at'])
                            review_date = datetime.strptime(review_date_str[:10], '%Y-%m-%d')

                            # Check if review was within 6 months of release
                            six_months_after = release_date + timedelta(days=180)
                            if review_date <= six_months_after:
                                success, msg = unlock_superlative(user_id, "Early Adopter", game['game_id'])
                                if success:
                                    unlocked.append(("Early Adopter", game['name']))
                    except Exception:
                        pass  # Skip if date parsing fails

    return unlocked


def calculate_friend_superlatives(user_id, friend_id):
    """Calculate which friend superlatives two users qualify for and unlock them."""
    unlocked = []

    with get_db() as conn:
        c = conn.cursor()

        # Get both users' games
        user_games = {g['game_id']: g for g in get_user_games(user_id) if g.get('enjoyment_score')}
        friend_games = {g['game_id']: g for g in get_user_games(friend_id) if g.get('enjoyment_score')}

        # Find common games
        common_game_ids = set(user_games.keys()) & set(friend_games.keys())

        if not common_game_ids:
            return unlocked

        # 1. Polar Opposites - difference in overall score >2
        for game_id in common_game_ids:
            user_score = user_games[game_id].get('enjoyment_score')
            friend_score = friend_games[game_id].get('enjoyment_score')
            if user_score and friend_score:
                diff = abs(user_score - friend_score)
                if diff > 2:
                    success, msg = unlock_superlative(user_id, "Polar Opposites", game_id, friend_id)
                    if success:
                        unlocked.append(("Polar Opposites", user_games[game_id]['name']))

        # 2. Cultists - both >2 points above community average
        for game_id in common_game_ids:
            user_score = user_games[game_id].get('enjoyment_score')
            friend_score = friend_games[game_id].get('enjoyment_score')
            if user_score and friend_score:
                c.execute('SELECT average_enjoyment_score FROM games WHERE game_id = ?', (game_id,))
                avg_row = c.fetchone()
                if avg_row and avg_row['average_enjoyment_score']:
                    user_diff = user_score - avg_row['average_enjoyment_score']
                    friend_diff = friend_score - avg_row['average_enjoyment_score']
                    if user_diff > 2 and friend_diff > 2:
                        success, msg = unlock_superlative(user_id, "Cultists", game_id, friend_id)
                        if success:
                            unlocked.append(("Cultists", user_games[game_id]['name']))

        # 3. In Good Company - share a game in top 5
        user_top_5 = sorted(user_games.values(),
                           key=lambda x: (-x['enjoyment_score'], x.get('enjoyment_order') or 999999))[:5]
        friend_top_5 = sorted(friend_games.values(),
                             key=lambda x: (-x['enjoyment_score'], x.get('enjoyment_order') or 999999))[:5]

        user_top_5_ids = {g['game_id'] for g in user_top_5}
        friend_top_5_ids = {g['game_id'] for g in friend_top_5}
        shared_top_5 = user_top_5_ids & friend_top_5_ids

        if shared_top_5:
            for game_id in shared_top_5:
                success, msg = unlock_superlative(user_id, "In Good Company", game_id, friend_id)
                if success:
                    unlocked.append(("In Good Company", user_games[game_id]['name']))
                break  # Only unlock once

        # 4. Great Minds - share #1 game
        if user_top_5 and friend_top_5:
            if user_top_5[0]['game_id'] == friend_top_5[0]['game_id']:
                game_id = user_top_5[0]['game_id']
                success, msg = unlock_superlative(user_id, "Great Minds", game_id, friend_id)
                if success:
                    unlocked.append(("Great Minds", user_games[game_id]['name']))

        # 5. Addicts - both >100 hours in same game
        for game_id in common_game_ids:
            user_hours = user_games[game_id].get('hours_played')
            friend_hours = friend_games[game_id].get('hours_played')
            if user_hours and friend_hours and user_hours > 100 and friend_hours > 100:
                success, msg = unlock_superlative(user_id, "Addicts", game_id, friend_id)
                if success:
                    unlocked.append(("Addicts", user_games[game_id]['name']))

    return unlocked
