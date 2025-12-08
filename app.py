from flask import Flask, render_template, request, redirect, url_for, send_file, session, jsonify
import urllib.parse
import sys
try:
    import requests
except ImportError:
    requests = None
import csv
import os
from io import StringIO
from functools import wraps
from database import (
    init_db, create_user, verify_user, get_user, add_or_get_game, get_all_games,
    get_user_games, set_user_score, delete_game, delete_user_score, update_game_info, import_csv_data,
    get_user_profile, set_user_profile_picture, set_tie_order, set_user_steam_profile,
    add_game_to_user_backlog, set_user_playtime, get_db, is_admin, admin_update_game_info,
    send_friend_request, get_friend_requests, get_sent_requests, accept_friend_request,
    reject_friend_request, remove_friend, get_friends, search_users,
    get_all_superlatives, get_user_superlatives, calculate_solo_superlatives,
    calculate_friend_superlatives, set_active_title, clear_active_title, get_active_title,
    get_review_points, get_unlocked_superlative_slots, set_favorite_game, get_user_profile_by_username,
    purchase_random_superlative
)

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-key-change-in-production')

# Alpha testing invite code
ALPHA_INVITE_CODE = os.environ.get('ALPHA_INVITE_CODE', 'ALPHA2025')

# Security: HTTPS enforcement in production
@app.before_request
def enforce_https():
    """Redirect HTTP to HTTPS in production"""
    if os.environ.get('FORCE_HTTPS') == '1':
        if not request.is_secure and not request.headers.get('X-Forwarded-Proto') == 'https':
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)

# Security: Add security headers to all responses
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    if os.environ.get('FORCE_HTTPS') == '1':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# Initialize database on startup
init_db()
DATA_CSV = os.path.join(os.path.dirname(__file__), "data.csv")
COVERS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'covers')
PROFILE_DIR = os.path.join(os.path.dirname(__file__), 'static', 'profiles')

# Start Steam library updater in background
from steam_updater import start_steam_updater
start_steam_updater()

# Global status tracker for bulk game updates
bulk_update_status = {
    'running': False,
    'total': 0,
    'current': 0,
    'updated': 0,
    'failed': 0,
    'current_game': '',
    'logs': []
}

# Global tracker for Steam import during registration
import_progress = {}


def login_required(f):
    """Decorator to require login for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('user_id'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        if not is_admin(session['user_id']):
            session['error'] = 'Admin privileges required'
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    # Clear any corrupted session data
    if 'user_id' in session and not session.get('user_id'):
        session.clear()

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            return render_template('login.html', error='Username and password required')
        
        success, user_id = verify_user(username, password)
        if success:
            session['user_id'] = user_id
            session['username'] = username
            next_page = request.args.get('next', url_for('index'))
            return redirect(next_page)
        else:
            return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    # Clear any corrupted session data
    if 'user_id' in session and not session.get('user_id'):
        session.clear()

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm = request.form.get('confirm_password', '').strip()
        invite_code = request.form.get('invite_code', '').strip()
        steam_url = request.form.get('steam_url', '').strip()

        # Check invite code for alpha access
        if invite_code != ALPHA_INVITE_CODE:
            return render_template('register.html', error='Invalid invite code. PeerPulse is currently in alpha testing.')

        if not username or not password:
            return render_template('register.html', error='Username and password required')

        if password != confirm:
            return render_template('register.html', error='Passwords do not match')

        if len(password) < 4:
            return render_template('register.html', error='Password must be at least 4 characters')
        
        success, message = create_user(username, password)
        if success:
            verified, user_id = verify_user(username, password)
            if not verified or not user_id:
                return render_template('register.html', error='Registration succeeded but login failed. Please try logging in.')
            session['user_id'] = user_id
            session['username'] = username
            
            # If Steam URL provided, link it and start import in background with progress tracking
            if steam_url:
                try:
                    from steam_integration import extract_steamid64, import_steam_games
                    steam_id = extract_steamid64(steam_url)
                    if steam_id:
                        set_user_steam_profile(user_id, steam_url)

                        # Initialize progress tracking for this user
                        import_progress[user_id] = {
                            'status': 'starting',
                            'total': 0,
                            'current': 0,
                            'imported': 0,
                            'message': 'Fetching Steam library...'
                        }

                        # Import games in background with progress tracking (non-daemon thread)
                        import threading
                        def import_with_progress():
                            try:
                                games = import_steam_games(steam_id, download_covers=True, covers_dir=COVERS_DIR)

                                if not games:
                                    import_progress[user_id] = {
                                        'status': 'complete',
                                        'total': 0,
                                        'current': 0,
                                        'imported': 0,
                                        'message': 'No games found. Make sure your game details are public.'
                                    }
                                    return

                                import_progress[user_id] = {
                                    'status': 'importing',
                                    'total': len(games),
                                    'current': 0,
                                    'imported': 0,
                                    'message': f'Importing {len(games)} games...'
                                }

                                imported_count = 0
                                backlog_order = 1

                                for idx, game_data in enumerate(games, 1):
                                    import_progress[user_id]['current'] = idx
                                    import_progress[user_id]['message'] = f'Importing {game_data["name"]}...'

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

                                    # Check if user already has this game
                                    with get_db() as conn:
                                        c = conn.cursor()
                                        c.execute('''
                                            SELECT 1 FROM user_scores
                                            WHERE user_id = ? AND game_id = ?
                                        ''', (user_id, game_id))
                                        existing = c.fetchone()

                                    if not existing:
                                        # New game - add to backlog
                                        add_game_to_user_backlog(user_id, game_id)
                                        if game_data.get('playtime_hours'):
                                            set_user_playtime(user_id, game_id, game_data['playtime_hours'])
                                        with get_db() as conn:
                                            c = conn.cursor()
                                            c.execute(
                                                'UPDATE user_scores SET backlog_order = ? WHERE user_id = ? AND game_id = ?',
                                                (backlog_order, user_id, game_id)
                                            )
                                            conn.commit()
                                        backlog_order += 1
                                        imported_count += 1
                                        import_progress[user_id]['imported'] = imported_count

                                # Mark as complete
                                import_progress[user_id] = {
                                    'status': 'complete',
                                    'total': len(games),
                                    'current': len(games),
                                    'imported': imported_count,
                                    'message': f'Successfully imported {imported_count} games!'
                                }

                            except Exception as e:
                                print(f"Steam import error during registration: {e}")
                                import_progress[user_id] = {
                                    'status': 'error',
                                    'message': f'Import failed: {str(e)}'
                                }

                        thread = threading.Thread(target=import_with_progress, daemon=False)
                        thread.start()

                        # Redirect to processing page
                        return redirect(url_for('registration_processing'))

                except Exception as e:
                    print(f"Steam linking during registration failed: {e}")
                    session['warning'] = f'Registration successful, but Steam linking failed: {str(e)}'

            return redirect(url_for('index'))
        else:
            return render_template('register.html', error=message)
    
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


def slugify(name):
    import re
    s = name.strip().lower()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    return s


def fetch_wikipedia_thumbnail(title):
    """Try to get a page thumbnail from Wikipedia for the given title."""
    api = 'https://en.wikipedia.org/w/api.php'
    try:
        # Try direct title lookup first
        params = {
            'action': 'query',
            'titles': title,
            'prop': 'pageimages',
            'pithumbsize': 500,
            'format': 'json',
            'redirects': 1,
            'formatversion': 2
        }
        r = requests.get(api, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        pages = data.get('query', {}).get('pages', [])
        for p in pages:
            thumb = p.get('thumbnail', {}).get('source') if p else None
            if thumb:
                return thumb

        # If no thumbnail found, try a search to find a better-matching page
        params_search = {
            'action': 'query',
            'list': 'search',
            'srsearch': title,
            'srlimit': 1,
            'format': 'json',
            'formatversion': 2
        }
        r2 = requests.get(api, params=params_search, timeout=10)
        r2.raise_for_status()
        data2 = r2.json()
        results = data2.get('query', {}).get('search', [])
        if not results:
            return None
        best = results[0]
        best_title = best.get('title')
        if not best_title:
            return None

        # Query pageimages for the found page title
        params3 = {
            'action': 'query',
            'titles': best_title,
            'prop': 'pageimages',
            'pithumbsize': 500,
            'format': 'json',
            'redirects': 1,
            'formatversion': 2
        }
        r3 = requests.get(api, params=params3, timeout=10)
        r3.raise_for_status()
        data3 = r3.json()
        pages3 = data3.get('query', {}).get('pages', [])
        for p in pages3:
            thumb = p.get('thumbnail', {}).get('source') if p else None
            if thumb:
                return thumb
    except Exception:
        return None
    return None


def fetch_image_via_google(query):
    """Placeholder."""
    return None


def fetch_image_via_commons(query):
    """Try RAWG.io API (free tier, no key needed)."""
    try:
        api = 'https://api.rawg.io/api/games'
        params = {
            'search': query,
            'page_size': 1
        }
        r = requests.get(api, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        results = data.get('results', [])
        if results:
            cover_url = results[0].get('background_image') or results[0].get('image_background')
            if cover_url:
                return cover_url
    except Exception:
        pass
    return None


def fetch_image_via_ddg(query):
    """Placeholder."""
    return None




def safe_float(x):
    try:
        return float(x)
    except:
        return None


def load_games(path):
    games = []
    if not os.path.exists(path):
        return games
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            games.append(row)
    return games


def save_games(path, games):
    if not games:
        return
    fieldnames = list(games[0].keys())
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for g in games:
            writer.writerow(g)


@app.route('/', methods=['GET'])
@login_required
def index():
    # Show all games in database sorted by community average enjoyment score
    from database import get_all_games_with_avg_scores, get_user_games
    user_id = session.get('user_id')
    
    # Get sort parameter
    sort_by = request.args.get('sort', 'enjoyment')
    games = get_all_games_with_avg_scores(user_id)
    
    # Get user's games to check backlog status
    user_games = get_user_games(user_id) if user_id else []
    backlog_game_ids = set()
    for ug in user_games:
        # Game is in backlog if it has no scores
        if all(ug.get(k) is None for k in ['enjoyment_score', 'gameplay_score', 'music_score', 'narrative_score']):
            backlog_game_ids.add(ug['game_id'])
    
    # Add in_backlog flag
    for game in games:
        game['in_backlog'] = game['id'] in backlog_game_ids
    
    prof = get_user_profile(user_id)
    
    # Apply search filter if provided
    q = request.args.get('q', '').lower()
    if q:
        games = [g for g in games if q in g.get('name', '').lower()]
    
    # Sort games based on sort parameter
    if sort_by == 'enjoyment':
        games.sort(key=lambda x: (x.get('enjoyment_score') or 0), reverse=True)
    elif sort_by == 'gameplay':
        games.sort(key=lambda x: (x.get('gameplay_score') or 0), reverse=True)
    elif sort_by == 'music':
        games.sort(key=lambda x: (x.get('music_score') or 0), reverse=True)
    elif sort_by == 'narrative':
        games.sort(key=lambda x: (x.get('narrative_score') or 0), reverse=True)
    elif sort_by == 'value':
        games.sort(key=lambda x: (x.get('playtime_value') if x.get('playtime_value') is not None else float('inf')))
    elif sort_by == 'reviews':
        games.sort(key=lambda x: (x.get('num_ratings') or 0), reverse=True)
    
    return render_template('index.html', games=games, q=q, sort_by=sort_by, username=session.get('username'), profile=prof, active_page='games')


@app.route('/game/<int:game_id>')
@login_required
def game_detail(game_id):
    """Show detailed information about a specific game."""
    from database import get_game_detail
    user_id = session.get('user_id')
    
    game = get_game_detail(game_id, user_id)
    if not game:
        return redirect(url_for('index'))
    
    prof = get_user_profile(user_id)
    user_is_admin = is_admin(user_id) if user_id else False
    return render_template('game_detail.html', game=game, username=session.get('username'), profile=prof, is_admin=user_is_admin)

    
@app.route('/toplists')
@login_required
def toplists():
    """Show top 10 games filtered by category."""
    user_id = session.get('user_id')
    category = request.args.get('category', 'overall')
    friend_username = request.args.get('friend')

    # Map category to score column
    category_map = {
        'overall': 'enjoyment_score',
        'gameplay': 'gameplay_score',
        'music': 'music_score',
        'narrative': 'narrative_score'
    }

    score_col = category_map.get(category, 'enjoyment_score')
    order_col_map = {
        'enjoyment_score': 'enjoyment_order',
        'gameplay_score': 'gameplay_order',
        'music_score': 'music_order',
        'narrative_score': 'narrative_order'
    }
    order_col = order_col_map.get(score_col)

    # Get user's top games
    all_games = get_user_games(user_id)
    games = [g for g in all_games if g.get(score_col) is not None]
    games = sorted(games, key=lambda g: (g.get(order_col) or 0))
    games = sorted(games, key=lambda g: float(g.get(score_col, 0)), reverse=True)
    games = games[:10]

    # If comparing with friend, get their top games too
    friend_games = None
    friend_profile = None
    if friend_username:
        # Get friend's user ID
        with get_db() as conn:
            c = conn.cursor()
            c.execute('SELECT id FROM users WHERE username = ?', (friend_username,))
            friend = c.fetchone()

        if friend:
            friend_id = friend['id']
            # Verify friendship
            friends_list = get_friends(user_id)
            is_friend = any(f['friend_user_id'] == friend_id for f in friends_list)

            if is_friend:
                friend_all_games = get_user_games(friend_id)
                friend_games = [g for g in friend_all_games if g.get(score_col) is not None]
                friend_games = sorted(friend_games, key=lambda g: (g.get(order_col) or 0))
                friend_games = sorted(friend_games, key=lambda g: float(g.get(score_col, 0)), reverse=True)
                friend_games = friend_games[:10]
                friend_profile = get_user_profile(friend_id)

    prof = get_user_profile(user_id)
    return render_template('toplists.html',
                         games=games,
                         category=category,
                         score_key=score_col,
                         username=session.get('username'),
                         profile=prof,
                         active_page='lists',
                         friend_username=friend_username,
                         friend_games=friend_games,
                         friend_profile=friend_profile)


@app.route('/full')
@login_required
def full():
    user_id = session.get('user_id')
    all_games = get_user_games(user_id)
    # Filter to only games that have at least one score
    games = [g for g in all_games if any(g.get(k) is not None for k in ['enjoyment_score', 'gameplay_score', 'music_score', 'narrative_score'])]
    # Default sort to enjoyment_score unless another sort is provided
    sort = request.args.get('sort') or 'enjoyment_score'
    order = request.args.get('order', 'desc')
    # Allow filtering by game name via query param `q`
    q = request.args.get('q', '').strip().lower()
    prof = get_user_profile(user_id)
    processed = []
    # Apply server-side name filter early so computed fields respect the filtered set
    if q:
        games = [g for g in games if q in (g.get('name') or '').lower()]

    for g in games:
        # compute average of user scores (exclude MetaCritic)
        scores = []
        meta = None
        for k in ['enjoyment_score', 'gameplay_score', 'music_score', 'narrative_score']:
            v = g.get(k)
            if v is not None:
                try:
                    scores.append(float(v))
                except:
                    pass
        meta = g.get('metacritic_score')
        
        avg_user = None
        if scores:
            avg_user = sum(scores) / len(scores)
        dev = None
        if avg_user is not None and meta is not None:
            dev = round(avg_user - float(meta), 1)
        # copy and add computed fields
        item = dict(g)
        item['_avg_user'] = avg_user
        item['_meta'] = meta
        item['_dev'] = dev
        processed.append(item)

    # Sorting logic
    score_keys = ['enjoyment_score', 'gameplay_score', 'music_score', 'narrative_score']
    if sort in score_keys:
        # Use stable sort: primary by score, secondary by user-defined tie order ascending
        order_col_map = {
            'enjoyment_score': 'enjoyment_order',
            'gameplay_score': 'gameplay_order',
            'music_score': 'music_order',
            'narrative_score': 'narrative_order'
        }
        order_col = order_col_map.get(sort)
        # First sort by secondary ascending to establish tie order
        processed = sorted(
            processed,
            key=lambda g: (g.get(order_col) or 0)
        )
        # Then stable sort by primary score
        def primary_key(game):
            v = game.get(sort)
            try:
                return float(v) if v is not None else (float('-inf') if order == 'desc' else float('inf'))
            except:
                return float('-inf') if order == 'desc' else float('inf')
        processed = sorted(processed, key=primary_key, reverse=(order == 'desc'))
    elif sort == 'name':
        processed = sorted(processed, key=lambda g: (g.get('name') or '').lower(), reverse=(order == 'desc'))
    elif sort == 'hours_played':
        def sort_key_hp(game):
            v = game.get('hours_played')
            try:
                return float(v) if v is not None else (float('-inf') if order == 'desc' else float('inf'))
            except:
                return float('-inf') if order == 'desc' else float('inf')
        processed = sorted(processed, key=sort_key_hp, reverse=(order == 'desc'))
    elif sort == 'pv_ratio':
        def sort_key_pv(game):
            hours = game.get('hours_played')
            price = game.get('original_price') or game.get('price')
            try:
                if hours and price and float(hours) > 0:
                    return float(price) / float(hours)
                else:
                    # Put games without PV ratio at the end
                    return float('-inf') if order == 'desc' else float('inf')
            except:
                return float('-inf') if order == 'desc' else float('inf')
        processed = sorted(processed, key=sort_key_pv, reverse=(order == 'desc'))
    return render_template('full.html', games=processed, username=session.get('username'), q=q, sort=sort, order=order, profile=prof, active_page='reviews')


@app.route('/backlog')
@login_required
def backlog():
    user_id = session.get('user_id')
    all_games = get_user_games(user_id)
    # Filter to only games that have NO scores
    games = [g for g in all_games if all(g.get(k) is None for k in ['enjoyment_score', 'gameplay_score', 'music_score', 'narrative_score'])]

    # Get community scores for all games
    from database import get_all_games_with_avg_scores
    community_games = get_all_games_with_avg_scores(user_id)
    community_scores = {g['game_id']: g for g in community_games}

    # Add community scores to backlog games
    for game in games:
        game_id = game['game_id']
        if game_id in community_scores:
            game['community_enjoyment'] = community_scores[game_id].get('avg_enjoyment')

    # Allow filtering by game name via query param `q`
    q = request.args.get('q', '').strip().lower()
    if q:
        games = [g for g in games if q in (g.get('name') or '').lower()]

    # Handle sorting
    sort_by = request.args.get('sort', 'backlog_order')
    order = request.args.get('order', 'asc')

    if sort_by == 'name':
        games = sorted(games, key=lambda g: (g.get('name') or '').lower(), reverse=(order == 'desc'))
    elif sort_by == 'hours_played':
        def sort_key_hp(game):
            v = game.get('hours_played')
            try:
                return float(v) if v is not None else (float('-inf') if order == 'desc' else float('inf'))
            except:
                return float('-inf') if order == 'desc' else float('inf')
        games = sorted(games, key=sort_key_hp, reverse=(order == 'desc'))
    elif sort_by == 'price':
        def sort_key_price(game):
            v = game.get('price')
            try:
                return float(v) if v is not None else (float('-inf') if order == 'desc' else float('inf'))
            except:
                return float('-inf') if order == 'desc' else float('inf')
        games = sorted(games, key=sort_key_price, reverse=(order == 'desc'))
    elif sort_by == 'community':
        def sort_key_comm(game):
            v = game.get('community_enjoyment')
            try:
                return float(v) if v is not None else (float('-inf') if order == 'desc' else float('inf'))
            except:
                return float('-inf') if order == 'desc' else float('inf')
        games = sorted(games, key=sort_key_comm, reverse=(order == 'desc'))
    else:
        # Default: sort by backlog_order (rank 1 is highest priority)
        # For backlog_order: both asc and desc show 1 at top since 1 is highest priority
        # asc = normal order (1,2,3...), desc = reverse but 1 is still "highest" so it stays at top
        games = sorted(games, key=lambda g: g.get('backlog_order') or 0, reverse=False)

    prof = get_user_profile(user_id)
    return render_template('backlog.html', games=games, username=session.get('username'), profile=prof, q=q, sort=sort_by, order=order, active_page='backlog')


@app.route('/api/reorder_backlog', methods=['POST'])
@login_required
def api_reorder_backlog():
    from database import set_backlog_order
    user_id = session.get('user_id')
    data = request.get_json()
    game_ids = data.get('game_ids', [])
    success = set_backlog_order(user_id, game_ids)
    return jsonify({'success': success})


@app.route('/api/add_to_backlog/<int:game_id>', methods=['POST'])
@login_required
def api_add_to_backlog(game_id):
    """Add a game to user's backlog (create user_score entry with no scores)."""
    from database import add_game_to_user_backlog
    user_id = session.get('user_id')
    success = add_game_to_user_backlog(user_id, game_id)
    return jsonify({'success': success})


@app.route('/upload', methods=['POST'])
@login_required
def upload():
    user_id = session.get('user_id')
    f = request.files.get('csvfile')
    if not f:
        return redirect(url_for('index'))
    
    content = f.read().decode('utf-8')
    imported = import_csv_data(user_id, content)
    
    return redirect(url_for('index'))


@app.route('/edit/<int:game_id>', methods=['GET', 'POST'])
@login_required
def edit(game_id):
    user_id = session.get('user_id')
    all_games = get_all_games()
    
    # Find the game by ID
    game = None
    for g in all_games:
        if g['game_id'] == game_id:
            game = g
            break
    
    if game is None:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Only update user scores, not game info
        enjoyment = request.form.get('enjoyment_score')
        gameplay = request.form.get('gameplay_score')
        music = request.form.get('music_score')
        narrative = request.form.get('narrative_score')
        review_text = request.form.get('review_text', '').strip() or None
        difficulty = request.form.get('difficulty', '').strip() or None
        graphics_quality = request.form.get('graphics_quality', '').strip() or None
        completion_time = request.form.get('completion_time', '').strip()
        replayability = request.form.get('replayability', '').strip() or None
        style = request.form.get('style', '').strip() or None
        
        # Convert to float or None
        enjoyment = float(enjoyment) if enjoyment and enjoyment.strip() else None
        gameplay = float(gameplay) if gameplay and gameplay.strip() else None
        music = float(music) if music and music.strip() else None
        narrative = float(narrative) if narrative and narrative.strip() else None
        completion_time = float(completion_time) if completion_time else None
        
        set_user_score(user_id, game_id, enjoyment, gameplay, music, narrative, None, review_text, difficulty, graphics_quality, completion_time, replayability, style)
        
        # Redirect back to full reviews page
        return redirect(url_for('full'))
    else:
        focus = request.args.get('focus')
        # Get user's scores for this game
        user_games = get_user_games(user_id)
        user_game = next((g for g in user_games if g['game_id'] == game_id), {})
        
        return render_template('edit.html', game_id=game_id, game=game, 
                             user_scores=user_game, focus=focus, username=session.get('username'))


@app.route('/delete/<int:game_id>', methods=['POST'])
@login_required
def delete(game_id):
    user_id = session.get('user_id')
    delete_user_score(user_id, game_id)
    # Redirect back to the referring page or index if no referrer
    referrer = request.referrer
    if referrer and ('backlog' in referrer or 'full' in referrer):
        return redirect(referrer)
    return redirect(url_for('index'))


@app.route('/download')
@login_required
def download():
    user_id = session.get('user_id')
    games = get_user_games(user_id)
    
    # Create CSV in memory
    output = StringIO()
    if games:
        fieldnames = ['GameID', 'AppID', 'Game', 'Release Year', 'Description', 'Genres', 'Price', 
                     'Cover Path', 'Enjoyment Score', 'Gameplay Score', 'Music Score', 
                     'Narrative Score', 'MetaCritic Score']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for g in games:
            writer.writerow({
                'GameID': g.get('game_id', ''),
                'AppID': g.get('app_id', ''),
                'Game': g.get('name', ''),
                'Release Year': g.get('release_date', ''),
                'Description': g.get('description', ''),
                'Genres': g.get('genres', ''),
                'Price': g.get('price', ''),
                'Cover Path': g.get('cover_path', ''),
                'Enjoyment Score': g.get('enjoyment_score', ''),
                'Gameplay Score': g.get('gameplay_score', ''),
                'Music Score': g.get('music_score', ''),
                'Narrative Score': g.get('narrative_score', ''),
                'MetaCritic Score': g.get('metacritic_score', '')
            })
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-disposition': 'attachment; filename=game_ratings.csv'}
    )


def _allowed_avatar(filename):
    ALLOWED = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED


def _sanitize_filename(name):
    keep = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
    return ''.join(ch if ch in keep else '_' for ch in name)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Redirect to the logged-in user's profile page."""
    return redirect(url_for('view_profile', username=session.get('username')))


@app.route('/profile/<username>', methods=['GET', 'POST'])
@login_required
def view_profile(username):
    """View a user's profile page (own or another user's)."""
    current_user_id = session.get('user_id')
    current_username = session.get('username')

    # Check if viewing own profile or another user's
    is_own_profile = (username == current_username)

    # Get the profile to view
    if is_own_profile:
        profile_user_id = current_user_id
        prof = get_user_profile(current_user_id)
    else:
        prof = get_user_profile_by_username(username)
        if not prof:
            return redirect(url_for('index'))
        profile_user_id = prof['id']

    os.makedirs(PROFILE_DIR, exist_ok=True)

    error = session.pop('error', None)
    success = session.pop('success', None)

    # Handle POST requests (only for own profile)
    if request.method == 'POST' and is_own_profile:
        f = request.files.get('avatar')
        if f and f.filename and _allowed_avatar(f.filename):
            from time import time
            ext = os.path.splitext(f.filename)[1].lower()
            fname = _sanitize_filename(f"user_{current_user_id}_{int(time())}{ext}")
            outpath = os.path.join(PROFILE_DIR, fname)
            f.save(outpath)
            web_path = f"/static/profiles/{fname}"
            set_user_profile_picture(current_user_id, web_path)
            return redirect(url_for('view_profile', username=username))
        else:
            return render_template('profile.html', profile=prof, error='Invalid image file',
                                 username=current_username, is_own_profile=is_own_profile,
                                 profile_username=username)

    # Get additional profile data
    user_is_admin = is_admin(current_user_id) if is_own_profile else False
    active_title = get_active_title(profile_user_id)
    review_points = get_review_points(profile_user_id)
    unlocked_slots = get_unlocked_superlative_slots(profile_user_id)

    # Get user's reviewed games for favorite game selector (only for own profile)
    reviewed_games = []
    if is_own_profile:
        all_games = get_user_games(profile_user_id)
        reviewed_games = [g for g in all_games if g.get('enjoyment_score') is not None]
        reviewed_games.sort(key=lambda x: x.get('enjoyment_score', 0), reverse=True)

    # Get unlocked superlatives for title selector
    unlocked_superlatives = get_user_superlatives(profile_user_id) if is_own_profile else []

    return render_template('profile.html',
                         profile=prof,
                         username=current_username,
                         profile_username=username,
                         error=error,
                         success=success,
                         is_admin=user_is_admin,
                         active_title=active_title,
                         review_points=review_points,
                         unlocked_slots=unlocked_slots,
                         is_own_profile=is_own_profile,
                         reviewed_games=reviewed_games,
                         unlocked_superlatives=unlocked_superlatives)


@app.route('/link_steam', methods=['POST'])
@login_required
def link_steam():
    """Link a Steam profile and import games to backlog."""
    user_id = session.get('user_id')
    steam_url = request.form.get('steam_url', '').strip()

    if not steam_url:
        session['error'] = 'Please provide a Steam profile URL'
        return redirect(url_for('profile'))

    try:
        from steam_integration import extract_steamid64, import_steam_games
        import requests as req_mod

        # Validate Steam URL and extract Steam ID
        steam_id = extract_steamid64(steam_url)
        if not steam_id:
            session['error'] = 'Invalid Steam profile URL. Please use a valid Steam profile link.'
            return redirect(url_for('profile'))

        # Save the Steam profile URL
        set_user_steam_profile(user_id, steam_url)

        # Import games in background (don't block the request)
        import threading
        def import_in_background():
            try:
                # Import games from Steam
                games = import_steam_games(steam_id, download_covers=True, covers_dir=COVERS_DIR)

                if not games:
                    print(f"Could not fetch games from Steam for user {user_id}")
                    return

                # Add games to database and user's backlog
                imported_count = 0
                updated_count = 0
                backlog_order = 1

                for game_data in games:
                    # Add or get the game in the master games table
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

                    # Check if user already has this game (in backlog or reviewed)
                    with get_db() as conn:
                        c = conn.cursor()
                        c.execute('''
                            SELECT enjoyment_score, gameplay_score, music_score, narrative_score
                            FROM user_scores
                            WHERE user_id = ? AND game_id = ?
                        ''', (user_id, game_id))
                        existing = c.fetchone()

                    if existing:
                        # Game already exists - only update playtime
                        if game_data.get('playtime_hours'):
                            set_user_playtime(user_id, game_id, game_data['playtime_hours'])
                            updated_count += 1
                    else:
                        # New game - add to backlog
                        add_game_to_user_backlog(user_id, game_id)

                        # Set playtime if available
                        if game_data.get('playtime_hours'):
                            set_user_playtime(user_id, game_id, game_data['playtime_hours'])

                        # Set backlog order (sorted by playtime, already sorted in import_steam_games)
                        with get_db() as conn:
                            c = conn.cursor()
                            c.execute(
                                'UPDATE user_scores SET backlog_order = ? WHERE user_id = ? AND game_id = ?',
                                (backlog_order, user_id, game_id)
                            )
                            conn.commit()
                        backlog_order += 1
                        imported_count += 1

                # Mark sync time
                with get_db() as conn:
                    c = conn.cursor()
                    c.execute('''
                        INSERT INTO steam_update_log (user_id, last_update)
                        VALUES (?, CURRENT_TIMESTAMP)
                        ON CONFLICT(user_id) DO UPDATE SET last_update = CURRENT_TIMESTAMP
                    ''', (user_id,))
                    conn.commit()

                print(f"Background Steam import completed for user {user_id}: {imported_count} imported, {updated_count} updated")

            except Exception as e:
                print(f"Background Steam import failed for user {user_id}: {e}")

        thread = threading.Thread(target=import_in_background)
        thread.daemon = True
        thread.start()

        # Return immediately with success message
        session['success'] = 'Steam profile linked! Your games are being imported in the background. Refresh the page in a few moments to see them.'
        return redirect(url_for('profile'))

    except Exception as e:
        print(f"Error linking Steam: {e}")
        session['error'] = f'Error linking Steam profile: {str(e)}'
        return redirect(url_for('profile'))


@app.route('/import_steam', methods=['POST'])
@login_required
def import_steam():
    """Re-import games from linked Steam profile."""
    user_id = session.get('user_id')
    prof = get_user_profile(user_id)
    
    if not prof or not prof.get('steam_profile_url'):
        session['error'] = 'No Steam profile linked'
        return redirect(url_for('profile'))
    
    try:
        from steam_integration import import_steam_games
        
        # Import games from Steam
        games = import_steam_games(prof['steam_profile_url'], download_covers=True, covers_dir=COVERS_DIR)
        
        if not games:
            session['error'] = 'Could not fetch games from Steam'
            return redirect(url_for('profile'))
        
        # Add new games to database and backlog
        imported_count = 0
        updated_count = 0
        backlog_order = 1
        
        for game_data in games:
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
            
            # Check if user already has this game (in backlog or reviewed)
            with get_db() as conn:
                c = conn.cursor()
                c.execute('''
                    SELECT enjoyment_score, gameplay_score, music_score, narrative_score 
                    FROM user_scores 
                    WHERE user_id = ? AND game_id = ?
                ''', (user_id, game_id))
                existing = c.fetchone()
            
            if existing:
                # Game already exists - only update playtime
                if game_data.get('playtime_hours'):
                    set_user_playtime(user_id, game_id, game_data['playtime_hours'])
                    updated_count += 1
            else:
                # New game - add to backlog
                add_game_to_user_backlog(user_id, game_id)
                
                # Set playtime if available
                if game_data.get('playtime_hours'):
                    set_user_playtime(user_id, game_id, game_data['playtime_hours'])
                
                # Set backlog order
                with get_db() as conn:
                    c = conn.cursor()
                    c.execute(
                        'UPDATE user_scores SET backlog_order = ? WHERE user_id = ? AND game_id = ?',
                        (backlog_order, user_id, game_id)
                    )
                    conn.commit()
                backlog_order += 1
                imported_count += 1
        
        if imported_count > 0 and updated_count > 0:
            session['success'] = f'Successfully synced! Added {imported_count} new games and updated {updated_count} playtimes.'
        elif imported_count > 0:
            session['success'] = f'Successfully synced! Added {imported_count} new games to your backlog.'
        elif updated_count > 0:
            session['success'] = f'Successfully synced! Updated {updated_count} playtimes (no new games).'
        else:
            session['success'] = 'Library is already up to date.'
        
        # Mark sync time
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO steam_update_log (user_id, last_update)
                VALUES (?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET last_update = CURRENT_TIMESTAMP
            ''', (user_id,))
            conn.commit()
        
        return redirect(url_for('profile'))
        
    except Exception as e:
        print(f"Error importing from Steam: {e}")
        session['error'] = f'Error importing from Steam: {str(e)}'
        return redirect(url_for('profile'))


@app.route('/unlink_steam', methods=['POST'])
@login_required
def unlink_steam():
    """Unlink Steam profile (doesn't remove games from backlog)."""
    user_id = session.get('user_id')
    set_user_steam_profile(user_id, None)
    session['success'] = 'Steam profile unlinked'
    return redirect(url_for('profile'))


@app.route('/api/update_score', methods=['POST'])
@login_required
def api_update_score():
    user_id = session.get('user_id')
    data = request.get_json()
    
    game_id = data.get('game_id')
    score_type = data.get('score_type')  # e.g., 'enjoyment_score'
    value = data.get('value')
    
    # Validate and coerce types
    try:
        game_id = int(game_id)
    except Exception:
        game_id = None

    if not game_id or not score_type:
        return jsonify({'success': False, 'error': 'Missing parameters'}), 400
    
    # Only allow specific fields
    allowed = {
        'enjoyment_score', 'gameplay_score', 'music_score', 'narrative_score', 'metacritic_score'
    }
    if score_type not in allowed:
        return jsonify({'success': False, 'error': 'Invalid score type'}), 400

    # Convert and validate value (allow empty to clear)
    if value is None or str(value).strip() == "":
        value = None
    else:
        try:
            value = float(value)
        except Exception:
            return jsonify({'success': False, 'error': 'Invalid numeric value'}), 400
        # Enforce range 1..10 and 1 decimal place max
        if value < 1 or value > 10:
            # Clamp to range
            value = min(10.0, max(1.0, value))
        # Round to a single decimal place
        value = round(value, 1)
    
    # Get current scores
    user_games = get_user_games(user_id)
    current = next((g for g in user_games if g['game_id'] == game_id), {})
    
    # Update specific score
    set_user_score(
        user_id, game_id,
        enjoyment=value if score_type == 'enjoyment_score' else current.get('enjoyment_score'),
        gameplay=value if score_type == 'gameplay_score' else current.get('gameplay_score'),
        music=value if score_type == 'music_score' else current.get('music_score'),
        narrative=value if score_type == 'narrative_score' else current.get('narrative_score'),
        metacritic=value if score_type == 'metacritic_score' else current.get('metacritic_score')
    )
    
    # Build a display string without trailing .0
    if value is None:
        value_display = None
    else:
        value_display = str(int(value)) if float(value).is_integer() else f"{value:.1f}"

    return jsonify({'success': True, 'value': value, 'value_display': value_display})


@app.route('/autofill_covers')
@login_required
def autofill_covers():
    """Search Wikipedia for thumbnails and download them for games missing covers."""
    if requests is None:
        cmd = f"{sys.executable} -m pip install -r requirements.txt"
        return (f"The 'requests' library is not installed.\nRun\n{cmd}\n\nthen restart the app.", 500)

    games = get_all_games()
    changed = False
    os.makedirs(COVERS_DIR, exist_ok=True)
    
    for g in games:
        cur = g.get('cover_path', '').strip()
        if cur:
            # skip if cover path already set and file exists
            fp = os.path.join(os.path.dirname(__file__), cur.lstrip('/\\'))
            if cur.startswith('/static/') and os.path.exists(fp):
                continue
        
        title = g.get('name', '').strip()
        if not title:
            continue
        
        thumb = fetch_wikipedia_thumbnail(title)
        if not thumb:
            # try RAWG.io
            thumb = fetch_image_via_commons(title)
        if not thumb:
            continue
        
        # download
        try:
            r = requests.get(thumb, timeout=15)
            r.raise_for_status()
            ext = os.path.splitext(urllib.parse.urlparse(thumb).path)[1] or '.jpg'
            fname = f"{slugify(title)}{ext}"
            outpath = os.path.join(COVERS_DIR, fname)
            with open(outpath, 'wb') as f:
                f.write(r.content)
            # set cover_path
            update_game_info(g['game_id'], cover_path=f"/static/covers/{fname}")
            changed = True
        except Exception:
            continue
    
    return redirect(url_for('full'))


@app.route('/api/reorder_ties', methods=['POST'])
@login_required
def api_reorder_ties():
    """Persist drag-and-drop reordering within tied score groups.
    Body: { score_key: 'enjoyment_score'|..., group_score: 8.5, ordered_game_ids: [..] }
    Only affects the provided ordered_game_ids; stores sequential order 1..N in the appropriate *_order column.
    """
    user_id = session.get('user_id')
    data = request.get_json() or {}
    score_key = data.get('score_key')
    ordered_game_ids = data.get('ordered_game_ids') or []
    # Validate
    allowed = {'enjoyment_score','gameplay_score','music_score','narrative_score'}
    if score_key not in allowed or not isinstance(ordered_game_ids, list):
        return jsonify({ 'success': False, 'error': 'Invalid parameters' }), 400
    ok = set_tie_order(user_id, score_key, ordered_game_ids)
    return jsonify({ 'success': ok })


@app.route('/api/search_games', methods=['GET'])
@login_required
def api_search_games():
    """Search all games in the database."""
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify({'games': []})
    
    from database import search_games
    games = search_games(query)
    return jsonify({'games': games})


@app.route('/api/add_game_to_user', methods=['POST'])
@login_required
def api_add_game_to_user():
    """Add an existing game to the user's list."""
    user_id = session.get('user_id')
    data = request.get_json() or {}
    game_id = data.get('game_id')
    
    if not game_id:
        return jsonify({'success': False, 'message': 'Game ID required'}), 400
    
    from database import add_game_to_user_list
    success = add_game_to_user_list(user_id, game_id)
    
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Game already in your list or error occurred'}), 400


@app.route('/api/create_and_add_game', methods=['POST'])
@login_required
def api_create_and_add_game():
    """Create a new game and add it to the user's list."""
    user_id = session.get('user_id')
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    year = data.get('year')
    developer = data.get('developer', '').strip()
    genres = data.get('genres', '').strip()
    
    if not name:
        return jsonify({'success': False, 'message': 'Game name required'}), 400
    
    # Format release_date from year if provided
    release_date = f"{year}-01-01" if year else None
    
    # Create or get the game (using genres field since there's no developer column)
    game_id = add_or_get_game(name, release_date=release_date, genres=genres or developer)
    
    # Add to user's list
    from database import add_game_to_user_list
    success = add_game_to_user_list(user_id, game_id)
    
    if success:
        return jsonify({'success': True, 'game_id': game_id})
    else:
        return jsonify({'success': False, 'message': 'Game already in your list'}), 400


@app.route('/admin/update_game/<int:game_id>', methods=['POST'])
@admin_required
def admin_update_game(game_id):
    """Admin route to update game information."""
    try:
        data = request.form
        updates = {}
        
        # Collect all the fields from the form
        for field in ['name', 'release_date', 'description', 'genres', 'developer', 
                      'publisher', 'app_id', 'price', 'original_price', 'sale_price']:
            value = data.get(field, '').strip()
            if value:
                # Convert price fields to float
                if field in ['price', 'original_price', 'sale_price']:
                    try:
                        float_value = float(value)
                        updates[field] = float_value
                    except (ValueError, TypeError):
                        print(f"[ADMIN UPDATE] Warning: Could not convert {field}='{value}' to float")
                        pass
                else:
                    updates[field] = value
        
        if admin_update_game_info(game_id, **updates):
            session['success'] = 'Game information updated successfully'
        else:
            session['error'] = 'Failed to update game information'
    except Exception as e:
        print(f"[ADMIN UPDATE] Error: {e}")
        import traceback
        traceback.print_exc()
        session['error'] = f'Error updating game: {str(e)}'
    
    return redirect(url_for('game_detail', game_id=game_id))


@app.route('/admin/trigger_steam_update', methods=['POST'])
@admin_required
def admin_trigger_steam_update():
    """Admin route to manually trigger Steam library updates for all users."""
    try:
        from steam_updater import _updater, logger
        
        if _updater and _updater.running:
            # Trigger an immediate update by calling the internal method
            import threading
            def run_update():
                try:
                    logger.info(f"Manual Steam update triggered by admin user {session.get('username')}")
                    _updater._update_all_steam_accounts()
                    logger.info("Manual Steam update completed")
                except Exception as e:
                    logger.error(f"Error in manual Steam update: {e}", exc_info=True)
            
            thread = threading.Thread(target=run_update, daemon=True)
            thread.start()
            
            session['success'] = 'Steam update started for all users with linked accounts'
        else:
            session['error'] = 'Steam updater service is not running'
    except Exception as e:
        session['error'] = f'Error triggering Steam update: {str(e)}'
    
    return redirect(url_for('profile'))


@app.route('/admin/refresh_game/<int:game_id>', methods=['POST'])
@admin_required
def admin_refresh_game(game_id):
    """Admin route to refresh a specific game's data from Steam API."""
    try:
        from database import get_game_detail
        
        # Get the game's app_id
        game = get_game_detail(game_id)
        if not game or not game.get('app_id'):
            session['error'] = 'Game not found or has no Steam App ID'
            return redirect(url_for('game_detail', game_id=game_id))
        
        app_id = game['app_id']
        print(f"[ADMIN REFRESH] Refreshing game {game.get('name')} (ID: {game_id}, App ID: {app_id})")
        
        # Fetch fresh data from Steam
        if requests:
            try:
                # Get game details from Steam Store API
                details_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc=us"
                print(f"[ADMIN REFRESH] Fetching from {details_url}")
                response = requests.get(details_url, timeout=10)
                
                if response.status_code == 200:
                    response.encoding = 'utf-8'  # Ensure proper encoding
                    data = response.json()
                    if data.get(str(app_id), {}).get('success'):
                        game_data = data[str(app_id)]['data']
                        print(f"[ADMIN REFRESH] Successfully fetched data for {game_data.get('name')}")
                        
                        # Extract information with proper encoding handling
                        updates = {}
                        
                        if game_data.get('name'):
                            # Clean up special characters if needed
                            name = game_data['name'].encode('utf-8', errors='ignore').decode('utf-8')
                            updates['name'] = name
                        
                        if game_data.get('short_description'):
                            desc = game_data['short_description'][:500]
                            desc = desc.encode('utf-8', errors='ignore').decode('utf-8')
                            updates['description'] = desc
                        
                        if game_data.get('developers'):
                            devs = ', '.join(game_data['developers'])
                            devs = devs.encode('utf-8', errors='ignore').decode('utf-8')
                            updates['developer'] = devs
                        
                        if game_data.get('publishers'):
                            pubs = ', '.join(game_data['publishers'])
                            pubs = pubs.encode('utf-8', errors='ignore').decode('utf-8')
                            updates['publisher'] = pubs
                        
                        if game_data.get('genres'):
                            updates['genres'] = ', '.join([g['description'] for g in game_data['genres']])
                        
                        if game_data.get('release_date', {}).get('date'):
                            updates['release_date'] = game_data['release_date']['date']
                        
                        # Price information
                        price_info = game_data.get('price_overview', {})
                        if price_info:
                            final_price = price_info.get('final')
                            initial_price = price_info.get('initial')
                            
                            if final_price is not None:
                                updates['price'] = final_price / 100.0  # Convert cents to dollars
                            if initial_price is not None:
                                updates['original_price'] = initial_price / 100.0
                            
                            if price_info.get('discount_percent', 0) > 0 and final_price is not None:
                                updates['sale_price'] = final_price / 100.0
                        
                        print(f"[ADMIN REFRESH] Updates prepared: {list(updates.keys())}")
                        
                        # Download cover art with ETag check
                        from steam_integration import download_cover_art
                        header_image = game_data.get('header_image')
                        if header_image:
                            print(f"[ADMIN REFRESH] Downloading cover from {header_image}")
                            try:
                                cover_path, etag = download_cover_art(
                                    app_id, 
                                    game_data.get('name'),
                                    COVERS_DIR,
                                    game.get('cover_etag')
                                )
                                if cover_path:
                                    updates['cover_path'] = cover_path
                                    updates['cover_etag'] = etag
                                    print(f"[ADMIN REFRESH] Cover updated: {cover_path}")
                            except Exception as e:
                                print(f"[ADMIN REFRESH] Error downloading cover: {e}")
                        
                        # Update the database
                        if updates:
                            if admin_update_game_info(game_id, **updates):
                                print(f"[ADMIN REFRESH] Database updated successfully")
                                session['success'] = f'Successfully refreshed {len(updates)} fields from Steam (App ID: {app_id})'
                            else:
                                print(f"[ADMIN REFRESH] Database update failed")
                                session['error'] = 'Failed to update game in database'
                        else:
                            session['error'] = 'No updates found from Steam API'
                    else:
                        print(f"[ADMIN REFRESH] Steam API returned success=false")
                        session['error'] = f'Steam API returned no data for App ID {app_id}'
                else:
                    print(f"[ADMIN REFRESH] Steam API status {response.status_code}")
                    session['error'] = f'Steam API request failed with status {response.status_code}'
            except Exception as e:
                print(f"[ADMIN REFRESH] Exception during fetch: {e}")
                import traceback
                traceback.print_exc()
                session['error'] = f'Error fetching from Steam API: {str(e)}'
        else:
            session['error'] = 'Requests library not available'
            
    except Exception as e:
        print(f"[ADMIN REFRESH] Top-level exception: {e}")
        import traceback
        traceback.print_exc()
        session['error'] = f'Error refreshing game: {str(e)}'
    
    return redirect(url_for('game_detail', game_id=game_id))


@app.route('/admin/update_all_games', methods=['POST'])
@admin_required
def admin_update_all_games():
    """Admin route to refresh all games with Steam App IDs from Steam API."""
    try:
        from database import get_db, admin_update_game_info
        
        # Get all games with Steam App IDs
        with get_db() as conn:
            c = conn.cursor()
            c.execute("SELECT game_id, name, app_id, cover_etag FROM games WHERE app_id IS NOT NULL")
            games = c.fetchall()
        
        if not games:
            session['error'] = 'No games found with Steam App IDs'
            return redirect(url_for('profile'))
        
        # Run the update in a background thread
        import threading
        from steam_updater import logger
        
        def run_bulk_update():
            """Background task to update all games."""
            global bulk_update_status
            
            # Initialize status
            bulk_update_status['running'] = True
            bulk_update_status['total'] = len(games)
            bulk_update_status['current'] = 0
            bulk_update_status['updated'] = 0
            bulk_update_status['failed'] = 0
            bulk_update_status['logs'] = []
            
            def add_log(message):
                bulk_update_status['logs'].append(message)
                if len(bulk_update_status['logs']) > 100:  # Keep only last 100 logs
                    bulk_update_status['logs'].pop(0)
            
            logger.info(f"[BULK UPDATE] Starting bulk game update for {len(games)} games")
            print(f"[BULK UPDATE] Starting update for {len(games)} games")
            add_log(f"Starting update for {len(games)} games...")
            
            for idx, game in enumerate(games, 1):
                game_id = game[0]
                game_name = game[1]
                app_id = game[2]
                cover_etag = game[3]
                
                bulk_update_status['current'] = idx
                bulk_update_status['current_game'] = game_name
                
                try:
                    print(f"[BULK UPDATE] Updating {game_name} (ID: {game_id}, App ID: {app_id})")
                    logger.info(f"Updating game: {game_name} (App ID: {app_id})")
                    add_log(f"[{idx}/{len(games)}] Updating {game_name}...")
                    
                    # Fetch from Steam API
                    if requests:
                        details_url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&cc=us"
                        response = requests.get(details_url, timeout=10)
                        
                        if response.status_code == 200:
                            response.encoding = 'utf-8'
                            data = response.json()
                            
                            if data.get(str(app_id), {}).get('success'):
                                game_data = data[str(app_id)]['data']
                                updates = {}
                                
                                # Extract game information
                                if game_data.get('name'):
                                    updates['name'] = game_data['name'].encode('utf-8', errors='ignore').decode('utf-8')
                                
                                if game_data.get('short_description'):
                                    desc = game_data['short_description'][:500]
                                    updates['description'] = desc.encode('utf-8', errors='ignore').decode('utf-8')
                                
                                if game_data.get('developers'):
                                    devs = ', '.join(game_data['developers'])
                                    updates['developer'] = devs.encode('utf-8', errors='ignore').decode('utf-8')
                                
                                if game_data.get('publishers'):
                                    pubs = ', '.join(game_data['publishers'])
                                    updates['publisher'] = pubs.encode('utf-8', errors='ignore').decode('utf-8')
                                
                                if game_data.get('genres'):
                                    updates['genres'] = ', '.join([g['description'] for g in game_data['genres']])
                                
                                if game_data.get('release_date', {}).get('date'):
                                    updates['release_date'] = game_data['release_date']['date']
                                
                                # Price information
                                price_info = game_data.get('price_overview', {})
                                if price_info:
                                    final_price = price_info.get('final')
                                    initial_price = price_info.get('initial')
                                    
                                    if final_price is not None:
                                        updates['price'] = final_price / 100.0
                                    if initial_price is not None:
                                        updates['original_price'] = initial_price / 100.0
                                    
                                    if price_info.get('discount_percent', 0) > 0 and final_price is not None:
                                        updates['sale_price'] = final_price / 100.0
                                
                                # Download cover art
                                from steam_integration import download_cover_art
                                header_image = game_data.get('header_image')
                                if header_image:
                                    try:
                                        cover_path, etag = download_cover_art(
                                            app_id,
                                            game_data.get('name'),
                                            COVERS_DIR,
                                            cover_etag
                                        )
                                        if cover_path:
                                            updates['cover_path'] = cover_path
                                            updates['cover_etag'] = etag
                                    except Exception as e:
                                        logger.error(f"Error downloading cover for {game_name}: {e}")
                                
                                # Update database
                                if updates:
                                    if admin_update_game_info(game_id, **updates):
                                        bulk_update_status['updated'] += 1
                                        logger.info(f"Successfully updated {game_name}: {list(updates.keys())}")
                                        add_log(f"✓ Updated {game_name}")

                                    else:
                                        bulk_update_status['failed'] += 1
                                        logger.error(f"Failed to update {game_name} in database")
                                        add_log(f"✗ Failed to update {game_name} in database")
                            else:
                                bulk_update_status['failed'] += 1
                                logger.warning(f"Steam API returned no data for {game_name} (App ID: {app_id})")
                                add_log(f"✗ No data from Steam for {game_name}")
                        else:
                            bulk_update_status['failed'] += 1
                            logger.error(f"Steam API request failed for {game_name}: status {response.status_code}")
                            add_log(f"✗ API error for {game_name} (status {response.status_code})")
                    
                    # Small delay to avoid rate limiting
                    import time
                    time.sleep(0.5)
                    
                except Exception as e:
                    bulk_update_status['failed'] += 1
                    logger.error(f"Error updating {game_name}: {e}", exc_info=True)
                    print(f"[BULK UPDATE] Error updating {game_name}: {e}")
                    add_log(f"✗ Error: {game_name} - {str(e)}")
            
            # Mark as complete
            bulk_update_status['running'] = False
            bulk_update_status['current_game'] = ''
            logger.info(f"[BULK UPDATE] Completed: {bulk_update_status['updated']} updated, {bulk_update_status['failed']} failed")
            print(f"[BULK UPDATE] Completed: {bulk_update_status['updated']} updated, {bulk_update_status['failed']} failed")
            add_log(f"✓ Completed: {bulk_update_status['updated']} updated, {bulk_update_status['failed']} failed")

        
        # Start the background thread
        thread = threading.Thread(target=run_bulk_update, daemon=True)
        thread.start()
        
        session['success'] = f'Started updating {len(games)} games from Steam API. This may take several minutes.'
        logger.info(f"Admin {session.get('username')} triggered bulk game update for {len(games)} games")
        
    except Exception as e:
        logger.error(f"Error starting bulk game update: {e}", exc_info=True)
        session['error'] = f'Error starting bulk update: {str(e)}'
    
    return redirect(url_for('profile'))


@app.route('/api/bulk_update_status')
@admin_required
def get_bulk_update_status():
    """API endpoint to get the current status of bulk game updates."""
    return jsonify(bulk_update_status)


# Friends Routes

@app.route('/friends')
@login_required
def friends():
    """Friends management page."""
    user_id = session.get('user_id')

    friends_list = get_friends(user_id)
    incoming_requests = get_friend_requests(user_id)
    sent_requests = get_sent_requests(user_id)

    prof = get_user_profile(user_id)

    return render_template('friends.html',
                         friends=friends_list,
                         incoming_requests=incoming_requests,
                         sent_requests=sent_requests,
                         username=session.get('username'),
                         profile=prof,
                         active_page='friends')


@app.route('/api/search_users', methods=['GET'])
@login_required
def api_search_users():
    """Search for users by username."""
    user_id = session.get('user_id')
    query = request.args.get('q', '').strip()

    if len(query) < 2:
        return jsonify({'users': []})

    users = search_users(query, exclude_user_id=user_id)
    return jsonify({'users': users})


@app.route('/api/friends', methods=['GET'])
@login_required
def api_get_friends():
    """Get user's friends list."""
    user_id = session.get('user_id')
    friends_list = get_friends(user_id)
    return jsonify({'friends': friends_list})


@app.route('/api/send_friend_request', methods=['POST'])
@login_required
def api_send_friend_request():
    """Send a friend request."""
    user_id = session.get('user_id')
    data = request.get_json() or {}
    username = data.get('username')

    # Debug logging
    print(f"DEBUG: send_friend_request called")
    print(f"DEBUG: user_id from session: {user_id}")
    print(f"DEBUG: session keys: {list(session.keys())}")
    print(f"DEBUG: target username: {username}")

    if not username:
        return jsonify({'success': False, 'message': 'Username required'}), 400

    if not user_id:
        return jsonify({'success': False, 'message': 'Session error: user_id is None'}), 400

    success, message = send_friend_request(user_id, username)
    return jsonify({'success': success, 'message': message})


@app.route('/api/accept_friend_request/<int:request_id>', methods=['POST'])
@login_required
def api_accept_friend_request(request_id):
    """Accept a friend request."""
    user_id = session.get('user_id')
    success, message = accept_friend_request(request_id, user_id)
    return jsonify({'success': success, 'message': message})


@app.route('/api/reject_friend_request/<int:request_id>', methods=['POST'])
@login_required
def api_reject_friend_request(request_id):
    """Reject a friend request."""
    user_id = session.get('user_id')
    success, message = reject_friend_request(request_id, user_id)
    return jsonify({'success': success, 'message': message})


@app.route('/api/remove_friend/<int:friend_id>', methods=['POST'])
@login_required
def api_remove_friend(friend_id):
    """Remove a friend."""
    user_id = session.get('user_id')
    success, message = remove_friend(user_id, friend_id)
    return jsonify({'success': success, 'message': message})


@app.route('/compare/<username>')
@login_required
def compare_games(username):
    """Compare game lists with a friend - only shows games both users have reviewed."""
    user_id = session.get('user_id')

    # Get friend's user ID
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE username = ?', (username,))
        friend = c.fetchone()

    if not friend:
        return redirect(url_for('friends'))

    friend_id = friend['id']

    # Verify friendship
    friends_list = get_friends(user_id)
    is_friend = any(f['friend_user_id'] == friend_id for f in friends_list)

    if not is_friend:
        return redirect(url_for('friends'))

    # Get both users' games
    user_games = get_user_games(user_id)
    friend_games = get_user_games(friend_id)

    # Create ranking maps - sort by enjoyment score with tie-breaking order
    # Filter games with enjoyment scores
    user_scored = [g for g in user_games if g.get('enjoyment_score') is not None]
    friend_scored = [g for g in friend_games if g.get('enjoyment_score') is not None]

    # Sort with two-step process: first by tie-breaking order, then by score (stable sort)
    user_ranked = sorted(user_scored, key=lambda x: x.get('enjoyment_order') or 0)
    user_ranked = sorted(user_ranked, key=lambda x: x.get('enjoyment_score'), reverse=True)

    friend_ranked = sorted(friend_scored, key=lambda x: x.get('enjoyment_order') or 0)
    friend_ranked = sorted(friend_ranked, key=lambda x: x.get('enjoyment_score'), reverse=True)

    user_rank_map = {g['game_id']: idx + 1 for idx, g in enumerate(user_ranked)}
    friend_rank_map = {g['game_id']: idx + 1 for idx, g in enumerate(friend_ranked)}

    # Create maps for easy lookup
    user_games_map = {g['game_id']: g for g in user_games}
    friend_games_map = {g['game_id']: g for g in friend_games}

    # Get search query
    search_query = request.args.get('q', '').strip().lower()

    # Only compare games that BOTH users have reviewed
    comparison = []
    for game_id in user_games_map.keys():
        if game_id in friend_games_map:
            user_game = user_games_map[game_id]
            friend_game = friend_games_map[game_id]

            # Only include if both have reviewed (have enjoyment_score)
            if user_game.get('enjoyment_score') is not None and friend_game.get('enjoyment_score') is not None:
                # Apply search filter
                if search_query and search_query not in user_game['name'].lower():
                    continue

                comparison.append({
                    'game_id': game_id,
                    'name': user_game['name'],
                    'cover_path': user_game.get('cover_path'),
                    'user_enjoyment': user_game.get('enjoyment_score'),
                    'user_gameplay': user_game.get('gameplay_score'),
                    'user_music': user_game.get('music_score'),
                    'user_narrative': user_game.get('narrative_score'),
                    'user_hours': user_game.get('hours_played'),
                    'user_difficulty': user_game.get('difficulty'),
                    'user_graphics': user_game.get('graphics_quality'),
                    'user_style': user_game.get('style'),
                    'user_replayability': user_game.get('replayability'),
                    'user_completion': user_game.get('completion_time'),
                    'user_rank': user_rank_map.get(game_id),
                    'friend_enjoyment': friend_game.get('enjoyment_score'),
                    'friend_gameplay': friend_game.get('gameplay_score'),
                    'friend_music': friend_game.get('music_score'),
                    'friend_narrative': friend_game.get('narrative_score'),
                    'friend_hours': friend_game.get('hours_played'),
                    'friend_difficulty': friend_game.get('difficulty'),
                    'friend_graphics': friend_game.get('graphics_quality'),
                    'friend_style': friend_game.get('style'),
                    'friend_replayability': friend_game.get('replayability'),
                    'friend_completion': friend_game.get('completion_time'),
                    'friend_rank': friend_rank_map.get(game_id),
                })

    # Handle sorting
    sort_by = request.args.get('sort', 'name')
    order = request.args.get('order', 'desc')

    if sort_by == 'name':
        comparison.sort(key=lambda x: x['name'].lower(), reverse=(order == 'desc'))
    elif sort_by == 'user_enjoyment':
        # Sort by user's rank (lower rank number = better, so invert the order)
        comparison.sort(key=lambda x: x.get('user_rank') or float('inf'), reverse=(order == 'asc'))
    elif sort_by == 'friend_enjoyment':
        # Sort by friend's rank (lower rank number = better, so invert the order)
        comparison.sort(key=lambda x: x.get('friend_rank') or float('inf'), reverse=(order == 'asc'))
    elif sort_by == 'avg_enjoyment':
        # Sort by average of both scores
        comparison.sort(key=lambda x: ((x.get('user_enjoyment') or 0) + (x.get('friend_enjoyment') or 0)) / 2, reverse=(order == 'desc'))
    elif sort_by == 'difference':
        # Sort by absolute difference between scores
        comparison.sort(key=lambda x: abs((x.get('user_enjoyment') or 0) - (x.get('friend_enjoyment') or 0)), reverse=(order == 'desc'))

    user_prof = get_user_profile(user_id)
    friend_prof = get_user_profile(friend_id)

    return render_template('compare.html',
                         comparison=comparison,
                         friend_username=username,
                         username=session.get('username'),
                         profile=user_prof,
                         friend_profile=friend_prof,
                         active_page='friends',
                         sort=sort_by,
                         order=order)


# Superlatives / Pulse Points Routes

@app.route('/superlatives')
@login_required
def superlatives():
    """Display Pulse Points where users can unlock random titles with RP."""
    user_id = session.get('user_id')
    username = session.get('username')

    # Get user's unlocked superlatives
    unlocked = get_user_superlatives(user_id)

    # Group by category
    solo_sups = [s for s in unlocked if s['category'] == 'solo']
    friend_sups = [s for s in unlocked if s['category'] == 'friend']

    user_prof = get_user_profile(user_id)
    review_points = get_review_points(user_id)
    unlocked_slots = get_unlocked_superlative_slots(user_id)

    # Count total available superlatives
    all_sups = get_all_superlatives()
    total_available = len(all_sups)

    return render_template('superlatives.html',
                         solo_superlatives=solo_sups,
                         friend_superlatives=friend_sups,
                         total_unlocked=len(unlocked),
                         total_available=total_available,
                         username=username,
                         profile=user_prof,
                         review_points=review_points,
                         unlocked_slots=unlocked_slots,
                         active_page='superlatives')


@app.route('/api/calculate_superlatives', methods=['POST'])
@login_required
def api_calculate_superlatives():
    """Calculate and unlock new superlatives for the user."""
    user_id = session.get('user_id')

    # Calculate solo superlatives
    solo_unlocked = calculate_solo_superlatives(user_id)

    # Calculate friend superlatives for all friends
    friends = get_friends(user_id)
    friend_unlocked = []
    for friend in friends:
        friend_id = friend['friend_user_id']
        new_friend_sups = calculate_friend_superlatives(user_id, friend_id)
        friend_unlocked.extend(new_friend_sups)

    total_unlocked = solo_unlocked + friend_unlocked

    return jsonify({
        'success': True,
        'unlocked': len(total_unlocked),
        'details': total_unlocked
    })


@app.route('/api/set_active_title', methods=['POST'])
@login_required
def api_set_active_title():
    """Set or clear the user's active title."""
    user_id = session.get('user_id')
    data = request.get_json()

    superlative_id = data.get('superlative_id')

    if superlative_id is None:
        # Clear title
        clear_active_title(user_id)
        return jsonify({'success': True, 'message': 'Title cleared'})

    # Set title
    success, message = set_active_title(user_id, superlative_id)
    return jsonify({'success': success, 'message': message})


@app.route('/api/set_favorite_game', methods=['POST'])
@login_required
def api_set_favorite_game():
    """Set the user's favorite game."""
    user_id = session.get('user_id')
    data = request.get_json()

    game_id = data.get('game_id')

    if not game_id:
        return jsonify({'success': False, 'message': 'Game ID required'}), 400

    success, message = set_favorite_game(user_id, game_id)
    return jsonify({'success': success, 'message': message})


@app.route('/api/unlock_superlative', methods=['POST'])
@login_required
def api_unlock_superlative():
    """Unlock a random superlative by spending RP."""
    user_id = session.get('user_id')

    success, message, title_name = purchase_random_superlative(user_id, cost=10)
    return jsonify({'success': success, 'message': message, 'title': title_name})


@app.route('/admin/backup-database')
@admin_required
def backup_database():
    """Admin-only endpoint to download the database file."""
    from flask import send_file
    import os
    from datetime import datetime

    db_path = os.path.join(os.path.dirname(__file__), 'ratings.db')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    download_name = f'ratings_backup_{timestamp}.db'

    return send_file(
        db_path,
        as_attachment=True,
        download_name=download_name,
        mimetype='application/x-sqlite3'
    )


@app.route('/api/debug/session')
def debug_session():
    """Debug endpoint to check session state."""
    return jsonify({
        'session_data': dict(session),
        'user_id': session.get('user_id'),
        'username': session.get('username'),
        'has_user_id_key': 'user_id' in session
    })


@app.route('/admin/db-status')
@admin_required
def db_status():
    """Admin-only endpoint to check database tables and friend requests status."""
    try:
        with get_db() as conn:
            c = conn.cursor()

            # Check if friends table exists
            c.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='friends'
            """)
            friends_table_exists = c.fetchone() is not None

            # Count friend requests
            c.execute("SELECT COUNT(*) as count FROM friends WHERE status='pending'")
            pending_count = dict(c.fetchone())['count']

            c.execute("SELECT COUNT(*) as count FROM friends WHERE status='accepted'")
            accepted_count = dict(c.fetchone())['count']

            # Get sample of recent requests
            c.execute("""
                SELECT f.id, f.user_id, f.friend_id, f.status, f.created_at
                FROM friends f
                ORDER BY f.created_at DESC
                LIMIT 10
            """)
            recent_requests = [dict(row) for row in c.fetchall()]

            return jsonify({
                'success': True,
                'friends_table_exists': friends_table_exists,
                'pending_requests': pending_count,
                'accepted_friendships': accepted_count,
                'recent_requests': recent_requests
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/registration_processing')
@login_required
def registration_processing():
    """Show processing page while Steam import is running"""
    return render_template('registration_processing.html')


@app.route('/api/import_progress')
@login_required
def get_import_progress():
    """API endpoint to check Steam import progress"""
    user_id = session.get('user_id')
    progress = import_progress.get(user_id, {
        'status': 'not_found',
        'message': 'No import in progress'
    })
    return jsonify(progress)


if __name__ == '__main__':
    # Debug mode OFF in production
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug_mode, host='0.0.0.0')