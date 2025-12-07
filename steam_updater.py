"""Background task to periodically update Steam libraries for linked accounts."""
import time
import threading
import logging
import os
from datetime import datetime, timedelta
from database import get_db, add_or_get_game, add_game_to_user_backlog, set_user_playtime
from steam_integration import import_steam_games

# Setup logging
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'steam_updater.log')

logger = logging.getLogger('SteamUpdater')
logger.setLevel(logging.INFO)

# File handler
fh = logging.FileHandler(log_file)
fh.setLevel(logging.INFO)
fh.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))

# Console handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))

logger.addHandler(fh)
logger.addHandler(ch)

# Update interval: 24 hours
UPDATE_INTERVAL = 24 * 60 * 60  # seconds

class SteamUpdater:
    """Background service to periodically update Steam libraries."""
    
    def __init__(self):
        self.running = False
        self.thread = None
    
    def start(self):
        """Start the background updater thread."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()
        logger.info("Steam updater service started")
    
    def stop(self):
        """Stop the background updater thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Steam updater service stopped")
    
    def _update_loop(self):
        """Main loop that checks for updates periodically."""
        while self.running:
            try:
                self._update_all_steam_accounts()
            except Exception as e:
                logger.error(f"Error in Steam updater: {e}", exc_info=True)
            
            # Sleep for 1 hour, checking every minute if we should stop
            for _ in range(60):
                if not self.running:
                    break
                time.sleep(60)
    
    def _update_all_steam_accounts(self):
        """Update all users with linked Steam accounts."""
        with get_db() as conn:
            c = conn.cursor()
            
            # Get all users with Steam profiles linked
            c.execute('''
                SELECT id, username, steam_profile_url 
                FROM users 
                WHERE steam_profile_url IS NOT NULL AND steam_profile_url != ''
            ''')
            users = c.fetchall()
        
        if not users:
            logger.debug("No users with linked Steam accounts found")
            return
        
        logger.info(f"Starting Steam library update for {len(users)} user(s)")
        
        for user in users:
            user_id = user['id']
            username = user['username']
            steam_url = user['steam_profile_url']
            
            try:
                # Check if this user was updated recently
                if self._should_skip_user(user_id):
                    logger.debug(f"Skipping {username} (updated recently)")
                    continue
                
                logger.info(f"Updating Steam library for user: {username}")
                result = self._update_user_steam_library(user_id, steam_url)
                
                # Mark last update time
                self._mark_user_updated(user_id)
                
                if result:
                    logger.info(f"Completed update for {username}: {result['new_games']} new games, {result['updated_playtime']} playtime updates")
                
                # Sleep between users to avoid rate limiting
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error updating {username}: {e}", exc_info=True)
    
    def _should_skip_user(self, user_id):
        """Check if user was updated recently (within last 23 hours)."""
        with get_db() as conn:
            c = conn.cursor()
            # Store last update time in a simple table
            c.execute('''
                CREATE TABLE IF NOT EXISTS steam_update_log (
                    user_id INTEGER PRIMARY KEY,
                    last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            c.execute('''
                SELECT last_update FROM steam_update_log WHERE user_id = ?
            ''', (user_id,))
            row = c.fetchone()
            
            if row:
                last_update = datetime.fromisoformat(row['last_update'])
                hours_since = (datetime.now() - last_update).total_seconds() / 3600
                if hours_since < 23:
                    return True
        
        return False
    
    def _mark_user_updated(self, user_id):
        """Mark that a user's library was just updated."""
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO steam_update_log (user_id, last_update)
                VALUES (?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET last_update = CURRENT_TIMESTAMP
            ''', (user_id,))
            conn.commit()
    
    def _update_user_steam_library(self, user_id, steam_url):
        """Update a single user's Steam library."""
        # Get existing games from database to check for complete metadata
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                SELECT app_id, name, description, genres, developer, publisher, 
                       price, original_price, sale_price, release_date, cover_etag
                FROM games 
                WHERE app_id IS NOT NULL AND app_id != ''
            ''')
            existing_games_dict = {row['app_id']: dict(row) for row in c.fetchall()}
        
        # Import games from Steam with optimization and cover downloads
        from app import COVERS_DIR
        logger.debug(f"Fetching Steam games from API")
        games = import_steam_games(
            steam_url, 
            skip_complete_games=True, 
            existing_games_dict=existing_games_dict,
            download_covers=True,
            covers_dir=COVERS_DIR
        )
        
        if not games:
            logger.warning(f"No games found for user {user_id}")
            return None
        
        logger.debug(f"Retrieved {len(games)} games from Steam")
        
        # Get existing games in user's library
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                SELECT g.app_id, us.hours_played 
                FROM user_scores us
                JOIN games g ON us.game_id = g.game_id
                WHERE us.user_id = ?
            ''', (user_id,))
            existing = {row['app_id']: row['hours_played'] for row in c.fetchall()}
        
        new_games = 0
        updated_playtime = 0
        
        # Process each game
        for game_data in games:
            app_id = game_data['app_id']
            
            # Add or get the game
            game_id = add_or_get_game(
                name=game_data['name'],
                app_id=game_data['app_id'],
                release_date=game_data.get('release_date'),
                description=game_data.get('description'),
                genres=game_data.get('genres'),
                price=game_data.get('price'),
                cover_path=game_data.get('cover_path'),
                developer=game_data.get('developer'),
                publisher=game_data.get('publisher'),
                original_price=game_data.get('original_price'),
                sale_price=game_data.get('sale_price'),
                cover_etag=game_data.get('cover_etag')
            )
            
            # Check if this is a new game for the user
            if app_id not in existing:
                # New game - add to backlog
                add_game_to_user_backlog(user_id, game_id)
                new_games += 1
            
            # Update playtime if it changed
            new_playtime = game_data.get('playtime_hours', 0)
            old_playtime = existing.get(app_id, 0)
            
            if new_playtime != old_playtime:
                set_user_playtime(user_id, game_id, new_playtime)
                updated_playtime += 1
                logger.debug(f"Updated playtime for {game_data['name']}: {old_playtime}h -> {new_playtime}h")
        
        return {'new_games': new_games, 'updated_playtime': updated_playtime}


# Global updater instance
_updater = None

def start_steam_updater():
    """Start the global Steam updater service."""
    global _updater
    if _updater is None:
        _updater = SteamUpdater()
        _updater.start()

def stop_steam_updater():
    """Stop the global Steam updater service."""
    global _updater
    if _updater:
        _updater.stop()
        _updater = None
